// Configuration
const CONFIG = {
    // API endpoints
    API_BASE_URL: 'http://localhost:8000',
    WS_BASE_URL: 'ws://localhost:8000',
    
    // Mapbox public access token (must start with "pk.")
    // Do NOT use secret/server tokens ("sk.") in the browser – they will fail and leak credentials.
    MAPBOX_TOKEN: 'pk.eyJ1IjoicmVkcmVwdGVyIiwiYSI6ImNtZmgza2ludTA2eXcybHF3OTJjcnp5d3MifQ.nu__SNPTTw3yJMF0jRgE6g',
    
    // Map settings
    MAP_STYLE: 'mapbox://styles/mapbox/streets-v12',
    DEFAULT_CENTER: [73.8786, 18.5246], // [lng, lat] - Pune, India
    DEFAULT_ZOOM: 12,
    
    // Route colors
    ROUTE_COLORS: [
        '#3498db',  // Blue - Route 0
        '#e74c3c',  // Red - Route 1
        '#2ecc71',  // Green - Route 2
    ],
    
    // GPS Simulator settings
    SIM_DEFAULT_SPEED: 20,      // m/s
    SIM_DEFAULT_INTERVAL: 2000, // ms
};

// Helper function to get full API URL
function getApiUrl(endpoint) {
    return `${CONFIG.API_BASE_URL}${endpoint}`;
}

// Helper function to get full WebSocket URL
function getWsUrl(endpoint) {
    return `${CONFIG.WS_BASE_URL}${endpoint}`;
}
