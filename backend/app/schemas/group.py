from pydantic import BaseModel
from typing import Optional, List
from app.schemas.device import DeviceDetailed

class GroupBase(BaseModel):
    name: str
    description: Optional[str] = None

class GroupCreate(GroupBase):
    device_ids: Optional[List[int]] = []

class Group(GroupBase):
    id: int
    devices: List[DeviceDetailed] = []
    
    class Config:
        from_attributes = True
