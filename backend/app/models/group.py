from sqlalchemy import Column, Integer, String, Text, Table, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

device_group_association = Table('device_group_members', Base.metadata,
    Column('device_id', Integer, ForeignKey('devices.id'), primary_key=True),
    Column('group_id', Integer, ForeignKey('device_groups.id'), primary_key=True)
)

class Group(Base):
    __tablename__ = "device_groups"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)

    devices = relationship("Device", secondary=device_group_association, back_populates="groups")
    geofences = relationship("Geofence", back_populates="group", cascade="all, delete-orphan")
