from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.schemas.integrations import ChirpstackUplinkPayload
from app.services import device_service
from app.schemas.device import DeviceCreate
import base64
import binascii
import struct
import aiohttp
import os
import logging
import json
from app.core.database import SessionLocal
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()

# Configuración de ChirpStack
CHIRPSTACK_API_URL = os.getenv("CHIRPSTACK_API_URL", "http://localhost:8080")
CHIRPSTACK_API_TOKEN = os.getenv("CHIRPSTACK_API_TOKEN", "")

async def send_buzzer_alert_downlink(dev_eui: str, duration_seconds: int = 10):
    """
    Envía comando downlink para activar buzzer cuando dispositivo sale de geocerca.
    """
    try:
        duration_seconds = max(1, min(255, duration_seconds))
        
        # Construir payload: [CMD=0x01][Duration]
        payload_bytes = struct.pack('BB', 0x01, duration_seconds)
        payload_b64 = base64.b64encode(payload_bytes).decode('utf-8')
        
        # URL para ChirpStack v3 API
        url = f"{CHIRPSTACK_API_URL}/api/devices/{dev_eui}/queue"
        
        headers = {
            "Grpc-Metadata-Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        downlink_data = {
            "deviceQueueItem": {
                "confirmed": False,
                "data": payload_b64,
                "devEUI": dev_eui,
                "fPort": 2
            }
        }
        
        logger.info(f"📡 Enviando downlink a {dev_eui}: Buzzer por {duration_seconds}s")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=downlink_data, headers=headers) as response:
                if response.status == 200:
                    logger.info(f"✅ Downlink enviado exitosamente a {dev_eui}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Error al enviar downlink: {response.status} - {error_text}")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ Excepción enviando downlink: {e}")
        return False

async def add_position_task(device_id: int, dev_eui: str, lat: float, lng: float, 
                           alt: float, rssi: int, snr: float, gps_valid: bool):
    """
    Guarda posición y verifica si el dispositivo salió de la geocerca.
    """
    logger.info(f"📍 Procesando posición de dispositivo {dev_eui}")
    logger.info(f"  Coordenadas: {lat:.6f}, {lng:.6f}, Alt: {alt}m")
    
    async with SessionLocal() as db:
        try:
            # Guardar posición
            position = await device_service.add_device_position(
                db, device_id, lat, lng, alt, rssi, snr, gps_valid
            )
            
            # Verificar estado de geocerca
            if position and position.inside_geofence is not None:
                if position.inside_geofence == False:
                    logger.warning(f"⚠️ ALERTA: Dispositivo {dev_eui} FUERA de geocerca!")
                    # Enviar comando para activar buzzer
                    await send_buzzer_alert_downlink(dev_eui, duration_seconds=15)
                else:
                    logger.info(f"✅ Dispositivo {dev_eui} DENTRO de geocerca")
            
        except Exception as e:
            logger.error(f"❌ Error procesando posición: {e}")
        finally:
            await db.close()

