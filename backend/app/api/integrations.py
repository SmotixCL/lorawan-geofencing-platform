# app/api/integrations.py
"""
Módulo de integración con ChirpStack para el backend de LoRaWAN
Compatible con ESP32 Collar BuenaCabra V3.0
"""

import struct
import requests
import base64
import logging
import json
from typing import Optional, Dict, Any, Union, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# CONFIGURACIÓN DE CHIRPSTACK - Tu token actual
# ============================================================================
CHIRPSTACK_API_URL = "http://localhost:8080"
CHIRPSTACK_API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlfa2V5X2lkIjoiNDRhNGE2MzAtMGM4MC00M2EyLTk2NmYtODAwYzQwMzdkOWI4IiwiYXVkIjoiYXMiLCJpc3MiOiJhcyIsIm5iZiI6MTc1NDg3NDMyMSwic3ViIjoiYXBpX2tleSJ9.GDvpbm6rdfj1NivGoxh2ehBeTsJN8-VUuBPnqX6Lios"

# ============================================================================
# FUNCIÓN PRINCIPAL PARA ENVIAR GEOCERCA AL ESP32
# ============================================================================

async def send_geofence_downlink(
    device_eui: str, 
    coordinates: Union[List[Dict], Dict],  # Cambiar parámetros
    geofence_type: str = "circle",
    group_id: str = "backend"
) -> bool:
    """
    Envía una geocerca al dispositivo ESP32 vía ChirpStack.
    Ahora el envío soporta tanto círculos como polígonos.
    """
    try:
        logger.info(f"📡 Preparando geocerca para {device_eui}")
        logger.info(f"   Tipo: {geofence_type}")
        logger.info(f"   Grupo: {group_id}")
                
        # Construir payload binario según formato esperado por ESP32
        payload = bytearray()
        
        # Tipo de geocerca (1 byte): 0=círculo, 1=polígono
        if geofence_type == "circle":
            # Validar parámetros de coordenadas
            if not (-90 <= coordinates['lat'] <= 90) or not (-180 <= coordinates['lng'] <= 180):
                logger.error(f"❌ Coordenadas inválidas: {coordinates['lat']}, {coordinates['lng']}")
                return False
            
            if not (10 <= coordinates['radius'] <= 65535):
                logger.error(f"❌ Radio inválido: {coordinates['radius']}")
                return False
                
            logger.info(f"   Centro: {coordinates['lat']:.6f}, {coordinates['lng']:.6f}")
            logger.info(f"   Radio: {coordinates['radius']} metros")
            
            # Construir el payload para círculo
            payload.append(0)
            # Latitud (4 bytes, float little-endian)
            payload.extend(struct.pack('<f', float(coordinates['lat'])))
            # Longitud (4 bytes, float little-endian)
            payload.extend(struct.pack('<f', float(coordinates['lng'])))
            # Radio (2 bytes, uint16 little-endian)
            payload.extend(struct.pack('<H', int(coordinates['radius'])))
            
        elif geofence_type == "polygon":
            if not isinstance(coordinates, list) or len(coordinates) < 3:
                logger.error("❌ Polígono debe tener al menos 3 puntos")
                return False
            
            logger.info(f"   Polígono con {len(coordinates)} puntos")
            
            # Construir payload para polígono
            payload.append(1)  # Tipo polígono
            
            # Número de puntos (1 byte)
            num_points = min(len(coordinates), 10)  # Límite del ESP32
            payload.append(num_points)
            
            # Coordenadas de cada punto (8 bytes por punto)
            for i in range(num_points):
                coord = coordinates[i]
                logger.info(f"   Punto {i+1}: {coord['lat']:.6f}, {coord['lng']:.6f}")
                payload.extend(struct.pack('<f', float(coord['lat'])))
                payload.extend(struct.pack('<f', float(coord['lng'])))
        
        # Lógica común: GroupId y envío a ChirpStack
        
        # GroupId (opcional, máximo 15 caracteres ASCII)
        if group_id:
            group_bytes = group_id[:15].encode('ascii')
            payload.extend(group_bytes)
        
        # Convertir a base64 para ChirpStack
        payload_b64 = base64.b64encode(payload).decode('utf-8')
        
        logger.info(f"📦 Payload preparado:")
        logger.info(f"   Tamaño: {len(payload)} bytes")
        logger.info(f"   Hex: {payload.hex()}")
        logger.info(f"   Base64: {payload_b64}")
        
        # Preparar request para ChirpStack v3 API
        url = f"{CHIRPSTACK_API_URL}/api/devices/{device_eui}/queue"
        
        headers = {
            "Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Estructura de datos para ChirpStack v3
        data = {
            "deviceQueueItem": {
                "confirmed": False,  # No confirmado para reducir tráfico
                "data": payload_b64,
                "devEUI": device_eui,
                "fPort": 10  # Puerto 10 para geocercas (debe coincidir con ESP32)
            }
        }
        
        # Enviar a ChirpStack
        response = requests.post(url, json=data, headers=headers)
        logger.info("Esto es lo que estamos enviando")
        logger.info(url)
        logger.info(data)
        logger.info(headers)
        
        if response.status_code == 200:
            response_data = response.json()
            logger.info(f"✅ Geocerca enviada exitosamente a ChirpStack")
            logger.info(f"   ID en cola: {response_data.get('fCnt', 'N/A')}")
            return True
        else:
            logger.error(f"❌ Error enviando a ChirpStack: HTTP {response.status_code}")
            logger.error(f"   Respuesta: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Excepción enviando geocerca: {e}")
        return False

# ============================================================================
# WEBHOOK PARA RECIBIR UPLINKS DE CHIRPSTACK
# ============================================================================

@router.post("/webhook/uplink")
async def process_uplink(payload: dict, db: AsyncSession = Depends(get_db)):
    """
    Procesa uplinks recibidos desde ChirpStack.
    ChirpStack debe estar configurado para enviar webhooks a:
    http://[TU_IP]:8000/api/integrations/webhook/uplink
    """
    try:
        # Extraer información del uplink según formato ChirpStack v3
        device_info = payload.get("deviceInfo", {})
        device_eui = device_info.get("devEui", "")
        device_name = device_info.get("deviceName", "")
        
        # Datos del uplink
        data = payload.get("data", "")  # Base64
        f_port = payload.get("fPort", 0)
        
        # Metadatos
        rx_info = payload.get("rxInfo", [])
        tx_info = payload.get("txInfo", {})
        
        logger.info(f"📥 Uplink recibido:")
        logger.info(f"   Device: {device_eui} ({device_name})")
        logger.info(f"   Puerto: {f_port}")
        
        # Decodificar payload base64
        if data:
            try:
                raw_data = base64.b64decode(data)
                logger.info(f"   Payload: {raw_data.hex()} ({len(raw_data)} bytes)")
                
                # Procesar según el puerto
                if f_port == 1:  # Puerto GPS/Estado
                    await process_gps_uplink(device_eui, raw_data, db)
                elif f_port == 2:  # Puerto Batería
                    await process_battery_uplink(device_eui, raw_data, db)
                elif f_port == 3:  # Puerto Eventos/Alertas
                    await process_alert_uplink(device_eui, raw_data, db)
                else:
                    logger.warning(f"⚠️ Puerto desconocido: {f_port}")
                    
            except Exception as e:
                logger.error(f"❌ Error decodificando payload: {e}")
        
        # Extraer métricas de señal si están disponibles
        if rx_info and len(rx_info) > 0:
            rssi = rx_info[0].get("rssi", 0)
            snr = rx_info[0].get("loRaSNR", 0)
            logger.info(f"   Señal: RSSI={rssi}dBm, SNR={snr}dB")
        
        return {"status": "ok", "device": device_eui}
        
    except Exception as e:
        logger.error(f"❌ Error procesando uplink: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# PROCESADORES DE UPLINKS POR TIPO
# ============================================================================

async def process_gps_uplink(device_eui: str, data: bytes, db: AsyncSession):
    """
    Procesa uplink de GPS/Estado del ESP32
    Formato esperado: [lat(4)][lng(4)][alt(2)][alert(1)][battery(1)]...
    """
    if len(data) < 12:
        logger.warning(f"⚠️ Payload GPS muy corto: {len(data)} bytes")
        return
    
    try:
        # Decodificar posición
        lat = struct.unpack('<f', data[0:4])[0]
        lng = struct.unpack('<f', data[4:8])[0]
        altitude = struct.unpack('<H', data[8:10])[0]
        alert_level = data[10] if len(data) > 10 else 0
        battery = data[11] if len(data) > 11 else 0
        
        logger.info(f"📍 Posición GPS de {device_eui}:")
        logger.info(f"   Coordenadas: {lat:.6f}, {lng:.6f}")
        logger.info(f"   Altitud: {altitude}m")
        logger.info(f"   Nivel alerta: {alert_level}")
        logger.info(f"   Batería: {battery}%")
        
        # Información adicional si está disponible
        if len(data) > 12:
            satellites = data[12]
            logger.info(f"   Satélites: {satellites}")
        
        # TODO: Guardar en base de datos
        # await device_service.update_position(db, device_eui, lat, lng, altitude)
        
        # Verificar si el dispositivo está fuera de la geocerca
        if alert_level >= 3:  # DANGER o EMERGENCY
            logger.warning(f"🚨 ALERTA: Dispositivo {device_eui} fuera de geocerca!")
            # TODO: Enviar notificación o activar alerta
            
    except Exception as e:
        logger.error(f"❌ Error procesando GPS: {e}")

async def process_battery_uplink(device_eui: str, data: bytes, db: AsyncSession):
    """
    Procesa uplink de estado de batería
    """
    if len(data) < 4:
        return
    
    try:
        voltage_mv = struct.unpack('>H', data[0:2])[0]
        percentage = data[2]
        flags = data[3]
        
        voltage = voltage_mv / 1000.0
        charging = (flags & 0x01) != 0
        low = (flags & 0x02) != 0
        critical = (flags & 0x04) != 0
        
        logger.info(f"🔋 Estado de batería de {device_eui}:")
        logger.info(f"   Voltaje: {voltage:.2f}V ({percentage}%)")
        logger.info(f"   Estado: {'Cargando' if charging else 'Descargando'}")
        
        if critical:
            logger.warning(f"   ⚠️ BATERÍA CRÍTICA!")
        elif low:
            logger.warning(f"   ⚠️ Batería baja")
            
    except Exception as e:
        logger.error(f"❌ Error procesando batería: {e}")

async def process_alert_uplink(device_eui: str, data: bytes, db: AsyncSession):
    """
    Procesa uplink de eventos y alertas
    """
    if len(data) < 1:
        return
    
    event_type = data[0]
    event_data = data[1:] if len(data) > 1 else b''
    
    events = {
        1: "Dispositivo iniciado",
        2: "Geocerca actualizada",
        3: "Alerta activada",
        4: "Batería baja",
        5: "GPS perdido",
        6: "GPS recuperado"
    }
    
    event_name = events.get(event_type, f"Evento desconocido ({event_type})")
    logger.info(f"📢 Evento de {device_eui}: {event_name}")
    
    if event_data:
        logger.info(f"   Datos adicionales: {event_data.hex()}")

# ============================================================================
# ENDPOINTS DE LA API
# ============================================================================

@router.post("/send-geofence/{device_eui}")
async def send_geofence_endpoint(
    device_eui: str,
    lat: float,
    lng: float, 
    radius: int = 100,
    background_tasks: BackgroundTasks = None
):
    """
    Endpoint para enviar una geocerca a un dispositivo específico.
    
    Ejemplo:
    POST /api/integrations/send-geofence/70b3d57ed8003421?lat=-33.45&lng=-70.67&radius=150
    """
    logger.info(f"📍 Request para enviar geocerca a {device_eui}")
    
    # Enviar en background para no bloquear la respuesta
    if background_tasks:
        background_tasks.add_task(
            send_geofence_downlink,
            device_eui, lat, lng, radius, "circle", "api"
        )
        message = "Geocerca programada para envío"
    else:
        # Enviar sincrónicamente
        success = await send_geofence_downlink(
            device_eui, lat, lng, radius, "circle", "api"
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Error enviando geocerca al dispositivo"
            )
        message = "Geocerca enviada exitosamente"
    
    return {
        "status": "ok",
        "message": message,
        "device": device_eui,
        "geofence": {
            "type": "circle",
            "center": {"lat": lat, "lng": lng},
            "radius": radius
        }
    }

@router.get("/device/{device_eui}/queue")
async def get_device_queue(device_eui: str):
    """
    Obtiene la cola de downlinks pendientes de un dispositivo
    """
    url = f"{CHIRPSTACK_API_URL}/api/devices/{device_eui}/queue"
    headers = {"Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}"}
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('result', [])
            
            return {
                "device": device_eui,
                "queue_length": len(items),
                "items": items
            }
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Error consultando ChirpStack: {response.text}"
            )
            
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Error de conexión: {str(e)}")

@router.delete("/device/{device_eui}/queue")
async def clear_device_queue(device_eui: str):
    """
    Limpia la cola de downlinks de un dispositivo
    """
    url = f"{CHIRPSTACK_API_URL}/api/devices/{device_eui}/queue"
    headers = {"Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}"}
    
    try:
        response = requests.delete(url, headers=headers)
        
        if response.status_code == 200:
            return {
                "status": "ok",
                "message": f"Cola limpiada para {device_eui}"
            }
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Error en ChirpStack: {response.text}"
            )
            
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Error de conexión: {str(e)}")

@router.get("/test-connection")
async def test_chirpstack_connection():
    """
    Verifica la conexión con ChirpStack y muestra información del sistema
    """
    try:
        # Probar conexión con endpoint de perfil
        url = f"{CHIRPSTACK_API_URL}/api/internal/profile"
        headers = {"Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}"}
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            profile_data = response.json()
            
            return {
                "status": "connected",
                "chirpstack_url": CHIRPSTACK_API_URL,
                "user": profile_data.get("user", {}).get("email", "N/A"),
                "is_admin": profile_data.get("user", {}).get("isAdmin", False),
                "message": "✅ Conexión exitosa con ChirpStack"
            }
        else:
            return {
                "status": "error",
                "code": response.status_code,
                "message": "❌ Error de autenticación. Verifica el token.",
                "chirpstack_url": CHIRPSTACK_API_URL
            }
            
    except Exception as e:
        logger.error(f"❌ Error verificando conexión: {e}")
        return {
            "status": "error",
            "message": str(e),
            "chirpstack_url": CHIRPSTACK_API_URL
        }
