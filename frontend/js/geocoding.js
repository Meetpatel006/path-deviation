// Mapbox Geocoding - Location Search and Autocomplete
// Enhanced version with better debugging and error handling

class GeocodingService {
    constructor() {
        this.baseUrl = 'https://api.mapbox.com/geocoding/v5/mapbox.places';
        this.searchCache = new Map();
        this.debounceTimer = null;
        this.debounceDelay = 300; // ms
        this.isInitialized = false;
        
        this.init();
    }

    /**
     * Initialize and validate the service
     */
    init() {
        if (!CONFIG || !CONFIG.MAPBOX_TOKEN) {
            console.error('[Geocoding] ERROR: CONFIG.MAPBOX_TOKEN is not defined!');
            console.error('[Geocoding] Please check frontend/js/config.js');
            return;
        }

        if (!CONFIG.MAPBOX_TOKEN.startsWith('pk.')) {
            console.error('[Geocoding] ERROR: Invalid Mapbox token! Must start with "pk."');
            console.error('[Geocoding] Current token:', CONFIG.MAPBOX_TOKEN.substring(0, 10) + '...');
            return;
        }

        this.isInitialized = true;
        console.log('[Geocoding] Service initialized successfully');
        console.log('[Geocoding] Token:', CONFIG.MAPBOX_TOKEN.substring(0, 20) + '...');
    }

    /**
     * Forward geocoding - Convert place name to coordinates
     * @param {string} query - Location name (e.g., "Delhi, India")
     * @param {object} options - Additional options
     * @returns {Promise<Array>} Array of location results
     */
    async forwardGeocode(query, options = {}) {
        if (!this.isInitialized) {
            console.error('[Geocoding] Service not initialized! Check token.');
            return [];
        }

        if (!query || query.trim().length < 2) {
            console.log('[Geocoding] Query too short:', query);
            return [];
        }

        const trimmedQuery = query.trim();

        // Check cache
        const cacheKey = `${trimmedQuery}-${JSON.stringify(options)}`;
        if (this.searchCache.has(cacheKey)) {
            console.log('[Geocoding] ✓ Using cached result for:', trimmedQuery);
            return this.searchCache.get(cacheKey);
        }

        try {
            // Build query parameters
            const params = new URLSearchParams({
                access_token: CONFIG.MAPBOX_TOKEN,
                limit: options.limit || 5,
                types: options.types || 'country,region,postcode,district,place,locality,neighborhood,address,poi',
                autocomplete: 'true',
                language: 'en'
            });

            // Add additional options
            if (options.country) {
                params.append('country', options.country);
            }
            if (options.proximity) {
                params.append('proximity', options.proximity);
            }

            const url = `${this.baseUrl}/${encodeURIComponent(trimmedQuery)}.json?${params}`;
            
            console.log('[Geocoding] 🔍 Searching for:', trimmedQuery);
            console.log('[Geocoding] URL:', url.substring(0, 120) + '...');
            
            const response = await fetch(url);
            
            console.log('[Geocoding] Response status:', response.status);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('[Geocoding] API Error:', response.status, errorText);
                throw new Error(`Geocoding API error: ${response.status} - ${errorText}`);
            }

            const data = await response.json();
            console.log('[Geocoding] Response data:', data);
            
            if (!data.features || data.features.length === 0) {
                console.warn('[Geocoding] ⚠ No results found for:', trimmedQuery);
                return [];
            }

            // Parse and format results
            const results = data.features.map((feature, index) => {
                console.log(`[Geocoding] Result ${index + 1}:`, feature.place_name, feature.center);
                return {
                    name: feature.place_name,
                    coordinates: {
                        lng: feature.center[0],
                        lat: feature.center[1]
                    },
                    type: feature.place_type ? feature.place_type[0] : 'unknown',
                    context: feature.context || [],
                    bbox: feature.bbox || null,
                    relevance: feature.relevance || 0
                };
            });

            // Cache results
            this.searchCache.set(cacheKey, results);
            
            console.log(`[Geocoding] ✓ Found ${results.length} results for: "${trimmedQuery}"`);
            return results;

        } catch (error) {
            console.error('[Geocoding] ❌ Search error:', error);
            console.error('[Geocoding] Stack:', error.stack);
            
            // Don't throw, return empty array to allow graceful degradation
            return [];
        }
    }

    /**
     * Reverse geocoding - Convert coordinates to place name
     * @param {number} lng - Longitude
     * @param {number} lat - Latitude
     * @returns {Promise<object>} Location information
     */
    async reverseGeocode(lng, lat) {
        if (!this.isInitialized) {
            console.error('[Geocoding] Service not initialized!');
            return null;
        }

        try {
            const params = new URLSearchParams({
                access_token: CONFIG.MAPBOX_TOKEN,
                types: 'country,region,postcode,district,place,locality,neighborhood,address',
                limit: 1
            });

            const url = `${this.baseUrl}/${lng},${lat}.json?${params}`;
            
            console.log(`[Geocoding] 🔄 Reverse geocoding: ${lat}, ${lng}`);
            
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`Reverse geocoding error: ${response.status}`);
            }

            const data = await response.json();
            
            if (!data.features || data.features.length === 0) {
                console.warn('[Geocoding] No results for reverse geocoding');
                return null;
            }

            const feature = data.features[0];
            const result = {
                name: feature.place_name,
                coordinates: {
                    lng: feature.center[0],
                    lat: feature.center[1]
                },
                type: feature.place_type ? feature.place_type[0] : 'unknown'
            };

            console.log('[Geocoding] ✓ Reverse geocoding result:', result.name);
            return result;

        } catch (error) {
            console.error('[Geocoding] Reverse geocoding error:', error);
            return null;
        }
    }

    /**
     * Parse input to determine if it's coordinates or location name
     * @param {string} input - User input
     * @returns {object} Parsed result with type and value
     */
    parseInput(input) {
        const trimmed = input.trim();
        
        // Check if input matches coordinate pattern (lat, lng)
        const coordPattern = /^(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)$/;
        const match = trimmed.match(coordPattern);
        
        if (match) {
            const lat = parseFloat(match[1]);
            const lng = parseFloat(match[2]);
            
            // Validate coordinate ranges
            if (lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
                console.log('[Geocoding] Detected coordinates:', { lat, lng });
                return {
                    type: 'coordinates',
                    coordinates: { lat, lng }
                };
            }
        }
        
        // Otherwise, treat as location name
        console.log('[Geocoding] Detected place name:', trimmed);
        return {
            type: 'name',
            query: trimmed
        };
    }

    /**
     * Resolve location input to coordinates
     * @param {string} input - User input (name or coordinates)
     * @returns {Promise<object>} Coordinates {lat, lng}
     */
    async resolveLocation(input) {
        const parsed = this.parseInput(input);
        
        if (parsed.type === 'coordinates') {
            console.log('[Geocoding] Using provided coordinates:', parsed.coordinates);
            return parsed.coordinates;
        }
        
        // Search for location name
        console.log('[Geocoding] Resolving location name:', parsed.query);
        const results = await this.forwardGeocode(parsed.query, { limit: 1 });
        
        if (results.length === 0) {
            throw new Error(`Location not found: ${parsed.query}`);
        }
        
        console.log('[Geocoding] ✓ Resolved location:', results[0].name, results[0].coordinates);
        return results[0].coordinates;
    }

    /**
     * Debounced search for autocomplete
     * @param {string} query - Search query
     * @param {function} callback - Callback with results
     */
    searchWithDebounce(query, callback) {
        clearTimeout(this.debounceTimer);
        
        console.log('[Geocoding] Debouncing search for:', query);
        
        this.debounceTimer = setTimeout(async () => {
            console.log('[Geocoding] Executing debounced search for:', query);
            try {
                const results = await this.forwardGeocode(query);
                console.log('[Geocoding] Calling callback with', results.length, 'results');
                callback(results);
            } catch (error) {
                console.error('[Geocoding] Debounced search error:', error);
                callback([]);
            }
        }, this.debounceDelay);
    }

    /**
     * Clear search cache
     */
    clearCache() {
        this.searchCache.clear();
        console.log('[Geocoding] Cache cleared');
    }
}

