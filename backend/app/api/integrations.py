from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.schemas.integrations import ChirpstackUplinkPayload
from app.services import device_service
from app.services.gps_decoder import decode_gps_payload
from app.schemas.device import DeviceCreate
import base64
import binascii
from app.core.database import SessionLocal

router = APIRouter()

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
async def handle_chirpstack_uplink(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    # Obtener tipo de evento
    event_type = request.query_params.get("event", "")
    
    # Parsear body
    data = await request.json()
    
    # Filtrar eventos que no son 'up'
    if event_type != "up":
        print(f"📡 Evento {event_type} recibido - ignorando")
        return {"status": "ok", "event": event_type}
    
    # Procesar uplink
    uplink = ChirpstackUplinkPayload(**data)
    
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
    
    # Intentar obtener datos decodificados
    decoded_data = uplink.decoded_content
    
    # Si ChirpStack no decodificó, usar decoder Python
    if not decoded_data and hasattr(uplink, 'data') and uplink.data:
        print("🔄 ChirpStack no envió campos decodificados, usando decoder Python...")
        
        try:
            # Asegurar que el string de base64 tenga padding correcto
            base64_string = uplink.data
            # Agregar padding si falta
            missing_padding = len(base64_string) % 4
            if missing_padding:
                base64_string += '=' * (4 - missing_padding)
            
            payload_bytes = base64.b64decode(base64_string)
            payload_hex = payload_bytes.hex()
            
            print(f"🔍 Payload bytes: {len(payload_bytes)} bytes")
            print(f"🔍 Payload hex: {payload_hex}")
            
            # Llamar al decoder
            decoded_dict = decode_gps_payload(payload_hex)
            
            if decoded_dict:
                # Crear estructura compatible con ChirpStack
                from types import SimpleNamespace
                decoded_data = SimpleNamespace(
                    gpsLocation=SimpleNamespace(**decoded_dict['gpsLocation']),
                    digitalInput=SimpleNamespace(channel2=decoded_dict['gps_valid'])
                )
                print("✅ Usando decoder Python")
        except Exception as e:
            print(f"❌ Error procesando payload base64: {e}")
            print(f"    Base64 original: {uplink.data}")
    
    # Procesar datos GPS
    if decoded_data and decoded_data.gpsLocation:
        lat = decoded_data.gpsLocation.latitude
        lng = decoded_data.gpsLocation.longitude
        alt = decoded_data.gpsLocation.altitude
        gps_valid = decoded_data.digitalInput.channel2 if decoded_data.digitalInput and hasattr(decoded_data.digitalInput, 'channel2') else True
        
        if gps_valid and lat != 0.0 and lng != 0.0:
            background_tasks.add_task(
   		add_position_task,
    		device.id, lat, lng, alt,
    		uplink.rxInfo[0].rssi if uplink.rxInfo and len(uplink.rxInfo) > 0 else None,
    		uplink.rxInfo[0].loRaSNR if uplink.rxInfo and len(uplink.rxInfo) > 0 else None,
    		gps_valid
		)
            print(f"✅ GPS PROCESADO EXITOSAMENTE")
            print(f"    🏷️ Dispositivo: {device.device_name}")
            print(f"    📍 Coordenadas: {lat}, {lng}")
            print(f"    🏔️ Altitud: {alt}m")
            print(f"    🛰️ GPS Válido: {gps_valid}")
            print(f"    📡 RSSI: {uplink.rxInfo[0].rssi if uplink.rxInfo and len(uplink.rxInfo) > 0 else 'N/A'} dBm, SNR: {uplink.rxInfo[0].loRaSNR if uplink.rxInfo and len(uplink.rxInfo) > 0 else 'N/A'} dB")
            print(f"    🔋 DevEUI: {dev_eui_hex}")
    else:
        print(f"❌ ERROR: No se pudieron extraer datos GPS válidos")
        print(f"    lat=None, lng=None")
        print(f"    uplink.data exists: {hasattr(uplink, 'data')}")
        print(f"    uplink.fPort: {getattr(uplink, 'fPort', None)}")
    
    return {"message": "Uplink processed successfully!"}