@router.post("/uplink")
async def handle_chirpstack_uplink(uplink: ChirpstackUplinkPayload, 
                                  background_tasks: BackgroundTasks, 
                                  db: AsyncSession = Depends(get_db)):
    """
    Procesa uplinks de ChirpStack - compatible con decodificadores custom.
    """
    try:
        # Decodificar DevEUI
        decoded_eui_bytes = base64.b64decode(uplink.devEUI)
        dev_eui_hex = binascii.hexlify(decoded_eui_bytes).decode('utf-8').upper()
    except (binascii.Error, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid DevEUI: {e}")

    # Buscar o crear dispositivo
    device = await device_service.get_device_by_eui(db=db, dev_eui=dev_eui_hex)
    
    if not device:
        device_name = uplink.deviceName if uplink.deviceName else "Unnamed Device"
        new_device_data = DeviceCreate(dev_eui=dev_eui_hex, device_name=device_name)
        device = await device_service.create_device(db=db, device=new_device_data)
        logger.info(f"🆕 Dispositivo {device.device_name} creado")

    logger.info(f"📡 Uplink recibido de {device.device_name} ({dev_eui_hex})")
    # DEBUG: Ver qué datos están llegando
    logger.info("=" * 50)
    logger.info("DEBUG - Datos recibidos del uplink:")
    logger.info(f"  DevEUI: {dev_eui_hex}")
    logger.info(f"  fPort: {uplink.fPort}")
    logger.info(f"  data (base64): {uplink.data}")
    
    # Mostrar todos los campos del uplink
    uplink_dict = uplink.dict()
    for key, value in uplink_dict.items():
        if value is not None:
            logger.info(f"  {key}: {value}")
    logger.info("=" * 50)
    # Intentar múltiples formas de obtener datos GPS
    lat = None
    lng = None
    alt = None
    gps_valid = False
    
    # Opción 1: Campos directos del payload (si el decodificador los pone aquí)
    if hasattr(uplink, 'latitude') and uplink.latitude:
        lat = uplink.latitude
        lng = uplink.longitude if hasattr(uplink, 'longitude') else 0
        alt = uplink.altitude if hasattr(uplink, 'altitude') else 0
        gps_valid = uplink.gpsValid if hasattr(uplink, 'gpsValid') else True
        logger.info(f"📍 GPS desde campos directos: {lat:.6f}, {lng:.6f}")
    
    # Opción 2: Objeto 'object' parseado
    elif hasattr(uplink, 'object') and uplink.object:
        obj = uplink.object
        if isinstance(obj, dict):
            if 'gpsLocation' in obj:
                gps = obj['gpsLocation']
                lat = gps.get('latitude', 0)
                lng = gps.get('longitude', 0)
                alt = gps.get('altitude', 0)
                gps_valid = obj.get('gpsValid', True)
                logger.info(f"📍 GPS desde object.gpsLocation: {lat:.6f}, {lng:.6f}")
            elif 'latitude' in obj:
                lat = obj.get('latitude', 0)
                lng = obj.get('longitude', 0)
                alt = obj.get('altitude', 0)
                gps_valid = obj.get('gpsValid', True)
                logger.info(f"📍 GPS desde object directo: {lat:.6f}, {lng:.6f}")
    
    # Opción 3: decoded_content (legacy)
    elif hasattr(uplink, 'decoded_content') and uplink.decoded_content:
        decoded = uplink.decoded_content
        if isinstance(decoded, dict) and 'gpsLocation' in decoded:
            gps = decoded['gpsLocation']
            lat = gps.get('latitude', 0)
            lng = gps.get('longitude', 0)
            alt = gps.get('altitude', 0)
            gps_valid = decoded.get('gpsValid', True)
            logger.info(f"📍 GPS desde decoded_content: {lat:.6f}, {lng:.6f}")
    
    # Verificar si tenemos coordenadas válidas
    if lat and lng and (lat != 0 or lng != 0):
        # Obtener RSSI y SNR correctamente de los objetos RxInfo
        rssi = -100  # Valor por defecto
        snr = 0.0
        
        if uplink.rxInfo and len(uplink.rxInfo) > 0:
            rx = uplink.rxInfo[0]  # Primer gateway
            if hasattr(rx, 'rssi'):
                rssi = rx.rssi
            if hasattr(rx, 'loRaSNR'):
                snr = rx.loRaSNR
        
        logger.info(f"📍 Posición válida: {lat:.6f}, {lng:.6f}, Alt: {alt}m, RSSI: {rssi}, SNR: {snr}")
        
        # Agregar tarea para procesar posición
        background_tasks.add_task(
            add_position_task,
            device.id, dev_eui_hex, lat, lng, alt,
            rssi, snr, gps_valid
        )
    else:
        logger.warning(f"⚠️ Uplink sin datos GPS válidos o coordenadas en 0,0")
        logger.debug(f"Datos recibidos: lat={lat}, lng={lng}, alt={alt}")

    return {"message": "Uplink processed", "device": dev_eui_hex}

@router.post("/test-buzzer/{dev_eui}")
async def test_buzzer_endpoint(dev_eui: str, duration: int = 5):
    """
    Endpoint de prueba para activar buzzer manualmente.
    """
    logger.info(f"🔔 Prueba manual de buzzer para {dev_eui}")
    
    success = await send_buzzer_alert_downlink(dev_eui, duration)
    
    if success:
        return {
            "message": f"Comando de buzzer enviado exitosamente",
            "device": dev_eui,
            "duration": duration
        }
    else:
        raise HTTPException(
            status_code=500, 
            detail="Error enviando comando al dispositivo"
        )

@router.get("/test-connection")
async def test_chirpstack_connection():
    """
    Verifica la conexión con ChirpStack API.
    """
    try:
        url = f"{CHIRPSTACK_API_URL}/api/organizations?limit=1"
        headers = {
            "Grpc-Metadata-Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return {
                        "status": "connected",
                        "chirpstack_url": CHIRPSTACK_API_URL,
                        "api_token_configured": bool(CHIRPSTACK_API_TOKEN)
                    }
                else:
                    return {
                        "status": "error",
                        "code": response.status,
                        "message": await response.text()
                    }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
