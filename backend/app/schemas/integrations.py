# app/schemas/integrations.py - SCHEMA COMPLETO
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class RxInfo(BaseModel):
    gatewayID: Optional[str] = None
    rssi: Optional[int] = None
    loRaSNR: Optional[float] = None
    channel: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[int] = None

class TxInfo(BaseModel):
    frequency: Optional[int] = None
    dr: Optional[int] = None

class ChirpstackUplinkPayload(BaseModel):
    # Campos básicos ChirpStack
    applicationID: Optional[str] = None
    applicationName: Optional[str] = None
    deviceName: Optional[str] = None
    devEUI: str
    fPort: Optional[int] = None
    data: Optional[str] = None
    fCnt: Optional[int] = None
    
    # ✅ CAMPOS DECODIFICADOS DIRECTOS (enviados por ChirpStack)
    alert: Optional[int] = None
    alertLevel: Optional[str] = None
    altitude: Optional[float] = None
    battery: Optional[int] = None
    gpsValid: Optional[bool] = None
    hdop: Optional[float] = None
    insideGeofence: Optional[bool] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    satellites: Optional[int] = None
    status: Optional[int] = None
    timestamp: Optional[str] = None
    
    # Location object (si existe)
    lat: Optional[float] = None
    lng: Optional[float] = None
    
    # Campos técnicos
    rxInfo: Optional[List[RxInfo]] = None
    txInfo: Optional[TxInfo] = None
    confirmedUplink: Optional[bool] = False
    devAddr: Optional[str] = None
    
    # Legacy fields (mantener compatibilidad)
    object: Optional[Dict[str, Any]] = None
    decoded_content: Optional[Any] = None
    
    # Metadatos
    tags: Optional[Dict[str, str]] = None
    publishedAt: Optional[str] = None
    deviceProfileID: Optional[str] = None
    deviceProfileName: Optional[str] = None

    class Config:
        # Permitir campos extra que no estén en el schema
        extra = "allow"
