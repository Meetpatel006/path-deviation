// UI Manager - Handles UI updates and interactions

/**
 * Update deviation status display
 */
function updateDeviationStatus(deviation) {
    if (!deviation) {
        console.warn('[UI] Invalid deviation data');
        return;
    }

    // Spatial status
    const spatialEl = document.getElementById('spatial-status');
    if (spatialEl && deviation.spatial) {
        spatialEl.textContent = deviation.spatial;
        spatialEl.className = `value badge ${deviation.spatial.toLowerCase().replace('_', '-')}`;
    }

    // Temporal status
    const temporalEl = document.getElementById('temporal-status');
    if (temporalEl && deviation.temporal) {
        temporalEl.textContent = deviation.temporal;
        temporalEl.className = `value badge ${deviation.temporal.toLowerCase().replace('_', '-')}`;
    }

    // Directional status
    const directionalEl = document.getElementById('directional-status');
    if (directionalEl && deviation.directional) {
        directionalEl.textContent = deviation.directional;
        directionalEl.className = `value badge ${deviation.directional.toLowerCase().replace('_', '-')}`;
    }

    // Severity
    const severityEl = document.getElementById('severity');
    if (severityEl && deviation.severity) {
        severityEl.textContent = deviation.severity;
        severityEl.className = `value badge ${deviation.severity}`;
    }
}

/**
 * Update route probabilities display
 */
function updateRouteProbabilities(routeProbs) {
    const container = document.getElementById('route-probs-container');
    if (!container) {
        console.warn('[UI] Route probabilities container not found');
        return;
    }

    container.innerHTML = '';

    if (!routeProbs || typeof routeProbs !== 'object') {
        console.warn('[UI] Invalid route probabilities data:', routeProbs);
        return;
    }

    Object.entries(routeProbs).forEach(([routeKey, probability]) => {
        const routeIndex = parseInt(routeKey.replace('route_', ''));
        const percent = (probability * 100).toFixed(0);

        const item = document.createElement('div');
        item.className = 'route-prob-item';
        item.innerHTML = `
            <span class="route-prob-label" style="color: ${CONFIG.ROUTE_COLORS[routeIndex % CONFIG.ROUTE_COLORS.length]}">
                Route ${routeIndex}
            </span>
            <div class="route-prob-bar">
                <div class="route-prob-fill" style="width: ${percent}%; background: ${CONFIG.ROUTE_COLORS[routeIndex % CONFIG.ROUTE_COLORS.length]}">
                    ${percent}%
                </div>
            </div>
        `;

        container.appendChild(item);
    });
}

/**
 * Add deviation alert
 */
function addAlert(deviation, timestamp) {
    const alertsContainer = document.getElementById('alerts-container');

    // Remove "no alerts" message
    const noAlerts = alertsContainer.querySelector('.no-alerts');
    if (noAlerts) {
        noAlerts.remove();
    }

    // Create alert element
    const alert = document.createElement('div');
    alert.className = `alert ${deviation.severity}`;

    const time = new Date(timestamp).toLocaleTimeString();

    alert.innerHTML = `
        <strong>${deviation.severity.toUpperCase()} Deviation Detected</strong><br>
        Spatial: ${deviation.spatial} | 
        Temporal: ${deviation.temporal} | 
        Direction: ${deviation.directional}
        <div class="alert-time">${time}</div>
    `;

    // Add to top of list
    alertsContainer.insertBefore(alert, alertsContainer.firstChild);

    // Keep only last 10 alerts
    while (alertsContainer.children.length > 10) {
        alertsContainer.removeChild(alertsContainer.lastChild);
    }
}

/**
 * Clear all alerts
 */
function clearAlerts() {
    const alertsContainer = document.getElementById('alerts-container');
    alertsContainer.innerHTML = '<p class="no-alerts">No deviations detected</p>';
}

/**
 * Show journey status panel
 */
function showJourneyStatus(journeyData) {
    // Hide setup form
    document.getElementById('journey-setup').style.display = 'none';

    // Show status panel
    document.getElementById('journey-status').style.display = 'block';
    document.getElementById('gps-simulator').style.display = 'block';

    // Also show test scenario section if it exists
    const testScenarioSection = document.getElementById('test-scenario');
    if (testScenarioSection) {
        testScenarioSection.style.display = 'block';
    }

    // Update journey ID
    document.getElementById('journey-id').textContent = journeyData.journey_id.substring(0, 8) + '...';

    // Update journey status text
    const journeyStatusText = document.getElementById('journey-status-text');
    if (journeyStatusText) {
        journeyStatusText.textContent = 'Created (Not Started)';
        journeyStatusText.className = 'value badge normal';
    }

    // Reset status
    document.getElementById('current-location').textContent = '-';
    document.getElementById('current-speed').textContent = '-';
    document.getElementById('distance-traveled').textContent = '0 m';
    document.getElementById('gps-accuracy').textContent = '-';
    document.getElementById('spatial-status').textContent = '-';
    document.getElementById('temporal-status').textContent = '-';
    document.getElementById('directional-status').textContent = '-';
    document.getElementById('severity').textContent = '-';
    document.getElementById('route-probs-container').innerHTML = '';

    clearAlerts();
}

