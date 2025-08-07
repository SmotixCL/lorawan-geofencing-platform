from pydantic import BaseModel, Field
from typing import List, Optional, Union
from enum import Enum
from geoalchemy2.shape import to_shape
from shapely.geometry import Point as ShapelyPoint, Polygon as ShapelyPolygon

class Coordinates(BaseModel):
    lat: float
    lng: float
    radius: Optional[float] = None

class GeofenceType(str, Enum):
    POLYGON = "polygon"
    CIRCLE = "circle"

class GeofenceBase(BaseModel):
    group_id: int
    name: str
    geofence_type: GeofenceType
    coordinates: Union[List[Coordinates], Coordinates]
    active: bool = True

class GeofenceCreate(GeofenceBase):
    pass

class Geofence(BaseModel):
    id: int
    group_id: int
    name: str
    geofence_type: GeofenceType
    active: bool
    
    # Este campo 'coordinates' será populado por la @property 'coordinates'
    # que se encuentra en el modelo SQLAlchemy (app.models.geofence.Geofence).
    coordinates: Union[List[Coordinates], Coordinates]
    radius: Optional[float] = None # El radio del círculo también se poblará directamente desde el modelo.

    class Config:
        from_attributes = True
        # Excluimos la columna 'geometry' del modelo, ya que sus datos se exponen a través de 'coordinates'.
