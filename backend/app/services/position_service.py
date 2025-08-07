from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import date
from sqlalchemy import func

from app.models.position import DevicePosition
from app.schemas.position import PositionCreate

async def create_device_position(db: AsyncSession, position_in: PositionCreate, is_inside: Optional[bool]) -> DevicePosition:
    wkt_location = f'POINT({position_in.longitude} {position_in.latitude})'
    db_position = DevicePosition(
        device_id=position_in.device_id,
        location=wkt_location,
        rssi=position_in.rssi,
        snr=position_in.snr,
        inside_geofence=is_inside
    )
    db.add(db_position)
    await db.commit()
    await db.refresh(db_position)
    return db_position

async def get_device_positions(db: AsyncSession, device_id: int, a_date: Optional[date] = None) -> List[DevicePosition]:
    query = select(DevicePosition).where(DevicePosition.device_id == device_id)
    if a_date:
        query = query.where(func.date(DevicePosition.time) == a_date)
    query = query.order_by(DevicePosition.time.desc()).limit(1000)
    result = await db.execute(query)
    return result.scalars().all()

async def get_latest_position_for_device(db: AsyncSession, device_id: int) -> Optional[DevicePosition]:
    query = select(DevicePosition).where(DevicePosition.device_id == device_id).order_by(DevicePosition.time.desc()).limit(1)
    result = await db.execute(query)
    return result.scalar_one_or_none()