/**
 * Hide journey status panel
 */
function hideJourneyStatus() {
    // Show setup form
    document.getElementById('journey-setup').style.display = 'block';

    // Hide status panel
    document.getElementById('journey-status').style.display = 'none';
    document.getElementById('gps-simulator').style.display = 'none';

    // Also hide test scenario section if it exists
    const testScenarioSection = document.getElementById('test-scenario');
    if (testScenarioSection) {
        testScenarioSection.style.display = 'none';
    }
}

/**
 * Parse lat,lng input
 */
function parseLatLng(input) {
    const parts = input.split(',').map(s => s.trim());
    if (parts.length !== 2) {
        throw new Error('Invalid format. Use: lat, lng or location name');
    }

    const lat = parseFloat(parts[0]);
    const lng = parseFloat(parts[1]);

    if (isNaN(lat) || isNaN(lng)) {
        throw new Error('Invalid coordinates');
    }

    return { lat, lng };
}

/**
 * Resolve location input (coordinates or place name)
 */
async function resolveLocation(input, inputElement) {
    // Validate input
    if (!input || typeof input !== 'string' || input.trim() === '') {
        throw new Error('Location input is required');
    }

    const trimmedInput = input.trim();

    // First check if coordinates are stored in data attributes (from autocomplete)
    if (inputElement && inputElement.dataset.lat && inputElement.dataset.lng) {
        const coords = {
            lat: parseFloat(inputElement.dataset.lat),
            lng: parseFloat(inputElement.dataset.lng)
        };

        // Validate parsed coordinates
        if (isNaN(coords.lat) || isNaN(coords.lng)) {
            console.error('[UI] Invalid stored coordinates:', inputElement.dataset);
            throw new Error('Invalid stored coordinates');
        }

        console.log('[UI] Using stored coordinates:', coords);
        return coords;
    }

    // Try to use geocoding service if available
    if (window.geocodingService) {
        try {
            const coords = await geocodingService.resolveLocation(trimmedInput);

            // Validate returned coordinates
            if (!coords || typeof coords !== 'object' || !coords.hasOwnProperty('lat') || !coords.hasOwnProperty('lng')) {
                throw new Error('Geocoding returned invalid coordinates');
            }

            if (isNaN(coords.lat) || isNaN(coords.lng)) {
                throw new Error('Geocoding returned NaN coordinates');
            }

            console.log('[UI] Resolved location:', trimmedInput, '=>', coords);
            return coords;
        } catch (error) {
            console.error('[UI] Geocoding failed:', error);
            // Fallback to manual parsing
            return parseLatLng(trimmedInput);
        }
    }

    // Fallback to manual parsing
    return parseLatLng(trimmedInput);
}

/**
 * Show loading state
 */
function setLoading(elementId, loading) {
    const element = document.getElementById(elementId);
    const button = element.querySelector('button[type="submit"]');

    if (button) {
        button.disabled = loading;
        button.textContent = loading ? 'Loading...' : 'Start Journey';
    }
}

/**
 * Show error message
 */
function showError(message) {
    alert(`Error: ${message}`);
    console.error('[UI] Error:', message);
}

/**
 * Format timestamp
 */
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
}

/**
 * Set coordinate input value
 */
function setCoordinateInput(inputId, lat, lng) {
    const input = document.getElementById(inputId);
    input.value = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
}

