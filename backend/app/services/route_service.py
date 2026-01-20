"""
Mapbox Directions API integration with retry logic
"""
import httpx
from typing import List, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import uuid

from app.models.schemas import LocationPoint, Route
from app.config import settings
from app.utils.logger import logger


class RouteService:
    """Service for fetching route alternatives from Mapbox Directions API"""
    
    def __init__(self):
        self.api_key = settings.MAPBOX_API_KEY
        self.base_url = "https://api.mapbox.com/directions/v5/mapbox"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True
    )
    async def fetch_routes(
        self,
        origin: LocationPoint,
        destination: LocationPoint,
        travel_mode: str
    ) -> List[Route]:
        """
        Fetch route alternatives from Mapbox Directions API
        
        Args:
            origin: Starting location
            destination: Ending location
            travel_mode: 'driving' or 'walking'
        
        Returns:
            List of up to 3 route alternatives
        
        Raises:
            ValueError: If API returns error or invalid data
            httpx.HTTPError: If API request fails
        """
        try:
            # Map travel mode to Mapbox profile
            profile_map = {
                "driving": "driving-traffic",
                "walking": "walking"
            }
            profile = profile_map.get(travel_mode, "driving")
            
            # Build request URL
            coordinates = f"{origin.lng},{origin.lat};{destination.lng},{destination.lat}"
            url = f"{self.base_url}/{profile}/{coordinates}"
            
            # Set request parameters
            params = {
                "access_token": self.api_key,
                "alternatives": "true",  # Request up to 3 alternatives
                "geometries": "geojson",  # Return GeoJSON geometry
                "overview": "full",  # Full geometry, not simplified
                "annotations": "distance,duration,speed",  # Additional metadata
                "steps": "false"  # We don't need turn-by-turn instructions yet
            }
            
            logger.info(f"Fetching routes from Mapbox: {origin.lat},{origin.lng} -> {destination.lat},{destination.lng}")
            
            # Make async HTTP request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Validate response
            if data.get("code") != "Ok":
                error_msg = data.get("message", "Unknown error")
                logger.error(f"Mapbox API error: {error_msg}")
                raise ValueError(f"Mapbox API error: {error_msg}")
            
            routes = data.get("routes", [])
            if not routes:
                logger.warning("No routes found from Mapbox API")
                raise ValueError("No routes found between the given locations")
            
            logger.info(f"Successfully fetched {len(routes)} route(s) from Mapbox")
            
            # Parse and return routes
            return [self._parse_route(route, idx) for idx, route in enumerate(routes[:3])]
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching routes: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error fetching routes: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching routes: {e}")
            raise
    
    def _parse_route(self, route_data: dict, index: int) -> Route:
        """
        Parse Mapbox route response to Route model
        
        Args:
            route_data: Route data from Mapbox API
            index: Route index (0, 1, or 2)
        
        Returns:
            Parsed Route object
        """
        try:
            # Extract geometry (GeoJSON format: coordinates are [lng, lat])
            geometry_coords = route_data["geometry"]["coordinates"]
            
            # Convert to list of tuples (lng, lat)
            geometry = [(coord[0], coord[1]) for coord in geometry_coords]
            
            # Extract metadata
            distance_meters = route_data.get("distance", 0.0)
            duration_seconds = route_data.get("duration", 0.0)
            
            # Generate route ID
            route_id = f"route_{index}"
            
            # Optional: extract route summary (road names)
            summary = None
            if "legs" in route_data and route_data["legs"]:
                # Get summary from first leg
                leg = route_data["legs"][0]
                summary = leg.get("summary", None)
            
            route = Route(
                route_id=route_id,
                route_index=index,
                geometry=geometry,
                distance_meters=distance_meters,
                duration_seconds=duration_seconds,
                summary=summary
            )
            
            logger.debug(
                f"Parsed route {index}: {distance_meters/1000:.2f}km, "
                f"{duration_seconds/60:.1f}min, {len(geometry)} points"
            )
            
            return route
            
        except KeyError as e:
            logger.error(f"Missing required field in route data: {e}")
            raise ValueError(f"Invalid route data structure: missing {e}")
        except Exception as e:
            logger.error(f"Error parsing route: {e}")
            raise


# Singleton instance
route_service = RouteService()
