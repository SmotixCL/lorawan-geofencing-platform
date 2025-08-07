// Lógica Principal del Frontend
let map;
const API_BASE_URL = '/api/v1';

// Almacenes de datos locales
let allDevices = [];
let allGroups = [];
let allGeofences = [];

// Capas del mapa
let drawnItems;
let currentGeofencesLayer;
let historyPathLayer;

// Controles del mapa
let drawControl;

/**
 * Evento que se dispara cuando el DOM está completamente cargado.
 * Es el punto de entrada de la aplicación.
 */
document.addEventListener('DOMContentLoaded', initializeApp);

/**
 * Inicializa la aplicación: el mapa, las capas y la carga inicial de datos.
 */
function initializeApp() {
    initializeMap();

    drawnItems = new L.FeatureGroup();
    currentGeofencesLayer = new L.FeatureGroup();
    historyPathLayer = new L.FeatureGroup();

    map.addLayer(drawnItems);
    map.addLayer(currentGeofencesLayer);
    map.addLayer(historyPathLayer);

    if (typeof initializeDrawingTools === 'function') {
        initializeDrawingTools(map);
    } else {
        console.error("Error: initializeDrawingTools no está definida. Asegúrate de que geofences.js se carga correctamente.");
    }

    fetchAllDataAndRender();
    setInterval(fetchAllDataAndRender, 15000);

    switchTab('devices');
}

/**
 * Inicializa la instancia del mapa Leaflet.
 */
function initializeMap() {
    if (map) return;
    map = L.map('map').setView([-34.6, -58.38], 4);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
}

/**
 * Carga todos los datos (dispositivos, grupos, geocercas) desde el backend.
 */
async function fetchAllDataAndRender() {
    try {
        const [devicesRes, groupsRes, geofencesRes] = await Promise.all([
            fetch(`${API_BASE_URL}/devices/`),
            fetch(`${API_BASE_URL}/groups/`),
            fetch(`${API_BASE_URL}/geofences/`)
        ]);

        if (!devicesRes.ok || !groupsRes.ok || !geofencesRes.ok) {
            throw new Error(`Fallo al cargar datos del API.`);
        }

        allDevices = await devicesRes.json();
        allGroups = await groupsRes.json();
        allGeofences = await geofencesRes.json();

        updateDeviceMarkers();
        renderAllLists();

    } catch (error) {
        console.error("Error crítico cargando datos:", error);
    }
}

/**
 * Obtiene y dibuja el historial de posiciones de un dispositivo.
 */
async function fetchDeviceHistory(deviceId) {
    historyPathLayer.clearLayers();
    try {
        const response = await fetch(`${API_BASE_URL}/devices/${deviceId}/positions`);
        if (!response.ok) {
            throw new Error('No se pudo obtener el historial del dispositivo.');
        }
        const positions = await response.json();

        if (positions.length === 0) {
            alert("Este dispositivo no tiene historial de posiciones.");
            return;
        }

        const latlngs = positions.map(p => [p.latitude, p.longitude]);

        const polyline = L.polyline(latlngs, {
            color: 'rgba(255, 87, 34, 0.8)',
            weight: 3,
            isHistoryPath: true
        }).addTo(historyPathLayer);

        L.marker(latlngs[0], { title: `Fin: ${new Date(positions[0].time).toLocaleString()}`, isHistoryMarker: true }).addTo(historyPathLayer);
        L.marker(latlngs[latlngs.length - 1], { title: `Inicio: ${new Date(positions[positions.length - 1].time).toLocaleString()}`, isHistoryMarker: true }).addTo(historyPathLayer);

        map.fitBounds(polyline.getBounds());
    } catch (error) {
        console.error("Error al obtener historial:", error);
        alert("Error al cargar el historial del dispositivo.");
    }
}


/**
 * Cambia la pestaña activa en la barra lateral.
 */