// Create global geocoding service instance
const geocodingService = new GeocodingService();
window.geocodingService = geocodingService;

// Location Autocomplete Manager
class LocationAutocomplete {
    constructor(inputId, dropdownId) {
        this.inputId = inputId;
        this.dropdownId = dropdownId;
        this.input = null;
        this.dropdown = null;
        this.selectedIndex = -1;
        this.results = [];
        this.isOpen = false;
        this.isInitialized = false;
        
        console.log(`[Autocomplete] Creating instance for ${inputId}`);
    }

    /**
     * Initialize the autocomplete (called after DOM is ready)
     */
    init() {
        this.input = document.getElementById(this.inputId);
        this.dropdown = document.getElementById(this.dropdownId);
        
        if (!this.input) {
            console.error(`[Autocomplete] Input element not found: ${this.inputId}`);
            return false;
        }
        
        if (!this.dropdown) {
            console.error(`[Autocomplete] Dropdown element not found: ${this.dropdownId}`);
            return false;
        }

        console.log(`[Autocomplete] ✓ Elements found for ${this.inputId}`);
        
        this.setupEventListeners();
        this.isInitialized = true;
        
        console.log(`[Autocomplete] ✓ Initialized for ${this.inputId}`);
        return true;
    }

    setupEventListeners() {
        // Input event listener
        this.input.addEventListener('input', (e) => {
            const query = e.target.value.trim();
            
            console.log(`[Autocomplete] Input event for ${this.inputId}:`, query);
            
            // Clear stored coordinates when user types (they need to reselect)
            delete this.input.dataset.lat;
            delete this.input.dataset.lng;
            console.log(`[Autocomplete] Cleared stored coordinates for ${this.inputId}`);
            
            if (query.length < 2) {
                console.log(`[Autocomplete] Query too short, closing dropdown`);
                this.close();
                return;
            }

            // Check if it's coordinates
            const parsed = geocodingService.parseInput(query);
            if (parsed.type === 'coordinates') {
                console.log(`[Autocomplete] Detected coordinates, closing dropdown`);
                this.close();
                return;
            }

            // Show loading state
            this.showLoading();

            // Search with debounce
            geocodingService.searchWithDebounce(query, (results) => {
                console.log(`[Autocomplete] Received ${results.length} results for ${this.inputId}`);
                this.showResults(results);
            });
        });

        // Keyboard navigation
        this.input.addEventListener('keydown', (e) => {
            if (!this.isOpen) return;

            switch (e.key) {
                case 'ArrowDown':
                    e.preventDefault();
                    this.selectNext();
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    this.selectPrevious();
                    break;
                case 'Enter':
                    e.preventDefault();
                    if (this.selectedIndex >= 0 && this.results[this.selectedIndex]) {
                        this.selectResult(this.results[this.selectedIndex]);
                    }
                    break;
                case 'Escape':
                    this.close();
                    break;
            }
        });

        // Close on click outside
        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.dropdown.contains(e.target)) {
                this.close();
            }
        });

        console.log(`[Autocomplete] Event listeners attached for ${this.inputId}`);
    }

    showLoading() {
        this.dropdown.innerHTML = '<div class="autocomplete-loading">Searching...</div>';
        this.dropdown.style.display = 'block';
    }

    showResults(results) {
        this.results = results;
        this.selectedIndex = -1;

        console.log(`[Autocomplete] Showing ${results.length} results for ${this.inputId}`);

        if (results.length === 0) {
            this.dropdown.innerHTML = '<div class="autocomplete-no-results">No locations found</div>';
            this.dropdown.style.display = 'block';
            this.isOpen = true;
            return;
        }

        this.dropdown.innerHTML = '';
        
        results.forEach((result, index) => {
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            item.innerHTML = `
                <div class="autocomplete-item-name">${this.highlightMatch(result.name, this.input.value)}</div>
                <div class="autocomplete-item-type">${result.type}</div>
            `;
            
            item.addEventListener('click', () => {
                console.log(`[Autocomplete] Clicked result ${index}:`, result.name);
                this.selectResult(result);
            });

            item.addEventListener('mouseenter', () => {
                this.selectedIndex = index;
                this.updateSelectedItem();
            });

            this.dropdown.appendChild(item);
        });

        this.dropdown.style.display = 'block';
        this.isOpen = true;
        
        console.log(`[Autocomplete] ✓ Dropdown displayed with ${results.length} items`);
    }

    highlightMatch(text, query) {
        if (!query) return text;
        const regex = new RegExp(`(${this.escapeRegex(query)})`, 'gi');
        return text.replace(regex, '<strong>$1</strong>');
    }

    escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    selectNext() {
        this.selectedIndex = Math.min(this.selectedIndex + 1, this.results.length - 1);
        this.updateSelectedItem();
    }

    selectPrevious() {
        this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
        this.updateSelectedItem();
    }

    updateSelectedItem() {
        const items = this.dropdown.querySelectorAll('.autocomplete-item');
        items.forEach((item, index) => {
            if (index === this.selectedIndex) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        });
    }

    selectResult(result) {
        console.log(`[Autocomplete] Selected result for ${this.inputId}:`, result);
        
        // Set input value to location name
        this.input.value = result.name;
        
        // Store coordinates as data attributes
        this.input.dataset.lat = result.coordinates.lat;
        this.input.dataset.lng = result.coordinates.lng;
        
        console.log(`[Autocomplete] Stored coordinates:`, result.coordinates);
        
        this.close();

        // Trigger custom event
        const event = new CustomEvent('locationSelected', {
            detail: result
        });
        this.input.dispatchEvent(event);
        
        console.log(`[Autocomplete] Dispatched locationSelected event`);
    }

    close() {
        this.dropdown.style.display = 'none';
        this.dropdown.innerHTML = '';
        this.isOpen = false;
        this.selectedIndex = -1;
        this.results = [];
        
        console.log(`[Autocomplete] Closed dropdown for ${this.inputId}`);
    }
}

// Initialize autocomplete when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Geocoding] DOM loaded, initializing autocomplete...');
    
    // Wait a bit for other scripts to load
    setTimeout(() => {
        // Initialize origin autocomplete
        const originAutocomplete = new LocationAutocomplete('origin', 'origin-suggestions');
        if (originAutocomplete.init()) {
            window.originAutocomplete = originAutocomplete;
            console.log('[Geocoding] ✓ Origin autocomplete ready');
        }

        // Initialize destination autocomplete
        const destinationAutocomplete = new LocationAutocomplete('destination', 'destination-suggestions');
        if (destinationAutocomplete.init()) {
            window.destinationAutocomplete = destinationAutocomplete;
            console.log('[Geocoding] ✓ Destination autocomplete ready');
        }

        console.log('[Geocoding] ✓✓✓ All autocomplete features initialized successfully!');
        console.log('[Geocoding] Try typing "Delhi" or "Mumbai" to test autocomplete');
    }, 100);
});
