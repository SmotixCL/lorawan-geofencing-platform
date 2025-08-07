from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.schemas.integrations import ChirpstackUplinkPayload
from app.services import device_service
from app.schemas.device import DeviceCreate
import base64
import binascii
import struct
from app.core.database import SessionLocal

router = APIRouter()

def decode_gps_payload(base64_data: str):
    """
    Decodifica payload GPS desde base64 (estructura ESP32 GPSPayload)
    """
    try:
        # Decodificar base64 a bytes
        data_bytes = base64.b64decode(base64_data)
        
        print(f"🔍 Payload bytes: {len(data_bytes)} bytes")
        print(f"🔍 Payload hex: {data_bytes.hex()}")
        
        if len(data_bytes) < 15:
            print(f"❌ Payload muy corto: {len(data_bytes)} < 15 bytes")
            return None
            
        # Estructura ESP32 GPSPayload (15 bytes):
        # int32_t latitude;   // 4 bytes (little endian, signed)
        # int32_t longitude;  // 4 bytes (little endian, signed)  
        # uint16_t altitude;  // 2 bytes (little endian, unsigned)
        # uint8_t satellites; // 1 byte
        # uint8_t hdop;       // 1 byte (hdop * 10)
        # uint8_t battery;    // 1 byte (0-100%)
        # uint8_t alert;      // 1 byte (0-4)
        # uint8_t status;     // 1 byte (bits: GPS_VALID(0), GEOFENCE_INSIDE(1))
        
        lat_raw, lng_raw, alt, sats, hdop, bat, alert, status = struct.unpack('<iihBBBBB', data_bytes)
        
        # Convertir coordenadas (están multiplicadas por 10^7)
        latitude = lat_raw / 10000000.0
        longitude = lng_raw / 10000000.0
        
        # Decodificar status bits
        gps_valid = (status & 0x01) != 0
        inside_geofence = (status & 0x02) != 0
        
        # Nombres de alertas
        alert_names = ["SAFE", "CAUTION", "WARNING", "DANGER", "EMERGENCY"]
        alert_level = alert_names[alert] if alert < len(alert_names) else "UNKNOWN"
        
        decoded = {
            'latitude': latitude,
            'longitude': longitude,
            'altitude': alt,
            'satellites': sats,
            'hdop': hdop / 10.0,
            'battery': bat,
            'alert': alert,
            'alertLevel': alert_level,
            'gpsValid': gps_valid,
            'insideGeofence': inside_geofence,
            'status': status
        }
        
        print(f"✅ GPS Decodificado:")
        print(f"    📍 Lat: {latitude}, Lng: {longitude}")
        print(f"    🏔️ Alt: {alt}m, Sats: {sats}")
        print(f"    🔋 Bat: {bat}%, HDOP: {hdop/10.0}")
        print(f"    🚨 Alert: {alert} ({alert_level})")
        print(f"    ✅ GPS: {gps_valid}, Geofence: {inside_geofence}")
        
        return decoded
        
    except struct.error as e:
        print(f"❌ Error struct.unpack: {e}")
        return None
    except Exception as e:
        print(f"❌ Error decodificando payload: {e}")
        return None

async def add_position_task(device_id: int, lat: float, lng: float, alt: float, rssi: int, snr: float, gps_valid: bool):
    """
    Tarea en segundo plano que crea su propia sesión de BD para guardar la posición.
    """
    print(f"Tarea en segundo plano: Abriendo sesión de BD para guardar posición del dispositivo {device_id}")
    async with SessionLocal() as db:
        try:
            await device_service.add_device_position(db, device_id, lat, lng, alt, rssi, snr, gps_valid)
            print(f"Tarea en segundo plano: Posición del dispositivo {device_id} guardada con éxito.")
        except Exception as e:
            print(f"Error en la tarea en segundo plano al guardar posición: {e}")
        finally:
            await db.close()

