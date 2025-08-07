from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from app.core.database import Base
from enum import Enum
from geoalchemy2.shape import to_shape
from shapely.geometry import Point as ShapelyPoint, Polygon as ShapelyPolygon
from typing import List, Union

class GeofenceType(str, Enum):
    POLYGON = "polygon"
    CIRCLE = "circle"

class Geofence(Base):
    __tablename__ = "geofences"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey('device_groups.id'), nullable=False)
    name = Column(String(100), nullable=False)
    geofence_type = Column(String(50), nullable=False) # 'polygon' o 'circle'
    
    geometry = Column(Geography(geometry_type='GEOMETRY', srid=4326, spatial_index=True), nullable=False)
    
    radius = Column(Float) # Solo para geocercas circulares
    active = Column(Boolean, default=True)

    group = relationship("Group", back_populates="geofences")

    @property
    def coordinates(self) -> Union[List[dict], dict]:
        if self.geometry:
            shapely_geom = to_shape(self.geometry)
            if isinstance(shapely_geom, ShapelyPolygon):
                return [{"lat": p[1], "lng": p[0]} for p in shapely_geom.exterior.coords]
            elif isinstance(shapely_geom, ShapelyPoint):
                return {"lat": shapely_geom.y, "lng": shapely_geom.x, "radius": self.radius}
        
        if self.geofence_type == GeofenceType.POLYGON:
            return []
        elif self.geofence_type == GeofenceType.CIRCLE:
            return {"lat": 0.0, "lng": 0.0, "radius": 0.0}
        return None
