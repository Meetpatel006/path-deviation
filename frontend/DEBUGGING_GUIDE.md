# Debugging Guide - GPS Path Deviation System

## Quick Diagnostics in Browser Console

### 1. Check All Components Are Loaded

```javascript
// Run this in browser console after page loads
console.log('=== Component Check ===');
console.log('mapManager:', typeof window.mapManager);
console.log('geocodingService:', typeof window.geocodingService);
console.log('wsClient:', typeof window.wsClient);
console.log('gpsSimulator:', typeof window.gpsSimulator);
console.log('realGPSTracker:', typeof window.realGPSTracker);
console.log('app:', typeof window.app);
console.log('CONFIG:', typeof window.CONFIG);
```

**Expected Output:**
```
mapManager: object
geocodingService: object
wsClient: object
gpsSimulator: object
realGPSTracker: object
app: object
CONFIG: object
```

### 2. Check Map Status

```javascript
console.log('=== Map Status ===');
console.log('Map ready:', mapManager?.isReady);
console.log('Map instance:', mapManager?.map);
console.log('Map loaded:', mapManager?.map?.loaded());
```

### 3. Test Location Resolution

```javascript
// Test with coordinates
async function testLocationResolution() {
    console.log('=== Testing Location Resolution ===');
    
    // Test 1: Direct coordinates
    try {
        const coords1 = await geocodingService.resolveLocation('18.5246, 73.8786');
        console.log('✓ Coordinates test passed:', coords1);
    } catch (e) {
        console.error('✗ Coordinates test failed:', e);
    }
    
    // Test 2: City name
    try {
        const coords2 = await geocodingService.resolveLocation('Mumbai, India');
        console.log('✓ City name test passed:', coords2);
    } catch (e) {
        console.error('✗ City name test failed:', e);
    }
    
    // Test 3: Check input dataset
    const originInput = document.getElementById('origin');
    console.log('Origin input dataset:', originInput.dataset);
    console.log('Origin value:', originInput.value);
}

testLocationResolution();
```

### 4. Check Autocomplete Status

```javascript
console.log('=== Autocomplete Status ===');
console.log('originAutocomplete:', window.originAutocomplete);
console.log('destinationAutocomplete:', window.destinationAutocomplete);

const originInput = document.getElementById('origin');
const destInput = document.getElementById('destination');

console.log('Origin dataset:', originInput?.dataset);
console.log('Destination dataset:', destInput?.dataset);
```

### 5. Test Journey Start Manually

```javascript
async function testJourneyStart() {
    console.log('=== Testing Journey Start ===');
    
    const origin = { lat: 18.5246, lng: 73.8786 }; // Pune
    const destination = { lat: 19.0760, lng: 72.8777 }; // Mumbai
    
    try {
        const response = await fetch('http://localhost:8000/api/journey/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                origin,
                destination,
                travel_mode: 'driving'
            })
        });
        
        const data = await response.json();
        console.log('✓ Journey started:', data);
        
        // Try to display routes
        if (mapManager.isReady) {
            mapManager.displayRoutes(data.routes, origin, destination);
            console.log('✓ Routes displayed on map');
        } else {
            console.error('✗ Map not ready');
        }
        
        return data;
    } catch (error) {
        console.error('✗ Journey start failed:', error);
    }
}

testJourneyStart();
```

## Common Issues and Solutions

### Issue 1: "Cannot read properties of undefined (reading 'lng')"

**Symptoms:** Error when starting journey, location resolution fails

**Diagnosis:**
```javascript
const originInput = document.getElementById('origin');
console.log('Origin value:', originInput.value);
console.log('Origin dataset:', originInput.dataset);
console.log('geocodingService exists:', !!window.geocodingService);
```

**Solutions:**
1. **User typed location without selecting from dropdown**
   - Make sure to select a location from the autocomplete dropdown
   - OR enter coordinates in format: `lat, lng` (e.g., `18.5246, 73.8786`)

2. **Geocoding service not loaded**
   - Refresh the page (Ctrl+Shift+R)
   - Check browser console for script loading errors
   - Verify `geocoding.js` is in `frontend/js/` directory

3. **Dataset not cleared properly**
   - Fixed: Input handler now clears dataset when user types
   - If still occurring, manually clear: `document.getElementById('origin').dataset = {}`

### Issue 2: "Map manager not found"

**Diagnosis:**
```javascript
console.log('window.mapManager:', window.mapManager);
console.log('mapManager defined:', typeof mapManager);
```

**Solutions:**
1. Check script load order in `index.html` - `map.js` should load before `ui.js`
2. Refresh page to ensure `window.mapManager = mapManager;` executes
3. Check browser console for JavaScript errors preventing script execution

### Issue 3: Routes Not Displaying

**Diagnosis:**
```javascript
console.log('Map ready:', mapManager?.isReady);
console.log('Map loaded:', mapManager?.map?.loaded());
console.log('Has routes layer:', mapManager?.map?.getLayer('routes-layer-0'));
```

