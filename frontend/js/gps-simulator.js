// GPS Simulator - Simulates GPS points along a route for testing

class GPSSimulator {
    constructor() {
        this.journeyId = null;
        this.route = null;
        this.isRunning = false;
        this.currentIndex = 0;
        this.pointsSent = 0;
        this.intervalId = null;
        this.speedMultiplier = 10; // Default 10x speed
        this.baseInterval = 500;   // Base interval in ms (500ms = 2 updates per second)
        this.pointsPerUpdate = 1;  // How many route points to skip per update
        this.testScenario = 'normal'; // Default test scenario
        this.originalRoute = null; // Store original route for scenario modifications
    }

    /**
     * Initialize simulator with journey and route
     */
    init(journeyId, route) {
        this.journeyId = journeyId;
        this.route = route;
        this.originalRoute = JSON.parse(JSON.stringify(route)); // Deep copy
        this.currentIndex = 0;
        this.pointsSent = 0;

        // Validate route before initialization
        if (!route) {
            console.error('[Simulator] No route provided, simulator will not work');
            throw new Error('No route provided to simulator');
        }

        // Debug log the route structure
        console.log('[Simulator] Route structure:', {
            has_geometry: !!route.geometry,
            geometry_type: typeof route.geometry,
            is_array: Array.isArray(route.geometry),
            route_keys: Object.keys(route)
        });

        // Get coordinates - handle both formats: geometry as array (backend) or as GeoJSON object
        const coordinates = this.getRouteCoordinates();

        if (!coordinates || !Array.isArray(coordinates) || coordinates.length === 0) {
            console.error('[Simulator] Route has no valid coordinates:', {
                coordinates_exists: !!coordinates,
                coordinates_type: typeof coordinates,
                is_array: Array.isArray(coordinates),
                length: coordinates ? coordinates.length : 'N/A'
            });
            throw new Error('Route has no valid coordinates');
        }

        console.log('[Simulator] Initialized for journey:', journeyId);
        console.log('[Simulator] Route has', coordinates.length, 'points');
    }

    /**
     * Get route coordinates - handles both backend and GeoJSON formats
     */
    getRouteCoordinates() {
        if (!this.route) {
            console.error('[Simulator] No route object');
            return [];
        }

        if (!this.route.geometry) {
            console.error('[Simulator] Route has no geometry property');
            return [];
        }

        // Handle array format (backend sends geometry as array of [lng, lat])
        if (Array.isArray(this.route.geometry)) {
            console.log('[Simulator] Using array geometry format');
            return this.route.geometry;
        }

        // Handle GeoJSON format (geometry.coordinates)
        if (this.route.geometry.coordinates && Array.isArray(this.route.geometry.coordinates)) {
            console.log('[Simulator] Using GeoJSON geometry format');
            return this.route.geometry.coordinates;
        }

        console.error('[Simulator] Unknown geometry format:', this.route.geometry);
        return [];
    }

    /**
     * Apply test scenario to route
     */
    applyTestScenario(scenario) {
        if (!this.originalRoute) {
            console.error('[Simulator] Cannot apply scenario - no original route stored');
            return;
        }

        this.testScenario = scenario;
        console.log(`[Simulator] Applying test scenario: ${scenario}`);

        // Create a modified route based on the original route and selected scenario
        const modifiedRoute = JSON.parse(JSON.stringify(this.originalRoute));

        if (scenario === 'normal') {
            // No modifications needed for normal scenario
            this.route = modifiedRoute;
        } else if (scenario === 'deviation') {
            // Add deviation in middle of route
            this.route = this.applyDeviationScenario(modifiedRoute);
        } else if (scenario === 'stop') {
            // Modify the route to simulate stops
            this.route = this.applyStopScenario(modifiedRoute);
        } else if (scenario === 'speed_slow') {
            // Adjust speeds for slow traffic
            this.route = modifiedRoute;
        } else if (scenario === 'speed_fast') {
            // Adjust speeds for highway speed
            this.route = modifiedRoute;
        }

        console.log(`[Simulator] Applied scenario: ${scenario}`);
    }

