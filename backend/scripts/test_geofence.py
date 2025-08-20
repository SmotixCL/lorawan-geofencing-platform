#!/usr/bin/env python3
"""
test_geofence_downlink.py
Script de prueba para enviar geocercas a dispositivos ESP32 vía ChirpStack
Configurado para tu Raspberry Pi
"""

import struct
import base64
import requests
import json
import sys
import argparse
from datetime import datetime
from typing import Optional

# Configuración de ChirpStack - TUS CREDENCIALES
CHIRPSTACK_API_URL = "http://localhost:8080"
CHIRPSTACK_API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlfa2V5X2lkIjoiNDRhNGE2MzAtMGM4MC00M2EyLTk2NmYtODAwYzQwMzdkOWI4IiwiYXVkIjoiYXMiLCJpc3MiOiJhcyIsIm5iZiI6MTc1NDg3NDMyMSwic3ViIjoiYXBpX2tleSJ9.GDvpbm6rdfj1NivGoxh2ehBeTsJN8-VUuBPnqX6Lios"

# Colores para output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header():
    """Imprime el header del script"""
    print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}📡 TEST DE DOWNLINK DE GEOCERCA - LORAWAN{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}\n")

def send_circle_geofence(device_eui: str, lat: float, lng: float, radius: int, group_id: str = "test"):
    """Envía una geocerca circular al dispositivo"""
    
    print(f"{Colors.OKBLUE}📍 Preparando geocerca circular:{Colors.ENDC}")
    print(f"   Device EUI: {device_eui}")
    print(f"   Centro: {lat:.6f}, {lng:.6f}")
    print(f"   Radio: {radius} metros")
    print(f"   Grupo: {group_id}\n")
    
    # Preparar payload
    payload = struct.pack('<B', 1)  # Tipo 1 = círculo
    payload += struct.pack('<f', float(lat))
    payload += struct.pack('<f', float(lng))
    payload += struct.pack('<H', int(radius))
    
    # Agregar group_id
    if group_id:
        payload += group_id.encode('utf-8')[:15]
    
    # Codificar en base64
    payload_b64 = base64.b64encode(payload).decode('utf-8')
    
    print(f"📦 Payload generado:")
    print(f"   Tamaño: {len(payload)} bytes")
    print(f"   Hex: {payload.hex()}")
    print(f"   Base64: {payload_b64}\n")
    
    # Preparar request para ChirpStack v3
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
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Enviar request
    print(f"📡 Enviando a ChirpStack...")
    print(f"   URL: {url}")
    
    try:
        response = requests.post(url, json=downlink_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201, 202]:
            print(f"{Colors.OKGREEN}✅ ÉXITO: Downlink enviado correctamente{Colors.ENDC}")
            print(f"   Respuesta: {response.text}\n")
            return True
        else:
            print(f"{Colors.FAIL}❌ ERROR: Código {response.status_code}{Colors.ENDC}")
            print(f"   Mensaje: {response.text}\n")
            
            # Intentar parsear error
            try:
                error_data = response.json()
                if 'error' in error_data:
                    print(f"   Detalle: {error_data['error']}")
            except:
                pass
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"{Colors.FAIL}❌ ERROR: No se puede conectar con ChirpStack{Colors.ENDC}")
        print(f"   Verifica que ChirpStack esté corriendo en {CHIRPSTACK_API_URL}\n")
        return False
    except requests.exceptions.Timeout:
        print(f"{Colors.FAIL}❌ ERROR: Timeout esperando respuesta{Colors.ENDC}\n")
        return False
    except Exception as e:
        print(f"{Colors.FAIL}❌ ERROR: {str(e)}{Colors.ENDC}\n")
        return False