@router.post("/uplink")
async def handle_chirpstack_uplink(uplink: ChirpstackUplinkPayload, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    try:
        decoded_eui_bytes = base64.b64decode(uplink.devEUI)
        dev_eui_hex = binascii.hexlify(decoded_eui_bytes).decode('utf-8').upper()
    except (binascii.Error, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid DevEUI Base64 format: {uplink.devEUI} - {e}")

    device = await device_service.get_device_by_eui(db=db, dev_eui=dev_eui_hex)

    if not device:
        device_name = uplink.deviceName if uplink.deviceName else "Unnamed Device"
        new_device_data = DeviceCreate(dev_eui=dev_eui_hex, device_name=device_name)
        device = await device_service.create_device(db=db, device=new_device_data)
        if not device:
            raise HTTPException(status_code=500, detail="Dispositivo no encontrado y no se pudo crear.")
        print(f"Dispositivo {device.device_name} (ID: {device.id}) creado automáticamente.")

    print(f"Uplink de {uplink.deviceName} procesado.")
    
    # Variables para GPS data
    lat = None
    lng = None
    alt = None
    gps_valid = None
    alert_level = None
    
    # MÉTODO 1: Intentar campos directos (si ChirpStack los envía)
    if hasattr(uplink, 'latitude') and uplink.latitude is not None:
        lat = uplink.latitude
        lng = uplink.longitude  
        alt = uplink.altitude or 0
        gps_valid = uplink.gpsValid
        alert_level = uplink.alertLevel
        print("✅ Usando datos decodificados de ChirpStack")
    
    # MÉTODO 2: Decoder Python (BACKUP - si ChirpStack no envía campos)
    elif uplink.data and uplink.fPort == 1:
        print("🔄 ChirpStack no envió campos decodificados, usando decoder Python...")
        decoded = decode_gps_payload(uplink.data)
        if decoded:
            lat = decoded['latitude']
            lng = decoded['longitude']
            alt = decoded['altitude']
            gps_valid = decoded['gpsValid']
            alert_level = decoded['alertLevel']
            print("✅ Usando decoder Python")
    
    # MÉTODO 3: Legacy format (si existe)
    elif hasattr(uplink, 'decoded_content') and uplink.decoded_content:
        print("🔄 Intentando formato legacy...")
        decoded_data = uplink.decoded_content
        if hasattr(decoded_data, 'gpsLocation') and decoded_data.gpsLocation:
            lat = float(decoded_data.gpsLocation.latitude)
            lng = float(decoded_data.gpsLocation.longitude)
            alt = float(decoded_data.gpsLocation.altitude) if hasattr(decoded_data.gpsLocation, 'altitude') else 0
            gps_valid = True
            print("✅ Usando formato legacy")
    
    # PROCESAR DATOS GPS SI EXISTEN
    if lat is not None and lng is not None and (abs(lat) > 0.001 or abs(lng) > 0.001):
        # Obtener RSSI y SNR 
        rssi = -999
        snr = 0
        if uplink.rxInfo and len(uplink.rxInfo) > 0:
            rssi = uplink.rxInfo[0].rssi if hasattr(uplink.rxInfo[0], 'rssi') and uplink.rxInfo[0].rssi is not None else -999
            snr = uplink.rxInfo[0].loRaSNR if hasattr(uplink.rxInfo[0], 'loRaSNR') and uplink.rxInfo[0].loRaSNR is not None else 0
        
        # Usar gps_valid, defaultear a True si no existe
        valid = gps_valid if gps_valid is not None else True
        
        # Tarea en segundo plano
        background_tasks.add_task(
            add_position_task,
            device.id, float(lat), float(lng), float(alt),
            int(rssi), float(snr), bool(valid)
        )
        
        print(f"✅ GPS PROCESADO EXITOSAMENTE")
        print(f"    🏷️ Dispositivo: {device.device_name}")
        print(f"    📍 Coordenadas: {lat}, {lng}")
        print(f"    🏔️ Altitud: {alt}m")
        print(f"    🛰️ GPS Válido: {valid}")
        print(f"    🚨 Alerta: {alert_level}")
        print(f"    📡 RSSI: {rssi} dBm, SNR: {snr} dB")
        print(f"    🔋 DevEUI: {dev_eui_hex}")
        
    else:
        print(f"❌ ERROR: No se pudieron extraer datos GPS válidos")
        print(f"    lat={lat}, lng={lng}")
        print(f"    uplink.data exists: {uplink.data is not None}")
        print(f"    uplink.fPort: {uplink.fPort}")

    return {"message": "Uplink processed successfully!"}
