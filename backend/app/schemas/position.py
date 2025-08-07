from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
class PositionBase(BaseModel):
    latitude: float
    longitude: float
    rssi: int
    snr: float
class PositionCreate(PositionBase):
    device_id: int
class Position(PositionBase):
    time: datetime
    device_id: int
    inside_geofence: Optional[bool] = None
    class Config:
        from_attributes = True
