"""
Compresor de coordenadas para geocercas poligonales en AU915 (Chile)
Optimizado para LoRaWAN con límites de payload restrictivos
"""

import struct
import base64
import math
from typing import List, Dict, Union, Tuple
import logging

# Configurar logging
logger = logging.getLogger(__name__)

# ============================================================================
# LÍMITES DE PAYLOAD PARA AU915 (REGIÓN CHILE)
# ============================================================================

AU915_PAYLOAD_LIMITS = {
    # Spreading Factor : Max Payload Bytes
    'SF7': 222,    # Mejor caso - alta velocidad
    'SF8': 222,    # Buena velocidad
    'SF9': 115,    # Velocidad media
    'SF10': 51,    # Velocidad baja - peor caso común
    'SF11': 51,    # Muy baja velocidad
    'SF12': 51     # Mínima velocidad - peor caso absoluto
}

# Para diseño conservador, usar SF10 como referencia (51 bytes)
DEFAULT_MAX_PAYLOAD = AU915_PAYLOAD_LIMITS['SF10']

# ============================================================================
# CLASE PARA COMPRESIÓN DE COORDENADAS AU915
# ============================================================================

class AU915CoordinateCompressor:
    """
    Compresor de coordenadas para región AU915 (Chile)
    Reduce payload de polígonos de ~82 bytes a ~25-35 bytes
    """
    
    def __init__(self, max_payload_size: int = DEFAULT_MAX_PAYLOAD):
        self.max_payload_size = max_payload_size
        
        # Factor de escala optimizado para coordenadas de Chile
        # Chile: latitud aproximada -17° a -56°, longitud -67° a -75°
        # 1 grado ≈ 111,000 metros en el ecuador
        # Para Chile (latitud media ~-33°), factor de corrección ≈ 0.84
        self.lat_scale_factor = 111000.0  # metros por grado de latitud
        self.lng_scale_factor = 93000.0   # metros por grado de longitud (ajustado para Chile)
        
        logger.info(f"🇨🇱 Compresor AU915 inicializado - Límite: {max_payload_size} bytes")
    
    def calculate_reference_point(self, coordinates: List[Dict]) -> Tuple[float, float]:
        """
        Calcula el punto de referencia óptimo (centroide) para minimizar offsets
        """
        ref_lat = sum(coord['lat'] for coord in coordinates) / len(coordinates)
        ref_lng = sum(coord['lng'] for coord in coordinates) / len(coordinates)
        
        logger.info(f"📍 Punto de referencia calculado: {ref_lat:.6f}, {ref_lng:.6f}")
        return ref_lat, ref_lng
    
    def validate_coordinates_for_chile(self, coordinates: List[Dict]) -> bool:
        """
        Valida que las coordenadas estén dentro del rango válido para Chile
        """
        chile_bounds = {
            'min_lat': -56.5,  # Cabo de Hornos
            'max_lat': -17.5,  # Frontera con Perú
            'min_lng': -75.5,  # Océano Pacífico
            'max_lng': -66.5   # Frontera con Argentina
        }
        
        for i, coord in enumerate(coordinates):
            lat, lng = coord['lat'], coord['lng']
            
            if not (chile_bounds['min_lat'] <= lat <= chile_bounds['max_lat']):
                logger.error(f"❌ Punto {i+1}: Latitud {lat} fuera de rango de Chile")
                return False
                
            if not (chile_bounds['min_lng'] <= lng <= chile_bounds['max_lng']):
                logger.error(f"❌ Punto {i+1}: Longitud {lng} fuera de rango de Chile")
                return False
        
        return True
    
    def compress_polygon_coordinates(self, coordinates: List[Dict], 
                                   group_id: str = "backend") -> bytearray:
        """
        ESTRATEGIA 1: Compresión de coordenadas con punto de referencia
        Optimizada para AU915 y coordenadas de Chile
        """
        
        # Validar entrada
        if not self.validate_coordinates_for_chile(coordinates):
            raise ValueError("Coordenadas fuera del rango válido para Chile")
        
        # Limitar número de puntos según capacidad del payload
        # Estimación: 9 bytes header + 4 bytes por punto + group_id
        max_points_possible = (self.max_payload_size - 9 - len(group_id)) // 4
        num_points = min(len(coordinates), max_points_possible, 10)  # También limitar por ESP32
        
        if num_points < len(coordinates):
            logger.warning(f"⚠️  Limitando polígono de {len(coordinates)} a {num_points} puntos")
        
        logger.info(f"🔄 Comprimiendo {num_points} puntos para AU915")
        
        # Calcular punto de referencia (centroide)
        ref_lat, ref_lng = self.calculate_reference_point(coordinates[:num_points])
        
        # Construir payload comprimido
        payload = bytearray()
        
        # Header: tipo polígono comprimido (1 byte)
        payload.append(2)  # Tipo 2 = polígono comprimido
        
        # Punto de referencia (8 bytes)
        payload.extend(struct.pack('<f', ref_lat))   # 4 bytes
        payload.extend(struct.pack('<f', ref_lng))   # 4 bytes
        
        # Número de puntos (1 byte)
        payload.append(num_points)
        
        # Procesar cada punto
        max_offset_error = 0
        for i in range(num_points):
            coord = coordinates[i]
            
            # Calcular offsets relativos en metros
            lat_offset_meters = (coord['lat'] - ref_lat) * self.lat_scale_factor
            lng_offset_meters = (coord['lng'] - ref_lng) * self.lng_scale_factor
            
            # Convertir a int16 (rango: -32,767 to 32,767 metros)
            lat_offset_int = max(-32767, min(32767, int(round(lat_offset_meters))))
            lng_offset_int = max(-32767, min(32767, int(round(lng_offset_meters))))
            
            # Calcular error de quantización para logging
            lat_error = abs(lat_offset_meters - lat_offset_int)
            lng_error = abs(lng_offset_meters - lng_offset_int)
            max_offset_error = max(max_offset_error, lat_error, lng_error)
            
            # Agregar offsets al payload (4 bytes por punto)
            payload.extend(struct.pack('<h', lat_offset_int))  # 2 bytes
            payload.extend(struct.pack('<h', lng_offset_int))  # 2 bytes
            
            logger.info(f"   Punto {i+1}: offset_lat={lat_offset_int}m, offset_lng={lng_offset_int}m")
        
        # Agregar group_id si hay espacio
        group_bytes_available = self.max_payload_size - len(payload)
        if group_id and group_bytes_available > 0:
            group_bytes = group_id[:group_bytes_available].encode('ascii')
            payload.extend(group_bytes)
        
        # Logging de resultados
        logger.info(f"✅ Compresión completada:")
        logger.info(f"   Tamaño original estimado: {2 + len(coordinates) * 8} bytes")
        logger.info(f"   Tamaño comprimido: {len(payload)} bytes")
        logger.info(f"   Reducción: {((2 + len(coordinates) * 8 - len(payload)) / (2 + len(coordinates) * 8) * 100):.1f}%")
        logger.info(f"   Error máximo de quantización: {max_offset_error:.1f} metros")
        logger.info(f"   Dentro del límite AU915: {'✅' if len(payload) <= self.max_payload_size else '❌'}")
        
        return payload
    
    def estimate_compression_ratio(self, num_points: int) -> Dict[str, float]:
        """
        Estima la eficiencia de compresión para diferentes números de puntos
        """
        original_size = 2 + (num_points * 8)  # tipo + num_points + coordenadas
        compressed_size = 9 + (num_points * 4)  # header + ref_point + offsets
        
        return {
            'original_bytes': original_size,
            'compressed_bytes': compressed_size,
            'reduction_percent': ((original_size - compressed_size) / original_size) * 100,
            'fits_in_sf10': compressed_size <= AU915_PAYLOAD_LIMITS['SF10'],
            'fits_in_sf9': compressed_size <= AU915_PAYLOAD_LIMITS['SF9']
        }

