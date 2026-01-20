"""
Route Probability Tracker

Tracks which route alternative the user is most likely following using a weighted scoring system:
- Distance from route: 50%
- Bearing alignment: 30%
- Historical probability: 20%
"""
from typing import List, Dict
import numpy as np

from app.models.schemas import GPSPoint, Route
from app.utils.geometry import (
    find_nearest_point_on_line,
    calculate_bearing,
    bearing_difference,
    get_route_bearing_at_point
)
from app.config import settings
from app.utils.logger import logger


class RouteTracker:
    """
    Tracks route probabilities and identifies which route user is following
    
    Attributes:
        routes: List of route alternatives
        probabilities: Dictionary mapping route_id to probability (0-1)
        update_count: Number of probability updates performed
    """
    
    def __init__(self, routes: List[Route]):
        """
        Initialize route tracker with equal probabilities
        
        Args:
            routes: List of Route objects
        """
        self.routes = routes
        self.probabilities = {
            route.route_id: 1.0 / len(routes) if routes else 0.0
            for route in routes
        }
        self.update_count = 0
        
        logger.debug(
            f"Initialized RouteTracker with {len(routes)} route(s), "
            f"initial probabilities: {self.probabilities}"
        )
    
    def update_probabilities(
        self,
        gps_point: GPSPoint,
        previous_probs: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Update route probabilities based on GPS point
        
        Uses weighted scoring:
        - Distance score (50%): How close to the route
        - Bearing score (30%): How aligned with route direction
        - History score (20%): Previous probability
        
        Args:
            gps_point: Current GPS location
            previous_probs: Previous probability distribution
        
        Returns:
            Updated probability distribution
        """
        if not self.routes:
            return {}
        
        scores = []
        
        for route in self.routes:
            # Convert route geometry from (lng, lat) to (lat, lng)
            route_coords = [(lat, lng) for lng, lat in route.geometry]
            
            # 1. Distance score (50% weight)
            nearest_point, distance, segment_idx = find_nearest_point_on_line(
                (gps_point.lat, gps_point.lng),
                route_coords
            )
            
            # Normalize distance: closer = higher score
            # Use 200m as threshold (score drops to 0 at 200m+)
            distance_score = max(0, 1 - (distance / 200))
            
            # 2. Bearing score (30% weight)
            if gps_point.bearing is not None:
                # Get route bearing at nearest point
                route_bearing = get_route_bearing_at_point(
                    route_coords,
                    nearest_point
                )
                
                # Calculate bearing difference
                bearing_diff = bearing_difference(gps_point.bearing, route_bearing)
                
                # Normalize: aligned = 1, perpendicular (90°) = 0
                bearing_score = max(0, 1 - (bearing_diff / 90))
            else:
                # No bearing data, use neutral score
                bearing_score = 0.5
            
            # 3. History score (20% weight)
            history_score = previous_probs.get(route.route_id, 1.0 / len(self.routes))
            
            # Calculate weighted total score
            total_score = (
                0.5 * distance_score +
                0.3 * bearing_score +
                0.2 * history_score
            )
            
            scores.append(total_score)
            
            logger.debug(
                f"Route {route.route_id}: dist={distance:.1f}m ({distance_score:.2f}), "
                f"bearing_diff={bearing_diff if gps_point.bearing else 'N/A'} ({bearing_score:.2f}), "
                f"history={history_score:.2f}, total={total_score:.2f}"
            )
        
        # Normalize scores using softmax
        probabilities = self._softmax(scores)
        
        # Create probability dictionary
        new_probs = {
            route.route_id: prob
            for route, prob in zip(self.routes, probabilities)
        }
        
        self.probabilities = new_probs
        self.update_count += 1
        
        logger.info(
            f"Updated probabilities (#{self.update_count}): "
            f"{', '.join([f'{k}={v:.2f}' for k, v in new_probs.items()])}"
        )
        
        return new_probs
    
    def get_most_likely_route(self) -> Route:
        """
        Get the route with highest probability
        
        Returns:
            Route object with highest probability
        """
        if not self.routes:
            raise ValueError("No routes available")
        
        max_prob_route_id = max(self.probabilities, key=self.probabilities.get)
        route = next(r for r in self.routes if r.route_id == max_prob_route_id)
        
        logger.debug(
            f"Most likely route: {max_prob_route_id} "
            f"(probability={self.probabilities[max_prob_route_id]:.2f})"
        )
        
        return route
    
    def is_route_locked(self) -> bool:
        """
        Check if probability is high enough to lock to a route
        
        Route is considered "locked" when one route has >70% probability
        
        Returns:
            True if locked to a specific route
        """
        if not self.probabilities:
            return False
        
        max_prob = max(self.probabilities.values())
        is_locked = max_prob > settings.ROUTE_LOCK_THRESHOLD
        
        if is_locked:
            logger.info(f"Route locked (max probability={max_prob:.2f})")
        
        return is_locked
    
    def should_force_lock(self) -> bool:
        """
        Determine if we should force-lock to a route
        
        After a certain number of updates, force lock to highest probability
        route even if threshold not reached
        
        Returns:
            True if should force lock
        """
        should_lock = self.update_count >= settings.FORCE_LOCK_BATCHES
        
        if should_lock:
            logger.info(
                f"Forcing route lock after {self.update_count} updates "
                f"(threshold={settings.FORCE_LOCK_BATCHES})"
            )
        
        return should_lock
    
    @staticmethod
    def _softmax(scores: List[float]) -> List[float]:
        """
        Apply softmax normalization to scores
        
        Converts raw scores to probabilities that sum to 1.0
        
        Args:
            scores: List of raw scores
        
        Returns:
            List of probabilities (0-1, sum=1.0)
        """
        if not scores:
            return []
        
        # Prevent overflow by subtracting max
        scores_array = np.array(scores)
        exp_scores = np.exp(scores_array - np.max(scores_array))
        
        # Normalize
        probabilities = exp_scores / exp_scores.sum()
        
        return probabilities.tolist()
    
    def get_route_by_id(self, route_id: str) -> Route:
        """
        Get route by ID
        
        Args:
            route_id: Route identifier
        
        Returns:
            Route object
        
        Raises:
            ValueError: If route_id not found
        """
        for route in self.routes:
            if route.route_id == route_id:
                return route
        
        raise ValueError(f"Route {route_id} not found")
