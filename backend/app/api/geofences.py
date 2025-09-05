# app/api/geofences.py
"""
API endpoints para gestión de geocercas - VERSIÓN CORREGIDA
Integrado con ChirpStack para envío automático al ESP32
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.dependencies import get_db
from app.schemas import geofence as schemas
from app.services import geofence_service, group_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Importar la función de envío de geocercas desde integrations
try:
    from app.api.integrations import send_geofence_downlink
    INTEGRATION_AVAILABLE = True
    logger.info("✅ Integración con ChirpStack disponible")
except ImportError:
    logger.warning("⚠️ Integración con ChirpStack no disponible")
    INTEGRATION_AVAILABLE = False

# Device EUI del collar - CAMBIAR según tu dispositivo
DEFAULT_DEVICE_EUI = "000048ca433cec58"  # Reemplazar con tu Device EUI real

@router.get("/", response_model=List[schemas.Geofence])
async def read_geofences(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db)
):
    """
    Obtener lista de geocercas
    """
    geofences = await geofence_service.get_geofences(db, skip=skip, limit=limit)
    return geofences

@router.get("/{geofence_id}", response_model=schemas.Geofence)
async def read_geofence(
    geofence_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """
    Obtener una geocerca específica
    """
    db_geofence = await geofence_service.get_geofence(db, geofence_id)
    if db_geofence is None:
        raise HTTPException(status_code=404, detail="Geocerca no encontrada")
    return db_geofence

@router.post("/", response_model=schemas.Geofence)
async def create_geofence(
    geofence: schemas.GeofenceCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    device_eui: Optional[str] = None
):
    """
    Crear una nueva geocerca y enviarla automáticamente al ESP32
    
    Args:
        geofence: Datos de la geocerca a crear
        device_eui: Device EUI opcional, si no se proporciona usa el default
    """
    # Crear geocerca en la base de datos
    db_geofence = await geofence_service.create_geofence(db, geofence)
    
    logger.info(f"📍 Geocerca creada: {geofence.name}")
    logger.info(f"   ID: {db_geofence.id}")
    logger.info(f"   Tipo: {geofence.geofence_type}")
    logger.info(f"   Grupo: {geofence.group_id}")
    
    # Si la integración está disponible, enviar al ESP32
    if INTEGRATION_AVAILABLE:
        try:
            target_device = device_eui or DEFAULT_DEVICE_EUI
            logger.info(f"📡 Enviando geocerca al dispositivo {target_device}")
            
            # Obtener el grupo si existe
            group_name = "default"
            if geofence.group_id:
                group = await group_service.get_group(db, geofence.group_id)
                if group:
                    group_name = group.name
            
            # Preparar coordenadas según el tipo
            if geofence.geofence_type == "circle":
                coords = {
                    "lat": geofence.coordinates.lat,
                    "lng": geofence.coordinates.lng,
                    "radius": geofence.coordinates.radius
                }   
            elif geofence.geofence_type == "polygon":
                coords = [{"lat": c.lat, "lng": c.lng} for c in geofence.coordinates]
            
            # Enviar para AMBOS tipos
            background_tasks.add_task(
                send_geofence_downlink,
                target_device,
                coords,
                geofence.geofence_type.value,
                group_name
            )
            
            logger.info(f"✅ Geocerca programada para envío a {target_device}")
            
        except Exception as e:
            logger.error(f"❌ Error enviando geocerca al dispositivo: {e}")
            
    return db_geofence

@router.put("/{geofence_id}", response_model=schemas.Geofence)
async def update_geofence(
    geofence_id: int,
    geofence: schemas.GeofenceCreate,  # Usar GeofenceCreate en lugar de GeofenceUpdate
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    device_eui: Optional[str] = None
):
    """
    Actualizar una geocerca existente y enviar la actualización al ESP32
    """
    db_geofence = await geofence_service.get_geofence(db, geofence_id)
    if db_geofence is None:
        raise HTTPException(status_code=404, detail="Geocerca no encontrada")
    
    # Actualizar en base de datos
    updated_geofence = await geofence_service.update_geofence(db, geofence_id, geofence)
    
    logger.info(f"📝 Geocerca actualizada: {updated_geofence.name}")
    
    # Si es circular y la integración está disponible, enviar actualización
    if INTEGRATION_AVAILABLE and updated_geofence.geofence_type == "circle":
        try:
            target_device = device_eui or DEFAULT_DEVICE_EUI
            
            # Obtener el grupo
            group_name = "default"
            if updated_geofence.group_id:
                group = await group_service.get_group(db, updated_geofence.group_id)
                if group:
                    group_name = group.name
            
            # Enviar en background
            background_tasks.add_task(
                send_geofence_downlink,
                target_device,
                updated_geofence.coordinates.lat,
                updated_geofence.coordinates.lng,
                int(updated_geofence.radius),
                "circle",
                group_name
            )
            
            logger.info(f"✅ Actualización enviada a {target_device}")
            
        except Exception as e:
            logger.error(f"❌ Error enviando actualización: {e}")
    
    return updated_geofence

@router.delete("/{geofence_id}")
async def delete_geofence(
    geofence_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Eliminar una geocerca
    """
    db_geofence = await geofence_service.get_geofence(db, geofence_id)
    if db_geofence is None:
        raise HTTPException(status_code=404, detail="Geocerca no encontrada")
    
    await geofence_service.delete_geofence(db, geofence_id)
    
    logger.info(f"🗑️ Geocerca {geofence_id} eliminada")
    
    return {"message": "Geocerca eliminada exitosamente"}

@router.post("/{geofence_id}/send")
async def send_geofence_to_device(
    geofence_id: int,
    device_eui: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Enviar manualmente una geocerca específica a un dispositivo
    """
    if not INTEGRATION_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Integración con ChirpStack no disponible"
        )
    
    # Obtener la geocerca
    db_geofence = await geofence_service.get_geofence(db, geofence_id)
    if db_geofence is None:
        raise HTTPException(status_code=404, detail="Geocerca no encontrada")
    
    if db_geofence.geofence_type != "circle":
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden enviar geocercas circulares por ahora"
        )
    
    # Obtener el grupo
    group_name = "default"
    if db_geofence.group_id:
        group = await group_service.get_group(db, db_geofence.group_id)
        if group:
            group_name = group.name
    
    # Enviar en background
    background_tasks.add_task(
        send_geofence_downlink,
        device_eui,
        db_geofence.center_lat,
        db_geofence.center_lng,
        int(db_geofence.radius),
        "circle",
        group_name
    )
    
    return {
        "message": f"Geocerca {db_geofence.name} programada para envío",
        "device": device_eui,
        "geofence": {
            "id": db_geofence.id,
            "name": db_geofence.name,
            "type": db_geofence.type,
            "center": {
                "lat": db_geofence.center_lat,
                "lng": db_geofence.center_lng
            },
            "radius": db_geofence.radius
        }
    }