    /**
     * Apply deviation scenario - adds wrong turn in middle of route
     */
    applyDeviationScenario(route) {
        const coordinates = this.getRouteCoordinatesFromRoute(route);

        if (!coordinates || coordinates.length === 0) {
            console.error('[Simulator] Cannot apply deviation - no coordinates');
            return route;
        }

        const modifiedCoordinates = [...coordinates];

        // Add deviation in middle of route (between 30% and 50% of the route)
        const deviationStart = Math.floor(coordinates.length * 0.3);
        const deviationEnd = Math.floor(coordinates.length * 0.5);

        for (let i = deviationStart; i < deviationEnd; i++) {
            if (i < modifiedCoordinates.length) {
                const factor = Math.sin((i - deviationStart) / (deviationEnd - deviationStart) * Math.PI);

                // Apply deviation offset (make it significant to trigger deviation detection)
                const [lng, lat] = modifiedCoordinates[i];
                modifiedCoordinates[i] = [
                    lng + 0.03 * factor, // Larger offset to be more noticeable (like in E2E test)
                    lat + 0.04 * factor
                ];
            }
        }

        // Update the route geometry with modified coordinates
        if (Array.isArray(route.geometry)) {
            route.geometry = modifiedCoordinates;
        } else if (route.geometry && route.geometry.coordinates) {
            route.geometry.coordinates = modifiedCoordinates;
        }

        return route;
    }

    /**
     * Apply stop scenario - simulates extended stops
     */
    applyStopScenario(route) {
        // For stop scenario, we keep the route the same but will modify behavior in sendNextPoint
        // The stop behavior will be handled dynamically in the speed calculation
        return route;
    }

    /**
     * Get route coordinates from a specific route object
     */
    getRouteCoordinatesFromRoute(routeObj) {
        if (!routeObj) {
            console.error('[Simulator] No route object provided');
            return [];
        }

        if (!routeObj.geometry) {
            console.error('[Simulator] Route has no geometry property');
            return [];
        }

        // Handle array format (backend sends geometry as array of [lng, lat])
        if (Array.isArray(routeObj.geometry)) {
            return routeObj.geometry;
        }

        // Handle GeoJSON format (geometry.coordinates)
        if (routeObj.geometry.coordinates && Array.isArray(routeObj.geometry.coordinates)) {
            return routeObj.geometry.coordinates;
        }

        console.error('[Simulator] Unknown geometry format:', routeObj.geometry);
        return [];
    }

    /**
     * Get speed based on scenario
     */
    getSpeedForScenario(baseSpeed) {
        switch (this.testScenario) {
            case 'stop':
                // Randomly return low speed to simulate stops (like in E2E test)
                return Math.random() < 0.3 ? 0.5 : baseSpeed * 0.7;
            case 'speed_slow':
                return 15 + Math.random() * 15; // Like in E2E test: 15-30 km/h range
            case 'speed_fast':
                return 90 + Math.random() * 30; // Like in E2E test: 90-120 km/h range
            default:
                return 50 + Math.random() * 30; // Like in E2E test: 50-80 km/h range
        }
    }

    /**
     * Start simulation
     */
    start() {
        if (this.isRunning) {
            console.log('[Simulator] Already running');
            return;
        }

        if (!this.journeyId || !this.route) {
            alert('No journey active');
            return;
        }

        // Get speed multiplier from dropdown
        const multiplierSelect = document.getElementById('sim-speed-multiplier');
        this.speedMultiplier = parseInt(multiplierSelect?.value) || 10;

        // Calculate interval and points to skip based on multiplier
        // Higher multiplier = faster animation (shorter interval, more points skipped)
        this.baseInterval = Math.max(100, 500 / Math.sqrt(this.speedMultiplier));
        this.pointsPerUpdate = Math.max(1, Math.floor(this.speedMultiplier / 5));

        this.isRunning = true;
        this.updateSimulatorUI();
        this.updateJourneyStatus('Active (Simulating)');

        console.log(`[Simulator] Started at ${this.speedMultiplier}x speed (interval=${this.baseInterval.toFixed(0)}ms, points/update=${this.pointsPerUpdate})`);

        // Start sending GPS points
        this.intervalId = setInterval(() => {
            this.sendNextPoint();
        }, this.baseInterval);
    }

