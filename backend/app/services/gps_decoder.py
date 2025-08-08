import struct
from typing import Optional, Dict, Any

def decode_gps_payload(payload_hex: str) -> Optional[Dict[str, Any]]:
    """
    Decodifica payload GPS del collar LoRaWAN
    Formato: [lat:4][lng:4][alt:2][sats:1][bat:1][hdop:1][alert:1][flags:1]
    Total: 15 bytes
    """
    try:
        # Limpiar el hex string por si tiene espacios o caracteres extraños
        payload_hex = payload_hex.strip().replace(" ", "")
        
        # Verificar longitud del hex (debe ser 30 caracteres para 15 bytes)
        if len(payload_hex) != 30:
            print(f"❌ Payload hex incorrecto: {len(payload_hex)} chars (esperados 30)")
            return None
        
        # Convertir hex a bytes
        payload_bytes = bytes.fromhex(payload_hex)
        
        if len(payload_bytes) != 15:
            print(f"❌ Payload incorrecto: {len(payload_bytes)} bytes (esperados 15)")
            return None
        
        # Desempaquetar según formato del collar
        lat_raw, lng_raw, alt, sats, bat, hdop_raw, alert, flags = struct.unpack(
            '<iihBBBBB', payload_bytes
        )
        
        # Convertir coordenadas (vienen multiplicadas por 10^7)
        latitude = lat_raw / 10000000.0
        longitude = lng_raw / 10000000.0
        hdop = hdop_raw / 10.0
        
        # Decodificar flags
        gps_valid = bool(flags & 0x01)
        inside_geofence = bool(flags & 0x02)
        
        # Mapear niveles de alerta
        alert_levels = {
            0: "SAFE",
            1: "WARNING", 
            2: "CAUTION",
            3: "DANGER",
            4: "EMERGENCY"
        }
        
        print(f"✅ GPS Decodificado:")
        print(f"    📍 Lat: {latitude:.7f}, Lng: {longitude:.7f}")
        print(f"    🏔️ Alt: {alt}m, Sats: {sats}")
        print(f"    🔋 Bat: {bat}%, HDOP: {hdop}")
        print(f"    🚨 Alert: {alert_levels.get(alert, 'UNKNOWN')}")
        print(f"    ✅ GPS: {gps_valid}, Geofence: {inside_geofence}")
        
        return {
            "gpsLocation": {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": alt
            },
            "satellites": sats,
            "battery": bat,
            "hdop": hdop,
            "alert": alert_levels.get(alert, "UNKNOWN"),
            "gps_valid": gps_valid,
            "inside_geofence": inside_geofence
        }
        
    except Exception as e:
        print(f"❌ Error decodificando payload: {e}")
        print(f"    Hex recibido: {payload_hex}")
        return None
