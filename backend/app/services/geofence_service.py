from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.models.geofence import Geofence
from app.schemas.geofence import GeofenceCreate, GeofenceType
from shapely.geometry import Polygon, Point
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape, from_shape
from typing import List, Dict, Any

async def create_geofence(db: AsyncSession, geofence_in: GeofenceCreate):
    geometry = None
    if geofence_in.geofence_type == GeofenceType.POLYGON:
        coords = [(p.lng, p.lat) for p in geofence_in.coordinates]
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])
        polygon = Polygon(coords)
        geometry = from_shape(polygon, srid=4326)
    elif geofence_in.geofence_type == GeofenceType.CIRCLE:
        center_coords = geofence_in.coordinates
        point = Point(center_coords.lng, center_coords.lat)
        geometry = from_shape(point, srid=4326)
    
    if geometry is None:
        raise ValueError("Invalid geometry for geofence type")

    db_geofence = Geofence(
        group_id=geofence_in.group_id,
        name=geofence_in.name,
        geofence_type=geofence_in.geofence_type,
        geometry=geometry,
        radius=geofence_in.coordinates.radius if geofence_in.geofence_type == GeofenceType.CIRCLE else None,
        active=geofence_in.active
    )
    db.add(db_geofence)
    await db.commit()
    await db.refresh(db_geofence)
    return db_geofence

async def get_geofence(db: AsyncSession, geofence_id: int):
    result = await db.execute(
        select(Geofence).where(Geofence.id == geofence_id)
    )
    return result.scalars().first()

async def get_geofences(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(
        select(Geofence).order_by(Geofence.name).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def get_geofences_by_group(db: AsyncSession, group_id: int):
    result = await db.execute(
        select(Geofence).where(Geofence.group_id == group_id)
    )
    return result.scalars().all()

async def update_geofence(db: AsyncSession, geofence_id: int, geofence_update: GeofenceCreate):
    db_geofence = await get_geofence(db, geofence_id)
    if not db_geofence:
        return None

    geometry = None
    if geofence_update.geofence_type == GeofenceType.POLYGON:
        coords = [(p.lng, p.lat) for p in geofence_update.coordinates]
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])
        polygon = Polygon(coords)
        geometry = from_shape(polygon, srid=4326)
    elif geofence_update.geofence_type == GeofenceType.CIRCLE:
        center_coords = geofence_update.coordinates
        point = Point(center_coords.lng, center_coords.lat)
        geometry = from_shape(point, srid=4326)

    if geometry is None:
        raise ValueError("Invalid geometry for geofence type on update")

    db_geofence.group_id = geofence_update.group_id
    db_geofence.name = geofence_update.name
    db_geofence.geofence_type = geofence_update.geofence_type
    db_geofence.geometry = geometry
    db_geofence.radius = geofence_update.coordinates.radius if geofence_update.geofence_type == GeofenceType.CIRCLE else None
    db_geofence.active = geofence_update.active 
    await db.commit()
    await db.refresh(db_geofence)
    return db_geofence

async def delete_geofence(db: AsyncSession, geofence_id: int):
    db_geofence = await get_geofence(db, geofence_id)
    if db_geofence:
        await db.delete(db_geofence)
        await db.commit()
    return db_geofence
