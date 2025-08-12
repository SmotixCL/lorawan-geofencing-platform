# app/api/integrations.py
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
    
    Args:
        dev_eui: DevEUI del dispositivo en formato hexadecimal
        duration_seconds: Duración del buzzer en segundos (1-255)
    """
    try:
        # Validar duración
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
                "fPort": 2  # Puerto 2 para comandos
            }
        }
        
        logger.info(f"📡 Enviando downlink a {dev_eui}: Buzzer por {duration_seconds}s")
        logger.info(f"   URL: {url}")
        logger.info(f"   Payload B64: {payload_b64}")
        
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

async def send_geofence_to_device(dev_eui: str, lat: float, lng: float, radius: int) -> bool:
    """
    Envía una geocerca circular al dispositivo vía downlink.
    
    Args:
        dev_eui: DevEUI del dispositivo
        lat: Latitud del centro
        lng: Longitud del centro
        radius: Radio en metros
    """
    try:
        # Comando 0x02 = actualizar geocerca
        # Formato: [CMD][LAT_4bytes][LNG_4bytes][RADIUS_2bytes]
        lat_int = int(lat * 10000000)
        lng_int = int(lng * 10000000)
        
        payload = struct.pack('<Biih', 
                             0x02,     # Comando
                             lat_int,  # Latitud
                             lng_int,  # Longitud  
                             radius)   # Radio
        
        payload_b64 = base64.b64encode(payload).decode('utf-8')
        
        url = f"{CHIRPSTACK_API_URL}/api/devices/{dev_eui}/queue"
        headers = {
            "Grpc-Metadata-Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        data = {
            "deviceQueueItem": {
                "devEUI": dev_eui,
                "fPort": 2,
                "data": payload_b64,
                "confirmed": False
            }
        }
        
        logger.info(f"📍 Enviando geocerca a {dev_eui}")
        logger.info(f"   Centro: {lat:.6f}, {lng:.6f}")
        logger.info(f"   Radio: {radius}m")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as response:
                if response.status == 200:
                    logger.info(f"✅ Geocerca enviada exitosamente a {dev_eui}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Error enviando geocerca: {response.status} - {error_text}")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ Excepción enviando geocerca: {e}")
        return False

async def add_position_task(device_id: int, dev_eui: str, lat: float, lng: float, 
                           alt: float, rssi: int, snr: float, gps_valid: bool):
    """
    Guarda posición y verifica si el dispositivo salió de la geocerca.
    Si salió, envía alerta por downlink.
    """
    logger.info(f"📍 Procesando posición de dispositivo {dev_eui}")
    logger.info(f"   Coordenadas: {lat:.6f}, {lng:.6f}, Alt: {alt}m")
    logger.info(f"   RSSI: {rssi} dBm, SNR: {snr} dB, GPS válido: {gps_valid}")
    
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
                    logger.warning(f"   Posición: {lat:.6f}, {lng:.6f}")
                    
                    # Enviar comando para activar buzzer por 15 segundos
                    await send_buzzer_alert_downlink(dev_eui, duration_seconds=15)
                else:
                    logger.info(f"✅ Dispositivo {dev_eui} DENTRO de geocerca")
            else:
                logger.info(f"ℹ️ No hay geocerca configurada para el dispositivo {dev_eui}")
            
            logger.info(f"✅ Posición guardada en BD para {dev_eui}")
            
        except Exception as e:
            logger.error(f"❌ Error procesando posición: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            await db.close()

@router.post("/uplink")
async def handle_chirpstack_uplink(uplink: ChirpstackUplinkPayload, 
                                  background_tasks: BackgroundTasks, 
                                  db: AsyncSession = Depends(get_db)):
    """
    Procesa uplinks de ChirpStack y verifica geocercas.
    Compatible con decodificadores custom y datos raw.
    """
    try:
        # Decodificar DevEUI de Base64 a Hex
        decoded_eui_bytes = base64.b64decode(uplink.devEUI)
        dev_eui_hex = binascii.hexlify(decoded_eui_bytes).decode('utf-8').upper()
    except (binascii.Error, ValueError) as e:
        logger.error(f"❌ DevEUI inválido: {uplink.devEUI}")
        raise HTTPException(status_code=400, detail=f"Invalid DevEUI: {e}")

    # Buscar o crear dispositivo
    device = await device_service.get_device_by_eui(db=db, dev_eui=dev_eui_hex)
    
    if not device:
        device_name = uplink.deviceName if uplink.deviceName else "Unnamed Device"
        new_device_data = DeviceCreate(dev_eui=dev_eui_hex, device_name=device_name)
        device = await device_service.create_device(db=db, device=new_device_data)
        logger.info(f"🆕 Dispositivo {device.device_name} (ID: {device.id}) creado automáticamente")

    # Log información del uplink
    logger.info("=" * 60)
    logger.info(f"📡 Uplink recibido de {device.device_name} ({dev_eui_hex})")
    logger.info(f"   Puerto: {uplink.fPort}")
    logger.info(f"   FCnt: {uplink.fCnt}")
    logger.info(f"   Data Base64: {uplink.data}")
    
    # Variables para GPS
    lat = None
    lng = None
    alt = None
    gps_valid = False
    satellites = 0
    hdop = 0.0
    battery = 0
    
    # OPCIÓN 1: Intentar obtener datos decodificados directamente del modelo Pydantic
    if hasattr(uplink, 'latitude') and uplink.latitude is not None:
        lat = float(uplink.latitude)
        lng = float(uplink.longitude) if hasattr(uplink, 'longitude') else 0
        alt = float(uplink.altitude) if hasattr(uplink, 'altitude') else 0
        gps_valid = bool(uplink.gpsValid) if hasattr(uplink, 'gpsValid') else True
        satellites = int(uplink.satellites) if hasattr(uplink, 'satellites') else 0
        battery = int(uplink.battery) if hasattr(uplink, 'battery') else 0
        logger.info(f"✅ GPS desde campos decodificados: {lat:.6f}, {lng:.6f}")
    
    # OPCIÓN 2: Si no hay datos decodificados, intentar decodificar el payload raw
    elif uplink.data and uplink.fPort == 1:  # Puerto 1 = datos GPS
        try:
            payload_bytes = base64.b64decode(uplink.data)
            logger.info(f"   Decodificando {len(payload_bytes)} bytes de payload raw...")
            
            if len(payload_bytes) >= 15:
                # Estructura del payload de la ESP32:
                # int32_t latitude (4 bytes)
                # int32_t longitude (4 bytes)
                # uint16_t altitude (2 bytes)
                # uint8_t satellites (1 byte)
                # uint8_t hdop (1 byte)
                # uint8_t battery (1 byte)
                # uint8_t alert (1 byte)
                # uint8_t status (1 byte)
                
                lat_int, lng_int, alt_uint, sats, hdop_raw, batt, alert, status = struct.unpack('<iihBBBBB', payload_bytes[:15])
                
                # Convertir a valores reales
                lat = lat_int / 10000000.0
                lng = lng_int / 10000000.0
                alt = float(alt_uint)
                satellites = sats
                hdop = hdop_raw / 10.0
                battery = batt
                gps_valid = bool(status & 0x01)
                inside_geofence = bool(status & 0x02)
                
                logger.info(f"✅ GPS decodificado del payload raw:")
                logger.info(f"   Lat: {lat:.6f}, Lng: {lng:.6f}, Alt: {alt}m")
                logger.info(f"   Satélites: {satellites}, HDOP: {hdop}, Batería: {battery}%")
                logger.info(f"   GPS válido: {gps_valid}, Dentro geocerca: {inside_geofence}")
                
        except Exception as e:
            logger.error(f"❌ Error decodificando payload raw: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    # OPCIÓN 3: Intentar con objectJSON si existe
    elif hasattr(uplink, 'objectJSON') and uplink.objectJSON:
        try:
            obj = json.loads(uplink.objectJSON)
            if 'gpsLocation' in obj:
                gps = obj['gpsLocation']
                lat = gps.get('latitude', 0)
                lng = gps.get('longitude', 0)
                alt = gps.get('altitude', 0)
            elif 'latitude' in obj:
                lat = obj.get('latitude', 0)
                lng = obj.get('longitude', 0)
                alt = obj.get('altitude', 0)
            gps_valid = obj.get('gpsValid', True)
            satellites = obj.get('satellites', 0)
            battery = obj.get('battery', 0)
            logger.info(f"✅ GPS desde objectJSON: {lat:.6f}, {lng:.6f}")
        except Exception as e:
            logger.error(f"❌ Error parseando objectJSON: {e}")
    
    # Verificar si tenemos coordenadas válidas
    if lat is not None and lng is not None and (abs(lat) > 0.001 or abs(lng) > 0.001):
        # Obtener RSSI y SNR correctamente
        rssi = -100
        snr = 0.0
        
        if uplink.rxInfo and len(uplink.rxInfo) > 0:
            rx = uplink.rxInfo[0]
            rssi = rx.rssi if hasattr(rx, 'rssi') else -100
            snr = rx.loRaSNR if hasattr(rx, 'loRaSNR') else 0.0
        
        logger.info(f"📍 Posición GPS válida detectada:")
        logger.info(f"   Coordenadas: {lat:.6f}, {lng:.6f}")
        logger.info(f"   Altitud: {alt}m")
        logger.info(f"   Satélites: {satellites}")
        logger.info(f"   RSSI: {rssi} dBm, SNR: {snr} dB")
        logger.info(f"   Batería: {battery}%")
        
        # Procesar posición en segundo plano
        background_tasks.add_task(
            add_position_task,
            device.id, dev_eui_hex, lat, lng, alt,
            rssi, snr, gps_valid
        )
    else:
        logger.warning(f"⚠️ Uplink sin datos GPS válidos")
        logger.warning(f"   lat={lat}, lng={lng}")
        if uplink.data:
            logger.warning(f"   Payload Base64: {uplink.data}")
            try:
                payload_bytes = base64.b64decode(uplink.data)
                logger.warning(f"   Payload Hex: {binascii.hexlify(payload_bytes).decode()}")
                logger.warning(f"   Payload Bytes: {list(payload_bytes)}")
            except:
                pass
    
    logger.info("=" * 60)
    
    return {"message": "Uplink processed", "device": dev_eui_hex, "gps_detected": lat is not None}

@router.post("/test-buzzer/{dev_eui}")
async def test_buzzer_endpoint(dev_eui: str, duration: int = 5):
    """
    Endpoint de prueba para activar el buzzer de un dispositivo.
    
    Ejemplo: POST /api/integrations/test-buzzer/000048CA433CEC58?duration=10
    """
    logger.info(f"🔔 Prueba manual de buzzer para {dev_eui} por {duration} segundos")
    
    success = await send_buzzer_alert_downlink(dev_eui, duration)
    
    if success:
        return {
            "message": f"Comando de buzzer enviado exitosamente",
            "device": dev_eui,
            "duration": duration,
            "status": "queued"
        }
    else:
        raise HTTPException(
            status_code=500, 
            detail="Error enviando comando al dispositivo. Verifica el DevEUI y la conexión con ChirpStack."
        )

@router.post("/send-geofence/{dev_eui}")
async def send_geofence_endpoint(dev_eui: str, lat: float, lng: float, radius: int = 100):
    """
    Endpoint para enviar una geocerca a un dispositivo.
    
    Ejemplo: POST /api/integrations/send-geofence/000048CA433CEC58?lat=-37.346&lng=-72.914&radius=100
    """
    logger.info(f"📍 Enviando geocerca a {dev_eui}")
    
    success = await send_geofence_to_device(dev_eui, lat, lng, radius)
    
    if success:
        return {
            "message": "Geocerca enviada exitosamente",
            "device": dev_eui,
            "center": {"lat": lat, "lng": lng},
            "radius": radius
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Error enviando geocerca al dispositivo"
        )

@router.get("/test-connection")
async def test_chirpstack_connection():
    """
    Verifica la conexión con ChirpStack API y muestra información de configuración.
    """
    try:
        url = f"{CHIRPSTACK_API_URL}/api/organizations?limit=1"
        headers = {
            "Grpc-Metadata-Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}"
        }
        
        logger.info(f"🔍 Probando conexión con ChirpStack en {CHIRPSTACK_API_URL}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "status": "connected",
                        "chirpstack_url": CHIRPSTACK_API_URL,
                        "api_token_configured": bool(CHIRPSTACK_API_TOKEN),
                        "api_token_length": len(CHIRPSTACK_API_TOKEN),
                        "organizations_found": len(data.get('result', [])) if 'result' in data else 0,
                        "message": "Conexión exitosa con ChirpStack"
                    }
                else:
                    error_text = await response.text()
                    return {
                        "status": "error",
                        "code": response.status,
                        "message": error_text,
                        "chirpstack_url": CHIRPSTACK_API_URL,
                        "api_token_configured": bool(CHIRPSTACK_API_TOKEN)
                    }
    except Exception as e:
        logger.error(f"❌ Error verificando conexión: {e}")
        return {
            "status": "error",
            "message": str(e),
            "chirpstack_url": CHIRPSTACK_API_URL,
            "api_token_configured": bool(CHIRPSTACK_API_TOKEN)
        }
