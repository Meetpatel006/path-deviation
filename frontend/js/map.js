// Map Manager
class MapManager {
    constructor() {
        this.map = null;
        this.markers = {
            origin: null,
            destination: null,
            current: null
        };
        this.smoothedPosition = null;
        this.routes = [];
        this.currentJourney = null;
        this.gpsTrail = [];
        this.pickingMode = null; // 'origin' or 'destination'
        this.clickHandler = null;
        this.isReady = false;
        this.readyCallbacks = [];
    }

    /**
     * Initialize Mapbox map
     */
    init() {
        try {
            // Require a public Mapbox token; sk.* tokens are secret-only and will fail in browsers
            if (!CONFIG.MAPBOX_TOKEN || !CONFIG.MAPBOX_TOKEN.startsWith('pk.')) {
                console.error('[Map] Missing or invalid Mapbox public token (needs to start with pk.)');
                alert('Map cannot load: please set a public Mapbox token (starts with pk.) in frontend/js/config.js.');
                return;
            }

            mapboxgl.accessToken = CONFIG.MAPBOX_TOKEN;

            console.log('[Map] Initializing map...');

            this.map = new mapboxgl.Map({
                container: 'map',
                style: CONFIG.MAP_STYLE,
                center: CONFIG.DEFAULT_CENTER,
                zoom: CONFIG.DEFAULT_ZOOM
            });

            // Add navigation controls
            this.map.addControl(new mapboxgl.NavigationControl(), 'top-right');

            // Add scale
            this.map.addControl(new mapboxgl.ScaleControl(), 'bottom-left');

            this.map.on('error', (event) => {
                console.error('[Map] Error event:', event.error);
            });

            this.map.on('load', () => {
                console.log('[Map] ✓ Map loaded successfully and ready!');
                this.isReady = true;

                // Hide loading indicator
                const loadingEl = document.getElementById('map-loading');
                if (loadingEl) {
                    loadingEl.style.display = 'none';
                }

                // Call any pending callbacks
                this.readyCallbacks.forEach(callback => {
                    try {
                        callback();
                    } catch (error) {
                        console.error('[Map] Callback error:', error);
                    }
                });
                this.readyCallbacks = [];
            });

            console.log('[Map] Map initialization started');
        } catch (error) {
            console.error('[Map] Failed to initialize:', error);
            alert('Failed to initialize map. Please check your internet connection and Mapbox token.');
        }
    }

    /**
     * Execute callback when map is ready
     */
    onReady(callback) {
        if (this.isReady) {
            callback();
        } else {
            this.readyCallbacks.push(callback);
            console.log('[Map] Callback queued, waiting for map to load...');
        }
    }

    /**
     * Display routes on map
     */
    displayRoutes(routes, origin, destination) {
        if (!this.map) {
            console.warn('[Map] Cannot display routes before map is initialized');
            return;
        }

        if (!routes || !Array.isArray(routes) || routes.length === 0) {
            console.warn('[Map] Invalid or empty routes array');
            return;
        }

        // Validate origin and destination
        if (!origin || typeof origin.lat !== 'number' || typeof origin.lng !== 'number') {
            console.warn('[Map] Invalid origin coordinates:', origin);
            return;
        }

        if (!destination || typeof destination.lat !== 'number' || typeof destination.lng !== 'number') {
            console.warn('[Map] Invalid destination coordinates:', destination);
            return;
        }

        this.clearRoutes();
        this.routes = routes;

        const renderRoutes = () => {
            // Add origin marker
            if (this.markers.origin) {
                this.markers.origin.remove();
            }
            this.markers.origin = new mapboxgl.Marker({ color: '#27ae60' })
                .setLngLat([origin.lng, origin.lat])
                .setPopup(new mapboxgl.Popup().setHTML('<b>Origin</b>'))
                .addTo(this.map);

            // Add destination marker
            if (this.markers.destination) {
                this.markers.destination.remove();
            }
            this.markers.destination = new mapboxgl.Marker({ color: '#e74c3c' })
                .setLngLat([destination.lng, destination.lat])
                .setPopup(new mapboxgl.Popup().setHTML('<b>Destination</b>'))
                .addTo(this.map);

            // Add route lines
            routes.forEach((route, index) => {
                // Handle both formats: geometry as array (backend) or as GeoJSON object
                const coordinates = Array.isArray(route.geometry)
                    ? route.geometry
                    : (route.geometry?.coordinates || null);

                if (!route || !coordinates || coordinates.length < 2) {
                    console.warn(`[Map] Invalid route at index ${index}`);
                    return;
                }

                const sourceId = `route-${index}`;
                const layerId = `route-layer-${index}`;

                // Create GeoJSON geometry from coordinates
                const geojsonGeometry = {
                    type: 'Feature',
                    geometry: {
                        type: 'LineString',
                        coordinates: coordinates
                    }
                };

                // Add source
                this.map.addSource(sourceId, {
                    type: 'geojson',
                    data: geojsonGeometry
                });

                // Add layer
                this.map.addLayer({
                    id: layerId,
                    type: 'line',
                    source: sourceId,
                    layout: {
                        'line-join': 'round',
                        'line-cap': 'round'
                    },
                    paint: {
                        'line-color': CONFIG.ROUTE_COLORS[index % CONFIG.ROUTE_COLORS.length],
                        'line-width': 4,
                        'line-opacity': 0.7
                    }
                });
            });

            // Fit map to show all routes
            this.fitToRoutes(routes);

            console.log(`[Map] Displayed ${routes.length} route(s)`);
        };

        // If style is not ready yet, wait to avoid Mapbox internal errors
        if (!this.map.isStyleLoaded()) {
            this.map.once('load', renderRoutes);
            return;
        }

        renderRoutes();
    }