function switchTab(tabName) {
    document.querySelectorAll('.tab-content, .sidebar-tab').forEach(el => el.classList.remove('active'));

    document.getElementById(`${tabName}Tab`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');

    historyPathLayer.clearLayers();
    drawnItems.clearLayers();
    if (typeof drawnGeometry !== 'undefined') drawnGeometry = null;

    if (tabName === 'geofences') {
        if (drawControl) map.addControl(drawControl);
        if (typeof renderGeofencesOnMap === 'function') {
            renderGeofencesOnMap();
        }
    } else {
        if (drawControl) map.removeControl(drawControl);
        currentGeofencesLayer.clearLayers();
    }

    renderAllLists();
}


/**
 * Llama a todas las funciones de renderizado de listas.
 */
function renderAllLists() {
    renderDeviceList();
    renderGroupList();
    renderGeofenceList();
}

/**
 * Renderiza la lista de dispositivos.
 */
function renderDeviceList() {
    const listEl = document.getElementById('deviceList');
    listEl.innerHTML = '';

    if (allDevices.length === 0) {
        listEl.innerHTML = '<div class="device-card"><p>No hay dispositivos registrados.</p></div>';
        return;
    }

    allDevices.forEach(device => {
        const card = document.createElement('div');
        card.className = "device-card";
        let statusClass = 'status-unknown-geofence';
        if (device.geofence_status === 'Dentro') statusClass = 'status-inside-geofence';
        else if (device.geofence_status === 'Fuera') statusClass = 'status-outside-geofence';
        const groupNames = device.group_names.join(', ') || 'Ninguno';
        const positionText = device.current_latitude !== null ?
            `<p><i class="fas fa-map-marked-alt"></i> Última Posición: ${device.current_latitude.toFixed(4)}, ${device.current_longitude.toFixed(4)}</p>` :
            '<p><i class="fas fa-map-marked-alt"></i> Sin posición reciente</p>';

        card.innerHTML = `
            <div class="device-header ${statusClass}">
                <h3><i class="fas fa-microchip"></i> ${device.device_name || 'Sin Nombre'}</h3>
                <div class="device-actions">
                    <button class="btn btn-sm btn-info" title="Ver Historial" onclick="fetchDeviceHistory(${device.id})"><i class="fas fa-history"></i></button>
                    <button class="btn btn-sm btn-warning" title="Editar Nombre" onclick="editDevice(${device.id})"><i class="fas fa-edit"></i></button>
                    <button class="btn btn-sm btn-danger" title="Eliminar Dispositivo" onclick="deleteDevice(${device.id})"><i class="fas fa-trash"></i></button>
                </div>
            </div>
            <div class="device-details">
                <p><i class="fas fa-id-card"></i> EUI: ${device.dev_eui}</p>
                <p><i class="fas fa-users"></i> Grupo(s): ${groupNames}</p>
                <p><i class="fas fa-draw-polygon"></i> Geocerca: ${device.associated_geofence_name || 'N/A'}</p>
                <p><i class="fas fa-map-marker-alt"></i> Estado: <b>${device.geofence_status || 'No Verificado'}</b></p>
                ${positionText}
            </div>`;
        listEl.appendChild(card);
    });
}

/**
 * Renderiza la lista de grupos.
 */
function renderGroupList() {
    const listEl = document.getElementById("groupList");
    listEl.innerHTML = '';

    if (allGroups.length === 0) {
        listEl.innerHTML = '<div class="group-card"><p>No hay grupos creados.</p></div>';
        return;
    }

    allGroups.forEach(group => {
        const card = document.createElement('div');
        card.className = "group-card";
        const deviceCount = group.devices ? group.devices.length : 0;
        const deviceSummary = deviceCount === 1 ? '1 Dispositivo' : `${deviceCount} Dispositivos`;
        const associatedGeofence = allGeofences.find(gf => gf.group_id === group.id);
        const geofenceInfo = associatedGeofence ?
            `<p><i class="fas fa-draw-polygon"></i> Geocerca: ${associatedGeofence.name}</p>` :
            '<p><i class="fas fa-draw-polygon"></i> Sin geocerca asignada</p>';

        card.innerHTML = `
            <div class="group-header">
                <h3><i class="fas fa-users"></i> ${group.name}</h3>
                <div class="group-actions">
                    <button class="btn btn-sm btn-info" title="Ver Detalles" onclick="showGroupDetailsModal(${group.id})"><i class="fas fa-info-circle"></i></button>
                    <button class="btn btn-sm btn-warning" title="Editar Grupo" onclick="editGroup(${group.id})"><i class="fas fa-edit"></i></button>
                    <button class="btn btn-sm btn-danger" title="Eliminar Grupo" onclick="deleteGroup(${group.id})"><i class="fas fa-trash"></i></button>
                </div>
            </div>
            <div class="group-details">
                <p><b>Descripción:</b> ${group.description || 'N/A'}</p>
                <p><b><i class="fas fa-microchip"></i></b> ${deviceSummary}</p>
                ${geofenceInfo}
            </div>`;
        listEl.appendChild(card);
    });
}

/**
 * Renderiza la lista de geocercas.
 */
function renderGeofenceList() {
    const listEl = document.getElementById("geofenceList");
    listEl.innerHTML = '';

    if (allGeofences.length === 0) {
        listEl.innerHTML = '<div class="geofence-card"><p>No hay geocercas creadas.</p></div>';
        return;
    }

    allGeofences.forEach(gf => {
        const card = document.createElement('div');
        card.className = "geofence-card";
        const groupName = allGroups.find(g => g.id === gf.group_id)?.name || 'Desconocido';
        const geometryType = gf.geofence_type === 'polygon' ? 'Polígono' : 'Círculo';
        const radiusInfo = gf.geofence_type === 'circle' && gf.radius ? `(Radio: ${gf.radius}m)` : '';
        let isLayerVisible = false;
        if (currentGeofencesLayer) {
            currentGeofencesLayer.eachLayer(layer => {
                if (layer.options.geofenceId === gf.id && map.hasLayer(layer)) {
                    isLayerVisible = true;
                }
            });
        }
        card.innerHTML = `
            <div class="geofence-header">
                <h3><i class="fas fa-draw-polygon"></i> ${gf.name}</h3>
                <div class="geofence-actions">
                    <button class="btn btn-sm btn-info" title="Centrar en Geocerca" onclick="zoomToGeofence(${gf.id})"><i class="fas fa-search-plus"></i></button>
                    <button class="btn btn-sm btn-warning" title="Editar Geocerca" onclick="editGeofence(${gf.id})"><i class="fas fa-edit"></i></button>
                    <button class="btn btn-sm btn-danger" title="Eliminar Geocerca" onclick="deleteGeofence(${gf.id})"><i class="fas fa-trash"></i></button>
                    <label class="switch" title="Mostrar/Ocultar en mapa">
                        <input type="checkbox" ${isLayerVisible ? 'checked' : ''} onchange="toggleGeofenceVisibility(${gf.id}, this)">
                        <span class="slider"></span>
                    </label>
                </div>
            </div>
            <div class="geofence-details">
                <p><i class="fas fa-users"></i> Grupo: ${groupName}</p>
                <p><i class="fas fa-vector-square"></i> Tipo: ${geometryType} ${radiusInfo}</p>
                <p><i class="fas fa-power-off"></i> Estado: ${gf.active ? 'Activa' : 'Inactiva'}</p>
            </div>`;
        listEl.appendChild(card);
    });

    renderGeofencesOnMapInitialState();
}

/**
 * Asegura que las geocercas marcadas como visibles se muestren al cargar la lista.
 */
function renderGeofencesOnMapInitialState() {
    if (typeof renderGeofencesOnMap === 'function') {
        renderGeofencesOnMap();
    }
    const geofenceCards = document.querySelectorAll('#geofenceList .geofence-card');
    geofenceCards.forEach(card => {
        const checkbox = card.querySelector('input[type="checkbox"]');
        const geofenceIdMatch = checkbox.onchange.toString().match(/\((\d+)/);
        if (!geofenceIdMatch) return;
        const geofenceId = parseInt(geofenceIdMatch[1]);
        if (!checkbox.checked) {
            currentGeofencesLayer.eachLayer(layer => {
                if (layer.options.geofenceId === geofenceId && map.hasLayer(layer)) {
                    map.removeLayer(layer);
                }
            });
        }
    });
}


/**
 * Dibuja los marcadores de dispositivos en el mapa.
 */
function updateDeviceMarkers() {
    map.eachLayer(function(layer) {
        if (layer.options && layer.options.isDeviceMarker) {
            map.removeLayer(layer);
        }
    });
    allDevices.forEach(device => {
        const { current_latitude: lat, current_longitude: lng, geofence_status } = device;
        if (lat !== null && lng !== null) {
            let markerColor = 'blue';
            if (geofence_status === 'Dentro') markerColor = 'green';
            else if (geofence_status === 'Fuera') markerColor = 'red';
            const deviceIcon = L.divIcon({
                className: 'custom-div-icon',
                html: `<i class="fas fa-bullseye fa-2x" style="color: ${markerColor};"></i>`,
                iconSize: [30, 30],
                iconAnchor: [15, 30]
            });
            const marker = L.marker([lat, lng], { icon: deviceIcon, isDeviceMarker: true }).addTo(map);
            let popupContent = `<b>${device.device_name || 'Sin Nombre'}</b><br>EUI: ${device.dev_eui}<br>Lat: ${lat.toFixed(5)}, Lng: ${lng.toFixed(5)}`;
            marker.bindPopup(popupContent);
        }
    });
}


/**
 * Muestra un modal por su ID.
 */
function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'block';
}

/**
 * Cierra un modal por su ID.
 */
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'none';
    if (modalId === 'geofenceModal') {
        drawnItems.clearLayers();
        if (typeof drawnGeometry !== 'undefined') drawnGeometry = null;
    }
}


