// Main Application Entry Point

console.log('GPS Path Deviation Detection System - Frontend v1.0.0');

// Application state
const app = {
    currentJourney: null,
    initialized: false
};

// Initialize application
function initApp() {
    if (app.initialized) return;

    console.log('[App] Initializing...');

    // Check if Mapbox token is configured
    if (CONFIG.MAPBOX_TOKEN === 'sk.eyJ1IjoicmVkcmVwdGVyIiwiYSI6ImNta2xrZ2I1dzA1NGYzZ3NhNmQ1ZzRoMG0ifQ.3qcMqT85bC1wAlnKmmdwuA') {
        console.warn('[App] WARNING: Mapbox token not configured in config.js');
        console.warn('[App] Please add your Mapbox API token to js/config.js');
        
        // Show warning to user
        const warning = document.createElement('div');
        warning.style.cssText = 'position:fixed;top:60px;left:50%;transform:translateX(-50%);background:#f39c12;color:white;padding:1rem 2rem;border-radius:4px;z-index:1000;box-shadow:0 2px 8px rgba(0,0,0,0.2);';
        warning.innerHTML = '<strong>⚠️ Mapbox Token Required</strong><br>Please configure MAPBOX_TOKEN in js/config.js';
        document.body.appendChild(warning);
        
        setTimeout(() => warning.remove(), 10000);
    }

    app.initialized = true;
    console.log('[App] Initialized successfully');
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

// Handle page visibility changes
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        console.log('[App] Page hidden');
    } else {
        console.log('[App] Page visible');
        // Reconnect WebSocket if needed
        if (app.currentJourney && !wsClient.connected) {
            wsClient.connect(app.currentJourney);
        }
    }
});

// Handle window unload
window.addEventListener('beforeunload', () => {
    if (wsClient.connected) {
        wsClient.disconnect();
    }
    if (gpsSimulator.isRunning) {
        gpsSimulator.stop();
    }
});

// Export app for debugging
window.app = app;
