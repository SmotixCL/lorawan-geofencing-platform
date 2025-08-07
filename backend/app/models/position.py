from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography
from app.core.database import Base

class DevicePosition(Base):
    __tablename__ = "device_positions"
    time = Column(DateTime(timezone=True), primary_key=True, default=func.now())
    device_id = Column(Integer, ForeignKey('devices.id'), primary_key=True)
    
    location = Column(Geography(geometry_type='POINT', srid=4326), nullable=True) 
    
    rssi = Column(Integer)
    snr = Column(Float)
    inside_geofence = Column(Boolean, nullable=True)

    device = relationship("Device", back_populates="positions")

    @property
    def latitude(self):
        if self.location:
            from geoalchemy2.shape import to_shape
            point = to_shape(self.location)
            return point.y
        return None

    @property
    def longitude(self):
        if self.location:
            from geoalchemy2.shape import to_shape
            point = to_shape(self.location)
            return point.x
        return None
