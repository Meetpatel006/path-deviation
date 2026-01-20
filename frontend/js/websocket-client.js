// WebSocket Client Manager
class WebSocketClient {
    constructor() {
        this.ws = null;
        this.journeyId = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        this.messageHandlers = [];
        this.totalDistance = 0;
        this.lastLocation = null;
    }

    /**
     * Connect to WebSocket
     */
    connect(journeyId) {
        if (this.connected) {
            console.log('[WebSocket] Already connected');
            return;
        }

        this.journeyId = journeyId;
        const wsUrl = getWsUrl(`/ws/journey/${journeyId}?client_id=web_client`);

        console.log(`[WebSocket] Connecting to ${wsUrl}`);

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => this.onOpen();
            this.ws.onmessage = (event) => this.onMessage(event);
            this.ws.onerror = (error) => this.onError(error);
            this.ws.onclose = () => this.onClose();
        } catch (error) {
            console.error('[WebSocket] Connection error:', error);
            this.updateConnectionStatus(false);
        }
    }

    /**
     * Handle WebSocket open
     */
    onOpen() {
        console.log('[WebSocket] Connected');
        this.connected = true;
        this.reconnectAttempts = 0;
        this.updateConnectionStatus(true);

        // Reset stats on new connection
        this.totalDistance = 0;
        this.lastLocation = null;
    }

    /**
     * Handle incoming messages
     */
    onMessage(event) {
        try {
            const message = JSON.parse(event.data);
            console.log('[WebSocket] Received:', message.type);

            // Call all registered handlers
            if (this.messageHandlers && Array.isArray(this.messageHandlers)) {
                this.messageHandlers.forEach(handler => {
                    try {
                        handler(message);
                    } catch (error) {
                        console.error('[WebSocket] Handler error:', error);
                    }
                });
            }

            // Handle specific message types
            switch (message.type) {
                case 'connection_ack':
                    this.handleConnectionAck(message);
                    break;
                case 'gps_update':
                    this.handleGpsUpdate(message);
                    break;
                case 'deviation_update':
                    this.handleDeviationUpdate(message);
                    break;
                case 'batch_processed':
                    this.handleBatchProcessed(message);
                    break;
                case 'ping':
                    this.handlePing(message);
                    break;
                case 'error':
                    this.handleError(message);
                    break;
                default:
                    console.warn('[WebSocket] Unknown message type:', message.type);
            }
        } catch (error) {
            console.error('[WebSocket] Failed to parse message:', error);
        }
    }

    /**
     * Handle WebSocket error
     */
    onError(error) {
        console.error('[WebSocket] Error:', error);
        // Debug: show error to user
        alert('WebSocket Error: ' + (error.message || 'Connection failed'));
    }

    /**
     * Handle WebSocket close
     */
    onClose() {
        console.log('[WebSocket] Disconnected');
        this.connected = false;
        this.ws = null;
        this.updateConnectionStatus(false);

        // Attempt reconnection
        if (this.reconnectAttempts < this.maxReconnectAttempts && this.journeyId) {
            this.reconnectAttempts++;
            console.log(`[WebSocket] Reconnecting in ${this.reconnectDelay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

            setTimeout(() => {
                this.connect(this.journeyId);
            }, this.reconnectDelay);
        }
    }

    /**
     * Handle connection acknowledgment
     */
    handleConnectionAck(message) {
        console.log('[WebSocket] Connection acknowledged:', message.message);
    }

    /**
     * Handle GPS update
     */
    handleGpsUpdate(message) {
        if (!message || !message.location) {
            console.warn('[WebSocket] Invalid GPS update message');
            return;
        }

        const { lat, lng, speed, accuracy } = message.location;

        // Update map position
        if (window.mapManager && mapManager.map) {
            mapManager.updateCurrentPosition(lat, lng);
        }

        // --- Update Stats ---

        // 1. Current Location
        const locationEl = document.getElementById('current-location');
        if (locationEl) {
            locationEl.textContent = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
        }

        // 2. Current Speed
        const speedEl = document.getElementById('current-speed');
        if (speedEl) {
            // Speed comes in m/s usually, convert to useful unit if needed, or keep m/s
            // Displaying as m/s for now as per label, or could be km/h
            // Let's assume m/s for consistency with simulator
            const speedVal = speed !== undefined && speed !== null ? speed.toFixed(1) + ' m/s' : '-';
            console.info('[WebSocket] Updating speed:', speedVal); // DEBUG LOG
            speedEl.textContent = speedVal;
        }

        // 3. Distance Traveled
        if (this.lastLocation) {
            const dist = this.calculateDistance(
                this.lastLocation.lat, this.lastLocation.lng,
                lat, lng
            );
            this.totalDistance += dist;
        }
        this.lastLocation = { lat, lng };

        const distEl = document.getElementById('distance-traveled');
        if (distEl) {
            if (this.totalDistance < 1000) {
                distEl.textContent = `${this.totalDistance.toFixed(0)} m`;
            } else {
                distEl.textContent = `${(this.totalDistance / 1000).toFixed(2)} km`;
            }
        }

        // 4. GPS Accuracy
        const accEl = document.getElementById('gps-accuracy');
        if (accEl) {
            accEl.textContent = accuracy !== undefined && accuracy !== null ? `± ${accuracy.toFixed(1)} m` : '-';
        }
    }

    /**
     * Calculate distance between two points in meters (Haversine formula)
     */
    calculateDistance(lat1, lng1, lat2, lng2) {
        const R = 6371e3; // Earth radius in meters
        const toRad = deg => deg * Math.PI / 180;
        const φ1 = toRad(lat1);
        const φ2 = toRad(lat2);
        const Δφ = toRad(lat2 - lat1);
        const Δλ = toRad(lng2 - lng1);

        const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

        return R * c;
    }

    /**
     * Handle deviation update
     */
    handleDeviationUpdate(message) {
        const { deviation, metrics, route_probabilities } = message;

        // Update deviation status in UI
        if (deviation) {
            updateDeviationStatus(deviation);
        }

        // Update route probabilities
        if (route_probabilities) {
            updateRouteProbabilities(route_probabilities);
        }

        // Add alert if deviation detected
        if (deviation && deviation.severity !== 'normal') {
            addAlert(deviation, message.timestamp);
        }

        // Highlight routes based on probabilities
        if (route_probabilities && typeof route_probabilities === 'object') {
            Object.entries(route_probabilities).forEach(([routeKey, prob]) => {
                const routeIndex = parseInt(routeKey.replace('route_', ''));
                if (window.mapManager) {
                    mapManager.highlightRoute(routeIndex, prob);
                }
            });
        }
    }

    /**
     * Handle batch processed notification
     */
    handleBatchProcessed(message) {
        console.log(`[WebSocket] Batch #${message.batch_number} processed (${message.points_processed} points, map_matched=${message.map_matched})`);

        // Update batch counter if simulator is running
        if (window.gpsSimulator && window.gpsSimulator.isRunning) {
            document.getElementById('current-batch').textContent = message.batch_number;
        }
    }

    /**
     * Handle ping (heartbeat)
     */
    handlePing(message) {
        // Respond with pong
        if (this.connected) {
            this.ws.send(JSON.stringify({
                type: 'pong',
                timestamp: message.timestamp
            }));
        }
    }

    /**
     * Handle error message
     */
    handleError(message) {
        console.error('[WebSocket] Server error:', message.message);
        alert(`Error: ${message.message}`);
    }

    /**
     * Register message handler
     */
    addMessageHandler(handler) {
        this.messageHandlers.push(handler);
    }

    /**
     * Disconnect WebSocket
     */
    disconnect() {
        if (this.ws) {
            console.log('[WebSocket] Disconnecting...');
            this.journeyId = null; // Prevent reconnection
            this.ws.close();
            this.ws = null;
        }
        this.connected = false;
        this.updateConnectionStatus(false);
    }

    /**
     * Update connection status indicator
     */
    updateConnectionStatus(connected) {
        const indicator = document.getElementById('connection-indicator');
        const text = document.getElementById('connection-text');

        if (connected) {
            indicator.classList.remove('disconnected');
            indicator.classList.add('connected');
            text.textContent = 'Connected';
        } else {
            indicator.classList.remove('connected');
            indicator.classList.add('disconnected');
            text.textContent = 'Disconnected';
        }
    }
}

// Create global WebSocket client instance
const wsClient = new WebSocketClient();
window.wsClient = wsClient;  // Make it globally accessible