def check_device_queue(device_eui: str):
    """Verifica la cola de downlinks del dispositivo"""
    
    print(f"{Colors.OKBLUE}📋 Verificando cola de downlinks...{Colors.ENDC}")
    
    url = f"{CHIRPSTACK_API_URL}/api/devices/{device_eui}/queue"
    headers = {
        "Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            if items:
                print(f"{Colors.WARNING}   📦 Hay {len(items)} downlinks en cola{Colors.ENDC}")
                for i, item in enumerate(items, 1):
                    print(f"      {i}. Puerto {item.get('fPort', 'N/A')} - "
                          f"Confirmado: {item.get('confirmed', False)}")
            else:
                print(f"{Colors.OKGREEN}   ✓ Cola vacía (el downlink se enviará en el próximo uplink){Colors.ENDC}")
            return True
        else:
            print(f"{Colors.FAIL}   ❌ Error obteniendo cola: {response.status_code}{Colors.ENDC}")
            return False
    except Exception as e:
        print(f"{Colors.FAIL}   ❌ Error: {str(e)}{Colors.ENDC}")
        return False

def get_device_info(device_eui: str):
    """Obtiene información del dispositivo"""
    
    print(f"{Colors.OKBLUE}🔍 Obteniendo información del dispositivo...{Colors.ENDC}")
    
    url = f"{CHIRPSTACK_API_URL}/api/devices/{device_eui}"
    headers = {
        "Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            device = data.get('device', {})
            
            print(f"   Nombre: {device.get('name', 'N/A')}")
            print(f"   Descripción: {device.get('description', 'N/A')}")
            
            # Obtener último seen
            last_seen = data.get('lastSeenAt', 'Nunca')
            if last_seen != 'Nunca':
                print(f"   Última actividad: {last_seen}")
            else:
                print(f"{Colors.WARNING}   ⚠️ El dispositivo nunca se ha conectado{Colors.ENDC}")
            
            return True
        elif response.status_code == 404:
            print(f"{Colors.FAIL}   ❌ Dispositivo no encontrado en ChirpStack{Colors.ENDC}")
            print(f"   Verifica que el Device EUI sea correcto: {device_eui}")
            return False
        else:
            print(f"{Colors.FAIL}   ❌ Error: {response.status_code}{Colors.ENDC}")
            return False
    except Exception as e:
        print(f"{Colors.FAIL}   ❌ Error: {str(e)}{Colors.ENDC}")
        return False

def main():
    """Función principal"""
    
    parser = argparse.ArgumentParser(description='Enviar geocerca a dispositivo ESP32 vía ChirpStack')
    parser.add_argument('device_eui', help='Device EUI del dispositivo (16 caracteres hex)')
    parser.add_argument('--lat', type=float, default=-33.4489, help='Latitud del centro (default: -33.4489)')
    parser.add_argument('--lng', type=float, default=-70.6693, help='Longitud del centro (default: -70.6693)')
    parser.add_argument('--radius', type=int, default=100, help='Radio en metros (default: 100)')
    parser.add_argument('--group', default='test', help='ID del grupo (default: test)')
    parser.add_argument('--check-only', action='store_true', help='Solo verificar dispositivo sin enviar')
    
    args = parser.parse_args()
    
    # Validar Device EUI
    device_eui = args.device_eui.replace(':', '').replace('-', '').lower()
    if len(device_eui) != 16:
        print(f"{Colors.FAIL}❌ Device EUI debe tener 16 caracteres hexadecimales{Colors.ENDC}")
        sys.exit(1)
    
    print_header()
    
    # Verificar dispositivo
    if not get_device_info(device_eui):
        print(f"\n{Colors.FAIL}❌ No se pudo obtener información del dispositivo{Colors.ENDC}")
        print("Verifica que:")
        print("1. El Device EUI sea correcto")
        print("2. El dispositivo esté registrado en ChirpStack")
        print("3. ChirpStack esté funcionando")
        sys.exit(1)
    
    print()
    
    # Verificar cola
    check_device_queue(device_eui)
    print()
    
    # Si es solo verificación, terminar aquí
    if args.check_only:
        print(f"{Colors.OKGREEN}✅ Verificación completada{Colors.ENDC}")
        sys.exit(0)
    
    # Enviar geocerca
    success = send_circle_geofence(
        device_eui=device_eui,
        lat=args.lat,
        lng=args.lng,
        radius=args.radius,
        group_id=args.group
    )
    
    if success:
        print(f"{Colors.OKGREEN}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}✅ DOWNLINK ENVIADO EXITOSAMENTE{Colors.ENDC}")
        print(f"{Colors.OKGREEN}{'='*60}{Colors.ENDC}")
        print("\n📝 Próximos pasos:")
        print("1. Espera a que el dispositivo envíe un uplink")
        print("2. El downlink se entregará en la ventana RX después del uplink")
        print("3. Verifica en el monitor serial del ESP32:")
        print("   '🌐 GEOCERCA RECIBIDA vía LoRaWAN'")
        print("4. La geocerca se guardará automáticamente en la memoria del ESP32")
        print()
    else:
        print(f"{Colors.FAIL}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}❌ ERROR AL ENVIAR DOWNLINK{Colors.ENDC}")
        print(f"{Colors.FAIL}{'='*60}{Colors.ENDC}")
        print("\nPosibles causas:")
        print("1. Device EUI incorrecto")
        print("2. Token de API inválido o expirado")
        print("3. ChirpStack no está funcionando")
        print("4. El dispositivo no está registrado")
        print()
        sys.exit(1)

if __name__ == "__main__":
    main()