    /**
     * Stop simulation
     */
    stop(reason = 'Manual') {
        if (!this.isRunning) return;

        this.isRunning = false;

        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }

        this.updateSimulatorUI();
        this.updateJourneyStatus('Created (Not Started)');
        console.warn(`[Simulator] Stopped. Reason: ${reason}`);
    }

    /**
     * Update journey status display
     */
    updateJourneyStatus(status) {
        const journeyStatusText = document.getElementById('journey-status-text');
        if (journeyStatusText) {
            journeyStatusText.textContent = status;
            // Update badge class based on status
            if (status.includes('Active')) {
                journeyStatusText.className = 'value badge normal';
            } else {
                journeyStatusText.className = 'value badge minor';
            }
        }
    }

    /**
     * Send next GPS point along route
     */
    async sendNextPoint() {
        try {
            const coordinates = this.getRouteCoordinates();

            if (!this.route || this.currentIndex >= coordinates.length) {
                console.log('[Simulator] Reached end of route');
                this.stop('End of route');
                return;
            }

            // Get current coordinate [lng, lat]
            const coord = coordinates[this.currentIndex];
            const [lng, lat] = coord;

            // Calculate bearing to next point
            let bearing = 0;
            if (this.currentIndex < coordinates.length - 1) {
                const nextCoord = coordinates[this.currentIndex + 1];
                bearing = this.calculateBearing(lat, lng, nextCoord[1], nextCoord[0]);
            }

            // Calculate base speed for scenario (convert from km/h to m/s for backend)
            const baseSpeedKmh = 60 * this.speedMultiplier; // Base speed in km/h scaled by multiplier

            // Apply test scenario modifications to speed (returns km/h)
            const simulatedSpeedKmh = this.getSpeedForScenario(baseSpeedKmh);

            // Convert km/h to m/s for the backend API
            const simulatedSpeed = simulatedSpeedKmh / 3.6; // Convert km/h to m/s

            // Simulate realistic GPS accuracy based on conditions
            // Real-world GPS accuracy:
            // - Good conditions (clear sky, strong signal): 3-8 meters
            // - Moderate conditions (some interference): 8-15 meters
            // - Poor conditions (buildings, trees): 15-30 meters
            // We'll use a weighted random distribution favoring good accuracy
            const accuracyType = Math.random();
            let accuracy;
            if (accuracyType < 0.6) {
                // 60% good conditions
                accuracy = 3.0 + Math.random() * 5.0; // 3-8m
            } else if (accuracyType < 0.9) {
                // 30% moderate conditions
                accuracy = 8.0 + Math.random() * 7.0; // 8-15m
            } else {
                // 10% poor conditions
                accuracy = 15.0 + Math.random() * 15.0; // 15-30m
            }

            // Create GPS point
            const gpsPoint = {
                lat,
                lng,
                timestamp: new Date().toISOString(),
                speed: simulatedSpeed,
                bearing,
                accuracy: parseFloat(accuracy.toFixed(1))
            };

            // UPDATE MAP MARKER IMMEDIATELY for visual feedback
            if (window.mapManager) {
                mapManager.updateCurrentPosition(lat, lng);
            }

            // Send GPS point to backend
            const response = await fetch(
                getApiUrl(`/api/journey/${this.journeyId}/gps`),
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(gpsPoint)
                }
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            this.pointsSent++;

            // Move forward by pointsPerUpdate (for faster simulation)
            this.currentIndex += this.pointsPerUpdate;

            // Update UI
            document.getElementById('points-sent').textContent = this.pointsSent;

            // Update current location display
            const locationEl = document.getElementById('current-location');
            if (locationEl) {
                locationEl.textContent = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
            }

            console.log(`[Simulator] Point ${this.pointsSent}: ${lat.toFixed(4)}, ${lng.toFixed(4)} (index: ${this.currentIndex}/${coordinates.length}), speed: ${simulatedSpeed.toFixed(2)} m/s, scenario: ${this.testScenario}`);

        } catch (error) {
            console.error('[Simulator] Failed to send GPS point:', error);
            // Alert user to ensure they see this error
            console.warn('[Simulator] CRITICAL ERROR:', error.message);
            this.stop(`Error sending point: ${error.message}`);
        }
    }

    /**
     * Calculate bearing between two points
     */
    calculateBearing(lat1, lng1, lat2, lng2) {
        const toRad = deg => deg * Math.PI / 180;
        const toDeg = rad => rad * 180 / Math.PI;

        const dLng = toRad(lng2 - lng1);
        const y = Math.sin(dLng) * Math.cos(toRad(lat2));
        const x = Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) -
            Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(dLng);

        let bearing = toDeg(Math.atan2(y, x));
        bearing = (bearing + 360) % 360; // Normalize to 0-360

        return bearing;
    }

    /**
     * Update simulator UI state
     */
    updateSimulatorUI() {
        const startBtn = document.getElementById('start-sim-btn');
        const stopBtn = document.getElementById('stop-sim-btn');
        const speedSelect = document.getElementById('sim-speed-multiplier');

        if (this.isRunning) {
            startBtn.disabled = true;
            stopBtn.disabled = false;
            if (speedSelect) speedSelect.disabled = true;
        } else {
            startBtn.disabled = false;
            stopBtn.disabled = true;
            if (speedSelect) speedSelect.disabled = false;
        }
    }

    /**
     * Reset simulator
     */
    reset() {
        this.stop();
        this.journeyId = null;
        this.route = null;
        this.currentIndex = 0;
        this.pointsSent = 0;

        document.getElementById('points-sent').textContent = '0';
        document.getElementById('current-batch').textContent = '0';

        // Update journey status when resetting
        if (this.updateJourneyStatus) {
            this.updateJourneyStatus('Created (Not Started)');
        }
    }
}

