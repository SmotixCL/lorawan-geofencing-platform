from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Any
from geoalchemy2.shape import to_shape
from app.dependencies import get_db
from app.schemas.geofence import GeofenceCreate, Geofence as GeofenceSchema
from app.services import geofence_service, group_service, chirpstack_service
from app.models.geofence import Geofence

router = APIRouter()

async def trigger_geofence_downlink(db: AsyncSession, group_id: int):
    """
    Tarea en segundo plano para enviar la configuración de la geocerca a los dispositivos.
    """
    # 1. Obtener la geocerca activa del grupo
    geofences_in_group = await geofence_service.get_geofences_by_group(db, group_id=group_id)
    active_geofence = next((gf for gf in geofences_in_group if gf.active), None)

    if not active_geofence:
        print(f"No hay geocerca activa para el grupo {group_id}. No se enviará downlink.")
        return

    # 2. Formatear la geocerca a un diccionario simple
    geofence_data = None
    if active_geofence.geofence_type == 'polygon':
        coords = [{"lat": lat, "lng": lon} for lon, lat in to_shape(active_geofence.geometry).exterior.coords]
        geofence_data = {"type": "polygon", "coords": coords}
    elif active_geofence.geofence_type == 'circle':
        center = to_shape(active_geofence.geometry)
        geofence_data = {"type": "circle", "center": {"lat": center.y, "lng": center.x}, "radius": active_geofence.radius}

    if not geofence_data:
        print("Error al formatear datos de geocerca.")
        return

    # 3. Empaquetar a bytes
    payload_bytes = chirpstack_service.pack_geofence_to_bytes(geofence_data)
    if not payload_bytes:
        print("No se pudo empaquetar la geocerca. Abortando downlink.")
        return

    # 4. Obtener los dispositivos del grupo y enviar el downlink a cada uno
    group = await group_service.get_group(db, group_id=group_id)
    if group and group.devices:
        for device in group.devices:
            print(f"Encolando downlink de geocerca para el dispositivo {device.dev_eui} en el puerto 10.")
            await chirpstack_service.send_downlink(device.dev_eui, fport=10, payload=payload_bytes)
    else:
        print(f"El grupo {group_id} no tiene dispositivos, no se enviarán downlinks.")

@router.post("/", response_model=GeofenceSchema)
async def create_geofence_endpoint(geofence: GeofenceCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    db_geofence = await geofence_service.create_geofence(db=db, geofence_in=geofence)
    background_tasks.add_task(trigger_geofence_downlink, db, db_geofence.group_id)
    return db_geofence

@router.put("/{geofence_id}", response_model=GeofenceSchema)
async def update_geofence_endpoint(geofence_id: int, geofence: GeofenceCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    db_geofence = await geofence_service.update_geofence(db, geofence_id, geofence)
    if db_geofence is None:
        raise HTTPException(status_code=404, detail="Geofence not found")
    background_tasks.add_task(trigger_geofence_downlink, db, db_geofence.group_id)
    return db_geofence

@router.get("/", response_model=List[GeofenceSchema])
async def get_geofences_endpoint(db: AsyncSession = Depends(get_db)):
    return await geofence_service.get_geofences(db)

@router.delete("/{geofence_id}", status_code=204)
async def delete_geofence_endpoint(geofence_id: int, db: AsyncSession = Depends(get_db)):
    await geofence_service.delete_geofence(db, geofence_id)
    return {"ok": True}
