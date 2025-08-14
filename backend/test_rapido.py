#!/usr/bin/env python3
import requests
import json
import time

BACKEND_URL = "http://localhost:8002"
DEVICE_EUI = "000048CA433CEC58"  # Tu DevEUI

print("🔍 1. Verificando conexión con ChirpStack...")
r = requests.get(f"{BACKEND_URL}/api/integrations/test-connection")
print(json.dumps(r.json(), indent=2))

if r.json().get("status") != "connected":
    print("❌ Error de conexión. Verifica el backend.")
    exit(1)

print("\n✅ Conexión OK!")

print("\n🔔 2. Probando buzzer (3 segundos)...")
r = requests.post(f"{BACKEND_URL}/api/integrations/test-buzzer/{DEVICE_EUI}?duration=3")
if r.status_code == 200:
    print("✅ Buzzer enviado")
else:
    print(f"❌ Error: {r.text}")

time.sleep(2)

print("\n📍 3. Enviando geocerca de prueba...")
params = {"lat": -37.346403, "lng": -72.914955, "radius": 150}
r = requests.post(f"{BACKEND_URL}/api/integrations/send-geofence/{DEVICE_EUI}", params=params)
if r.status_code == 200:
    print("✅ Geocerca enviada")
    print(f"   Centro: {params['lat']}, {params['lng']}")
    print(f"   Radio: {params['radius']}m")
else:
    print(f"❌ Error: {r.text}")

print("\n📊 4. Creando geocerca con envío automático...")
# Obtener grupos
r = requests.get(f"{BACKEND_URL}/api/v1/groups/")
if r.status_code == 200 and r.json():
    group_id = r.json()[0]["id"]
    print(f"   Usando grupo ID: {group_id}")
    
    # Crear geocerca
    geofence_data = {
        "group_id": group_id,
        "name": f"Test Auto {time.strftime('%H:%M:%S')}",
        "geofence_type": "circle",
        "coordinates": {"lat": -37.346403, "lng": -72.914955, "radius": 200},
        "active": True
    }
    
    r = requests.post(f"{BACKEND_URL}/api/v1/geofences/", json=geofence_data)
    if r.status_code == 201:
        print("✅ Geocerca creada - downlinks enviados automáticamente")
    else:
        print(f"❌ Error: {r.text}")
else:
    print("❌ No hay grupos disponibles")

print("\n" + "="*50)
print("✅ PRUEBA COMPLETADA")
print("Verifica en la ESP32:")
print("  - El contador RX debe incrementarse")
print("  - El buzzer debe sonar")
print("  - Los logs deben mostrar 'GEOCERCA RECIBIDA'")
print("="*50)
