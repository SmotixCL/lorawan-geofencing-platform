from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.dependencies import get_db
from app.schemas.geofence import GeofenceCreate, Geofence
from app.services import geofence_service, group_service
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

async def send_geofence_to_devices(group_id: int, name: str, lat: float, lng: float, radius: float):
    """Envía geocerca a todos los dispositivos del grupo"""
    from app.api.integrations import send_geofence_to_device
    from app.core.database import SessionLocal
    
    try:
        async with SessionLocal() as db:
            group = await group_service.get_group(db, group_id)
            if not group or not group.devices:
                logger.warning(f"Grupo {group_id} sin dispositivos")
                return
            
            logger.info(f"📡 Enviando geocerca '{name}' a {len(group.devices)} dispositivos")
            logger.info(f"   Centro: {lat:.6f}, {lng:.6f}")
            logger.info(f"   Radio: {radius}m")
            
            for device in group.devices:
                # IMPORTANTE: Enviar el nombre real, no "backend"
                success = await send_geofence_to_device(
                    device.dev_eui,
                    float(lat),
                    float(lng),
                    int(radius)
                )
                if success:
                    logger.info(f"   ✅ Enviado a {device.device_name} ({device.dev_eui})")
                else:
                    logger.error(f"   ❌ Fallo con {device.device_name}")
                    
    except Exception as e:
        logger.error(f"Error enviando geocerca: {e}")
        import traceback
        logger.error(traceback.format_exc())

@router.post("/", response_model=Geofence, status_code=201)
async def create_geofence_endpoint(
    geofence: GeofenceCreate, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Crea una nueva geocerca y la envía a todos los dispositivos del grupo."""
    db_geofence = await geofence_service.create_geofence(db=db, geofence_in=geofence)
    
    if db_geofence and db_geofence.group_id:
        # Extraer valores ANTES de que la sesión se cierre
        group_id = db_geofence.group_id
        name = db_geofence.name
        geofence_type = db_geofence.geofence_type
        
        # Extraer coordenadas correctamente
        coords = db_geofence.coordinates
        
        if geofence_type == "circle":
            # Para círculos, coordinates es un objeto con lat, lng, radius
            if hasattr(coords, 'lat'):
                center_lat = coords.lat
                center_lng = coords.lng
                radius = coords.radius
            elif isinstance(coords, dict):
                center_lat = coords.get('lat', 0)
                center_lng = coords.get('lng', 0)
                radius = coords.get('radius', 100)
            else:
                # Si es un objeto del modelo
                center_lat = coords.lat if hasattr(coords, 'lat') else 0
                center_lng = coords.lng if hasattr(coords, 'lng') else 0
                radius = coords.radius if hasattr(coords, 'radius') else 100
        else:
            # Para polígonos, calcular centroide
            if isinstance(coords, list) and len(coords) > 0:
                if hasattr(coords[0], 'lat'):
                    lats = [p.lat for p in coords]
                    lngs = [p.lng for p in coords]
                else:
                    lats = [p.get('lat', 0) for p in coords]
                    lngs = [p.get('lng', 0) for p in coords]
                center_lat = sum(lats) / len(lats)
                center_lng = sum(lngs) / len(lngs)
            else:
                center_lat = center_lng = 0
            radius = 100  # Radio por defecto para polígonos
        
        logger.info(f"📍 Geocerca creada: {name}")
        logger.info(f"   Tipo: {geofence_type}")
        logger.info(f"   Centro: {center_lat:.6f}, {center_lng:.6f}")
        logger.info(f"   Radio: {radius}m")
        
        # Enviar a dispositivos con todos los datos
        background_tasks.add_task(
            send_geofence_to_devices,
            group_id,
            name,
            float(center_lat),
            float(center_lng),
            float(radius)
        )
    
    return db_geofence

@router.get("/", response_model=List[Geofence])
async def read_geofences(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Obtiene todas las geocercas."""
    geofences = await geofence_service.get_geofences(db, skip=skip, limit=limit)
    return geofences

@router.get("/{geofence_id}", response_model=Geofence)
async def read_geofence(geofence_id: int, db: AsyncSession = Depends(get_db)):
    """Obtiene una geocerca por ID."""
    db_geofence = await geofence_service.get_geofence(db, geofence_id)
    if db_geofence is None:
        raise HTTPException(status_code=404, detail="Geofence not found")
    return db_geofence

@router.get("/group/{group_id}", response_model=List[Geofence])
async def read_geofences_by_group(group_id: int, db: AsyncSession = Depends(get_db)):
    """Obtiene todas las geocercas de un grupo específico."""
    geofences = await geofence_service.get_geofences_by_group(db, group_id)
    return geofences

@router.put("/{geofence_id}", response_model=Geofence)
async def update_geofence_endpoint(
    geofence_id: int, 
    geofence: GeofenceCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Actualiza una geocerca existente y notifica a los dispositivos."""
    db_geofence = await geofence_service.update_geofence(db, geofence_id, geofence)
    if db_geofence is None:
        raise HTTPException(status_code=404, detail="Geofence not found")
    
    if db_geofence and db_geofence.group_id:
        # Misma lógica de extracción que en create
        group_id = db_geofence.group_id
        name = db_geofence.name
        geofence_type = db_geofence.geofence_type
        coords = db_geofence.coordinates
        
        if geofence_type == "circle":
            if hasattr(coords, 'lat'):
                center_lat = coords.lat
                center_lng = coords.lng
                radius = coords.radius
            elif isinstance(coords, dict):
                center_lat = coords.get('lat', 0)
                center_lng = coords.get('lng', 0)
                radius = coords.get('radius', 100)
            else:
                center_lat = coords.lat if hasattr(coords, 'lat') else 0
                center_lng = coords.lng if hasattr(coords, 'lng') else 0
                radius = coords.radius if hasattr(coords, 'radius') else 100
        else:
            if isinstance(coords, list) and len(coords) > 0:
                if hasattr(coords[0], 'lat'):
                    lats = [p.lat for p in coords]
                    lngs = [p.lng for p in coords]
                else:
                    lats = [p.get('lat', 0) for p in coords]
                    lngs = [p.get('lng', 0) for p in coords]
                center_lat = sum(lats) / len(lats)
                center_lng = sum(lngs) / len(lngs)
            else:
                center_lat = center_lng = 0
            radius = 100
        
        logger.info(f"📍 Geocerca actualizada: {name}")
        logger.info(f"   Centro: {center_lat:.6f}, {center_lng:.6f}")
        logger.info(f"   Radio: {radius}m")
        
        background_tasks.add_task(
            send_geofence_to_devices,
            group_id,
            name,
            float(center_lat),
            float(center_lng),
            float(radius)
        )
    
    return db_geofence

@router.delete("/{geofence_id}", status_code=204)
async def delete_geofence_endpoint(geofence_id: int, db: AsyncSession = Depends(get_db)):
    """Elimina una geocerca."""
    success = await geofence_service.delete_geofence(db, geofence_id)
    if not success:
        raise HTTPException(status_code=404, detail="Geofence not found")
    return {"ok": True}
