from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload # Importa selectinload
from app.models.group import Group
from app.models.device import Device # Asegúrate de importar Device para la carga anidada
from app.models.geofence import Geofence # Asegúrate de importar Geofence
from app.schemas.group import GroupCreate
from typing import List

async def create_group(db: AsyncSession, group: GroupCreate):
    """
    Crea un nuevo grupo en la base de datos.
    Asocia dispositivos existentes si se proporcionan sus IDs.
    """
    db_group = Group(name=group.name, description=group.description)
    
    if group.device_ids:
        # Carga los objetos Device correspondientes a los IDs proporcionados,
        # ¡incluyendo sus posiciones para evitar MissingGreenlet durante el commit!
        devices_stmt = select(Device).options(selectinload(Device.positions)).where(Device.id.in_(group.device_ids))
        devices_result = await db.execute(devices_stmt)
        db_group.devices = devices_result.scalars().all() 
    
    db.add(db_group)
    await db.commit() 
    await db.refresh(db_group) 
    return db_group

async def get_group(db: AsyncSession, group_id: int):
    """
    Obtiene un grupo por su ID, cargando ansiosamente sus dispositivos y geocercas asociadas.
    """
    result = await db.execute(
        select(Group)
        .options(
            # Carga ansiosa de la relación 'devices' y, dentro de ella, la relación 'positions' de cada dispositivo.
            # Esto previene el error MissingGreenlet al serializar.
            selectinload(Group.devices).selectinload(Device.positions), 
            # Carga ansiosa de la relación 'geofences'
            selectinload(Group.geofences) 
        )
        .where(Group.id == group_id)
    )
    return result.scalars().first()

async def get_groups(db: AsyncSession, skip: int = 0, limit: int = 100):
    """
    Obtiene una lista de grupos, con paginación, cargando ansiosamente sus dispositivos y geocercas.
    """
    result = await db.execute(
        select(Group)
        .options(
            # ¡CORRECCIÓN CLAVE: Carga ansiosa anidada de la relación 'devices' y sus 'positions'!
            # Esto es crucial para que Pydantic pueda serializar los DeviceDetailed sin MissingGreenlet.
            selectinload(Group.devices).selectinload(Device.positions), 
            # Carga ansiosa de la relación 'geofences'
            selectinload(Group.geofences) 
        )
        .order_by(Group.name)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def update_group(db: AsyncSession, group_id: int, group_update: GroupCreate):
    """
    Actualiza un grupo existente por su ID.
    Permite actualizar el nombre, la descripción y los dispositivos asociados.
    """
    db_group = await get_group(db, group_id) 
    if db_group:
        db_group.name = group_update.name
        db_group.description = group_update.description
        
        # Si se proporcionan IDs de dispositivos, actualiza la relación muchos a muchos
        if group_update.device_ids is not None:
            db_group.devices.clear() # Elimina las asociaciones existentes
            await db.flush() # Fuerza la ejecución de los cambios de eliminación antes de añadir nuevos

            if group_update.device_ids:
                # Carga los nuevos objetos Device y los asocia, incluyendo sus posiciones
                devices_to_add_stmt = select(Device).options(selectinload(Device.positions)).where(Device.id.in_(group_update.device_ids))
                devices_to_add_result = await db.execute(devices_to_add_stmt)
                db_group.devices.extend(devices_to_add_result.scalars().all()) 
            
        await db.commit()
        await db.refresh(db_group)
    return db_group

async def delete_group(db: AsyncSession, group_id: int):
    """
    Elimina un grupo por su ID.
    """
    db_group = await get_group(db, group_id) 
    if db_group:
        await db.delete(db_group)
        await db.commit()
    return db_group
