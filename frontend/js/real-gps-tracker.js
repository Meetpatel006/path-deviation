// Real GPS Tracker - Uses browser Geolocation API for real-time tracking

class RealGPSTracker {
    constructor() {
        this.journeyId = null;
        this.isTracking = false;
        this.watchId = null;
        this.lastPosition = null;
        this.pointsSent = 0;
        this.totalDistance = 0;
        this.gpsTrail = [];
        this.updateInterval = 2000; // Minimum time between updates (ms)
        this.lastUpdateTime = 0;
    }

    /**
     * Initialize tracker with journey
     */
    init(journeyId) {
        this.journeyId = journeyId;
        this.lastPosition = null;
        this.pointsSent = 0;
        this.totalDistance = 0;
        this.gpsTrail = [];
        this.lastUpdateTime = 0;
        
        console.log('[RealGPS] Initialized for journey:', journeyId);
    }

    /**
     * Check if Geolocation API is available
     */
    isAvailable() {
        return 'geolocation' in navigator;
    }

    /**
     * Start real-time GPS tracking
     */
    start() {
        if (this.isTracking) {
            console.log('[RealGPS] Already tracking');
            return;
        }

        if (!this.isAvailable()) {
            alert('Geolocation is not supported by your browser');
            return;
        }

        if (!this.journeyId) {
            alert('No journey active');
            return;
        }

        console.log('[RealGPS] Starting real-time GPS tracking...');
        this.isTracking = true;
        this.updateTrackerUI();
        this.updateJourneyStatus('Active (Real GPS)');

        // Request high accuracy position tracking
        const options = {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        };

        // Start watching position
        this.watchId = navigator.geolocation.watchPosition(
            (position) => this.onPositionUpdate(position),
            (error) => this.onPositionError(error),
            options
        );
    }

    /**
     * Stop GPS tracking
     */
    stop() {
        if (!this.isTracking) return;

        console.log('[RealGPS] Stopping GPS tracking');
        this.isTracking = false;

        if (this.watchId !== null) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
        }

        this.updateTrackerUI();
        this.updateJourneyStatus('Created (Not Started)');
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
     * Handle position update from Geolocation API
     */
    async onPositionUpdate(position) {
        const { latitude, longitude, accuracy, speed, heading } = position.coords;
        const timestamp = new Date(position.timestamp);

        console.log(`[RealGPS] Position update: ${latitude.toFixed(6)}, ${longitude.toFixed(6)} (accuracy: ${accuracy.toFixed(0)}m)`);

        // Update accuracy display
        document.getElementById('gps-accuracy').textContent = `${accuracy.toFixed(0)} m`;

        // Throttle updates based on interval
        const now = Date.now();
        if (now - this.lastUpdateTime < this.updateInterval) {
            console.log('[RealGPS] Throttling update');
            return;
        }
        this.lastUpdateTime = now;

        // Calculate distance from last position
        if (this.lastPosition) {
            const distance = this.calculateDistance(
                this.lastPosition.latitude,
                this.lastPosition.longitude,
                latitude,
                longitude
            );
            this.totalDistance += distance;
            
            // Update distance display
            const distanceText = this.totalDistance >= 1000 
                ? `${(this.totalDistance / 1000).toFixed(2)} km`
                : `${this.totalDistance.toFixed(0)} m`;
            document.getElementById('distance-traveled').textContent = distanceText;
        }

        // Calculate speed (if not provided by device)
        let calculatedSpeed = speed;
        if (calculatedSpeed === null && this.lastPosition) {
            const timeDiff = (timestamp - this.lastPosition.timestamp) / 1000; // seconds
            if (timeDiff > 0) {
                const distance = this.calculateDistance(
                    this.lastPosition.latitude,
                    this.lastPosition.longitude,
                    latitude,
                    longitude
                );
                calculatedSpeed = distance / timeDiff; // m/s
            }
        }

        // Calculate bearing (if not provided)
        let calculatedBearing = heading;
        if (calculatedBearing === null && this.lastPosition) {
            calculatedBearing = this.calculateBearing(
                this.lastPosition.latitude,
                this.lastPosition.longitude,
                latitude,
                longitude
            );
        }

        // Update speed display
        if (calculatedSpeed !== null) {
            const speedKmh = (calculatedSpeed * 3.6).toFixed(1);
            document.getElementById('current-speed').textContent = `${speedKmh} km/h`;
        }

        // Create GPS point
        const gpsPoint = {
            lat: latitude,
            lng: longitude,
            timestamp: timestamp.toISOString(),
            speed: calculatedSpeed || 0,
            bearing: calculatedBearing || 0,
            accuracy: accuracy
        };

        // Add to trail
        this.gpsTrail.push([longitude, latitude]);

        // Update map visualization
        if (window.mapManager) {
            mapManager.updateCurrentPosition(latitude, longitude);
            mapManager.updateGPSTrail(this.gpsTrail);
        }

        // Send to backend
        try {
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
            document.getElementById('points-sent').textContent = this.pointsSent;

            console.log(`[RealGPS] Sent GPS point ${this.pointsSent}`);

        } catch (error) {
            console.error('[RealGPS] Failed to send GPS point:', error);
        }

        // Update last position
        this.lastPosition = {
            latitude,
            longitude,
            timestamp
        };
    }

