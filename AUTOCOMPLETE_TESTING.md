# Location Search Autocomplete - Testing & Troubleshooting Guide

## 🚀 Quick Test

### 1. Open the Application
```
Open: frontend/index.html in your browser
```

### 2. Open Browser Console
- **Chrome/Edge**: Press `F12` or `Ctrl+Shift+I`
- **Firefox**: Press `F12`
- Look for messages starting with `[Geocoding]` and `[Autocomplete]`

### 3. Test Autocomplete

**Origin Input:**
1. Click on the "Origin" input field
2. Type: `del`
3. You should see console logs:
   ```
   [Geocoding] Detected place name: del
   [Geocoding] 🔍 Searching for: del
   [Autocomplete] Received 5 results
   ```
4. Dropdown should appear with suggestions like:
   - Delhi, Delhi, India
   - Delft, Netherlands
   - etc.

**Destination Input:**
1. Click on "Destination" field
2. Type: `mum`
3. Dropdown should show Mumbai suggestions

## 🔍 Detailed Console Logs

When autocomplete is working, you'll see:

```javascript
[Geocoding] DOM loaded, initializing autocomplete...
[Geocoding] Service initialized successfully
[Geocoding] Token: pk.eyJ1IjoicmVkcmVw...
[Autocomplete] Creating instance for origin
[Autocomplete] ✓ Elements found for origin
[Autocomplete] Event listeners attached for origin
[Autocomplete] ✓ Initialized for origin
[Geocoding] ✓ Origin autocomplete ready
[Geocoding] ✓✓✓ All autocomplete features initialized successfully!
```

When you type:
```javascript
[Autocomplete] Input event for origin: del
[Geocoding] Debouncing search for: del
[Geocoding] Executing debounced search for: del
[Geocoding] 🔍 Searching for: del
[Geocoding] Response status: 200
[Geocoding] Response data: {type: 'FeatureCollection', features: Array(5)}
[Geocoding] Result 1: Delhi, Delhi, India [77.2295, 28.6692]
[Geocoding] Result 2: Delft, Netherlands [4.3571, 52.0116]
[Geocoding] ✓ Found 5 results for: "del"
[Autocomplete] Received 5 results for origin
[Autocomplete] Showing 5 results for origin
[Autocomplete] ✓ Dropdown displayed with 5 items
```

## ❌ Common Issues & Solutions

### Issue 1: No Dropdown Appears

**Symptoms:**
- You type but nothing shows up
- No console logs

**Solution:**
```javascript
// Check in console:
console.log(window.geocodingService);  // Should be defined
console.log(window.originAutocomplete); // Should be defined

// Check elements exist:
document.getElementById('origin');  // Should not be null
document.getElementById('origin-suggestions');  // Should not be null
```

**Fix:** Make sure all scripts are loaded in correct order in `index.html`:
```html
<script src="js/config.js"></script>
<script src="js/geocoding.js"></script>  <!-- Must be before ui.js -->
<script src="js/map.js"></script>
<!-- etc -->
```

### Issue 2: Console Shows "Service not initialized"

**Symptoms:**
```
[Geocoding] ERROR: CONFIG.MAPBOX_TOKEN is not defined!
```

**Solution:**
1. Open `frontend/js/config.js`
2. Verify MAPBOX_TOKEN starts with `pk.`
3. Current token in config.js:
   ```javascript
   MAPBOX_TOKEN: 'pk.eyJ1IjoicmVkcmVwdGVyIiwiYSI6ImNtZmgza2ludTA2eXcybHF3OTJjcnp5d3MifQ.nu__SNPTTw3yJMF0jRgE6g'
   ```

### Issue 3: API Returns 401 Unauthorized

**Symptoms:**
```
[Geocoding] API Error: 401
```

**Solution:**
- Token expired or invalid
- Get new token from: https://account.mapbox.com/access-tokens/
- Update in `frontend/js/config.js`

### Issue 4: Dropdown Appears But Empty

**Symptoms:**
```
[Geocoding] ⚠ No results found for: xyz
[Autocomplete] Showing 0 results
```

**Solution:**
- Try common place names: "New York", "London", "Paris"
- Check spelling
- Try full names: "Mumbai, India" instead of just "Mumbai"

### Issue 5: CORS Error

**Symptoms:**
```
Access to fetch at 'https://api.mapbox.com/...' from origin 'null' has been blocked by CORS
```

**Solution:**
- Don't open HTML file directly (file://)
- Use a local server:

