"""
Geocoding service for converting place names to coordinates
"""
from typing import Optional, Tuple, List, Dict, Any
import httpx
from app.config import settings
from app.utils.logger import logger


class GeocodingService:
    """
    Service to handle forward geocoding using Mapbox Geocoding API v6
    Converts location names (e.g., "Delhi", "New York") to coordinates
    """
    
    GEOCODING_URL = "https://api.mapbox.com/search/geocode/v6/forward"
    
    def __init__(self):
        self.api_key = settings.MAPBOX_API_KEY
    
    async def geocode_location(
        self,
        query: str,
        limit: int = 5,
        types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Forward geocode a location query to get coordinates
        
        Args:
            query: Location name to search for (e.g., "Delhi", "Mumbai")
            limit: Maximum number of results to return (default: 5, max: 10)
            types: Filter by feature types (e.g., ["place", "address"])
        
        Returns:
            List of geocoding results with coordinates and details
        
        Example:
            >>> results = await geocode_location("Delhi")
            >>> results[0]["coordinates"]
            {"lat": 28.7041, "lng": 77.1025}
        """
        try:
            params = {
                "q": query,
                "access_token": self.api_key,
                "limit": min(limit, 10),  # Max 10
                "autocomplete": "false",  # Get exact matches
            }
            
            if types:
                params["types"] = ",".join(types)
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.GEOCODING_URL, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Parse response
            results = []
            for feature in data.get("features", []):
                props = feature.get("properties", {})
                coords = props.get("coordinates", {})
                
                result = {
                    "name": props.get("name", ""),
                    "full_address": props.get("full_address", props.get("place_formatted", "")),
                    "feature_type": props.get("feature_type", ""),
                    "coordinates": {
                        "lat": coords.get("latitude"),
                        "lng": coords.get("longitude")
                    },
                    "context": props.get("context", {}),
                    "mapbox_id": props.get("mapbox_id", "")
                }
                
                # Add formatted place string for display
                context = props.get("context", {})
                place_parts = []
                if context.get("place"):
                    place_parts.append(context["place"].get("name"))
                if context.get("region"):
                    place_parts.append(context["region"].get("name"))
                if context.get("country"):
                    place_parts.append(context["country"].get("name"))
                
                result["place_string"] = ", ".join(place_parts) if place_parts else result["full_address"]
                
                results.append(result)
            
            logger.info(f"Geocoded '{query}': found {len(results)} result(s)")
            return results
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Mapbox API error for query '{query}': {e}")
            raise ValueError(f"Failed to geocode location: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Geocoding error for query '{query}': {e}")
            raise ValueError(f"Failed to geocode location: {str(e)}")
    
    async def geocode_single(self, query: str) -> Tuple[float, float]:
        """
        Geocode a single location and return the best match coordinates
        
        Args:
            query: Location name to search for
        
        Returns:
            Tuple of (latitude, longitude)
        
        Raises:
            ValueError: If no results found
        """
        results = await self.geocode_location(query, limit=1)
        
        if not results:
            raise ValueError(f"No location found for '{query}'")
        
        coords = results[0]["coordinates"]
        return coords["lat"], coords["lng"]
    
    async def autocomplete_location(
        self,
        query: str,
        limit: int = 5,
        proximity: Optional[Tuple[float, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get autocomplete suggestions for a location query
        
        Args:
            query: Partial location name
            limit: Maximum number of suggestions
            proximity: (lat, lng) tuple to bias results near this location
        
        Returns:
            List of autocomplete suggestions
        """
        try:
            params = {
                "q": query,
                "access_token": self.api_key,
                "limit": min(limit, 10),
                "autocomplete": "true",  # Enable autocomplete
            }
            
            if proximity:
                lat, lng = proximity
                params["proximity"] = f"{lng},{lat}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.GEOCODING_URL, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Parse suggestions
            suggestions = []
            for feature in data.get("features", []):
                props = feature.get("properties", {})
                coords = props.get("coordinates", {})
                
                suggestion = {
                    "name": props.get("name", ""),
                    "place_string": props.get("place_formatted", ""),
                    "feature_type": props.get("feature_type", ""),
                    "coordinates": {
                        "lat": coords.get("latitude"),
                        "lng": coords.get("longitude")
                    }
                }
                suggestions.append(suggestion)
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Autocomplete error for query '{query}': {e}")
            return []


# Global geocoding service instance
geocoding_service = GeocodingService()
