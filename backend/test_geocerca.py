#!/usr/bin/env python3
import requests
import json

BACKEND_URL = "http://localhost:8002"

# Obtener grupos
r = requests.get(f"{BACKEND_URL}/api/v1/groups/")
if r.status_code == 200 and r.json():
    group_id = r.json()[0]["id"]
    print(f"Usando grupo ID: {group_id}")
    
    # Crear geocerca con valores específicos
    geofence_data = {
        "group_id": group_id,
        "name": "Mi Geocerca Test",
        "geofence_type": "circle",
        "coordinates": {
            "lat": -37.34640277978371,
            "lng": -72.91495492379738,
            "radius": 300.0  # 300 metros
        },
        "active": True
    }
    
    print(f"\nCreando geocerca:")
    print(f"  Nombre: {geofence_data['name']}")
    print(f"  Centro: {geofence_data['coordinates']['lat']:.6f}, {geofence_data['coordinates']['lng']:.6f}")
    print(f"  Radio: {geofence_data['coordinates']['radius']}m")
    
    r = requests.post(f"{BACKEND_URL}/api/v1/geofences/", json=geofence_data)
    if r.status_code == 201:
        print("✅ Geocerca creada exitosamente")
        result = r.json()
        print(f"  ID: {result['id']}")
    else:
        print(f"❌ Error: {r.text}")