# ============================================================================
# FUNCIONES DE UTILIDAD PARA ANÁLISIS
# ============================================================================

def analyze_compression_for_polygon(coordinates: List[Dict], 
                                  spreading_factors: List[str] = None) -> Dict[str, any]:
    """
    Analiza la eficiencia de compresión para un polígono específico
    Retorna un diccionario con los resultados del análisis
    """
    if spreading_factors is None:
        spreading_factors = ['SF7', 'SF8', 'SF9', 'SF10']
    
    # Calcular tamaño original
    original_size = 2 + len(coordinates) * 8
    
    results = {
        'original_size': original_size,
        'polygon_points': len(coordinates),
        'analysis_by_sf': {}
    }
    
    for sf in spreading_factors:
        max_payload = AU915_PAYLOAD_LIMITS[sf]
        compressor = AU915CoordinateCompressor(max_payload)
        
        sf_result = {
            'max_payload': max_payload,
            'original_fits': original_size <= max_payload,
            'compression_needed': original_size > max_payload
        }
        
        if original_size > max_payload:
            try:
                compressed_payload = compressor.compress_polygon_coordinates(coordinates, "test")
                compression_stats = compressor.estimate_compression_ratio(len(coordinates))
                
                sf_result.update({
                    'compressed_size': len(compressed_payload),
                    'reduction_percent': compression_stats['reduction_percent'],
                    'compressed_fits': len(compressed_payload) <= max_payload,
                    'compression_success': True
                })
                
            except Exception as e:
                sf_result.update({
                    'compression_success': False,
                    'error': str(e)
                })
        
        results['analysis_by_sf'][sf] = sf_result
    
    return results