// Create global GPS simulator instance
const gpsSimulator = new GPSSimulator();
window.gpsSimulator = gpsSimulator; // Make it globally accessible

// Initialize simulator controls
document.addEventListener('DOMContentLoaded', () => {
    // Start simulation button (uses currently selected scenario from dropdown)
    const startSimBtn = document.getElementById('start-sim-btn');
    if (startSimBtn) {
        startSimBtn.addEventListener('click', () => {
            // Apply the currently selected scenario from the test scenario dropdown first, then start simulation
            const testScenarioSelect = document.getElementById('test-scenario-select');
            let selectedScenario = 'normal'; // default

            if (testScenarioSelect && testScenarioSelect.value) {
                selectedScenario = testScenarioSelect.value;
            }

            if (gpsSimulator && gpsSimulator.applyTestScenario) {
                gpsSimulator.applyTestScenario(selectedScenario);
            }
            gpsSimulator.start();
        });
    }

    // Stop simulation button
    document.getElementById('stop-sim-btn').addEventListener('click', () => {
        gpsSimulator.stop();
    });

    // Test scenario controls (for the advanced scenario section if needed)
    const applyScenarioBtn = document.getElementById('apply-scenario-btn');
    const testScenarioSelect = document.getElementById('test-scenario-select');

    if (applyScenarioBtn && testScenarioSelect) {
        // Apply scenario button
        applyScenarioBtn.addEventListener('click', () => {
            const selectedScenario = testScenarioSelect.value;
            if (gpsSimulator && gpsSimulator.applyTestScenario) {
                gpsSimulator.applyTestScenario(selectedScenario);
                console.log(`[App] Applied test scenario: ${selectedScenario}`);

                // Show confirmation to user
                const scenarioText = testScenarioSelect.options[testScenarioSelect.selectedIndex].text;
                alert(`Test scenario applied: ${scenarioText}`);
            } else {
                console.error('[App] GPS simulator not available or applyTestScenario method missing');
            }
        });
    }
});
