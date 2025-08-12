from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.dependencies import get_db
from app.schemas.geofence import GeofenceCreate, Geofence
from app.services import geofence_service

router = APIRouter()

@router.post("/", response_model=Geofence, status_code=201)
async def create_geofence_endpoint(geofence: GeofenceCreate, db: AsyncSession = Depends(get_db)):
    """
    Crea una nueva geocerca.
    """
    db_geofence = await geofence_service.create_geofence(db=db, geofence_in=geofence)
    return db_geofence

@router.get("/", response_model=List[Geofence])
async def read_geofences(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """
    Obtiene todas las geocercas.
    """
    geofences = await geofence_service.get_geofences(db, skip=skip, limit=limit)
    return geofences

@router.get("/{geofence_id}", response_model=Geofence)
async def read_geofence(geofence_id: int, db: AsyncSession = Depends(get_db)):
    """
    Obtiene una geocerca por ID.
    """
    db_geofence = await geofence_service.get_geofence(db, geofence_id)
    if db_geofence is None:
        raise HTTPException(status_code=404, detail="Geofence not found")
    return db_geofence

@router.get("/group/{group_id}", response_model=List[Geofence])
async def read_geofences_by_group(group_id: int, db: AsyncSession = Depends(get_db)):
    """
    Obtiene todas las geocercas de un grupo específico.
    """
    geofences = await geofence_service.get_geofences_by_group(db, group_id)
    return geofences

@router.put("/{geofence_id}", response_model=Geofence)
async def update_geofence_endpoint(geofence_id: int, geofence: GeofenceCreate, db: AsyncSession = Depends(get_db)):
    """
    Actualiza una geocerca existente.
    """
    db_geofence = await geofence_service.update_geofence(db, geofence_id, geofence)
    if db_geofence is None:
        raise HTTPException(status_code=404, detail="Geofence not found")
    return db_geofence

@router.delete("/{geofence_id}", status_code=204)
async def delete_geofence_endpoint(geofence_id: int, db: AsyncSession = Depends(get_db)):
    """
    Elimina una geocerca.
    """
    success = await geofence_service.delete_geofence(db, geofence_id)
    if not success:
        raise HTTPException(status_code=404, detail="Geofence not found")
    return {"ok": True}
