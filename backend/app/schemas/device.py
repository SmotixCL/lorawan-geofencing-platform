from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class DeviceBase(BaseModel):
    dev_eui: str
    device_name: Optional[str] = None

class DeviceCreate(DeviceBase):
    pass

class DevicePositionSchema(BaseModel):
    time: datetime
    latitude: float
    longitude: float
    rssi: Optional[int] = None
    snr: Optional[float] = None
    inside_geofence: Optional[bool] = None

    class Config:
        from_attributes = True

class DeviceInDB(DeviceBase):
    id: int

    class Config:
        from_attributes = True

class DeviceDetailed(DeviceInDB):
    group_names: List[str] = []
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    current_inside_geofence: Optional[bool] = None
    last_position_time: Optional[datetime] = None
    associated_geofence_name: Optional[str] = None
    geofence_status: Optional[str] = None # Estado como 'Dentro', 'Fuera', 'Sin Ubicación', 'No Verificado'
