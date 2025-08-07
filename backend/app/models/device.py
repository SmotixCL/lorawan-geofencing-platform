from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base
from .group import device_group_association

class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True)
    dev_eui = Column(String(16), unique=True, nullable=False)
    device_name = Column(String(100))

    groups = relationship("Group", secondary=device_group_association, back_populates="devices")
    positions = relationship("DevicePosition", back_populates="device", cascade="all, delete-orphan")