**Option 1: Python Server**
```bash
cd frontend
python -m http.server 8080
# Open: http://localhost:8080
```

**Option 2: Node.js http-server**
```bash
cd frontend
npx http-server -p 8080
# Open: http://localhost:8080
```

**Option 3: VS Code Live Server**
- Install "Live Server" extension
- Right-click `index.html` → "Open with Live Server"

## 🧪 Test Queries

Try these to verify autocomplete works:

### Cities:
- `del` → Delhi, Delft, Delaware
- `mum` → Mumbai, Munich
- `par` → Paris, Paraguay
- `lon` → London, Long Island
- `tok` → Tokyo

### Countries:
- `ind` → India, Indonesia
- `usa` → United States
- `uk` → United Kingdom

### Addresses:
- `times square` → Times Square, New York
- `eiffel tower` → Eiffel Tower, Paris
- `big ben` → Big Ben, London

## 🐛 Debug Commands

Run these in browser console:

```javascript
// Check if geocoding service is initialized
geocodingService.isInitialized  // Should be true

// Test search directly
geocodingService.forwardGeocode('Delhi').then(results => {
    console.log('Results:', results);
});

// Check autocomplete instances
originAutocomplete.isInitialized  // Should be true
destinationAutocomplete.isInitialized  // Should be true

// Force a search
originAutocomplete.input.value = 'Delhi';
originAutocomplete.input.dispatchEvent(new Event('input'));

// Check dropdown
originAutocomplete.dropdown.style.display  // Should be 'block' when open
```

## 📊 Network Inspection

1. Open DevTools → Network tab
2. Type in origin field
3. Look for request to `api.mapbox.com/geocoding/v5/`
4. Check:
   - Status: 200 OK
   - Response: JSON with features array
   - Request URL contains your token

## ✅ Success Indicators

Autocomplete is working when you see:

1. ✓ Console shows initialization messages
2. ✓ Typing shows "Searching..." briefly
3. ✓ Dropdown appears with location suggestions
4. ✓ Clicking a suggestion fills the input
5. ✓ Console shows coordinates are stored
6. ✓ Submitting form works with selected location

## 🎯 Expected Behavior

### Before Selection:
```html
<input id="origin" value="Del">
<!-- No data attributes -->
```

### After Selection:
```html
<input id="origin" 
       value="Delhi, Delhi, India" 
       data-lat="28.6692" 
       data-lng="77.2295">
```

### On Form Submit:
```javascript
// Uses stored coordinates
origin: { lat: 28.6692, lng: 77.2295 }
```

## 📝 Testing Checklist

- [ ] Open browser console (F12)
- [ ] See "[Geocoding] ✓✓✓ All autocomplete features initialized"
- [ ] Type "del" in Origin field
- [ ] See "Searching..." message
- [ ] See dropdown with 5 suggestions
- [ ] Click a suggestion
- [ ] Input filled with location name
- [ ] Type "mum" in Destination field
- [ ] See Mumbai suggestions
- [ ] Click "Start Journey"
- [ ] Journey starts with correct locations

## 🆘 Still Not Working?

If autocomplete still doesn't work:

1. **Clear browser cache**: Ctrl+Shift+Delete
2. **Hard reload**: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
3. **Check console for errors**: Any red error messages?
4. **Verify file structure**:
   ```
   frontend/
   ├── index.html
   ├── js/
   │   ├── config.js
   │   ├── geocoding.js ← Must exist
   │   ├── ui.js
   │   └── ...
   └── css/
       └── styles.css
   ```
5. **Share console output**: Copy all [Geocoding] messages for debugging

## 💡 Tips

- **Minimum 2 characters**: Autocomplete only triggers after typing 2+ characters
- **300ms delay**: Results appear 300ms after you stop typing
- **Caching**: Same queries use cached results (faster)
- **Keyboard shortcuts**: Use ↑↓ arrows and Enter to select
- **Click outside**: Closes dropdown automatically
- **ESC key**: Closes dropdown

## 📞 Getting Help

If you need help, provide:
1. Browser console output (all [Geocoding] messages)
2. Network tab showing Mapbox API requests
3. Browser and version
4. Any error messages

Example console output to share:
```
[Geocoding] Service initialized successfully
[Autocomplete] ✓ Initialized for origin
[Geocoding] 🔍 Searching for: delhi
[Geocoding] Response status: 200
[Geocoding] ✓ Found 5 results for: "delhi"
```
