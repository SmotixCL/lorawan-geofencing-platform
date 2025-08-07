// Lógica para Geocercas y Dibujo en el Mapa
let drawnGeometry = null;

function initializeDrawingTools(mapInstance) {
    if (!mapInstance) return;

    drawControl = new L.Control.Draw({
        edit: {
            featureGroup: currentGeofencesLayer,
            poly: { allowIntersection: false }
        },
        draw: {
            polygon: {
                allowIntersection: false,
                showArea: true,
                shapeOptions: { color: '#3498db', weight: 2 }
            },
            circle: {
                shapeOptions: { color: '#3498db', weight: 2 }
            },
            rectangle: false,
            marker: false,
            polyline: false,
            circlemarker: false
        }
    });

    mapInstance.on(L.Draw.Event.CREATED, function(event) {
        const layer = event.layer;
        const type = event.layerType;
        drawnItems.clearLayers();
        drawnItems.addLayer(layer);
        drawnGeometry = layer.toGeoJSON();
        if (type === 'circle') {
            drawnGeometry.properties.radius = layer.getRadius();
        }
        showGeofenceModal(null, drawnGeometry, type);
    });

    mapInstance.on(L.Draw.Event.EDITED, function(event) {
        event.layers.eachLayer(function(layer) {
            if (layer.options && layer.options.geofenceId) {
                const geofenceId = layer.options.geofenceId;
                const updatedGeoJSON = layer.toGeoJSON();
                let updatedRadius = (layer instanceof L.Circle) ? layer.getRadius() : null;
                const originalGeofence = allGeofences.find(gf => gf.id === geofenceId);
                if (originalGeofence) {
                    updateGeofenceInDB(geofenceId, originalGeofence, updatedGeoJSON, updatedRadius);
                }
            }
        });
    });

    mapInstance.on(L.Draw.Event.DELETED, function(event) {
        event.layers.eachLayer(function(layer) {
            if (layer.options && layer.options.geofenceId) {
                deleteGeofence(layer.options.geofenceId);
            }
        });
    });
}

function renderGeofencesOnMap() {
    currentGeofencesLayer.clearLayers();
    allGeofences.forEach(gf => {
        let layer;
        const options = { geofenceId: gf.id, color: '#e74c3c', weight: 2, fillOpacity: 0.2 };
        if (gf.geofence_type === 'polygon' && gf.coordinates && Array.isArray(gf.coordinates)) {
            layer = L.polygon(gf.coordinates.map(p => [p.lat, p.lng]), options);
        } else if (gf.geofence_type === 'circle' && gf.coordinates) {
            layer = L.circle([gf.coordinates.lat, gf.coordinates.lng], { ...options, radius: gf.radius });
        }
        if (layer) {
            layer.bindPopup(`<b>${gf.name}</b>`);
            currentGeofencesLayer.addLayer(layer);
        }
    });
}

function zoomToGeofence(geofenceId) {
    let layerToZoom = null;
    currentGeofencesLayer.eachLayer(layer => {
        if (layer.options.geofenceId === geofenceId) layerToZoom = layer;
    });
    if (layerToZoom) {
        map.fitBounds(layerToZoom.getBounds());
        layerToZoom.openPopup();
    }
}

function toggleGeofenceVisibility(geofenceId, checkbox) {
    let layerToToggle = null;
    currentGeofencesLayer.eachLayer(layer => {
        if (layer.options.geofenceId === geofenceId) layerToToggle = layer;
    });
    if (!layerToToggle) return;
    if (checkbox.checked) {
        if (!map.hasLayer(layerToToggle)) map.addLayer(layerToToggle);
    } else {
        if (map.hasLayer(layerToToggle)) map.removeLayer(layerToToggle);
    }
}

function showGeofenceModal(geofence = null, geometry = null, detectedType = null) {
    const geofenceIdEl = document.getElementById("geofenceId");
    const geofenceNameEl = document.getElementById("geofenceName");
    const geofenceGroupEl = document.getElementById("geofenceGroup");
    const geofenceTypeEl = document.getElementById("geofenceType");
    const geofenceRadiusEl = document.getElementById("geofenceRadius");
    
    geofenceGroupEl.innerHTML = "";
    allGroups.forEach(g => geofenceGroupEl.appendChild(new Option(g.name, g.id)));

    if (geofence) { // Modo Edición
        geofenceIdEl.value = geofence.id;
        geofenceNameEl.value = geofence.name;
        geofenceGroupEl.value = geofence.group_id;
        geofenceTypeEl.value = geofence.geofence_type;
        geofenceRadiusEl.value = geofence.radius || '';
        drawnGeometry = geofence.coordinates; // Formato API
    } else { // Modo Creación
        geofenceIdEl.value = '';
        geofenceNameEl.value = '';
        geofenceGroupEl.value = allGroups.length > 0 ? allGroups[0].id : '';
        geofenceTypeEl.value = detectedType || 'polygon';
        geofenceRadiusEl.value = (detectedType === 'circle' && geometry?.properties) ? geometry.properties.radius : '';
        drawnGeometry = geometry; // Formato GeoJSON
    }
    geofenceTypeEl.disabled = !!(geofence || detectedType);
    toggleGeofenceRadius();
    showModal("geofenceModal");
}

