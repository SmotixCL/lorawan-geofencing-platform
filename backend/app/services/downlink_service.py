import struct
import base64
import aiohttp
import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_geofence_to_device(dev_eui: str, lat: float, lng: float, radius: int) -> bool:
    """
    Envía una geocerca circular al dispositivo vía downlink.
    """
    try:
        # Comando 0x02 = actualizar geocerca
        # Formato: [CMD][LAT_4bytes][LNG_4bytes][RADIUS_2bytes]
        lat_int = int(lat * 10000000)
        lng_int = int(lng * 10000000)
        
        payload = struct.pack('<BiihH', 
                             0x02,  # Comando
                             lat_int,  # Latitud
                             lng_int,  # Longitud  
                             radius)  # Radio
        
        payload_b64 = base64.b64encode(payload).decode('utf-8')
        
        url = f"{settings.CHIRPSTACK_API_URL}/api/devices/{dev_eui}/queue"
        headers = {
            "Grpc-Metadata-Authorization": f"Bearer {settings.CHIRPSTACK_API_TOKEN}",
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
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as response:
                if response.status == 200:
                    logger.info(f"✅ Geocerca enviada a {dev_eui}: {lat:.6f},{lng:.6f} R:{radius}m")
                    return True
                else:
                    logger.error(f"❌ Error enviando geocerca: {response.status}")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ Excepción enviando geocerca: {e}")
        return False