    /**
     * Fit map bounds to show all routes
     */
    fitToRoutes(routes) {
        if (!routes || routes.length === 0) return;

        const bounds = new mapboxgl.LngLatBounds();

        routes.forEach(route => {
            // Handle both formats: geometry as array (backend) or as GeoJSON object
            const coordinates = Array.isArray(route?.geometry)
                ? route.geometry
                : (route?.geometry?.coordinates || []);

            coordinates.forEach(coord => {
                if (coord && coord.length >= 2) {
                    bounds.extend(coord);
                }
            });
        });

        this.map.fitBounds(bounds, {
            padding: 50,
            maxZoom: 14
        });
    }

    /**
     * Update current position marker
     */
    updateCurrentPosition(lat, lng) {
        const smoothingEnabled = CONFIG.POSITION_SMOOTHING_ENABLED !== false;
        const smoothingAlpha = CONFIG.POSITION_SMOOTHING_ALPHA || 0.12;
        const minDistance = CONFIG.POSITION_MIN_DISTANCE_METERS || 0;

        let targetLat = lat;
        let targetLng = lng;

        if (smoothingEnabled) {
            if (!this.smoothedPosition) {
                this.smoothedPosition = { lat: targetLat, lng: targetLng };
            } else {
                if (minDistance > 0) {
                    const dist = this.calculateDistance(
                        this.smoothedPosition.lat,
                        this.smoothedPosition.lng,
                        targetLat,
                        targetLng
                    );
                    if (dist < minDistance) {
                        targetLat = this.smoothedPosition.lat;
                        targetLng = this.smoothedPosition.lng;
                    }
                }

                this.smoothedPosition.lat =
                    this.smoothedPosition.lat + smoothingAlpha * (targetLat - this.smoothedPosition.lat);
                this.smoothedPosition.lng =
                    this.smoothedPosition.lng + smoothingAlpha * (targetLng - this.smoothedPosition.lng);
            }

            targetLat = this.smoothedPosition.lat;
            targetLng = this.smoothedPosition.lng;
        }

        if (!this.markers.current) {
            // Create current position marker with animated pulse
            const el = document.createElement('div');
            el.className = 'current-position-marker';
            el.innerHTML = `
                <div class="pulse-ring"></div>
                <div class="pulse-dot"></div>
            `;

            this.markers.current = new mapboxgl.Marker({ element: el })
                .setLngLat([targetLng, targetLat])
                .addTo(this.map);
        } else {
            // Animate position update
            this.markers.current.setLngLat([targetLng, targetLat]);
        }

        console.log(`[Map] Updated position: ${targetLat.toFixed(4)}, ${targetLng.toFixed(4)}`);
    }