function toggleGeofenceRadius() {
    const type = document.getElementById("geofenceType").value;
    document.getElementById("geofenceRadiusGroup").style.display = (type === 'circle') ? 'block' : 'none';
}

async function createGeofence() {
    const geofenceId = document.getElementById("geofenceId").value;
    const name = document.getElementById("geofenceName").value;
    const group_id = parseInt(document.getElementById("geofenceGroup").value);
    const geofence_type = document.getElementById("geofenceType").value;
    const radius = parseFloat(document.getElementById("geofenceRadius").value);

    if (!name.trim() || !group_id) return alert("El nombre y el grupo son obligatorios.");
    if (!drawnGeometry) return alert("Dibuja la geocerca en el mapa antes de guardar.");

    let coordinates_payload;

    if (geofenceId) { // MODO EDICIÓN: drawnGeometry es formato API
        if (geofence_type === 'polygon') {
            coordinates_payload = drawnGeometry; // Ya está en formato [{lat, lng}, ...]
        } else { // Círculo
            coordinates_payload = { lat: drawnGeometry.lat, lng: drawnGeometry.lng, radius: radius };
        }
    } else { // MODO CREACIÓN: drawnGeometry es formato GeoJSON
        const geometry_source = drawnGeometry.geometry;
        if (geofence_type === 'polygon') {
            coordinates_payload = geometry_source.coordinates[0].map(c => ({ lat: c[1], lng: c[0] }));
        } else { // Círculo
             if (geofence_type === 'circle' && (isNaN(radius) || radius <= 0)) {
                return alert("El radio del círculo debe ser un número positivo.");
            }
            coordinates_payload = { lat: geometry_source.coordinates[1], lng: geometry_source.coordinates[0], radius: radius };
        }
    }

    const payload = { group_id, name, geofence_type, coordinates: coordinates_payload, active: true };
    const url = geofenceId ? `${API_BASE_URL}/geofences/${geofenceId}` : `${API_BASE_URL}/geofences/`;
    const method = geofenceId ? 'PUT' : 'POST';

    try {
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail);
        }
        closeModal("geofenceModal");
        await fetchAllDataAndRender();
    } catch (error) {
        alert(error.message);
    }
}

function editGeofence(geofenceId) {
    const geofenceToEdit = allGeofences.find(gf => gf.id === geofenceId);
    if (geofenceToEdit) showGeofenceModal(geofenceToEdit);
}

async function updateGeofenceInDB(geofenceId, originalGeofence, updatedGeoJSON, updatedRadius) {
    let coordinates_payload;
    if (originalGeofence.geofence_type === 'polygon') {
        coordinates_payload = updatedGeoJSON.geometry.coordinates[0].map(c => ({ lat: c[1], lng: c[0] }));
    } else {
        coordinates_payload = { lat: updatedGeoJSON.geometry.coordinates[1], lng: updatedGeoJSON.geometry.coordinates[0], radius: updatedRadius };
    }
    const payload = { ...originalGeofence, coordinates: coordinates_payload };
    try {
        await fetch(`${API_BASE_URL}/geofences/${geofenceId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        await fetchAllDataAndRender();
    } catch (error) {
        console.error("Error en actualización desde mapa:", error);
    }
}

async function deleteGeofence(geofenceId) {
    if (!confirm("¿Estás seguro de que quieres eliminar esta geocerca?")) return;
    try {
        const response = await fetch(`${API_BASE_URL}/geofences/${geofenceId}`, {
            method: 'DELETE'
        });
        if (!response.ok && response.status !== 204) {
            throw new Error("Fallo al eliminar la geocerca.");
        }
        await fetchAllDataAndRender();
    } catch (error) {
        console.error("Error al eliminar geocerca:", error);
        alert(error.message);
    }
}