**Solutions:**
1. Wait for map to be ready: `mapManager.onReady(() => { /* your code */ })`
2. Check if routes data is valid: `console.log(data.routes)`
3. Verify Mapbox access token is valid in `js/config.js`

### Issue 4: Autocomplete Not Working

**Diagnosis:**
```javascript
console.log('originAutocomplete initialized:', window.originAutocomplete?.isInitialized);
console.log('Mapbox token:', CONFIG?.MAPBOX_ACCESS_TOKEN?.substring(0, 10) + '...');
```

**Solutions:**
1. Type at least 2 characters
2. Wait 300ms for debounce
3. Check network tab for geocoding API calls
4. Verify Mapbox token is valid (starts with `pk.`)
5. Check console for API errors (quota exceeded, invalid token, etc.)

## Step-by-Step Manual Testing

### Test 1: Basic Journey with Coordinates

1. Open browser console (F12)
2. Paste origin coordinates: `18.5246, 73.8786`
3. Paste destination coordinates: `19.0760, 72.8777`
4. Select travel mode: `Driving`
5. Click "Start Journey"
6. Check console for:
   ```
   [UI] Resolving origin: 18.5246, 73.8786
   [UI] ✓ Origin resolved: {lat: 18.5246, lng: 73.8786}
   [UI] Resolving destination: 19.0760, 72.8777
   [UI] ✓ Destination resolved: {lat: 19.0760, lng: 72.8777}
   [UI] Starting journey: ...
   [UI] Journey started: ...
   [Map] Displayed 2 route(s)
   ```

### Test 2: Journey with Autocomplete

1. Clear origin and destination fields
2. Type "Pune" in origin field
3. Wait for autocomplete dropdown
4. Click on "Pune, India" from dropdown
5. Check console:
   ```
   [Autocomplete] Stored coordinates: {lat: ..., lng: ...}
   ```
6. Type "Mumbai" in destination
7. Select from dropdown
8. Click "Start Journey"
9. Verify no errors in console

### Test 3: Real GPS Tracking

1. Start a journey (either method above)
2. Click "Start Real GPS" button
3. Allow location permissions when prompted
4. Check console:
   ```
   [RealGPS] ✓ Started tracking
   [RealGPS] Position update: ...
   ```
5. Verify blue pulse marker appears on map
6. Verify speed and distance update

## Network Debugging

### Check Backend Connection

```javascript
// Test backend health
fetch('http://localhost:8000/health')
    .then(r => r.json())
    .then(data => console.log('Backend health:', data))
    .catch(e => console.error('Backend unreachable:', e));
```

### Monitor WebSocket

```javascript
// Check WebSocket status
console.log('WebSocket client:', wsClient);
console.log('Connected:', wsClient?.connected);
console.log('Journey ID:', wsClient?.journeyId);

// Listen for WebSocket messages
if (wsClient?.ws) {
    const originalOnMessage = wsClient.ws.onmessage;
    wsClient.ws.onmessage = function(event) {
        console.log('WS message received:', JSON.parse(event.data));
        if (originalOnMessage) originalOnMessage.call(this, event);
    };
}
```

## Performance Monitoring

```javascript
// Monitor GPS update frequency
let lastUpdate = Date.now();
let updateCount = 0;

setInterval(() => {
    if (updateCount > 0) {
        console.log(`GPS updates/sec: ${updateCount}`);
        updateCount = 0;
    }
}, 1000);

// Hook into map update function (run this before starting journey)
const originalUpdate = mapManager.updateCurrentLocation;
mapManager.updateCurrentLocation = function(...args) {
    updateCount++;
    lastUpdate = Date.now();
    return originalUpdate.apply(this, args);
};
```

## Logs to Share When Reporting Issues

When reporting issues, include these console outputs:

```javascript
// 1. Component status
console.log('Components:', {
    mapManager: !!window.mapManager,
    geocodingService: !!window.geocodingService,
    wsClient: !!window.wsClient,
    mapReady: mapManager?.isReady
});

// 2. Current state
console.log('Current state:', {
    originValue: document.getElementById('origin')?.value,
    originDataset: document.getElementById('origin')?.dataset,
    destValue: document.getElementById('destination')?.value,
    destDataset: document.getElementById('destination')?.dataset
});

// 3. Browser info
console.log('Browser:', {
    userAgent: navigator.userAgent,
    online: navigator.onLine,
    geolocation: !!navigator.geolocation
});
```

## Quick Fixes

### Reset Everything

```javascript
// Nuclear option - reset all state
location.reload(true); // Hard refresh
```

### Clear Cached Coordinates

```javascript
// Clear all stored coordinates
document.getElementById('origin').dataset = {};
document.getElementById('destination').dataset = {};
document.getElementById('origin').value = '';
document.getElementById('destination').value = '';
console.log('✓ Inputs cleared');
```

### Reinitialize Map

```javascript
// Reinitialize map if it's stuck
mapManager.reset();
mapManager.init();
```