def get_optimal_spreading_factor(coordinates: List[Dict]) -> str:
    """
    Determina el spreading factor óptimo para un polígono dado
    Retorna el SF más rápido que puede manejar el polígono
    """
    analysis = analyze_compression_for_polygon(coordinates)
    
    # Orden de preferencia (más rápido primero)
    sf_preference = ['SF7', 'SF8', 'SF9', 'SF10', 'SF11', 'SF12']
    
    for sf in sf_preference:
        if sf in analysis['analysis_by_sf']:
            sf_data = analysis['analysis_by_sf'][sf]
            
            # Si el payload original cabe, usar ese SF
            if sf_data['original_fits']:
                return sf
            
            # Si la compresión funciona y cabe, usar ese SF
            if (sf_data.get('compression_success', False) and 
                sf_data.get('compressed_fits', False)):
                return sf
    
    # Si nada funciona, retornar SF10 por defecto
    return 'SF10'

# ============================================================================
# FUNCIÓN PARA CREAR PAYLOAD COMPRIMIDO (INTERFAZ SIMPLE)
# ============================================================================

def create_compressed_polygon_payload(coordinates: List[Dict], 
                                    group_id: str = "backend",
                                    spreading_factor: str = "SF10") -> bytearray:
    """
    Interfaz simple para crear payload comprimido
    
    Args:
        coordinates: Lista de coordenadas [{'lat': float, 'lng': float}, ...]
        group_id: Identificador del grupo
        spreading_factor: SF a usar ('SF7', 'SF8', 'SF9', 'SF10', etc.)
    
    Returns:
        bytearray: Payload comprimido listo para enviar
    
    Raises:
        ValueError: Si las coordenadas son inválidas o no se puede comprimir
    """
    max_payload = AU915_PAYLOAD_LIMITS.get(spreading_factor, DEFAULT_MAX_PAYLOAD)
    compressor = AU915CoordinateCompressor(max_payload)
    
    return compressor.compress_polygon_coordinates(coordinates, group_id)

# ============================================================================
# EXPORTAR CLASES Y FUNCIONES PRINCIPALES
# ============================================================================

__all__ = [
    'AU915CoordinateCompressor',
    'AU915_PAYLOAD_LIMITS',
    'DEFAULT_MAX_PAYLOAD',
    'analyze_compression_for_polygon',
    'get_optimal_spreading_factor',
    'create_compressed_polygon_payload'
]