// Initialize UI event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Pick origin on map
    document.getElementById('pick-origin-btn').addEventListener('click', () => {
        mapManager.startPickingLocation('origin', (coords) => {
            setCoordinateInput('origin', coords.lat, coords.lng);
        });
    });

    // Pick destination on map
    document.getElementById('pick-destination-btn').addEventListener('click', () => {
        mapManager.startPickingLocation('destination', (coords) => {
            setCoordinateInput('destination', coords.lat, coords.lng);
        });
    });

    // Use current location as origin
    document.getElementById('use-current-location-btn').addEventListener('click', async () => {
        try {
            const location = await realGPSTracker.getCurrentLocation();
            setCoordinateInput('origin', location.lat, location.lng);

            // Also update map center
            mapManager.map.flyTo({
                center: [location.lng, location.lat],
                zoom: 14
            });
        } catch (error) {
            console.error('[UI] Failed to get current location:', error);
            showError('Failed to get current location. Please ensure location permissions are enabled.');
        }
    });

    // Start journey form
    document.getElementById('start-journey-form').addEventListener('submit', async (e) => {
        e.preventDefault();

        try {
            setLoading('start-journey-form', true);

            // Get input elements
            const originInput = document.getElementById('origin');
            const destinationInput = document.getElementById('destination');
            const travelMode = document.getElementById('travel-mode').value;

            // Resolve locations (handles both coordinates and place names)
            console.log('[UI] Resolving origin:', originInput.value);
            const origin = await resolveLocation(originInput.value, originInput);
            console.log('[UI] ✓ Origin resolved:', origin);

            if (!origin || !origin.lat || !origin.lng) {
                throw new Error('Failed to resolve origin location');
            }

            console.log('[UI] Resolving destination:', destinationInput.value);
            const destination = await resolveLocation(destinationInput.value, destinationInput);
            console.log('[UI] ✓ Destination resolved:', destination);

            if (!destination || !destination.lat || !destination.lng) {
                throw new Error('Failed to resolve destination location');
            }

            console.log('[UI] Starting journey:', { origin, destination, travelMode });

            // Start journey
            const response = await fetch(getApiUrl('/api/journey/start'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    origin,
                    destination,
                    travel_mode: travelMode
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('[UI] Journey started:', data);

            // Validate response data
            if (!data.routes || !Array.isArray(data.routes) || data.routes.length === 0) {
                throw new Error('Invalid journey response: no routes available');
            }

            // Wait for map to be ready, then display routes
            if (window.mapManager) {
                console.log('[UI] Map manager found, waiting for map to be ready...');

                mapManager.onReady(() => {
                    console.log('[UI] Map is ready, displaying routes');

                    try {
                        mapManager.displayRoutes(data.routes, origin, destination);

                        // Show journey status
                        showJourneyStatus(data);

                        // Connect to WebSocket
                        if (window.wsClient) {
                            wsClient.connect(data.journey_id);
                        } else {
                            console.warn('[UI] WebSocket client not available');
                        }

                        // Initialize GPS simulator with validation (but don't auto-start)
                        if (window.gpsSimulator) {
                            if (data.routes && Array.isArray(data.routes) && data.routes.length > 0) {
                                const primaryRoute = data.routes[0];
                                console.log('[UI] Initializing GPS simulator with primary route');

                                if (primaryRoute && primaryRoute.geometry && Array.isArray(primaryRoute.geometry)) {
                                    try {
                                        gpsSimulator.init(data.journey_id, primaryRoute);

                                        console.log('[UI] ✓ GPS simulator initialized');
                                        // NOTE: Not auto-starting simulator anymore - user will start manually

                                        // Double-check that simulator is not running
                                        if (gpsSimulator.isRunning) {
                                            console.warn('[UI] Warning: Simulator was running after init, stopping it');
                                            gpsSimulator.stop();
                                        }
                                    } catch (error) {
                                        console.error('[UI] Failed to initialize GPS simulator:', error);
                                        throw error; // Re-throw to be caught by outer catch
                                    }
                                } else {
                                    console.error('[UI] Primary route has invalid or missing geometry');
                                    throw new Error('Primary route has no valid geometry array');
                                }
                            } else {
                                console.error('[UI] No routes available for GPS simulator');
                                throw new Error('No routes available from backend');
                            }
                        } else {
                            console.warn('[UI] GPS simulator not available');
                        }

                        // Initialize real GPS tracker
                        if (window.realGPSTracker) {
                            realGPSTracker.init(data.journey_id);
                        }

                        // Store journey in app state
                        if (window.app) {
                            app.currentJourney = data.journey_id;
                        }

                        console.log('[UI] ✓ Journey fully initialized');
                    } catch (innerError) {
                        console.error('[UI] Error during journey initialization:', innerError);
                        showError('Failed to initialize journey: ' + innerError.message);
                    }
                });
            } else {
                console.error('[UI] Map manager not found on window object!');
                console.error('[UI] window.mapManager:', window.mapManager);
                console.error('[UI] Checking all scripts loaded...');
                throw new Error('Map manager not available. Please refresh the page and check console.');
            }

        } catch (error) {
            showError(error.message);
        } finally {
            setLoading('start-journey-form', false);
        }
    });

    // Complete journey button
    document.getElementById('complete-journey-btn').addEventListener('click', async () => {
        if (!wsClient.journeyId) return;

        try {
            // Stop simulator if running
            if (window.gpsSimulator && gpsSimulator.isRunning) {
                gpsSimulator.stop();
            }

            // Stop real GPS tracker if running
            if (window.realGPSTracker && realGPSTracker.isTracking) {
                realGPSTracker.stop();
            }

            // Complete journey
            const response = await fetch(
                getApiUrl(`/api/journey/${wsClient.journeyId}/complete`),
                { method: 'PUT' }
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            console.log('[UI] Journey completed');

            // Disconnect WebSocket
            wsClient.disconnect();

            // Reset UI
            hideJourneyStatus();
            mapManager.reset();

            // Reset trackers
            if (window.gpsSimulator) {
                gpsSimulator.reset();
            }
            if (window.realGPSTracker) {
                realGPSTracker.reset();
            }

        } catch (error) {
            showError(error.message);
        }
    });
});
