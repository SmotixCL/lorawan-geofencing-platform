from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.dependencies import get_db
from app.schemas import geofence as schemas
from app.services import geofence_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Importar la función correcta de integrations
try:
    from app.api.integrations import send_geofence_downlink
    INTEGRATION_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ Integración con ChirpStack no disponible")
    INTEGRATION_AVAILABLE = False

@router.get("/", response_model=List[schemas.Geofence])
async def read_geofences(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    geofences = await geofence_service.get_geofences(db, skip=skip, limit=limit)
    return geofences

@router.get("/{geofence_id}", response_model=schemas.Geofence)
async def read_geofence(geofence_id: int, db: AsyncSession = Depends(get_db)):
    db_geofence = await geofence_service.get_geofence(db, geofence_id)
    if db_geofence is None:
        raise HTTPException(status_code=404, detail="Geofence not found")
    return db_geofence

@router.post("/", response_model=schemas.Geofence)
async def create_geofence(
    geofence: schemas.GeofenceCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    # Crear geocerca en DB
    db_geofence = await geofence_service.create_geofence(db, geofence)
    
    logger.info(f"📍 Geocerca creada: {geofence.name}")
    logger.info(f"   Geocerca creada exitosamente")
    
    # Si es círculo, enviar downlink
    if INTEGRATION_AVAILABLE and geofence.type == "circle":
        try:
            # Device EUI hardcoded por ahora - cambiar según necesidad
            device_eui = "000048ca433cec58"  # Tu Device EUI
            
            # Programar envío en background
            background_tasks.add_task(
                send_geofence_downlink,
                device_eui,
                float(geofence.center_lat),
                float(geofence.center_lng),
                int(geofence.radius),
                1,  # tipo círculo
                "group1"
            )
            logger.info(f"📡 Downlink programado para {device_eui}")
        except Exception as e:
            logger.error(f"Error programando downlink: {e}")
    
    return db_geofence

@router.put("/{geofence_id}", response_model=schemas.Geofence)
async def update_geofence(
    geofence_id: int,
    geofence: schemas.GeofenceCreate,
    db: AsyncSession = Depends(get_db)
):
    db_geofence = await geofence_service.update_geofence(db, geofence_id, geofence)
    if not db_geofence:
        raise HTTPException(status_code=404, detail="Geofence not found")
    return db_geofence

@router.delete("/{geofence_id}", status_code=204)
async def delete_geofence(geofence_id: int, db: AsyncSession = Depends(get_db)):
    await geofence_service.delete_geofence(db, geofence_id)
    return {"ok": True}