/**
 * Muestra el modal de detalles de un grupo.
 */
function showGroupDetailsModal(groupId) {
    const group = allGroups.find(g => g.id === groupId);
    if (!group) return alert("Grupo no encontrado.");
    document.getElementById('detailGroupName').textContent = group.name;
    document.getElementById('detailGroupDescription').textContent = group.description || 'Sin descripción.';
    const devicesListEl = document.getElementById('detailGroupDevicesList');
    devicesListEl.innerHTML = group.devices.length > 0 ?
        group.devices.map(d => `<div class="detail-item"><i class="fas fa-microchip"></i> <b>${d.device_name || 'Sin Nombre'}</b> (EUI: ${d.dev_eui})</div>`).join('') :
        '<p>No hay dispositivos asignados a este grupo.</p>';
    const geofencesListEl = document.getElementById('detailGroupGeofencesList');
    const associatedGeofences = allGeofences.filter(gf => gf.group_id === groupId);
    geofencesListEl.innerHTML = associatedGeofences.length > 0 ?
        associatedGeofences.map(gf => `<div class="detail-item"><i class="fas fa-draw-polygon"></i> <b>${gf.name}</b> (${gf.geofence_type})</div>`).join('') :
        '<p>No hay geocercas asignadas a este grupo.</p>';
    showModal('groupDetailsModal');
}


