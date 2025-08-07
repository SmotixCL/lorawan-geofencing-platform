from pydantic import BaseModel, Field
from typing import Optional, List, Dict
class RxInfo(BaseModel):
    rssi: int
    snr: float = Field(..., alias="loRaSNR")
class LppGpsData(BaseModel):
    latitude: float
    longitude: float
    altitude: float
class LppGpsObject(BaseModel):
    gps_1: LppGpsData = Field(..., alias="1")
class LppDigitalInput(BaseModel):
    value: int = Field(..., alias="2")
class DecodedObjectLPP(BaseModel):
    gps_location: Optional[LppGpsObject] = Field(None, alias="gpsLocation")
    digital_input: Optional[LppDigitalInput] = Field(None, alias="digitalInput")
    @property
    def has_valid_gps(self) -> bool: return self.gps_location is not None and "1" in self.gps_location.model_fields_set
    @property
    def latitude(self) -> float: return self.gps_location.gps_1.latitude if self.has_valid_gps else 0.0
    @property
    def longitude(self) -> float: return self.gps_location.gps_1.longitude if self.has_valid_gps else 0.0
class UplinkEvent(BaseModel):
    dev_eui: str = Field(..., alias="devEUI")
    rx_info: List[RxInfo] = Field(..., alias="rxInfo")
    object_json: Optional[str] = Field(None, alias="objectJSON")
