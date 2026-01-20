"""
Map Matching Service

Uses Mapbox Map Matching API to snap GPS traces to road network.
Handles API failures gracefully with fallback to raw GPS data.
"""
from typing import List, Optional, Tuple
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models.schemas import GPSPoint
from app.config import settings
from app.utils.logger import logger


class MapMatchingService:
    """
    Service for map matching GPS traces to road network
    
    Uses Mapbox Map Matching API:
    https://docs.mapbox.com/api/navigation/map-matching/
    """
    
    def __init__(self):
        """Initialize map matching service"""
        self.base_url = "https://api.mapbox.com/matching/v5/mapbox"
        self.api_key = settings.MAPBOX_API_KEY
        logger.info("Initialized Map Matching Service")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def match_trace(
        self,
        gps_points: List[GPSPoint],
        travel_mode: str = "driving"
    ) -> Optional[List[Tuple[float, float]]]:
        """
        Match GPS trace to road network
        
        Args:
            gps_points: List of GPS points to match
            travel_mode: Travel mode (driving, walking, cycling)
        
        Returns:
            List of (lat, lng) coordinates snapped to roads, or None on failure
        """
        if not gps_points or len(gps_points) < 2:
            logger.warning("Need at least 2 GPS points for map matching")
            return None
        
        try:
            # Format coordinates for Mapbox API
            # Format: lng1,lat1;lng2,lat2;...
            coordinates = ";".join([
                f"{point.lng},{point.lat}" for point in gps_points
            ])
            
            # Build request URL
            url = f"{self.base_url}/{travel_mode}/{coordinates}"
            
            params = {
                "access_token": self.api_key,
                "geometries": "geojson",
                "overview": "full",
                "steps": "false",
                "timestamps": ";".join([
                    str(int(point.timestamp.timestamp())) for point in gps_points
                ])
            }
            
            logger.debug(
                f"Map matching {len(gps_points)} GPS points "
                f"(mode: {travel_mode})"
            )
            
            # Make API request
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Extract matched coordinates
            if data.get("code") != "Ok":
                logger.warning(f"Map matching failed: {data.get('message', 'Unknown error')}")
                return None
            
            matchings = data.get("matchings", [])
            if not matchings:
                logger.warning("No matchings returned from API")
                return None
            
            # Get the best matching (first one)
            best_match = matchings[0]
            geometry = best_match.get("geometry", {})
            
            if geometry.get("type") != "LineString":
                logger.warning(f"Unexpected geometry type: {geometry.get('type')}")
                return None
            
            # Extract coordinates (lng, lat) and convert to (lat, lng)
            coordinates = geometry.get("coordinates", [])
            matched_points = [(lat, lng) for lng, lat in coordinates]
            
            confidence = best_match.get("confidence", 0)
            logger.info(
                f"Map matched {len(gps_points)} points to {len(matched_points)} points "
                f"(confidence: {confidence:.2f})"
            )
            
            return matched_points
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during map matching: {e.response.status_code}")
            if e.response.status_code == 429:
                logger.warning("Rate limit exceeded for Mapbox Map Matching API")
            return None
        
        except httpx.RequestError as e:
            logger.error(f"Network error during map matching: {e}")
            return None
        
        except Exception as e:
            logger.error(f"Unexpected error during map matching: {e}", exc_info=True)
            return None
    
    async def match_trace_with_fallback(
        self,
        gps_points: List[GPSPoint],
        travel_mode: str = "driving"
    ) -> Tuple[List[Tuple[float, float]], bool]:
        """
        Match GPS trace with fallback to raw GPS if matching fails
        
        Args:
            gps_points: List of GPS points
            travel_mode: Travel mode
        
        Returns:
            Tuple of (coordinates, is_matched)
            - coordinates: List of (lat, lng) points
            - is_matched: True if successfully matched, False if using raw GPS
        """
        # Try map matching
        matched = await self.match_trace(gps_points, travel_mode)
        
        if matched and len(matched) > 0:
            return matched, True
        
        # Fallback to raw GPS coordinates
        logger.info("Falling back to raw GPS coordinates (map matching unavailable)")
        raw_coords = [(point.lat, point.lng) for point in gps_points]
        return raw_coords, False
    
    def validate_match_quality(
        self,
        original_points: List[GPSPoint],
        matched_points: List[Tuple[float, float]]
    ) -> dict:
        """
        Validate quality of map matching result
        
        Args:
            original_points: Original GPS points
            matched_points: Matched coordinates
        
        Returns:
            Dictionary with quality metrics
        """
        quality = {
            "original_count": len(original_points),
            "matched_count": len(matched_points),
            "point_ratio": len(matched_points) / len(original_points) if original_points else 0
        }
        
        # Good matching typically results in similar or more points
        # (more points = smoother road-snapped path)
        if quality["point_ratio"] < 0.5:
            logger.warning(
                f"Low match quality: {quality['matched_count']} matched points "
                f"from {quality['original_count']} GPS points"
            )
        
        return quality


# Global instance
map_matching_service = MapMatchingService()
