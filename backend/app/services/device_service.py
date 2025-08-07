from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc
from sqlalchemy.orm import selectinload
from app.models.device import Device
from app.models.position import DevicePosition
from app.models.group import Group
from app.models.geofence import Geofence
from app.schemas.device import DeviceCreate, DeviceDetailed, DevicePositionSchema
from typing import List, Optional, Any
from geoalchemy2 import Geography
from geoalchemy2.types import Geometry

async def create_device(db: AsyncSession, device: DeviceCreate):
    db_device = Device(dev_eui=device.dev_eui.upper(), device_name=device.device_name)
    db.add(db_device)
    await db.commit()
    await db.refresh(db_device)
    return db_device

async def get_device_by_eui(db: AsyncSession, dev_eui: str):
    result = await db.execute(
        select(Device).where(Device.dev_eui == dev_eui)
    )
    return result.scalars().first()

async def get_device(db: AsyncSession, device_id: int):
    result = await db.execute(
        select(Device).options(selectinload(Device.groups)).where(Device.id == device_id)
    )
    return result.scalars().first()

async def get_devices(db: AsyncSession, skip: int = 0, limit: int = 100):
    stmt = (
        select(Device)
        .options(selectinload(Device.groups))
        .order_by(Device.id)
        .offset(skip)
        .limit(limit)
    )
    devices_result = await db.execute(stmt)
    devices = devices_result.scalars().all()

    detailed_devices = []
    for device in devices:
        last_position_result = await db.execute(
            select(DevicePosition)
            .where(DevicePosition.device_id == device.id)
            .order_by(DevicePosition.time.desc())
            .limit(1)
        )
        last_position = last_position_result.scalars().first()

        group_names = [group.name for group in device.groups]
        geofence_status = "Sin Geocerca"
        associated_geofence_name = "N/A"

        if device.groups:
            for group in device.groups:
                geofence_result = await db.execute(
                    select(Geofence)
                    .where(Geofence.group_id == group.id, Geofence.active == True)
                    .limit(1)
                )
                group_geofence = geofence_result.scalars().first()

                if group_geofence:
                    associated_geofence_name = group_geofence.name
                    if last_position and last_position.location:
                        # La lógica de 'inside_geofence' se basa en el valor ya guardado en la BD,
                        # que es actualizado cuando llega un nuevo uplink.
                        is_inside = last_position.inside_geofence
                        geofence_status = "Dentro" if is_inside else "Fuera"
                    else:
                        geofence_status = "Sin Ubicación"
                    break

        detailed_device = DeviceDetailed(
            id=device.id,
            dev_eui=device.dev_eui,
            device_name=device.device_name,
            group_names=group_names,
            current_latitude=last_position.latitude if last_position else None,
            current_longitude=last_position.longitude if last_position else None,
            current_inside_geofence=last_position.inside_geofence if last_position else None,
            last_position_time=last_position.time if last_position else None,
            associated_geofence_name=associated_geofence_name,
            geofence_status=geofence_status
        )
        detailed_devices.append(detailed_device)

    return detailed_devices

async def update_device(db: AsyncSession, device_id: int, device_update: DeviceCreate):
    db_device = await get_device(db, device_id)
    if db_device:
        db_device.device_name = device_update.device_name
        await db.commit()
        await db.refresh(db_device)
    return db_device

async def delete_device(db: AsyncSession, device_id: int):
    db_device = await get_device(db, device_id)
    if db_device:
        await db.delete(db_device)
        await db.commit()
    return True

async def get_device_positions(db: AsyncSession, device_id: int, skip: int = 0, limit: int = 100):
    result = await db.execute(
        select(DevicePosition)
        .where(DevicePosition.device_id == device_id)
        .order_by(DevicePosition.time.desc())
        .offset(skip)
        .limit(limit)
    )
    return [DevicePositionSchema.from_orm(p) for p in result.scalars().all()]

async def add_device_position(db: AsyncSession, device_id: int, lat: float, lng: float, alt: Optional[float], rssi: Optional[int], snr: Optional[float], gps_valid: Optional[bool]):
    point = func.ST_SetSRID(func.ST_Point(lng, lat), 4326).cast(Geography)
    
    inside_geofence = None
    if gps_valid and lat != 0.0 and lng != 0.0:
        device = await get_device(db, device_id)
        if device and device.groups:
            for group in device.groups:
                geofence_result = await db.execute(
                    select(Geofence)
                    .where(Geofence.group_id == group.id, Geofence.active == True)
                    .limit(1)
                )
                group_geofence = geofence_result.scalars().first()

                if group_geofence:
                    inside_geofence = await check_point_in_geofence(db, point, group_geofence)
                    break

    db_position = DevicePosition(
        device_id=device_id,
        location=point,
        rssi=rssi,
        snr=snr,
        inside_geofence=inside_geofence
    )
    db.add(db_position)
    await db.commit()
    await db.refresh(db_position)
    return db_position

async def check_point_in_geofence(db: AsyncSession, point_geography: Any, geofence: Geofence) -> bool:
    point_as_geometry = func.cast(point_geography, Geometry)
    geofence_as_geometry = func.cast(geofence.geometry, Geometry)

    query = None
    if geofence.geofence_type == 'circle' and geofence.radius is not None:
        query = select(func.ST_DWithin(point_as_geometry, geofence_as_geometry, geofence.radius))
    
    elif geofence.geofence_type == 'polygon':
        query = select(func.ST_Contains(geofence_as_geometry, point_as_geometry))

    if query is None:
        return False

    result = await db.execute(query)
    is_inside = result.scalar_one_or_none()
    
    return is_inside or False