    /**
     * Handle position error
     */
    onPositionError(error) {
        console.error('[RealGPS] Position error:', error);
        
        let message = 'GPS error: ';
        switch (error.code) {
            case error.PERMISSION_DENIED:
                message += 'Location permission denied';
                break;
            case error.POSITION_UNAVAILABLE:
                message += 'Location information unavailable';
                break;
            case error.TIMEOUT:
                message += 'Location request timed out';
                break;
            default:
                message += 'Unknown error';
        }
        
        alert(message);
        this.stop();
    }

    /**
     * Calculate distance between two GPS points using Haversine formula
     */
    calculateDistance(lat1, lng1, lat2, lng2) {
        const R = 6371000; // Earth's radius in meters
        const toRad = deg => deg * Math.PI / 180;
        
        const dLat = toRad(lat2 - lat1);
        const dLng = toRad(lng2 - lng1);
        
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
                  Math.sin(dLng / 2) * Math.sin(dLng / 2);
        
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        
        return R * c; // Distance in meters
    }

    /**
     * Calculate bearing between two GPS points
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
     * Update tracker UI state
     */
    updateTrackerUI() {
        const startBtn = document.getElementById('start-real-gps-btn');
        const stopBtn = document.getElementById('stop-real-gps-btn');

        if (this.isTracking) {
            startBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }
    }

    /**
     * Reset tracker
     */
    reset() {
        this.stop();
        this.journeyId = null;
        this.lastPosition = null;
        this.pointsSent = 0;
        this.totalDistance = 0;
        this.gpsTrail = [];

        document.getElementById('gps-accuracy').textContent = '-';
        document.getElementById('current-speed').textContent = '-';
        document.getElementById('distance-traveled').textContent = '0 m';

        // Update journey status when resetting
        this.updateJourneyStatus('Created (Not Started)');
    }

    /**
     * Get current location once (for setting origin)
     */
    async getCurrentLocation() {
        return new Promise((resolve, reject) => {
            if (!this.isAvailable()) {
                reject(new Error('Geolocation not supported'));
                return;
            }

            navigator.geolocation.getCurrentPosition(
                (position) => {
                    resolve({
                        lat: position.coords.latitude,
                        lng: position.coords.longitude,
                        accuracy: position.coords.accuracy
                    });
                },
                (error) => {
                    reject(error);
                },
                {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0
                }
            );
        });
    }
}

// Create global real GPS tracker instance
const realGPSTracker = new RealGPSTracker();
window.realGPSTracker = realGPSTracker;

// Initialize tracker controls
document.addEventListener('DOMContentLoaded', () => {
    // Start real GPS button
    document.getElementById('start-real-gps-btn').addEventListener('click', () => {
        realGPSTracker.start();
    });

    // Stop real GPS button
    document.getElementById('stop-real-gps-btn').addEventListener('click', () => {
        realGPSTracker.stop();
    });
});
