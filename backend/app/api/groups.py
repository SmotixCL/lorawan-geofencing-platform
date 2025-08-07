from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.dependencies import get_db
from app.schemas.group import GroupCreate, Group # Importa el esquema Group
from app.schemas.device import DeviceDetailed # Asegúrate de importar DeviceDetailed
from app.services import group_service
from app.models.group import Group as GroupModel # Importa el modelo ORM Group
from app.models.device import Device as DeviceModel # Importa el modelo ORM Device

router = APIRouter()

@router.post("/", response_model=Group, status_code=201)
async def create_group_endpoint(group: GroupCreate, db: AsyncSession = Depends(get_db)):
    """Crea un nuevo grupo."""
    db_group = await group_service.create_group(db=db, group=group)
    # Tras la creación, obtenemos el grupo de nuevo con las relaciones cargadas para la respuesta
    # ¡CORRECCIÓN CLAVE: Esto asegura que el objeto Group se obtenga con todas las relaciones cargadas
    # antes de ser serializado por FastAPI!
    full_db_group = await group_service.get_group(db, db_group.id)
    if not full_db_group:
        raise HTTPException(status_code=500, detail="Grupo creado pero no se pudo recuperar para la respuesta.")
    return full_db_group


@router.get("/", response_model=List[Group])
async def read_groups(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Obtiene una lista de grupos."""
    groups_data = await group_service.get_groups(db, skip=skip, limit=limit)
    # ¡CORRECCIÓN CLAVE: Se devuelve directamente el objeto ORM, ya que get_groups lo carga ansiosamente!
    # FastAPI/Pydantic debería ser capaz de serializarlo sin MissingGreenlet debido a la carga ansiosa.
    return groups_data

@router.get("/{group_id}", response_model=Group)
async def read_group(group_id: int, db: AsyncSession = Depends(get_db)):
    """Obtiene un grupo por ID."""
    db_group = await group_service.get_group(db, group_id)
    if db_group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    # ¡CORRECCIÓN CLAVE: Se devuelve directamente el objeto ORM, ya que get_group lo carga ansiosamente!
    return db_group

@router.put("/{group_id}", response_model=Group)
async def update_group_endpoint(group_id: int, group: GroupCreate, db: AsyncSession = Depends(get_db)):
    """Actualiza un grupo existente."""
    db_group = await group_service.update_group(db, group_id, group)
    if db_group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return db_group

@router.delete("/{group_id}", status_code=204)
async def delete_group_endpoint(group_id: int, db: AsyncSession = Depends(get_db)):
    """Elimina un grupo."""
    success = await group_service.delete_group(db, group_id)
    if not success:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"ok": True}
