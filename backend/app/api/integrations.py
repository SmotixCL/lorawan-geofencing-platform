# app/api/integrations.py

import struct
import requests
import base64
import logging
import os
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.schemas import geofence as schemas
from app.services import geofence_service, group_service
import asyncio
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# CONFIGURACIÓN DE CHIRPSTACK - TUS CREDENCIALES
# ============================================================================
CHIRPSTACK_API_URL = "http://localhost:8080"
CHIRPSTACK_API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlfa2V5X2lkIjoiNDRhNGE2MzAtMGM4MC00M2EyLTk2NmYtODAwYzQwMzdkOWI4IiwiYXVkIjoiYXMiLCJpc3MiOiJhcyIsIm5iZiI6MTc1NDg3NDMyMSwic3ViIjoiYXBpX2tleSJ9.GDvpbm6rdfj1NivGoxh2ehBeTsJN8-VUuBPnqX6Lios"

# ============================================================================
# FUNCIÓN PRINCIPAL PARA ENVIAR DOWNLINK DE GEOCERCA
# ============================================================================

async def send_geofence_downlink(
    device_eui: str, 
    lat: float, 
    lng: float, 
    radius: int,
    geofence_type: int = 1,  # 1=círculo, 2=polígono
    group_id: str = "backend"
) -> bool:
    """
    Envía una geocerca circular como downlink al dispositivo ESP32 vía ChirpStack v3
    """
    try:
        logger.info(f"📡 Preparando downlink para {device_eui}")
        
        # Validar coordenadas
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            logger.error(f"❌ Coordenadas inválidas: {lat}, {lng}")
            return False
        
        if not (10 <= radius <= 10000):
            logger.error(f"❌ Radio inválido: {radius}")
            return False
        
        # Preparar payload para círculo
        # Formato: [tipo(1)][lat(4)][lng(4)][radio(2)][groupId(N)]
        payload = struct.pack('<B', 1)  # Tipo: 1 = círculo
        payload += struct.pack('<f', float(lat))  # Latitud como float (4 bytes)
        payload += struct.pack('<f', float(lng))  # Longitud como float (4 bytes)
        payload += struct.pack('<H', int(radius))  # Radio como uint16 (2 bytes)
        
        # Agregar groupId si se proporciona (máximo 15 caracteres)
        if group_id:
            group_bytes = group_id.encode('utf-8')[:15]
            payload += group_bytes
        
        # Codificar en base64
        payload_b64 = base64.b64encode(payload).decode('utf-8')
        
        logger.info(f"📦 Payload preparado: {len(payload)} bytes")
        logger.info(f"📦 Base64: {payload_b64}")
        
        # URL de ChirpStack v3 API
        url = f"{CHIRPSTACK_API_URL}/api/devices/{device_eui}/queue"
        
        # Datos del downlink para ChirpStack v3
        downlink_data = {
            "deviceQueueItem": {
                "confirmed": False,
                "data": payload_b64,
                "devEUI": device_eui,
                "fPort": 10  # Puerto 10 para geocercas
            }
        }
        
        # Headers con tu API token
        headers = {
            "Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Enviar request
        logger.info(f"📡 Enviando a ChirpStack: {url}")
        response = requests.post(
            url,
            json=downlink_data,
            headers=headers,
            timeout=10
        )
        
        # Verificar respuesta
        if response.status_code in [200, 201, 202]:
            logger.info(f"✅ Geocerca enviada exitosamente a {device_eui}")
            logger.info(f"   Centro: {lat:.6f}, {lng:.6f}")
            logger.info(f"   Radio: {radius} metros")
            logger.info(f"   Grupo: {group_id}")
            return True
        else:
            logger.error(f"❌ Error de ChirpStack: {response.status_code}")
            logger.error(f"   Respuesta: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ No se puede conectar con ChirpStack en {CHIRPSTACK_API_URL}")
        return False
    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout conectando con ChirpStack")
        return False
    except Exception as e:
        logger.error(f"❌ Error inesperado: {str(e)}")
        return False

async def send_polygon_geofence_downlink(
    device_eui: str,
    points: List[dict],  # Lista de diccionarios con 'lat' y 'lng'
    group_id: str = "backend"
) -> bool:
    """
    Envía una geocerca poligonal como downlink al dispositivo ESP32
    """
    try:
        if len(points) < 3 or len(points) > 10:
            logger.error(f"❌ Número de puntos inválido: {len(points)} (debe ser 3-10)")
            return False
        
        logger.info(f"📡 Preparando polígono con {len(points)} puntos para {device_eui}")
        
        # Formato: [tipo(1)][numPuntos(1)][lat1(4)][lng1(4)]...[groupId(N)]
        payload = struct.pack('<BB', 2, len(points))  # Tipo 2 = polígono
        
        # Agregar cada punto
        for point in points:
            lat = float(point.get('lat', 0))
            lng = float(point.get('lng', 0))
            payload += struct.pack('<ff', lat, lng)
            logger.info(f"   Punto: {lat:.6f}, {lng:.6f}")
        
        # Agregar groupId
        if group_id:
            group_bytes = group_id.encode('utf-8')[:15]
            payload += group_bytes
        
        # Codificar y enviar
        payload_b64 = base64.b64encode(payload).decode('utf-8')
        
        # URL de ChirpStack v3
        url = f"{CHIRPSTACK_API_URL}/api/devices/{device_eui}/queue"
        
        downlink_data = {
            "deviceQueueItem": {
                "confirmed": False,
                "data": payload_b64,
                "devEUI": device_eui,
                "fPort": 10
            }
        }
        
        headers = {
            "Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=downlink_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201, 202]:
            logger.info(f"✅ Polígono enviado exitosamente a {device_eui}")
            return True
        else:
            logger.error(f"❌ Error: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Error enviando polígono: {e}")
        return False

# ============================================================================
# ENDPOINTS DE GEOCERCAS CON DOWNLINK AUTOMÁTICO
# ============================================================================

@router.post("/geofences/", response_model=schemas.Geofence)
async def create_geofence_with_downlink(
    geofence: schemas.GeofenceCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Crea una nueva geocerca y envía downlink automático a dispositivos del grupo
    """
    logger.info(f"🆕 Creando nueva geocerca: {geofence.name}")
    
    # Crear geocerca en base de datos
    db_geofence = await geofence_service.create_geofence(db, geofence)
    
    try:
        # Si la geocerca tiene un grupo asignado
        if hasattr(geofence, 'group_id') and geofence.group_id:
            # Obtener el grupo y sus dispositivos
            group = await group_service.get_group(db, geofence.group_id)
            
            if group and hasattr(group, 'devices') and group.devices:
                logger.info(f"📱 Enviando a {len(group.devices)} dispositivos del grupo {geofence.group_id}")
                
                # Para cada dispositivo del grupo
                for device in group.devices:
                    if hasattr(device, 'dev_eui'):
                        # Programar envío asíncrono en background
                        if geofence.type == "circle":
                            background_tasks.add_task(
                                send_geofence_downlink,
                                device.dev_eui,
                                float(geofence.center_lat),
                                float(geofence.center_lng),
                                int(geofence.radius),
                                1,
                                str(geofence.group_id)
                            )
                            logger.info(f"   📡 Downlink programado para {device.dev_eui}")
                        
                        elif geofence.type == "polygon" and hasattr(geofence, 'points'):
                            background_tasks.add_task(
                                send_polygon_geofence_downlink,
                                device.dev_eui,
                                geofence.points,
                                str(geofence.group_id)
                            )
                            logger.info(f"   📡 Downlink poligonal programado para {device.dev_eui}")
            else:
                logger.warning(f"⚠️ El grupo {geofence.group_id} no tiene dispositivos")
        else:
            logger.info("ℹ️ Geocerca creada sin grupo asignado")
    
    except Exception as e:
        logger.error(f"❌ Error enviando downlinks: {str(e)}")
        # No fallar la creación por error en downlinks
    
    return db_geofence

@router.put("/geofences/{geofence_id}", response_model=schemas.Geofence)
async def update_geofence_with_downlink(
    geofence_id: int,
    geofence: schemas.GeofenceCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Actualiza una geocerca existente y envía la actualización a los dispositivos
    """
    logger.info(f"🔄 Actualizando geocerca ID: {geofence_id}")
    
    # Actualizar en base de datos
    db_geofence = await geofence_service.update_geofence(db, geofence_id, geofence)
    if not db_geofence:
        raise HTTPException(status_code=404, detail="Geocerca no encontrada")
    
    # Enviar actualización a dispositivos (misma lógica que create)
    # ... (copiar lógica de arriba)
    
    return db_geofence

# ============================================================================
# ENDPOINT DE TEST MANUAL
# ============================================================================

@router.post("/test-downlink/")
async def test_geofence_downlink(
    device_eui: str,
    lat: float = -33.4489,
    lng: float = -70.6693,
    radius: int = 100,
    group_id: str = "test"
):
    """
    Endpoint para probar el envío de downlink manualmente
    
    Ejemplo de uso:
    POST /api/integrations/test-downlink/
    {
        "device_eui": "70b3d57ed8003421",
        "lat": -33.4489,
        "lng": -70.6693,
        "radius": 100,
        "group_id": "test"
    }
    """
    logger.info(f"🧪 Test de downlink solicitado para {device_eui}")
    
    success = await send_geofence_downlink(
        device_eui=device_eui,
        lat=lat,
        lng=lng,
        radius=radius,
        geofence_type=1,
        group_id=group_id
    )
    
    if success:
        return {
            "status": "success",
            "message": f"Downlink enviado exitosamente a {device_eui}",
            "details": {
                "device_eui": device_eui,
                "center": {"lat": lat, "lng": lng},
                "radius": radius,
                "group_id": group_id,
                "timestamp": datetime.now().isoformat()
            }
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Error enviando downlink a {device_eui}. Verificar logs."
        )

# ============================================================================
# WEBHOOK PARA RECIBIR UPLINKS DE CHIRPSTACK
# ============================================================================

@router.post("/webhook/uplink")
async def process_uplink(payload: dict, db: AsyncSession = Depends(get_db)):
    """
    Procesa uplinks recibidos desde ChirpStack
    ChirpStack debe estar configurado para enviar webhooks a:
    http://localhost:8000/api/integrations/webhook/uplink
    """
    try:
        # Extraer información del uplink de ChirpStack v3
        device_info = payload.get("deviceInfo", {})
        device_eui = device_info.get("devEui", "")
        
        # Datos del uplink
        data = payload.get("data", "")
        f_port = payload.get("fPort", 0)
        
        # Metadatos
        rx_info = payload.get("rxInfo", [])
        tx_info = payload.get("txInfo", {})
        
        logger.info(f"📥 Uplink recibido de {device_eui} en puerto {f_port}")
        
        # Decodificar payload base64
        if data:
            raw_data = base64.b64decode(data)
            
            if f_port == 1:  # Puerto GPS
                if len(raw_data) >= 12:
                    # Decodificar posición GPS
                    lat = struct.unpack('<f', raw_data[0:4])[0]
                    lng = struct.unpack('<f', raw_data[4:8])[0]
                    altitude = struct.unpack('<H', raw_data[8:10])[0]
                    alert_level = raw_data[10] if len(raw_data) > 10 else 0
                    battery = raw_data[11] if len(raw_data) > 11 else 0
                    
                    logger.info(f"📍 Posición GPS de {device_eui}:")
                    logger.info(f"   Coordenadas: {lat:.6f}, {lng:.6f}")
                    logger.info(f"   Altitud: {altitude}m")
                    logger.info(f"   Nivel de alerta: {alert_level}")
                    logger.info(f"   Batería: {battery}%")
                    
                    # Guardar en base de datos
                    # await save_device_position(db, device_eui, lat, lng, altitude, battery)
                    
                    # Si hay alerta, podríamos notificar
                    if alert_level > 2:  # WARNING o mayor
                        logger.warning(f"⚠️ ALERTA nivel {alert_level} de dispositivo {device_eui}")
                        # await send_alert_notification(device_eui, alert_level, lat, lng)
            
            elif f_port == 2:  # Puerto batería
                if len(raw_data) >= 4:
                    voltage = struct.unpack('<H', raw_data[0:2])[0] / 1000.0
                    percentage = raw_data[2]
                    flags = raw_data[3]
                    
                    logger.info(f"🔋 Estado de batería de {device_eui}:")
                    logger.info(f"   Voltaje: {voltage}V")
                    logger.info(f"   Porcentaje: {percentage}%")
                    logger.info(f"   Cargando: {bool(flags & 0x01)}")
                    logger.info(f"   Batería baja: {bool(flags & 0x02)}")
        
        # Responder OK a ChirpStack
        return {
            "status": "processed",
            "device_eui": device_eui,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error procesando uplink: {str(e)}")
        # No fallar para que ChirpStack no reintente
        return {"status": "error", "message": str(e)}

# ============================================================================
# ENDPOINTS DE UTILIDAD
# ============================================================================

@router.get("/chirpstack/status")
async def check_chirpstack_status():
    """
    Verifica el estado de la conexión con ChirpStack
    """
    try:
        headers = {
            "Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}",
            "Accept": "application/json"
        }
        
        # Intentar obtener info del servidor
        response = requests.get(
            f"{CHIRPSTACK_API_URL}/api/internal/profile",
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            return {
                "status": "connected",
                "chirpstack_url": CHIRPSTACK_API_URL,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "code": response.status_code,
                "message": "Error conectando con ChirpStack"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@router.get("/devices/{device_eui}/queue")
async def get_device_queue(device_eui: str):
    """
    Obtiene la cola de downlinks pendientes para un dispositivo
    """
    try:
        headers = {
            "Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}",
            "Accept": "application/json"
        }
        
        response = requests.get(
            f"{CHIRPSTACK_API_URL}/api/devices/{device_eui}/queue",
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# INICIALIZACIÓN
# ============================================================================

logger.info("=" * 60)
logger.info("📡 MÓDULO DE INTEGRACIÓN LORAWAN INICIALIZADO")
logger.info(f"   ChirpStack URL: {CHIRPSTACK_API_URL}")
logger.info(f"   Token configurado: {'Sí' if CHIRPSTACK_API_TOKEN else 'No'}")
logger.info("=" * 60)
