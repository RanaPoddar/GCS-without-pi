// Mission Control Dashboard
class MissionControl {
    constructor() {
        this.map = null;
        this.socket = null;
        this.missionData = null;
        this.boundaryLayer = null;
        this.gridLayer = null;
        this.drone1Marker = null;
        this.drone2Marker = null;
        this.drone1Path = [];
        this.drone2Path = [];
        this.drone1PathLine = null;
        this.drone2PathLine = null;
        this.gcsMarker = null;
        this.gcsLocation = null;
        this.detectionMarkers = [];
        this.detectionLog = []; // Store all detections
        this.missionStartTime = null;
        this.missionInterval = null;
        this.hasReceivedTelemetry = false;
        this.activeMission = null;
        this.missionProgressInterval = null;
        this.currentWaypointMarker = null;
        this.waypointPreviewLayer = null;
        this.lastUploadedFile = null; // Store last uploaded file for re-processing
        
        this.init();
    }
    
    init() {
        this.initMap();
        this.initSocket();
        this.initEventListeners();
        this.initGCSLocation();
        
        // Initialize drone connection status as disconnected
        this.updateDroneConnectionStatus(1, false);
        this.updateDroneConnectionStatus(2, false);
        
        this.addAlert('System initialized', 'info');
    }
    
    // Map Initialization
    initMap() {
        this.map = L.map('map', {
            zoomControl: true,
            attributionControl: true,
            maxZoom: 22
        }).setView([0, 0], 2);
        
        // Use Google Satellite tiles (most reliable for high zoom)
        L.tileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
            maxZoom: 22,
            minZoom: 1,
            attribution: '&copy; Google'
        }).addTo(this.map);
        
        // Add labels overlay
        L.tileLayer('https://mt1.google.com/vt/lyrs=h&x={x}&y={y}&z={z}', {
            maxZoom: 22,
            minZoom: 1,
            opacity: 1.0,
            attribution: '&copy; Google'
        }).addTo(this.map);
        
        // Initialize layer groups
        this.boundaryLayer = L.layerGroup().addTo(this.map);
        this.gridLayer = L.layerGroup().addTo(this.map);
        
        // Custom drone icons
        this.drone1Icon = L.icon({
            iconUrl: 'assets/scanning_drone.png',
            iconSize: [40, 40],
            iconAnchor: [20, 20],
            popupAnchor: [0, -20]
        });
        
        this.drone2Icon = L.icon({
            iconUrl: 'assets/spray_drone.png',
            iconSize: [40, 40],
            iconAnchor: [20, 20],
            popupAnchor: [0, -20]
        });
        
        // GCS icon
        this.gcsIcon = L.icon({
            iconUrl: 'assets/gcs.png',
            iconSize: [45, 45],
            iconAnchor: [22, 22],
            popupAnchor: [0, -22]
        });
        
        // Drone markers
        this.drone1Marker = L.marker([0, 0], { 
            icon: this.drone1Icon,
            opacity: 0 
        }).addTo(this.map)
        .bindPopup('<b>Drone 1</b><br>Waiting for telemetry...');
        
        this.drone2Marker = L.marker([0, 0], { 
            icon: this.drone2Icon,
            opacity: 0 
        }).addTo(this.map)
        .bindPopup('<b>Drone 2</b><br>Waiting for telemetry...');
        
        // GCS marker (will be positioned when first telemetry is received)
        this.gcsMarker = L.marker([0, 0], {
            icon: this.gcsIcon,
            opacity: 0
        }).addTo(this.map)
        .bindPopup('<b>Ground Control Station</b><br>Dashboard Location');
        
        // Path lines
        this.drone1PathLine = L.polyline([], {
            color: '#0ea5e9',
            weight: 2,
            opacity: 0.7
        }).addTo(this.map);
        
        this.drone2PathLine = L.polyline([], {
            color: '#22c55e',
            weight: 2,
            opacity: 0.7
        }).addTo(this.map);
        
        console.log('Map initialized');
    }
    
    // GCS Location Initialization
    initGCSLocation() {
        // Try to get browser geolocation
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const accuracy = position.coords.accuracy;
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    
                    // Only accept location if accuracy is reasonable (< 100m)
                    if (accuracy < 100) {
                        this.gcsLocation = [lat, lon];
                        this.gcsMarker.setLatLng(this.gcsLocation);
                        this.gcsMarker.setOpacity(1);
                        console.log(`GCS location set: [${lat.toFixed(6)}, ${lon.toFixed(6)}] (±${accuracy.toFixed(0)}m)`);
                        this.addAlert(`GCS location acquired (±${accuracy.toFixed(0)}m)`, 'success');
                        
                        // Update popup with accuracy
                        this.gcsMarker.setPopupContent(
                            `<b>Ground Control Station</b><br>` +
                            `Lat: ${lat.toFixed(6)}<br>` +
                            `Lon: ${lon.toFixed(6)}<br>` +
                            `Accuracy: ±${accuracy.toFixed(0)}m`
                        );
                        
                        // Center on GCS if no telemetry yet
                        if (!this.hasReceivedTelemetry) {
                            this.map.setView(this.gcsLocation, 15);
                        }
                    } else {
                        console.warn(`GCS location accuracy poor (±${accuracy.toFixed(0)}m), waiting for better fix...`);
                        this.addAlert(`GCS location accuracy poor (±${accuracy.toFixed(0)}m), retrying...`, 'warning');
                    }
                },
                (error) => {
                    console.warn('Could not get GCS location:', error.message);
                    this.addAlert('GCS location unavailable - geolocation disabled', 'warning');
                },
                {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 30000
                }
            );
            
            // Watch position for updates
            navigator.geolocation.watchPosition(
                (position) => {
                    const accuracy = position.coords.accuracy;
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    
                    // Only update if accuracy is good (< 50m for updates)
                    if (accuracy < 50) {
                        this.gcsLocation = [lat, lon];
                        this.gcsMarker.setLatLng(this.gcsLocation);
                        this.gcsMarker.setOpacity(1);
                        this.gcsMarker.setPopupContent(
                            `<b>Ground Control Station</b><br>` +
                            `Lat: ${lat.toFixed(6)}<br>` +
                            `Lon: ${lon.toFixed(6)}<br>` +
                            `Accuracy: ±${accuracy.toFixed(0)}m`
                        );
                        console.log(`GCS location updated: [${lat.toFixed(6)}, ${lon.toFixed(6)}] (±${accuracy.toFixed(0)}m)`);
                    }
                },
                null,
                {
                    enableHighAccuracy: true,
                    timeout: 15000,
                    maximumAge: 60000
                }
            );
        } else {
            console.warn('Geolocation not supported by browser');
            this.addAlert('GCS location unavailable - browser not supported', 'warning');
        }
    }
    
    // Socket.IO Initialization
    initSocket() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.updateConnectionStatus(true);
            this.addAlert('Connected to server', 'success');
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.updateConnectionStatus(false);
            this.addAlert('Disconnected from server', 'error');
        });

        // Drone connection status updates
        this.socket.on('drone_connected', (data) => {
            console.log(`Drone ${data.drone_id} connected`);
            this.updateDroneConnectionStatus(data.drone_id, true);
            this.addAlert(`Drone ${data.drone_id} connected`, 'success');
        });

        this.socket.on('drone_disconnected', (data) => {
            console.log(`Drone ${data.drone_id} disconnected`);
            this.updateDroneConnectionStatus(data.drone_id, false);
            this.addAlert(`Drone ${data.drone_id} disconnected`, 'warning');
        });

        // Reconnect button handlers
        document.getElementById('reconnectDrone1').addEventListener('click', () => {
            this.reconnectDrone(1);
        });
        
        document.getElementById('reconnectDrone2').addEventListener('click', () => {
            this.reconnectDrone(2);
        });
        
        // Simulation mode buttons
        document.getElementById('simulateDrone1').addEventListener('click', () => {
            this.startSimulation(1);
        });
        
        document.getElementById('simulateDrone2').addEventListener('click', () => {
            this.startSimulation(2);
        });
        
        // Telemetry updates
        // Drone telemetry updates
        this.socket.on('drone_telemetry_update', (data) => {
            this.handleTelemetryUpdate(data);
        });
        
        // Drone status updates
        this.socket.on('drones_status', (data) => {
            this.handleDronesStatus(data);
        });
        
        // Drone connected/disconnected
        this.socket.on('drone_connected', (data) => {
            this.addAlert(`Drone ${data.drone_id} connected`, 'success');
        });
        
        this.socket.on('drone_disconnected', (data) => {
            this.addAlert(`Drone ${data.drone_id} disconnected`, 'error');
        });
        
        // Pi connected/disconnected (treat as drone)
        this.socket.on('pi_connected', (data) => {
            console.log('Pi connected:', data);
            // Map pi_id to drone_id
            if (data.pi_id === 'detection_drone_pi_pushpak') {
                this.updateDroneConnectionStatus(1, true);
                this.addAlert('Detection Pi connected', 'success');
            }
        });
        
        this.socket.on('pi_disconnected', (data) => {
            console.log('Pi disconnected:', data);
            if (data.pi_id === 'detection_drone_pi_pushpak') {
                this.updateDroneConnectionStatus(1, false);
                this.addAlert('Detection Pi disconnected', 'error');
            }
        });
        
        // Detection updates
        this.socket.on('detection', (data) => {
            this.handleDetection(data);
        });
        
        // Crop detection from Pi
        this.socket.on('crop_detection', (data) => {
            console.log('Crop detection received:', data);
            this.handleDetection(data);
        });
        
        // Detection status updates
        this.socket.on('detection_status', (data) => {
            this.handleDetectionStatus(data);
        });
        
        // Detection stats updates
        this.socket.on('detection_stats', (data) => {
            this.handleDetectionStats(data);
        });
        
        // Mission status updates
        this.socket.on('mission_status', (data) => {
            this.handleMissionStatus(data);
        });
    }
    
    // Event Listeners
    initEventListeners() {
        // KML Upload
        const uploadZone = document.getElementById('uploadZone');
        const fileInput = document.getElementById('kmlFileInput');
        
        uploadZone.addEventListener('click', () => fileInput.click());
        
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('drag-over');
        });
        
        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('drag-over');
        });
        
        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('drag-over');
            const file = e.dataTransfer.files[0];
            if (file) this.handleKMLUpload(file);
        });
        
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) this.handleKMLUpload(file);
        });
        
        // Generate Grid
        document.getElementById('generateGrid').addEventListener('click', () => {
            this.generateSurveyGrid();
        });
        
        // Mission Control Buttons
        document.getElementById('startMission').addEventListener('click', () => {
            console.log('🔘 Start Mission button clicked');
            this.startMission();
        });
        
        document.getElementById('pauseMission').addEventListener('click', () => {
            console.log('🔘 Pause Mission button clicked');
            this.pauseMission();
        });
        
        document.getElementById('stopMission').addEventListener('click', () => {
            console.log('🔘 Stop Mission button clicked');
            this.stopMission();
        });
        
        document.getElementById('returnToHome').addEventListener('click', () => {
            this.returnToHome();
        });
        
        // Detection Control Buttons
        document.getElementById('startDetection1').addEventListener('click', () => {
            this.startDetection(1);
        });
        
        document.getElementById('stopDetection1').addEventListener('click', () => {
            this.stopDetection(1);
        });
        
        document.getElementById('startDetection2').addEventListener('click', () => {
            this.startDetection(2);
        });
        
        document.getElementById('stopDetection2').addEventListener('click', () => {
            this.stopDetection(2);
        });
        
        // Map Controls
        document.getElementById('centerMap').addEventListener('click', () => {
            this.centerOnDrones();
        });
        
        document.getElementById('toggleLayers').addEventListener('click', () => {
            document.getElementById('layerPanel').classList.toggle('hidden');
        });
        
        document.getElementById('clearMission').addEventListener('click', () => {
            this.clearMission();
        });
        
        // Layer Toggles
        document.getElementById('showBoundary').addEventListener('change', (e) => {
            if (e.target.checked) {
                this.map.addLayer(this.boundaryLayer);
            } else {
                this.map.removeLayer(this.boundaryLayer);
            }
        });
        
        document.getElementById('showGrid').addEventListener('change', (e) => {
            if (e.target.checked) {
                this.map.addLayer(this.gridLayer);
            } else {
                this.map.removeLayer(this.gridLayer);
            }
        });
        
        document.getElementById('showDronePaths').addEventListener('change', (e) => {
            if (e.target.checked) {
                this.drone1PathLine.addTo(this.map);
                this.drone2PathLine.addTo(this.map);
            } else {
                this.map.removeLayer(this.drone1PathLine);
                this.map.removeLayer(this.drone2PathLine);
            }
        });

        // Bottom Panel Controls
        document.getElementById('bottomPanelToggle').addEventListener('click', () => {
            this.toggleBottomPanel();
        });

        document.getElementById('bottomPanelHeader').addEventListener('click', (e) => {
            if (e.target !== document.getElementById('bottomPanelToggle')) {
                this.toggleBottomPanel();
            }
        });

        // Manual Detection Trigger
        document.getElementById('triggerDetection').addEventListener('click', () => {
            this.triggerManualDetection();
        });

        // Confidence slider update
        document.getElementById('detectionConfidence').addEventListener('input', (e) => {
            document.getElementById('confidenceValue').textContent = e.target.value + '%';
        });

        // Detection Log Controls
        document.getElementById('clearLog').addEventListener('click', () => {
            this.clearDetectionLog();
        });

        document.getElementById('exportLog').addEventListener('click', () => {
            this.exportDetectionLog();
        });
        
        // System console controls
        document.getElementById('clearConsole').addEventListener('click', () => {
            this.clearSystemConsole();
        });
    }
    
    // KML Upload Handler
    async handleKMLUpload(file) {
        try {
            // Store the file for later re-processing with different parameters
            this.lastUploadedFile = file;
            
            this.addAlert(`Uploading ${file.name}...`, 'info');
            
            // Create FormData to upload file to server
            const formData = new FormData();
            formData.append('kml', file);
            formData.append('altitude', document.getElementById('altitude').value);
            formData.append('speed', document.getElementById('speed').value);
            formData.append('pi_id', 'mission_control');
            
            // Upload to server for storage
            const uploadResponse = await fetch('/api/mission/upload_kml', {
                method: 'POST',
                body: formData
            });
            
            if (!uploadResponse.ok) {
                throw new Error('Failed to upload KML to server');
            }
            
            const uploadData = await uploadResponse.json();
            console.log('KML uploaded to server:', uploadData);
            
            // Store server mission ID for later use
            const serverMissionId = uploadData.mission_id;
            
            // Now parse for display
            const text = await file.text();
            const parser = new DOMParser();
            const kml = parser.parseFromString(text, 'text/xml');
            
            // Parse KML to GeoJSON
            const geojson = toGeoJSON.kml(kml);
            
            // Extract boundary
            if (geojson.features && geojson.features.length > 0) {
                const feature = geojson.features[0];
                
                // Clear existing boundary
                this.boundaryLayer.clearLayers();
                
                // Add to map
                const layer = L.geoJSON(feature, {
                    style: {
                        color: '#ffff00',
                        weight: 3,
                        fillColor: '#ffff00',
                        fillOpacity: 0.15
                    }
                }).addTo(this.boundaryLayer);
                
                this.map.fitBounds(layer.getBounds());
                
                // Store mission data
                this.missionData = {
                    fileName: file.name,
                    boundary: feature,
                    geojson: geojson,
                    serverMissionId: serverMissionId
                };
                
                // Update UI
                document.getElementById('fileName').textContent = file.name;
                document.getElementById('waypointCount').textContent = 
                    this.countCoordinates(feature);
                document.getElementById('missionArea').textContent = 
                    this.calculateArea(feature).toFixed(2) + ' ha';
                document.getElementById('missionInfo').classList.remove('hidden');
                
                this.addAlert(`KML loaded: ${file.name}`, 'success');
                alert(`✅ KML File Loaded!\n\nFile: ${file.name}\n\nNext: Click "Generate Grid" button.`);
                this.updateMissionStatus('ready');
                document.getElementById('generateGrid').disabled = false;
            }
        } catch (error) {
            console.error('KML upload error:', error);
            this.addAlert('Failed to load KML file', 'error');
        }
    }
    
    // Generate Survey Grid - using server-generated waypoints
    async generateSurveyGrid() {
        if (!this.missionData) {
            this.addAlert('Please upload a KML file first', 'warning');
            return;
        }
        
        // If we have the original file, re-upload with current parameters
        if (this.lastUploadedFile) {
            this.addAlert('Regenerating mission with current parameters...', 'info');
            await this.handleKMLUpload(this.lastUploadedFile);
            // Short delay to ensure server processing is complete
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        
        if (!this.missionData.serverMissionId) {
            this.addAlert('No mission ID from server. Please re-upload KML.', 'warning');
            return;
        }
        
        try {
            this.addAlert('Loading survey grid...', 'info');
            // Clear existing grid
            this.gridLayer.clearLayers();
            // Fetch the mission data with waypoints from server
            const response = await fetch(`/api/mission/${this.missionData.serverMissionId}`);
            if (!response.ok) {
                throw new Error('Failed to fetch mission from server');
            }
            const missionData = await response.json();
            console.log('Mission data from server:', missionData);
            // Defensive: log keys and structure
            if (!missionData) throw new Error('No data from server');
            const mission = missionData.mission_data || missionData.mission;
            if (!mission) throw new Error('No mission object in response');
            if (!Array.isArray(mission.waypoints)) {
                console.error('Waypoints missing or not array:', mission.waypoints);
                throw new Error('No waypoints array in mission data');
            }
            if (mission.waypoints.length === 0) {
                throw new Error('Waypoints array is empty');
            }
            // Check for lat/lon in first waypoint
            if (!('lat' in mission.waypoints[0]) || !('lon' in mission.waypoints[0])) {
                console.error('First waypoint:', mission.waypoints[0]);
                throw new Error('Waypoints missing lat/lon properties');
            }
            const waypoints = mission.waypoints;
            // Draw waypoints as connected path (survey grid)
            const waypointCoords = waypoints.map(wp => [wp.lat, wp.lon]);
            L.polyline(waypointCoords, {
                color: '#00ff00',
                weight: 3,
                opacity: 0.8
            }).addTo(this.gridLayer);
            // Add waypoint markers
            waypoints.forEach((wp, i) => {
                let color = '#00ff00';
                let radius = 4;
                if (i === 0) { color = '#00ff00'; radius = 8; }
                else if (i === waypoints.length - 1) { color = '#ff0000'; radius = 8; }
                L.circleMarker([wp.lat, wp.lon], {
                    radius: radius,
                    fillColor: color,
                    color: '#fff',
                    weight: 2,
                    fillOpacity: 1
                }).addTo(this.gridLayer).bindPopup(`WP ${wp.seq}: ${wp.alt}m`);
            });
            // Update mission stats
            const stats = mission.mission_stats || {};
            document.getElementById('waypointCount').textContent = waypoints.length;
            document.getElementById('estTime').textContent = this.formatTime(stats.estimated_time_minutes * 60 || 0);
            // Store waypoints in mission data
            this.missionData.waypoints = waypoints;
            this.missionData.stats = stats;
            
            // Draw preview with waypoint markers
            this.drawWaypointPreview(waypoints);
            
            this.addAlert(`Survey grid loaded: ${waypoints.length} waypoints`, 'success');
            alert(`✅ Survey Grid Generated!\n\n${waypoints.length} waypoints created\n\nNext step: Connect drone and click "Start Mission" to begin.`);
            document.getElementById('startMission').disabled = false;
        } catch (error) {
            console.error('Grid generation error:', error);
            this.addAlert('Failed to generate survey grid: ' + error.message, 'error');
        }
    }
    
    // Mission Control Functions - Now with automated execution
    async startMission() {
        console.log('🎯 Start Mission button clicked');
        console.log('Mission data:', this.missionData);
        
        // Validate mission data exists
        if (!this.missionData || !this.missionData.waypoints || this.missionData.waypoints.length === 0) {
            console.error('❌ No mission data available');
            console.log('this.missionData:', this.missionData);
            const errorMsg = '❌ No mission loaded!\n\nPlease upload KML file and generate survey grid first.';
            alert(errorMsg);
            this.addAlert('❌ No mission loaded! Please upload KML and generate survey grid first.', 'error');
            return;
        }
        
        console.log(`✅ Mission has ${this.missionData.waypoints.length} waypoints`);
        
        // Check drone connection
        const drone1StatusEl = document.getElementById('drone1StatusText');
        console.log('Drone status element:', drone1StatusEl);
        const drone1Text = drone1StatusEl ? drone1StatusEl.textContent : 'NOT FOUND';
        console.log('Drone 1 status text:', drone1Text);
        
        if (drone1Text !== 'Connected') {
            console.error('❌ Drone not connected, status:', drone1Text);
            const errorMsg = `❌ Drone 1 is not connected!\n\nCurrent Status: ${drone1Text}\n\nPlease connect the drone using PyMAVLink service before starting mission.`;
            alert(errorMsg);
            this.addAlert('❌ Drone 1 is not connected!', 'error');
            this.addAlert('ℹ️ Please connect the drone before starting mission.', 'info');
            return;
        }
        
        console.log('✅ All validations passed, starting automated mission...');
        
        // Use automated mission execution instead of manual control
        try {
            await this.startAutomatedMission();
        } catch (error) {
            console.error('Start mission error:', error);
            const errorMsg = `❌ Mission Start Failed!\n\n${error.message}`;
            alert(errorMsg);
            this.addAlert(`❌ Mission start failed: ${error.message}`, 'error');
        }
    }
    
    async pauseMission() {
        const pauseBtn = document.getElementById('pauseMission');
        if (pauseBtn.textContent.includes('Resume')) {
            await this.resumeAutomatedMission();
        } else {
            await this.pauseAutomatedMission();
        }
    }
    
    async stopMission() {
        await this.stopAutomatedMission();
    }
    
    returnToHome() {
        this.addAlert('Return to home initiated', 'info');
        this.socket.emit('return_to_home');
    }
    
    // Telemetry Update Handler
    handleTelemetryUpdate(data) {
        const telemetry = data.telemetry || {};
        const droneId = data.drone_id || 1;
        const prefix = `drone${droneId}`;
        
        // Update connection status when telemetry is received
        this.updateDroneConnectionStatus(droneId, true);
        
        // Extract GPS coordinates - handle both nested and flat structures
        const latitude = telemetry.gps?.lat || telemetry.latitude;
        const longitude = telemetry.gps?.lon || telemetry.longitude;
        const altitude = telemetry.altitude || 0;
        const heading = telemetry.heading || 0;
        const groundspeed = telemetry.groundspeed || 0;
        const flightMode = telemetry.flight_mode || 'UNKNOWN';
        const armed = telemetry.armed || false;
        const batteryVoltage = telemetry.battery?.voltage || telemetry.battery_voltage || 0;
        const batteryPercent = telemetry.battery?.remaining || telemetry.battery_remaining || 100;
        const satellites = telemetry.gps?.satellites_visible || telemetry.satellites_visible || 0;
        const gpsFixType = telemetry.gps?.fix_type || telemetry.gps_fix_type || 0;
        
        // Update position
        if (latitude && longitude) {
            const pos = [latitude, longitude];
            
            // Update marker
            const marker = droneId === 1 ? this.drone1Marker : this.drone2Marker;
            marker.setLatLng(pos);
            marker.setOpacity(1);
            
            // Update marker popup with current info
            marker.setPopupContent(`
                <b>Drone ${droneId}</b><br>
                ${armed ? '🚁 <span style="color: #22c55e;">ARMED</span>' : '🔒 DISARMED'}<br>
                Mode: ${flightMode}<br>
                Lat: ${latitude.toFixed(6)}<br>
                Lon: ${longitude.toFixed(6)}<br>
                Alt: ${altitude.toFixed(1)}m<br>
                Speed: ${groundspeed.toFixed(1)}m/s<br>
                Battery: ${batteryPercent}%<br>
                Satellites: ${satellites}
            `);
            
            // Update path
            const path = droneId === 1 ? this.drone1Path : this.drone2Path;
            path.push(pos);
            
            // Limit path length
            if (path.length > 1000) path.shift();
            
            // Update path line
            const pathLine = droneId === 1 ? this.drone1PathLine : this.drone2PathLine;
            pathLine.setLatLngs(path);
            
            // Auto-center on first telemetry
            if (!this.hasReceivedTelemetry) {
                this.centerOnDrones();
                this.hasReceivedTelemetry = true;
            }
            
            // Update UI
            document.getElementById(`${prefix}Lat`).textContent = latitude.toFixed(6);
            document.getElementById(`${prefix}Lon`).textContent = longitude.toFixed(6);
        }
        
        // Update altitude
        const altText = altitude.toFixed(1) + 'm';
        document.getElementById(`${prefix}Alt`).textContent = altText;
        document.getElementById(`${prefix}AltHud`).textContent = altText;
        
        // Update heading
        document.getElementById(`${prefix}Heading`).textContent = heading.toFixed(0) + '°';
        
        // Update speed
        const spdText = groundspeed.toFixed(1) + 'm/s';
        document.getElementById(`${prefix}Speed`).textContent = spdText;
        document.getElementById(`${prefix}SpdHud`).textContent = spdText;
        
        // Update battery
        document.getElementById(`${prefix}Battery`).style.width = batteryPercent + '%';
        document.getElementById(`${prefix}BatteryText`).textContent = batteryPercent + '%';
        document.getElementById(`${prefix}BatHud`).textContent = batteryPercent + '%';
        document.getElementById(`${prefix}VoltHud`).textContent = batteryVoltage.toFixed(2) + 'V';
        
        // Update GPS
        const gpsStatus = this.getGPSStatus(gpsFixType);
        document.getElementById(`${prefix}Gps`).textContent = `${gpsStatus} (${satellites})`;
        
        // Update mode
        document.getElementById(`${prefix}Mode`).textContent = flightMode;
        
        // Update armed status
        const armedBadge = document.getElementById(`${prefix}Armed`);
        if (armed) {
            armedBadge.textContent = 'ARMED';
            armedBadge.classList.remove('badge-offline');
            armedBadge.classList.add('badge-online');
        } else {
            armedBadge.textContent = 'DISARMED';
            armedBadge.classList.remove('badge-online');
            armedBadge.classList.add('badge-offline');
        }
        
        // Update status
        const statusBadge = document.getElementById(`${prefix}Status`);
        statusBadge.textContent = 'ONLINE';
        statusBadge.classList.remove('badge-offline');
        statusBadge.classList.add('badge-online');
    }
    
    // Handle drones status
    handleDronesStatus(data) {
        if (data.drones && Array.isArray(data.drones)) {
            data.drones.forEach(drone => {
                // Update connection status for each drone
                this.updateDroneConnectionStatus(drone.drone_id, drone.connected);
                
                // Update telemetry if available
                if (drone.telemetry) {
                    this.handleTelemetryUpdate(drone);
                }
            });
        }
    }
    
    // Detection Control Methods
    startDetection(droneId) {
        console.log(`Starting detection for Drone ${droneId}`);
        
        // Try Socket.IO first (WiFi - shorter range but faster)
        this.socket.emit('start_detection', { 
            pi_id: droneId === 1 ? 'detection_drone_pi_pushpak' : 'drone_2_pi'
        });
        
        // Also send via MAVLink for long-range control (1-10km)
        this.sendMAVLinkDetectionCommand(droneId, 'start');
        
        this.addAlert(`Starting detection on Drone ${droneId} (WiFi + MAVLink)...`, 'info');
    }
    
    stopDetection(droneId) {
        console.log(`Stopping detection for Drone ${droneId}`);
        
        // Try Socket.IO first
        this.socket.emit('stop_detection', { 
            pi_id: droneId === 1 ? 'detection_drone_pi_pushpak' : 'drone_2_pi'
        });
        
        // Also send via MAVLink for long-range control
        this.sendMAVLinkDetectionCommand(droneId, 'stop');
        
        this.addAlert(`Stopping detection on Drone ${droneId} (WiFi + MAVLink)...`, 'info');
    }
    
    async sendMAVLinkDetectionCommand(droneId, action) {
        /**
         * Send detection control via MAVLink (long-range 1-10km).
         * This works even when drone is outside WiFi range.
         */
        try {
            const endpoint = action === 'start' ? 
                `/drone/${droneId}/pi/start_detection` : 
                `/drone/${droneId}/pi/stop_detection`;
            
            const response = await fetch(`http://localhost:5000${endpoint}`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                console.log(`✅ MAVLink ${action} detection command sent to Drone ${droneId}`);
            } else {
                console.warn(`⚠️  MAVLink command failed: ${data.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error(`❌ Failed to send MAVLink command: ${error.message}`);
            // Don't show error to user - Socket.IO might still work
        }
    }
    
    handleDetectionStatus(data) {
        console.log('Detection status update:', data);
        
        // Determine drone ID from pi_id
        const droneId = data.pi_id === 'detection_drone_pi_pushpak' ? 1 : 2;
        const statusElement = document.getElementById(`detection${droneId}Status`);
        
        if (statusElement) {
            if (data.status === 'active') {
                statusElement.textContent = '🟢 Active';
                statusElement.style.color = '#22c55e';
                this.addAlert(`Drone ${droneId} detection started`, 'success');
            } else if (data.status === 'inactive') {
                statusElement.textContent = '⚪ Inactive';
                statusElement.style.color = '#64748b';
                this.addAlert(`Drone ${droneId} detection stopped`, 'warning');
            } else if (data.status === 'failed') {
                statusElement.textContent = '🔴 Failed';
                statusElement.style.color = '#ef4444';
                this.addAlert(`Drone ${droneId} detection failed: ${data.message}`, 'error');
            }
        }
    }
    
    handleDetectionStats(data) {
        console.log('Detection stats update:', data);
        
        const droneId = data.pi_id === 'detection_drone_pi_pushpak' ? 1 : 2;
        const countElement = document.getElementById(`drone${droneId}Detections`);
        
        if (countElement && data.stats) {
            countElement.textContent = data.stats.detection_count || data.stats.total_detections || 0;
        }
    }
    
    // Detection Handler
    handleDetection(data) {
        if (data.latitude && data.longitude) {
            const marker = L.circleMarker([data.latitude, data.longitude], {
                radius: 6,
                fillColor: '#ef4444',
                color: '#fff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8
            }).addTo(this.map);
            
            marker.bindPopup(`
                <div style="color: #fff;">
                    <strong>Detection</strong><br>
                    Type: ${data.type === 'manual' ? 'Manual (Test)' : 'Automatic'}<br>
                    Confidence: ${(data.confidence * 100).toFixed(1)}%<br>
                    Time: ${new Date(data.timestamp).toLocaleTimeString()}
                </div>
            `);
            
            this.detectionMarkers.push(marker);
            
            // Update detection count
            const droneId = data.drone_id || 1;
            const countEl = document.getElementById(`drone${droneId}Detections`);
            const currentCount = parseInt(countEl.textContent) || 0;
            countEl.textContent = currentCount + 1;
            
            // Add to detection log
            this.addDetectionToLog(data);
            
            const alertMsg = data.type === 'manual' 
                ? `Manual detection test by Drone ${droneId}` 
                : `Detection by Drone ${droneId}`;
            this.addAlert(alertMsg, 'warning');
        }
    }
    
    // Mission Status Handler
    handleMissionStatus(data) {
        if (data.progress !== undefined) {
            document.getElementById('progressFill').style.width = data.progress + '%';
            document.getElementById('progressPercent').textContent = 
                data.progress.toFixed(1) + '%';
        }
    }
    
    // UI Helper Functions
    updateConnectionStatus(connected) {
        const indicator = document.querySelector('.connection-indicator');
        const text = document.querySelector('.connection-status span:last-child');
        
        if (connected) {
            indicator.classList.add('online');
            indicator.classList.remove('offline');
            text.textContent = 'Server: Connected';
        } else {
            indicator.classList.remove('online');
            indicator.classList.add('offline');
            text.textContent = 'Server: Disconnected';
        }
    }

    updateDroneConnectionStatus(droneId, connected) {
        const indicator = document.getElementById(`drone${droneId}StatusIndicator`);
        const text = document.getElementById(`drone${droneId}StatusText`);
        
        // Update detection control buttons
        const startBtn = document.getElementById(`startDetection${droneId}`);
        const stopBtn = document.getElementById(`stopDetection${droneId}`);
        
        if (connected) {
            indicator.classList.remove('disconnected');
            indicator.classList.add('connected');
            text.textContent = 'Connected';
            text.style.color = '#48bb78';
            
            // Enable detection buttons
            if (startBtn) startBtn.disabled = false;
            if (stopBtn) stopBtn.disabled = false;
        } else {
            indicator.classList.remove('connected');
            indicator.classList.add('disconnected');
            text.textContent = 'Disconnected';
            text.style.color = '#fc8181';
            
            // Disable detection buttons
            if (startBtn) startBtn.disabled = true;
            if (stopBtn) stopBtn.disabled = true;
        }
    }

    reconnectDrone(droneId) {
        console.log(`Attempting to reconnect Drone ${droneId}...`);
        const btn = document.getElementById(`reconnectDrone${droneId}`);
        btn.disabled = true;
        btn.textContent = '⟳';
        
        this.socket.emit('drone_reconnect', { drone_id: droneId });
        
        this.addAlert(`Reconnecting Drone ${droneId}...`, 'info');
        
        // Re-enable button after 3 seconds
        setTimeout(() => {
            btn.disabled = false;
            btn.textContent = '⟲';
        }, 3000);
    }
    
    async startSimulation(droneId) {
        console.log(`🎮 Starting simulation mode for Drone ${droneId}...`);
        const btn = document.getElementById(`simulateDrone${droneId}`);
        btn.disabled = true;
        btn.textContent = '⏳';
        
        try {
            const response = await fetch(`http://localhost:5000/drone/${droneId}/simulate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.addAlert(`🎮 Drone ${droneId} connected in SIMULATION mode`, 'success');
                this.updateDroneConnectionStatus(droneId, true);
                console.log(`✅ Simulation started for Drone ${droneId}`);
            } else {
                this.addAlert(`❌ Failed to start simulation for Drone ${droneId}`, 'error');
                console.error('Simulation failed:', result.error);
            }
        } catch (error) {
            console.error('Simulation request failed:', error);
            this.addAlert(`❌ Cannot connect to PyMAVLink service`, 'error');
        }
        
        // Re-enable button
        setTimeout(() => {
            btn.disabled = false;
            btn.textContent = '🎮';
        }, 2000);
    }
    
    updateMissionStatus(status) {
        const statusEl = document.getElementById('missionStatus');
        const indicator = statusEl.querySelector('.status-indicator');
        const text = statusEl.querySelector('.status-text');
        
        indicator.className = 'status-indicator status-' + status;
        text.textContent = status.toUpperCase();
    }
    
    updateMissionTimer() {
        if (!this.missionStartTime) return;
        
        const elapsed = Math.floor((Date.now() - this.missionStartTime) / 1000);
        document.getElementById('elapsedTime').textContent = this.formatTime(elapsed);
    }
    
    addAlert(message, type = 'info') {
        const container = document.getElementById('alertsContainer');
        
        const alert = document.createElement('div');
        alert.className = `alert-item alert-${type}`;
        
        const icons = {
            info: 'ℹ️',
            success: '✅',
            warning: '⚠️',
            error: '❌'
        };
        
        alert.innerHTML = `
            <span class="alert-icon">${icons[type]}</span>
            <span class="alert-text">${message}</span>
        `;
        
        container.insertBefore(alert, container.firstChild);
        
        // Also add to system console
        this.addConsoleMessage(message, type);
        
        // Limit alerts
        while (container.children.length > 10) {
            container.removeChild(container.lastChild);
        }
    }
    
    /**
     * Add message to system console (like Mission Planner)
     */
    addConsoleMessage(message, type = 'info') {
        const console = document.getElementById('systemConsole');
        if (!console) return;
        
        const now = new Date();
        const timeStr = now.toLocaleTimeString('en-US', { hour12: false });
        
        const msgDiv = document.createElement('div');
        msgDiv.className = `console-message console-${type}`;
        msgDiv.innerHTML = `
            <span class="console-time">${timeStr}</span>
            <span class="console-text">${message}</span>
        `;
        
        console.appendChild(msgDiv);
        
        // Auto-scroll to bottom
        console.scrollTop = console.scrollHeight;
        
        // Keep only last 100 messages
        while (console.children.length > 100) {
            console.removeChild(console.firstChild);
        }
    }
    
    /**
     * Clear system console
     */
    clearSystemConsole() {
        const console = document.getElementById('systemConsole');
        if (!console) return;
        
        console.innerHTML = `
            <div class="console-message console-info">
                <span class="console-time">${new Date().toLocaleTimeString('en-US', { hour12: false })}</span>
                <span class="console-text">Console cleared</span>
            </div>
        `;
    }
    
    centerOnDrones() {
        const bounds = L.latLngBounds();
        let hasPosition = false;
        
        // Include GCS location
        if (this.gcsMarker && this.gcsMarker.getLatLng().lat !== 0) {
            bounds.extend(this.gcsMarker.getLatLng());
            hasPosition = true;
        }
        
        if (this.drone1Marker.getLatLng().lat !== 0) {
            bounds.extend(this.drone1Marker.getLatLng());
            hasPosition = true;
        }
        
        if (this.drone2Marker.getLatLng().lat !== 0) {
            bounds.extend(this.drone2Marker.getLatLng());
            hasPosition = true;
        }
        
        if (hasPosition) {
            this.map.fitBounds(bounds, { padding: [50, 50], maxZoom: 18 });
        } else {
            this.addAlert('No drone positions available', 'warning');
        }
    }
    
    clearMission() {
        if (confirm('Clear current mission?')) {
            this.boundaryLayer.clearLayers();
            this.gridLayer.clearLayers();
            this.detectionMarkers.forEach(m => m.remove());
            this.detectionMarkers = [];
            this.missionData = null;
            
            document.getElementById('missionInfo').classList.add('hidden');
            document.getElementById('generateGrid').disabled = true;
            document.getElementById('startMission').disabled = true;
            
            this.addAlert('Mission cleared', 'info');
            this.updateMissionStatus('idle');
        }
    }
    
    // Utility Functions
    countCoordinates(feature) {
        let count = 0;
        if (feature.geometry.type === 'Polygon') {
            count = feature.geometry.coordinates[0].length;
        } else if (feature.geometry.type === 'LineString') {
            count = feature.geometry.coordinates.length;
        }
        return count;
    }
    
    calculateArea(feature) {
        // Simple area calculation in hectares
        if (feature.geometry.type !== 'Polygon') return 0;
        
        const coords = feature.geometry.coordinates[0];
        let area = 0;
        
        for (let i = 0; i < coords.length - 1; i++) {
            area += coords[i][0] * coords[i + 1][1];
            area -= coords[i + 1][0] * coords[i][1];
        }
        
        area = Math.abs(area / 2);
        // Convert to hectares (rough approximation)
        return area * 12100;
    }
    
    extractCoordinates(feature) {
        if (feature.geometry.type === 'Polygon') {
            return feature.geometry.coordinates[0].map(c => [c[1], c[0]]);
        } else if (feature.geometry.type === 'LineString') {
            return feature.geometry.coordinates.map(c => [c[1], c[0]]);
        }
        return [];
    }
    
    calculateBounds(coords) {
        let minLat = Infinity, maxLat = -Infinity;
        let minLon = Infinity, maxLon = -Infinity;
        
        coords.forEach(([lat, lon]) => {
            minLat = Math.min(minLat, lat);
            maxLat = Math.max(maxLat, lat);
            minLon = Math.min(minLon, lon);
            maxLon = Math.max(maxLon, lon);
        });
        
        return { minLat, maxLat, minLon, maxLon };
    }
    
    calculateLineSpacing(altitude, overlap) {
        // Simplified calculation
        const sensorWidth = 0.006; // m
        const focalLength = 0.004; // m
        const groundWidth = (altitude * sensorWidth) / focalLength;
        return groundWidth * (1 - overlap / 100);
    }
    
    generateGridLines(bounds, spacing, angle) {
        const lines = [];
        const { minLat, maxLat, minLon, maxLon } = bounds;
        
        // Convert spacing to degrees (rough approximation)
        const spacingDeg = spacing / 111000;
        
        // Calculate center for rotation
        const centerLat = (minLat + maxLat) / 2;
        const centerLon = (minLon + maxLon) / 2;
        
        // Generate lawnmower pattern (back and forth)
        let isLeftToRight = true;
        for (let lat = minLat; lat <= maxLat; lat += spacingDeg) {
            if (isLeftToRight) {
                lines.push([
                    [lat, minLon],
                    [lat, maxLon]
                ]);
            } else {
                lines.push([
                    [lat, maxLon],
                    [lat, minLon]
                ]);
            }
            isLeftToRight = !isLeftToRight;
        }
        
        return lines;
    }
    
    calculateTotalDistance(lines) {
        let total = 0;
        lines.forEach(line => {
            for (let i = 0; i < line.length - 1; i++) {
                total += this.calculateDistance(line[i], line[i + 1]);
            }
        });
        return total;
    }
    
    calculateDistance(point1, point2) {
        const R = 6371000; // Earth radius in meters
        const lat1 = point1[0] * Math.PI / 180;
        const lat2 = point2[0] * Math.PI / 180;
        const deltaLat = (point2[0] - point1[0]) * Math.PI / 180;
        const deltaLon = (point2[1] - point1[1]) * Math.PI / 180;
        
        const a = Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
                  Math.cos(lat1) * Math.cos(lat2) *
                  Math.sin(deltaLon / 2) * Math.sin(deltaLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        
        return R * c;
    }
    
    formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
    
    calculateBatteryPercentage(voltage) {
        // Assuming 4S LiPo (12.6V - 14.4V)
        const minVoltage = 12.6;
        const maxVoltage = 16.8;
        const percentage = ((voltage - minVoltage) / (maxVoltage - minVoltage)) * 100;
        return Math.max(0, Math.min(100, percentage)).toFixed(0);
    }
    
    getGPSStatus(fixType) {
        const statuses = {
            0: 'No Fix',
            1: 'No Fix',
            2: '2D Fix',
            3: '3D Fix',
            4: 'DGPS',
            5: 'RTK Float',
            6: 'RTK Fixed'
        };
        return statuses[fixType] || 'Unknown';
    }
    
    // ============= AUTOMATED MISSION METHODS =============
    
    /**
     * Upload mission waypoints to drone and start automated execution
     */
    async startAutomatedMission() {
        console.log('🚀 Starting automated mission...');
        
        if (!this.missionData || !this.missionData.waypoints) {
            console.error('No mission data available');
            this.addAlert('❌ No mission loaded. Please generate survey grid first.', 'warning');
            return;
        }
        
        try {
            this.addAlert('🚀 Starting automated mission...', 'info');
            
            const waypoints = this.missionData.waypoints;
            console.log(`Mission has ${waypoints.length} waypoints`);
            this.addAlert(`📊 Mission has ${waypoints.length} waypoints`, 'info');
            
            // Select drone - for now use Drone 1
            const droneId = 1;
            
            // Check if drone is connected
            const drone1Text = document.getElementById('drone1StatusText').textContent;
            console.log(`Drone 1 status: ${drone1Text}`);
            if (drone1Text !== 'Connected') {
                console.error('Drone 1 not connected');
                this.addAlert('❌ Drone 1 not connected! Connect drone first.', 'error');
                return;
            }
            
            // Check drone position vs mission start point
            const firstWaypoint = waypoints[0];
            const currentPos = this.drone1Marker.getLatLng();
            const distance = this.calculateDistance(
                { lat: currentPos.lat, lon: currentPos.lng },
                { lat: firstWaypoint.latitude, lon: firstWaypoint.longitude }
            );
            
            console.log(`Distance from mission start: ${distance.toFixed(1)}m`);
            
            // Warn if drone is far from start point
            if (distance > 10) {
                this.addAlert(`⚠️ Warning: Drone is ${distance.toFixed(0)}m from mission start point`, 'warning');
                
                const proceed = confirm(
                    `⚠️ Warning: Drone Position Mismatch!\n\n` +
                    `Current position: ${currentPos.lat.toFixed(6)}, ${currentPos.lng.toFixed(6)}\n` +
                    `Mission start: ${firstWaypoint.latitude.toFixed(6)}, ${firstWaypoint.longitude.toFixed(6)}\n` +
                    `Distance: ${distance.toFixed(1)} meters\n\n` +
                    `The drone will:\n` +
                    `1. Navigate to mission start at 5m altitude\n` +
                    `2. Takeoff vertically to survey altitude\n` +
                    `3. Execute survey waypoints\n\n` +
                    `This is safe, but will add ${(distance / 10).toFixed(0)} seconds to mission time.\n\n` +
                    `Continue with mission start?`
                );
                
                if (!proceed) {
                    this.addAlert('❌ Mission start cancelled by user', 'warning');
                    return;
                }
            } else {
                this.addAlert(`✅ Drone position OK (${distance.toFixed(1)}m from start)`, 'success');
            }
            
            // Upload mission to PyMAVLink service
            this.addAlert('📤 Uploading waypoints to drone...', 'info');
            console.log(`Uploading ${waypoints.length} waypoints to drone ${droneId}`);
            
            let uploadResponse;
            try {
                uploadResponse = await fetch(`http://localhost:5000/drone/${droneId}/mission/upload`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ waypoints })
                });
            } catch (fetchError) {
                console.error('Network error during mission upload:', fetchError);
                const errorMsg = '❌ Cannot connect to PyMAVLink service!\n\nPlease ensure:\n1. PyMAVLink service is running on port 5000\n2. Run: python external-services/pymavlink_service.py\n3. Or use: ./start-pymavlink.sh';
                alert(errorMsg);
                throw new Error(`Cannot connect to PyMAVLink service. Is it running on port 5000?`);
            }
            
            if (!uploadResponse.ok) {
                let errorDetails = `HTTP ${uploadResponse.status}`;
                try {
                    const errorData = await uploadResponse.json();
                    if (errorData.error) {
                        errorDetails = errorData.error;
                    }
                } catch (jsonError) {
                    // If JSON parsing fails, use status text
                    errorDetails = uploadResponse.statusText || errorDetails;
                }
                
                console.error('Upload response not OK:', errorDetails);
                this.addAlert('❌ Failed to upload mission!', 'error');
                this.addAlert(`⚠️ ${errorDetails}`, 'warning');
                
                const errorMsg = `❌ Failed to upload mission!\n\n${errorDetails}\n\nCheck System Messages console for details.`;
                alert(errorMsg);
                throw new Error(`Failed to upload mission: ${errorDetails}`);
            }
            
            const uploadResult = await uploadResponse.json();
            console.log('Upload result:', uploadResult);
            if (!uploadResult.success) {
                throw new Error('Mission upload returned failure');
            }
            
            // Note: PyMAVLink automatically adds NAV and TAKEOFF waypoints
            const totalWaypoints = uploadResult.waypoint_count;
            this.addAlert(`✅ ${totalWaypoints} waypoints uploaded (includes NAV→START + TAKEOFF)`, 'success');
            
            // ARM the drone if not already armed
            this.addAlert('🔧 Arming drone...', 'info');
            let armResponse;
            try {
                armResponse = await fetch(`http://localhost:5000/drone/${droneId}/arm`, {
                    method: 'POST'
                });
            } catch (fetchError) {
                console.error('Network error during ARM:', fetchError);
                this.addAlert('❌ Cannot connect to PyMAVLink service for ARM command!', 'error');
                const errorMsg = '❌ Cannot connect to PyMAVLink service!\n\nPlease ensure PyMAVLink service is running on port 5000.';
                alert(errorMsg);
                return;
            }
            
            const armResult = await armResponse.json();
            
            if (armResult.success) {
                this.addAlert('✅ Drone armed successfully', 'success');
                if (armResult.message) {
                    console.log('ARM success message:', armResult.message);
                }
            } else {
                // Display the detailed error message from PyMAVLink
                const errorDetails = armResult.error || 'Unknown ARM failure';
                this.addAlert('❌ Failed to arm drone!', 'error');
                this.addAlert(`⚠️ ${errorDetails}`, 'warning');
                
                // Log to console
                console.error('ARM failed:', errorDetails);
                console.error('Full response:', armResult);
                
                // Show detailed alert
                const errorMsg = `❌ Failed to ARM drone!\n\n${errorDetails}\n\nCommon issues:\n• GPS: Need 3D fix with 8+ satellites\n• Battery: Check voltage is sufficient\n• Compass: Ensure proper calibration\n• Safety: Check all safety switches\n• RC: Verify RC connection if required\n\nCheck System Messages console for details.`;
                alert(errorMsg);
                return;
            }
            
            await this.sleep(2000); // Wait for arm to settle
            
            // Start mission (will automatically set GUIDED then AUTO mode)
            this.addAlert('🚀 Starting mission execution...', 'info');
            let startResponse;
            try {
                startResponse = await fetch(`http://localhost:5000/drone/${droneId}/mission/start`, {
                    method: 'POST'
                });
            } catch (fetchError) {
                console.error('Network error during mission start:', fetchError);
                this.addAlert('❌ Cannot connect to PyMAVLink service for mission start!', 'error');
                const errorMsg = '❌ Cannot connect to PyMAVLink service!\n\nPlease ensure PyMAVLink service is running on port 5000.';
                alert(errorMsg);
                return;
            }
            
            const startResult = await startResponse.json();
            
            if (!startResult.success) {
                const errorDetails = startResult.error || 'Unknown mission start failure';
                this.addAlert('❌ Failed to start mission!', 'error');
                this.addAlert(`⚠️ ${errorDetails}`, 'warning');
                
                // Log to console
                console.error('Mission start failed:', errorDetails);
                console.error('Full response:', startResult);
                
                const errorMsg = `❌ Failed to start mission!\n\n${errorDetails}\n\nCheck System Messages console for details.`;
                alert(errorMsg);
                return;
            }
            
            this.addAlert(' Mission ACTIVE! Drone executing waypoints...', 'success');
            alert('✅ Mission Started Successfully!\n\nThe drone will now:\n1. Takeoff to altitude\n2. Execute waypoints\n3. Complete survey mission\n\nMonitor progress on the dashboard.');
            this.updateMissionStatus('active');
            
            // Enable control buttons
            document.getElementById('startMission').disabled = true;
            document.getElementById('pauseMission').disabled = false;
            document.getElementById('stopMission').disabled = false;
            
            // Start mission progress monitoring
            this.startMissionProgressMonitoring(droneId);
            
            // Store active mission info
            this.activeMission = {
                droneId: droneId,
                waypoints: waypoints,
                startTime: Date.now()
            };
            
            // Start mission timer
            this.missionStartTime = Date.now();
            this.missionInterval = setInterval(() => {
                this.updateMissionTimer();
            }, 1000);
            
        } catch (error) {
            console.error('❌ Automated mission error:', error);
            this.addAlert(`❌ Mission start failed: ${error.message}`, 'error');
            
            // Show alert popup for errors that might not have been caught earlier
            if (!error.message.includes('PyMAVLink') && !error.message.includes('upload') && !error.message.includes('ARM')) {
                alert(`❌ Mission Error!\n\n${error.message}`);
            }
            
            // Re-enable start button on error
            document.getElementById('startMission').disabled = false;
            document.getElementById('pauseMission').disabled = true;
            document.getElementById('stopMission').disabled = true;
            
            // Stop mission timer if it was started
            if (this.missionInterval) {
                clearInterval(this.missionInterval);
                this.missionInterval = null;
            }
        }
    }
    
    /**
     * Monitor mission progress in real-time
     */
    startMissionProgressMonitoring(droneId) {
        if (this.missionProgressInterval) {
            clearInterval(this.missionProgressInterval);
        }
        
        this.missionProgressInterval = setInterval(async () => {
            try {
                const response = await fetch(`http://localhost:5000/drone/${droneId}/mission/status`);
                if (!response.ok) return;
                
                const data = await response.json();
                const status = data.mission_status;
                
                // Update progress UI
                const progressPercent = status.progress_percent || 0;
                document.getElementById('progressFill').style.width = progressPercent + '%';
                document.getElementById('progressPercent').textContent = progressPercent.toFixed(0) + '%';
                
                // Highlight current waypoint on map
                this.highlightCurrentWaypoint(status.current_waypoint);
                
                // Check if mission completed
                if (status.current_waypoint >= status.total_waypoints - 1 && status.active) {
                    this.addAlert('Mission completed!', 'success');
                    this.stopMissionProgressMonitoring();
                    this.updateMissionStatus('completed');
                    
                    if (this.missionInterval) {
                        clearInterval(this.missionInterval);
                    }
                }
                
            } catch (error) {
                console.error('Mission status error:', error);
            }
        }, 2000);
    }
    
    stopMissionProgressMonitoring() {
        if (this.missionProgressInterval) {
            clearInterval(this.missionProgressInterval);
            this.missionProgressInterval = null;
        }
    }
    
    /**
     * Highlight current waypoint on map
     */
    highlightCurrentWaypoint(wpIndex) {
        if (!this.activeMission || !this.activeMission.waypoints) return;
        
        const waypoints = this.activeMission.waypoints;
        if (wpIndex >= 0 && wpIndex < waypoints.length) {
            const wp = waypoints[wpIndex];
            const lat = wp.lat || wp.latitude;
            const lon = wp.lon || wp.longitude;
            
            // Remove previous highlight if exists
            if (this.currentWaypointMarker) {
                this.map.removeLayer(this.currentWaypointMarker);
            }
            
            // Add pulsing marker at current waypoint
            this.currentWaypointMarker = L.circleMarker([lat, lon], {
                radius: 15,
                fillColor: '#ff00ff',
                color: '#fff',
                weight: 3,
                opacity: 1,
                fillOpacity: 0.6,
                className: 'pulse-marker'
            }).addTo(this.map);
            
            // Optionally pan to current waypoint (disabled to avoid jumpy map)
            // this.map.panTo([lat, lon]);
        }
    }
    
    /**
     * Pause automated mission
     */
    async pauseAutomatedMission() {
        if (!this.activeMission) return;
        
        try {
            this.addAlert('⏸️ Pausing mission...', 'info');
            
            const response = await fetch(`http://localhost:5000/drone/${this.activeMission.droneId}/mission/pause`, {
                method: 'POST'
            });
            const result = await response.json();
            
            if (result.success) {
                this.addAlert('Mission paused (LOITER mode)', 'warning');
                this.updateMissionStatus('paused');
                document.getElementById('pauseMission').innerHTML = '<span class="btn-icon">▶️</span> Resume';
            }
        } catch (error) {
            this.addAlert('Failed to pause mission', 'error');
        }
    }
    
    /**
     * Resume automated mission
     */
    async resumeAutomatedMission() {
        if (!this.activeMission) return;
        
        try {
            this.addAlert('▶️ Resuming mission...', 'info');
            
            const response = await fetch(`http://localhost:5000/drone/${this.activeMission.droneId}/mission/resume`, {
                method: 'POST'
            });
            const result = await response.json();
            
            if (result.success) {
                this.addAlert('Mission resumed', 'success');
                this.updateMissionStatus('active');
                document.getElementById('pauseMission').innerHTML = '<span class="btn-icon">⏸️</span> Pause';
            }
        } catch (error) {
            this.addAlert('Failed to resume mission', 'error');
        }
    }
    
    /**
     * Stop automated mission
     */
    async stopAutomatedMission() {
        if (!this.activeMission) return;
        
        if (!confirm('Are you sure you want to stop the mission? The drone will enter LOITER mode.')) {
            return;
        }
        
        try {
            this.addAlert('⏹️ Stopping mission...', 'info');
            
            const response = await fetch(`http://localhost:5000/drone/${this.activeMission.droneId}/mission/stop`, {
                method: 'POST'
            });
            const result = await response.json();
            
            if (result.success) {
                this.addAlert('Mission stopped', 'warning');
                this.updateMissionStatus('stopped');
                this.stopMissionProgressMonitoring();
                
                // Clear mission highlight
                if (this.currentWaypointMarker) {
                    this.map.removeLayer(this.currentWaypointMarker);
                }
                
                // Reset buttons
                document.getElementById('startMission').disabled = false;
                document.getElementById('pauseMission').disabled = true;
                document.getElementById('pauseMission').innerHTML = '<span class="btn-icon">⏸️</span> Pause';
                document.getElementById('stopMission').disabled = true;
                
                // Clear timer
                if (this.missionInterval) {
                    clearInterval(this.missionInterval);
                }
                
                this.activeMission = null;
            }
        } catch (error) {
            this.addAlert('Failed to stop mission', 'error');
        }
    }
    
    /**
     * Draw waypoint preview on map
     */
    drawWaypointPreview(waypoints) {
        if (this.waypointPreviewLayer) {
            this.map.removeLayer(this.waypointPreviewLayer);
        }
        
        this.waypointPreviewLayer = L.layerGroup().addTo(this.map);
        
        // Draw path line
        const coords = waypoints.map(wp => [wp.lat || wp.latitude, wp.lon || wp.longitude]);
        L.polyline(coords, {
            color: '#00ff00',
            weight: 3,
            opacity: 0.8,
            dashArray: '10, 5'
        }).addTo(this.waypointPreviewLayer);
        
        // Draw waypoint markers with numbers
        waypoints.forEach((wp, i) => {
            const lat = wp.lat || wp.latitude;
            const lon = wp.lon || wp.longitude;
            
            let color = '#00ffff';
            let radius = 6;
            
            if (i === 0) {
                color = '#00ff00';
                radius = 10;
            } else if (i === waypoints.length - 1) {
                color = '#ff0000';
                radius = 10;
            }
            
            const marker = L.circleMarker([lat, lon], {
                radius: radius,
                fillColor: color,
                color: '#fff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8
            }).addTo(this.waypointPreviewLayer);
            
            marker.bindPopup(`
                <b>Waypoint ${i + 1}/${waypoints.length}</b><br>
                Lat: ${lat.toFixed(6)}<br>
                Lon: ${lon.toFixed(6)}<br>
                Alt: ${wp.altitude || wp.alt || 0}m
            `);
        });
        
        // Fit map to waypoints
        if (coords.length > 0) {
            this.map.fitBounds(L.latLngBounds(coords));
        }
    }
    
    /**
     * Helper sleep function
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // ========================================
    // Bottom Panel & Detection Testing Methods
    // ========================================

    /**
     * Toggle bottom panel visibility
     */
    toggleBottomPanel() {
        const panel = document.getElementById('bottomPanel');
        const toggleIcon = document.getElementById('toggleIcon');
        
        panel.classList.toggle('collapsed');
        
        if (panel.classList.contains('collapsed')) {
            toggleIcon.textContent = '▲';
        } else {
            toggleIcon.textContent = '▼';
        }
    }

    /**
     * Trigger manual detection for testing
     */
    triggerManualDetection() {
        // Get selected drone
        const selectedDrone = document.querySelector('input[name="triggerDrone"]:checked').value;
        const droneId = parseInt(selectedDrone);
        
        // Get confidence level
        const confidence = parseFloat(document.getElementById('detectionConfidence').value) / 100;
        
        // Get drone marker position
        const marker = droneId === 1 ? this.drone1Marker : this.drone2Marker;
        
        if (!marker || marker.getOpacity() === 0) {
            this.showTriggerMessage('error', `Drone ${droneId} is not active or has no position data`);
            this.addAlert(`Cannot trigger detection - Drone ${droneId} not active`, 'error');
            return;
        }
        
        const position = marker.getLatLng();
        
        // Create detection object
        const detection = {
            drone_id: droneId,
            latitude: position.lat,
            longitude: position.lng,
            confidence: confidence,
            timestamp: new Date().toISOString(),
            type: 'manual', // Mark as manual trigger
            test: true
        };
        
        console.log('Manual detection triggered:', detection);
        
        // Send to server via socket
        this.socket.emit('manual_detection', detection);
        
        // Handle detection locally (add to map and log)
        this.handleDetection(detection);
        
        // Show success message
        this.showTriggerMessage('success', `Detection triggered for Drone ${droneId} at [${position.lat.toFixed(6)}, ${position.lng.toFixed(6)}]`);
        this.addAlert(`Manual detection triggered (Drone ${droneId})`, 'success');
    }

    /**
     * Show message in trigger info area
     */
    showTriggerMessage(type, message) {
        const triggerInfo = document.getElementById('triggerInfo');
        const icon = triggerInfo.querySelector('.info-icon');
        const text = triggerInfo.querySelector('.info-text');
        
        // Reset classes
        triggerInfo.classList.remove('success', 'error');
        
        if (type === 'success') {
            triggerInfo.classList.add('success');
            icon.textContent = '✅';
        } else if (type === 'error') {
            triggerInfo.classList.add('error');
            icon.textContent = '❌';
        } else {
            icon.textContent = 'ℹ️';
        }
        
        text.textContent = message;
        
        // Reset after 5 seconds
        setTimeout(() => {
            triggerInfo.classList.remove('success', 'error');
            icon.textContent = 'ℹ️';
            text.textContent = 'Drone must be flying to trigger detection';
        }, 5000);
    }

    /**
     * Add detection to log
     */
    addDetectionToLog(detection) {
        // Add to log array
        this.detectionLog.unshift(detection); // Add to beginning
        
        // Update total count
        document.getElementById('totalDetections').textContent = this.detectionLog.length;
        
        // Hide empty message
        document.getElementById('logEmpty').style.display = 'none';
        
        // Create log item
        const logContainer = document.getElementById('detectionLogContainer');
        const logItem = document.createElement('div');
        logItem.className = 'log-item';
        logItem.dataset.detectionId = detection.timestamp;
        
        const time = new Date(detection.timestamp);
        const timeStr = time.toLocaleTimeString();
        const dateStr = time.toLocaleDateString();
        
        const type = detection.type || 'auto';
        const typeClass = type === 'manual' ? 'manual' : 'auto';
        const typeLabel = type === 'manual' ? 'Manual' : 'Auto';
        
        logItem.innerHTML = `
            <div class="log-item-icon">${detection.drone_id === 1 ? '🔍' : '💧'}</div>
            <div class="log-item-content">
                <div class="log-item-header">
                    <span class="log-item-drone">Drone ${detection.drone_id}</span>
                    <span class="log-item-type ${typeClass}">${typeLabel}</span>
                    <span class="log-item-time">${timeStr} • ${dateStr}</span>
                </div>
                <div class="log-item-coords">
                    <span>Lat: ${detection.latitude.toFixed(6)}</span>
                    <span>Lon: ${detection.longitude.toFixed(6)}</span>
                </div>
                <div class="log-item-confidence">Confidence: ${(detection.confidence * 100).toFixed(1)}%</div>
            </div>
            <div class="log-item-actions">
                <button class="log-item-action" onclick="missionControl.zoomToDetection(${detection.latitude}, ${detection.longitude})">
                    📍 View
                </button>
            </div>
        `;
        
        // Add to container
        logContainer.insertBefore(logItem, logContainer.firstChild);
        
        // Limit log size (keep last 100)
        if (this.detectionLog.length > 100) {
            this.detectionLog.pop();
            const items = logContainer.querySelectorAll('.log-item');
            if (items.length > 100) {
                items[items.length - 1].remove();
            }
        }
    }

    /**
     * Zoom map to detection location
     */
    zoomToDetection(lat, lng) {
        this.map.setView([lat, lng], 18);
        this.addAlert('Zoomed to detection location', 'info');
    }

    /**
     * Clear detection log
     */
    clearDetectionLog() {
        if (this.detectionLog.length === 0) {
            return;
        }
        
        if (confirm(`Clear all ${this.detectionLog.length} detections from log?`)) {
            this.detectionLog = [];
            document.getElementById('totalDetections').textContent = '0';
            document.getElementById('detectionLogContainer').innerHTML = `
                <div class="log-empty" id="logEmpty">
                    <span class="empty-icon">📭</span>
                    <p>No detections yet</p>
                </div>
            `;
            this.addAlert('Detection log cleared', 'info');
        }
    }

    /**
     * Export detection log to JSON
     */
    exportDetectionLog() {
        if (this.detectionLog.length === 0) {
            alert('No detections to export');
            return;
        }
        
        const dataStr = JSON.stringify(this.detectionLog, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `detection_log_${new Date().toISOString().replace(/:/g, '-')}.json`;
        link.click();
        
        URL.revokeObjectURL(url);
        this.addAlert(`Exported ${this.detectionLog.length} detections`, 'success');
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.missionControl = new MissionControl();
});
