from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.dependencies import get_db
from app.schemas.device import DeviceCreate, DeviceDetailed, DevicePositionSchema
from app.services import device_service

router = APIRouter()

@router.post("/", response_model=DeviceDetailed)
async def create_device_endpoint(device: DeviceCreate, db: AsyncSession = Depends(get_db)):
    db_device = await device_service.get_device_by_eui(db, device.dev_eui)
    if db_device:
        raise HTTPException(status_code=400, detail="Device with this DevEUI already registered")
    return await device_service.create_device(db=db, device=device)

@router.get("/", response_model=List[DeviceDetailed])
async def read_devices(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    devices = await device_service.get_devices(db, skip=skip, limit=limit)
    return devices

@router.get("/{device_id}", response_model=DeviceDetailed)
async def read_device(device_id: int, db: AsyncSession = Depends(get_db)):
    db_device = await device_service.get_device(db, device_id)
    if db_device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return db_device

@router.put("/{device_id}", response_model=DeviceDetailed)
async def update_device_endpoint(device_id: int, device: DeviceCreate, db: AsyncSession = Depends(get_db)):
    db_device = await device_service.update_device(db, device_id, device)
    if db_device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return db_device

@router.delete("/{device_id}", status_code=204)
async def delete_device_endpoint(device_id: int, db: AsyncSession = Depends(get_db)):
    success = await device_service.delete_device(db, device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"ok": True}

@router.get("/{device_id}/positions", response_model=List[DevicePositionSchema])
async def read_device_positions(device_id: int, skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    positions = await device_service.get_device_positions(db, device_id, skip=skip, limit=limit)
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found for this device")
    return positions
