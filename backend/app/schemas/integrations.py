# app/schemas/integrations.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class RxInfo(BaseModel):
    """Información de recepción del gateway"""
    gatewayID: Optional[str] = None
    rssi: Optional[int] = None
    loRaSNR: Optional[float] = None
    channel: Optional[int] = None
    rfChain: Optional[int] = None
    board: Optional[int] = None
    antenna: Optional[int] = None
    location: Optional[dict] = None
    fineTimestampType: Optional[str] = None
    context: Optional[str] = None
    uplinkID: Optional[str] = None
    crcStatus: Optional[str] = None

class TxInfo(BaseModel):
    """Información de transmisión"""
    frequency: Optional[int] = None
    modulation: Optional[str] = None
    loRaModulationInfo: Optional[dict] = None
    dr: Optional[int] = None

class GPSLocation(BaseModel):
    """Ubicación GPS decodificada"""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None

class DigitalInput(BaseModel):
    """Entradas digitales decodificadas"""
    channel1: Optional[bool] = None  # GPS válido
    channel2: Optional[bool] = None  # Dentro de geocerca

class AnalogInput(BaseModel):
    """Entradas analógicas decodificadas"""
    channel1: Optional[int] = None   # Batería
    channel2: Optional[float] = None # HDOP

class ChirpstackUplinkPayload(BaseModel):
    """
    Payload completo de uplink desde ChirpStack v3.
    Soporta tanto datos raw como decodificados por el codec JavaScript.
    """
    
    # ===== CAMPOS BÁSICOS =====
    applicationID: Optional[str] = None
    applicationName: Optional[str] = None
    deviceName: Optional[str] = None
    devEUI: str  # Requerido - en Base64
    deviceProfileID: Optional[str] = None
    deviceProfileName: Optional[str] = None
    
    # ===== DATOS DEL PAYLOAD =====
    fPort: Optional[int] = None
    fCnt: Optional[int] = None
    data: Optional[str] = None  # Payload raw en Base64
    objectJSON: Optional[str] = None  # Objeto decodificado como string JSON
    
    # ===== CAMPOS DECODIFICADOS DIRECTOS =====
    # Estos campos son poblados por el decoder JavaScript en ChirpStack
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    satellites: Optional[int] = None
    hdop: Optional[float] = None
    battery: Optional[int] = None
    alertLevel: Optional[int] = None
    gpsValid: Optional[bool] = None
    insideGeofence: Optional[bool] = None
    
    # ===== OBJETOS ANIDADOS OPCIONALES =====
    # Estructura alternativa que algunos decoders pueden usar
    gpsLocation: Optional[GPSLocation] = None
    digitalInput: Optional[DigitalInput] = None
    analogInput: Optional[AnalogInput] = None
    status: Optional[dict] = None
    
    # ===== INFORMACIÓN DE RADIO =====
    rxInfo: Optional[List[RxInfo]] = None
    txInfo: Optional[TxInfo] = None
    adr: Optional[bool] = None
    dr: Optional[int] = None
    
    # ===== METADATOS =====
    confirmedUplink: Optional[bool] = False
    devAddr: Optional[str] = None
    tags: Optional[Dict[str, str]] = None
    publishedAt: Optional[str] = None
    
    # ===== CAMPOS LEGACY =====
    # Mantener compatibilidad con versiones anteriores
    object: Optional[Dict[str, Any]] = None
    decoded_content: Optional[Any] = None
    
    class Config:
        # Permitir campos adicionales no definidos
        extra = "allow"
        # Usar valores de atributos para serialización
        use_enum_values = True
        # Permitir mutación del modelo
        allow_mutation = True

class ChirpstackDownlinkPayload(BaseModel):
    """
    Payload para enviar downlinks a ChirpStack.
    """
    devEUI: str
    fPort: int = 2
    data: str  # Base64
    confirmed: bool = False
    
class GeofenceUpdate(BaseModel):
    """
    Actualización de geocerca recibida por downlink.
    """
    name: str
    centerLat: float
    centerLng: float
    radius: float
    active: bool = True

class DeviceCommand(BaseModel):
    """
    Comandos que se pueden enviar al dispositivo.
    """
    command: str  # "buzzer", "updateGeofence", "config", "reset"
    duration: Optional[int] = None  # Para buzzer
    latitude: Optional[float] = None  # Para geocerca
    longitude: Optional[float] = None  # Para geocerca
    radius: Optional[int] = None  # Para geocerca
    txInterval: Optional[int] = None  # Para config
    alertMode: Optional[int] = None  # Para config