    /**
     * Calculate distance between two points in meters (Haversine formula)
     */
    calculateDistance(lat1, lng1, lat2, lng2) {
        const R = 6371000; // Earth radius in meters
        const toRad = deg => deg * Math.PI / 180;
        const phi1 = toRad(lat1);
        const phi2 = toRad(lat2);
        const dPhi = toRad(lat2 - lat1);
        const dLambda = toRad(lng2 - lng1);

        const a = Math.sin(dPhi / 2) * Math.sin(dPhi / 2) +
            Math.cos(phi1) * Math.cos(phi2) *
            Math.sin(dLambda / 2) * Math.sin(dLambda / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

        return R * c;
    }

    /**
     * Highlight route based on probability
     */
    highlightRoute(routeIndex, probability) {
        const layerId = `route-layer-${routeIndex}`;

        if (this.map.getLayer(layerId)) {
            // Increase width and opacity for likely routes
            const width = probability > 0.5 ? 6 : 4;
            const opacity = 0.5 + (probability * 0.5); // 0.5 to 1.0

            this.map.setPaintProperty(layerId, 'line-width', width);
            this.map.setPaintProperty(layerId, 'line-opacity', opacity);
        }
    }

    /**
     * Clear all routes from map
     */
    clearRoutes() {
        if (!this.routes || !Array.isArray(this.routes)) {
            this.routes = [];
            return;
        }

        this.routes.forEach((route, index) => {
            const sourceId = `route-${index}`;
            const layerId = `route-layer-${index}`;

            if (this.map && this.map.getLayer(layerId)) {
                this.map.removeLayer(layerId);
            }
            if (this.map && this.map.getSource(sourceId)) {
                this.map.removeSource(sourceId);
            }
        });

        this.routes = [];
    }

    /**
     * Clear all markers
     */
    clearMarkers() {
        if (this.markers && typeof this.markers === 'object') {
            Object.values(this.markers).forEach(marker => {
                if (marker && typeof marker.remove === 'function') {
                    marker.remove();
                }
            });
        }

        this.markers = {
            origin: null,
            destination: null,
            current: null
        };
    }

    /**
     * Reset map
     */
    reset() {
        this.clearRoutes();
        this.clearMarkers();
        this.clearGPSTrail();
        this.currentJourney = null;
        this.stopPickingLocation();
        this.smoothedPosition = null;

        this.map.flyTo({
            center: CONFIG.DEFAULT_CENTER,
            zoom: CONFIG.DEFAULT_ZOOM
        });

        console.log('[Map] Reset');
    }

    /**
     * Update GPS trail on map
     */
    updateGPSTrail(trailCoordinates) {
        if (!this.map || !this.map.isStyleLoaded()) return;

        this.gpsTrail = trailCoordinates;

        const sourceId = 'gps-trail';
        const layerId = 'gps-trail-layer';

        // Create GeoJSON line
        const geojson = {
            type: 'Feature',
            geometry: {
                type: 'LineString',
                coordinates: trailCoordinates
            }
        };

        // Add or update source
        if (this.map.getSource(sourceId)) {
            this.map.getSource(sourceId).setData(geojson);
        } else {
            this.map.addSource(sourceId, {
                type: 'geojson',
                data: geojson
            });

            // Add layer with animated dash pattern
            this.map.addLayer({
                id: layerId,
                type: 'line',
                source: sourceId,
                layout: {
                    'line-join': 'round',
                    'line-cap': 'round'
                },
                paint: {
                    'line-color': '#3498db',
                    'line-width': 4,
                    'line-opacity': 0.8
                }
            });
        }

        console.log(`[Map] Updated GPS trail (${trailCoordinates.length} points)`);
    }

    /**
     * Clear GPS trail
     */
    clearGPSTrail() {
        const sourceId = 'gps-trail';
        const layerId = 'gps-trail-layer';

        if (this.map.getLayer(layerId)) {
            this.map.removeLayer(layerId);
        }
        if (this.map.getSource(sourceId)) {
            this.map.removeSource(sourceId);
        }

        this.gpsTrail = [];
    }

    /**
     * Enable location picking mode
     */
    startPickingLocation(mode, callback) {
        this.pickingMode = mode;
        this.map.getCanvas().style.cursor = 'crosshair';

        // Remove previous handler if exists
        if (this.clickHandler) {
            this.map.off('click', this.clickHandler);
        }

        // Create new click handler
        this.clickHandler = (e) => {
            const { lng, lat } = e.lngLat;
            callback({ lat, lng });
            this.stopPickingLocation();
        };

        this.map.on('click', this.clickHandler);

        console.log(`[Map] Started picking ${mode}`);
    }

    /**
     * Disable location picking mode
     */
    stopPickingLocation() {
        if (this.clickHandler) {
            this.map.off('click', this.clickHandler);
            this.clickHandler = null;
        }
        this.pickingMode = null;
        this.map.getCanvas().style.cursor = '';
    }
}

// Create global map manager instance
const mapManager = new MapManager();
window.mapManager = mapManager;  // Make it globally accessible

console.log('[Map] MapManager instance created');

// Initialize map when page loads
window.addEventListener('DOMContentLoaded', () => {
    console.log('[Map] DOMContentLoaded - initializing map');
    mapManager.init();
});
