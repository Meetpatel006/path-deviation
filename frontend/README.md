# GPS Path Deviation Detection - Frontend

Interactive web-based frontend for real-time GPS tracking and path deviation monitoring.

## Features

- **Real-time Map Visualization** with Mapbox GL JS
- **Multiple Route Display** with color-coded alternatives
- **Live Position Updates** via WebSocket
- **Deviation Alerts** with severity indicators
- **Route Probability Tracking** with visual progress bars
- **GPS Simulator** for testing without real GPS data
- **Responsive Design** for desktop and mobile

## Setup

### 1. Get Mapbox API Token

1. Sign up for free at [mapbox.com](https://account.mapbox.com/auth/signup/)
2. Get your access token from [account.mapbox.com/access-tokens](https://account.mapbox.com/access-tokens/)
3. Copy your token

### 2. Configure Frontend

Edit `js/config.js` and replace the Mapbox token:

```javascript
MAPBOX_TOKEN: 'YOUR_ACTUAL_MAPBOX_TOKEN_HERE',
```

### 3. Start Backend Server

Make sure the backend server is running:

```bash
cd backend
python -m app.main
```

Server should be running at `http://localhost:8000`

### 4. Open Frontend

Simply open `index.html` in your web browser:

- **Double-click** `index.html`, or
- **Serve with HTTP server** (recommended):
  ```bash
  # Python 3
  python -m http.server 8080
  
  # Node.js (npx)
  npx http-server -p 8080
  ```
  Then open `http://localhost:8080`

## Usage

### Starting a Journey

1. Enter origin and destination coordinates (lat, lng format)
2. Select travel mode (Driving, Walking, or Cycling)
3. Click "Start Journey"
4. Routes will be displayed on the map

### Using GPS Simulator

1. After starting a journey, the GPS Simulator panel appears
2. Adjust speed (m/s) and update interval (ms) if desired
3. Click "Start Simulation"
4. GPS points will be sent automatically along the route
5. Watch real-time deviation detection in action

### Monitoring Deviations

- **Status Panel** shows current location and deviation metrics
- **Route Probabilities** indicate which route the user is likely following
- **Deviation Alerts** appear when deviations are detected
- **Map** highlights the most probable route

### Completing a Journey

Click "Complete Journey" button to:
- Stop GPS simulation
- Close WebSocket connection
- Reset the interface

## File Structure

```
frontend/
├── index.html              # Main HTML page
├── css/
│   └── styles.css          # Styling
├── js/
│   ├── config.js           # Configuration (API URLs, Mapbox token)
│   ├── map.js              # Mapbox map manager
│   ├── websocket-client.js # WebSocket connection handler
│   ├── ui.js               # UI components and updates
│   ├── gps-simulator.js    # GPS point simulator
│   └── app.js              # Main application entry point
└── README.md               # This file
```

## WebSocket Messages

### Received from Server

1. **connection_ack** - Connection established
2. **gps_update** - GPS location update
3. **deviation_update** - Deviation detected
4. **batch_processed** - GPS batch processed
5. **ping** - Heartbeat check
6. **error** - Error message

### Sent to Server

1. **pong** - Heartbeat response

## Deviation Status Indicators

### Spatial Status
- **ON_ROUTE** (Green) - Within route buffer
- **NEAR_ROUTE** (Yellow) - Close but outside buffer
- **OFF_ROUTE** (Red) - Far from route

### Temporal Status
- **ON_TIME** (Green) - Normal progress
- **DELAYED** (Yellow) - Behind schedule
- **STOPPED** (Red) - No movement

### Directional Status
- **TOWARD_DEST** (Green) - Moving toward destination
- **PERPENDICULAR** (Yellow) - Moving sideways
- **AWAY** (Red) - Moving away from destination

### Severity Levels
- **normal** (Green) - No issues
- **minor** (Blue) - Small deviation
- **moderate** (Yellow) - Noticeable deviation
- **concerning** (Orange) - Significant deviation
- **major** (Red) - Severe deviation

## Customization

### Map Style

Edit `config.js` to change map style:

```javascript
MAP_STYLE: 'mapbox://styles/mapbox/dark-v11',  // Dark theme
MAP_STYLE: 'mapbox://styles/mapbox/satellite-v9',  // Satellite
```

### Route Colors

Edit `config.js` to change route colors:

```javascript
ROUTE_COLORS: [
    '#3498db',  // Blue
    '#e74c3c',  // Red
    '#2ecc71',  // Green
],
```

### Default Location

Edit `config.js` to change default map center:

```javascript
DEFAULT_CENTER: [lng, lat],  // [longitude, latitude]
```

## Troubleshooting

### Map not loading
- Check that Mapbox token is configured correctly
- Open browser console (F12) to see errors
- Verify internet connection (Mapbox requires online access)

### WebSocket not connecting
- Ensure backend server is running at `http://localhost:8000`
- Check browser console for connection errors
- Verify CORS is enabled in backend

### GPS Simulator not working
- Make sure journey is started first
- Check that route data was loaded correctly
- Look for errors in browser console

## Browser Compatibility

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Development

### Testing

1. Start backend with test database
2. Open frontend in browser
3. Use GPS Simulator to test functionality
4. Monitor browser console for logs
5. Check Network tab for WebSocket messages

### Debugging

Enable verbose logging by opening browser console:

```javascript
// Set log level
localStorage.setItem('debug', 'true');

// View application state
console.log(app);
console.log(mapManager);
console.log(wsClient);
console.log(gpsSimulator);
```

## API Endpoints Used

- `POST /api/journey/start` - Start new journey
- `POST /api/journey/{id}/gps` - Submit GPS point
- `GET /api/journey/{id}` - Get journey status
- `PUT /api/journey/{id}/complete` - Complete journey
- `WS /ws/journey/{id}` - WebSocket connection

## License

Part of GPS Path Deviation Detection System
