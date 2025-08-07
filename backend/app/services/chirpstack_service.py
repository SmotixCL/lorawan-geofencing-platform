import httpx
import struct
import base64
from typing import Dict, Any
from app.core.config import settings

async def send_downlink(dev_eui: str, fport: int, payload: bytes, confirmed: bool = False):
    """
    Construye y envía una solicitud a la API de ChirpStack para encolar un downlink.
    """
    api_url = f"{settings.CHIRPSTACK_API_URL}/devices/{dev_eui}/queue"

    payload_b64 = base64.b64encode(payload).decode('utf-8')

    json_body = {
        "deviceQueueItem": {
            "confirmed": confirmed,
            "data": payload_b64,
            "fPort": fport
        }
    }

    headers = {
        "Grpc-Metadata-Authorization": f"Bearer {settings.CHIRPSTACK_API_KEY}"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(api_url, json=json_body, headers=headers)
            response.raise_for_status()
            print(f"Downlink encolado con éxito para el dispositivo {dev_eui}")
            return True
        except httpx.HTTPStatusError as e:
            print(f"Error al encolar downlink para {dev_eui}: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            print(f"Ocurrió un error inesperado al enviar el downlink: {e}")
            return False

def pack_geofence_to_bytes(geofence_data: Dict[str, Any]) -> bytes:
    """
    Compacta los datos de la geocerca en un array de bytes para el downlink.
    """
    try:
        if geofence_data['type'] == 'circle':
            # Formato: Tipo (1 byte) + Lat (4) + Lng (4) + Radio (2) = 11 bytes
            lat = int(geofence_data['center']['lat'] * 1000000)
            lng = int(geofence_data['center']['lng'] * 1000000)
            radius = int(geofence_data['radius'])
            # 'B' UChar, 'i' Int32, 'H' UInt16. '>' para big-endian (network order).
            return struct.pack('>BiiH', 1, lat, lng, radius)

        elif geofence_data['type'] == 'polygon':
            # Formato: Tipo (1) + Num_Vertices (1) + N * (Lat(4) + Lng(4))
            vertices = geofence_data['coords']
            num_vertices = len(vertices)

            format_string = f'>BB{num_vertices * "ii"}'

            args = [2, num_vertices]
            for v in vertices:
                args.append(int(v['lat'] * 1000000))
                args.append(int(v['lng'] * 1000000))

            return struct.pack(format_string, *args)
    except (KeyError, TypeError) as e:
        print(f"Error al empaquetar la geocerca: datos inválidos. {e}")
        return b'' # Retorna un payload vacío si hay un error

    return b''