/**
 * Permite editar el nombre de un dispositivo.
 */
async function editDevice(deviceId) {
    const device = allDevices.find(d => d.id === deviceId);
    if (!device) return alert("Dispositivo no encontrado.");
    const newName = prompt(`Editar nombre para ${device.device_name || device.dev_eui}:`, device.device_name);
    if (newName === null) return;
    try {
        const response = await fetch(`${API_BASE_URL}/devices/${deviceId}`, {
            method: 'PUT',
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ device_name: newName, dev_eui: device.dev_eui })
        });
        if (!response.ok) throw new Error("Fallo al actualizar el dispositivo.");
        await fetchAllDataAndRender();
    } catch (error) {
        console.error("Error al actualizar dispositivo:", error);
    }
}

/**
 * Elimina un dispositivo.
 */
async function deleteDevice(deviceId) {
    if (!confirm("¿Seguro que quieres eliminar este dispositivo? Se borrará todo su historial.")) {
        return;
    }
    try {
        const response = await fetch(`${API_BASE_URL}/devices/${deviceId}`, { method: 'DELETE' });
        if (!response.ok) throw new Error("Fallo al eliminar el dispositivo.");
        await fetchAllDataAndRender();
    } catch (error) {
        console.error("Error al eliminar dispositivo:", error);
    }
}


/**
 * Muestra el modal para crear o editar un grupo.
 */
function showGroupModal(groupId = null) {
    document.getElementById('groupId').value = '';
    document.getElementById('groupName').value = '';
    document.getElementById('groupDescription').value = '';
    const devicesSelect = document.getElementById('groupDevices');
    devicesSelect.innerHTML = '';
    allDevices.forEach(device => {
        const option = new Option(`${device.device_name || 'Sin Nombre'} (${device.dev_eui})`, device.id);
        devicesSelect.appendChild(option);
    });
    if (groupId) {
        const group = allGroups.find(g => g.id === groupId);
        if (group) {
            document.getElementById('groupId').value = group.id;
            document.getElementById('groupName').value = group.name;
            document.getElementById('groupDescription').value = group.description || '';
            const deviceIds = group.devices.map(d => d.id.toString());
            Array.from(devicesSelect.options).forEach(opt => {
                if (deviceIds.includes(opt.value)) opt.selected = true;
            });
        }
    }
    showModal('groupModal');
}

/**
 * Envía la solicitud para crear o actualizar un grupo.
 */
async function createGroup() {
    const groupId = document.getElementById('groupId').value;
    const name = document.getElementById('groupName').value;
    if (!name.trim()) return alert("El nombre del grupo es obligatorio.");
    const payload = {
        name: name,
        description: document.getElementById('groupDescription').value,
        device_ids: Array.from(document.getElementById('groupDevices').selectedOptions).map(opt => parseInt(opt.value))
    };
    const url = groupId ? `${API_BASE_URL}/groups/${groupId}` : `${API_BASE_URL}/groups/`;
    const method = groupId ? 'PUT' : 'POST';
    try {
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail);
        }
        closeModal('groupModal');
        await fetchAllDataAndRender();
    } catch (error) {
        alert(error.message);
    }
}

/**
 * Wrapper para llamar a showGroupModal en modo edición.
 */
function editGroup(groupId) {
    showGroupModal(groupId);
}

/**
 * Elimina un grupo.
 */
async function deleteGroup(groupId) {
    if (!confirm("¿Seguro que quieres eliminar este grupo?")) {
        return;
    }
    try {
        const response = await fetch(`${API_BASE_URL}/groups/${groupId}`, { method: 'DELETE' });
        if (!response.ok) throw new Error("Fallo al eliminar el grupo.");
        await fetchAllDataAndRender();
    } catch (error) {
        console.error("Error al eliminar grupo:", error);
    }
}
