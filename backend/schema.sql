CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE devices (id SERIAL PRIMARY KEY, dev_eui VARCHAR(16) UNIQUE NOT NULL, device_name VARCHAR(100));
CREATE TABLE device_groups (id SERIAL PRIMARY KEY, name VARCHAR(100) UNIQUE NOT NULL, description TEXT);
CREATE TABLE device_group_members (device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE, group_id INTEGER REFERENCES device_groups(id) ON DELETE CASCADE, PRIMARY KEY (device_id, group_id));
CREATE TABLE geofences (id SERIAL PRIMARY KEY, group_id INTEGER REFERENCES device_groups(id) ON DELETE CASCADE, name VARCHAR(100) NOT NULL, geofence_type VARCHAR(20) NOT NULL, geometry GEOGRAPHY NOT NULL, radius REAL, active BOOLEAN DEFAULT true);
CREATE TABLE device_positions (time TIMESTAMP WITH TIME ZONE NOT NULL, device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE, location GEOGRAPHY(POINT, 4326) NOT NULL, rssi INTEGER, snr REAL, inside_geofence BOOLEAN, PRIMARY KEY (time, device_id));
CREATE INDEX idx_positions_time ON device_positions (time DESC);
CREATE INDEX idx_positions_location ON device_positions USING GIST(location);
CREATE INDEX idx_geofences_geometry ON geofences USING GIST(geometry);
