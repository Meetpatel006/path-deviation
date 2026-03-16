"""
WebSocket Manager

Manages WebSocket connections for real-time journey updates.
Supports multiple clients per journey with broadcast capabilities.
"""
from typing import Dict, Set
from fastapi import WebSocket
import json
import asyncio

from app.utils.logger import logger


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates
    
    Supports:
    - Multiple clients per journey
    - Broadcast updates to all clients of a journey
    - Connection lifecycle management
    - Heartbeat/ping-pong for connection health
    """
    
    def __init__(self):
        """Initialize connection manager"""
        # Map journey_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        
        # Track client info for debugging
        self.client_info: Dict[WebSocket, dict] = {}
        
        logger.info("Initialized WebSocket Connection Manager")
    
    async def connect(self, websocket: WebSocket, journey_id: str, client_id: str = "unknown") -> None:
        """
        Accept and register new WebSocket connection
        
        Args:
            websocket: WebSocket connection
            journey_id: Journey to subscribe to
            client_id: Optional client identifier
        """
        await websocket.accept()
        
        # Add to journey's connection set
        if journey_id not in self.active_connections:
            self.active_connections[journey_id] = set()
        
        self.active_connections[journey_id].add(websocket)
        
        # Store client info
        self.client_info[websocket] = {
            "journey_id": journey_id,
            "client_id": client_id,
            "connected_at": asyncio.get_event_loop().time()
        }
        
        logger.info(
            f"WebSocket connected: journey={journey_id}, client={client_id}, "
            f"total_clients={len(self.active_connections[journey_id])}"
        )
        
        # Send connection acknowledgment
        await self.send_personal_message(websocket, {
            "type": "connection_ack",
            "journey_id": journey_id,
            "message": "Connected successfully"
        })
    
    def disconnect(self, websocket: WebSocket) -> None:
        """
        Unregister WebSocket connection
        
        Args:
            websocket: WebSocket connection to remove
        """
        if websocket not in self.client_info:
            logger.warning("Attempted to disconnect unknown websocket")
            return
        
        client_info = self.client_info[websocket]
        journey_id = client_info["journey_id"]
        
        # Remove from connections
        if journey_id in self.active_connections:
            self.active_connections[journey_id].discard(websocket)
            
            # Clean up empty journey sets
            if not self.active_connections[journey_id]:
                del self.active_connections[journey_id]
                logger.debug(f"Removed empty connection set for journey {journey_id}")
        
        # Remove client info
        del self.client_info[websocket]
        
        logger.info(
            f"WebSocket disconnected: journey={journey_id}, "
            f"client={client_info['client_id']}"
        )
    
    async def send_personal_message(self, websocket: WebSocket, message: dict) -> None:
        """
        Send message to specific client
        
        Args:
            websocket: Target WebSocket connection
            message: Message dictionary to send
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast_to_journey(self, journey_id: str, message: dict) -> int:
        """
        Broadcast message to all clients of a journey
        
        Args:
            journey_id: Journey ID
            message: Message dictionary to broadcast
        
        Returns:
            Number of clients message was sent to
        """
        if journey_id not in self.active_connections:
            logger.warning(f"No active connections for journey {journey_id} - skipping broadcast")
            return 0
        
        connections = self.active_connections[journey_id].copy()
        logger.info(f"Broadcasting to journey {journey_id}: target_clients={len(connections)}")
        sent_count = 0
        failed_connections = []
        
        for websocket in connections:
            try:
                await websocket.send_json(message)
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send to client: {e}")
                failed_connections.append(websocket)
        
        # Clean up failed connections
        for websocket in failed_connections:
            self.disconnect(websocket)
        
        logger.debug(
            f"Broadcast to journey {journey_id}: "
            f"{sent_count} sent, {len(failed_connections)} failed"
        )
        
        return sent_count
    
    async def broadcast_deviation_update(
        self,
        journey_id: str,
        deviation_data: dict
    ) -> int:
        """
        Broadcast deviation detection update
        
        Args:
            journey_id: Journey ID
            deviation_data: Deviation event data
        
        Returns:
            Number of clients notified
        """
        message = {
            "type": "deviation_update",
            "journey_id": journey_id,
            "timestamp": deviation_data.get("timestamp"),
            "deviation": {
                "spatial": deviation_data.get("spatial_status"),
                "temporal": deviation_data.get("temporal_status"),
                "directional": deviation_data.get("directional_status"),
                "severity": deviation_data.get("severity")
            },
            "metrics": {
                "distance_from_route": deviation_data.get("distance_from_route"),
                "time_deviation": deviation_data.get("time_deviation")
            },
            "route_probabilities": json.loads(deviation_data.get("route_probabilities", "{}"))
        }
        
        return await self.broadcast_to_journey(journey_id, message)
    
    async def broadcast_gps_update(
        self,
        journey_id: str,
        gps_data: dict
    ) -> int:
        """
        Broadcast GPS location update
        
        Args:
            journey_id: Journey ID
            gps_data: GPS point data
        
        Returns:
            Number of clients notified
        """
        message = {
            "type": "gps_update",
            "journey_id": journey_id,
            "location": {
                "lat": gps_data.get("lat"),
                "lng": gps_data.get("lng"),
                "timestamp": gps_data.get("timestamp"),
                "speed": gps_data.get("speed"),
                "bearing": gps_data.get("bearing"),
                "accuracy": gps_data.get("accuracy")
            }
        }
        
        return await self.broadcast_to_journey(journey_id, message)
    
    async def broadcast_batch_processed(
        self,
        journey_id: str,
        batch_info: dict
    ) -> int:
        """
        Notify clients that a GPS batch was processed
        
        Args:
            journey_id: Journey ID
            batch_info: Batch processing information
        
        Returns:
            Number of clients notified
        """
        message = {
            "type": "batch_processed",
            "journey_id": journey_id,
            "batch_number": batch_info.get("batch_number"),
            "points_processed": batch_info.get("points_processed"),
            "map_matched": batch_info.get("map_matched", False),
            "matched_coords": batch_info.get("matched_coords")
        }
        
        return await self.broadcast_to_journey(journey_id, message)
    
    async def send_error(self, websocket: WebSocket, error_message: str) -> None:
        """
        Send error message to client
        
        Args:
            websocket: Target WebSocket
            error_message: Error description
        """
        message = {
            "type": "error",
            "message": error_message
        }
        
        await self.send_personal_message(websocket, message)
    
    async def heartbeat(self, websocket: WebSocket) -> None:
        """
        Send heartbeat/ping to check connection health
        
        Args:
            websocket: Target WebSocket
        """
        message = {
            "type": "ping",
            "timestamp": asyncio.get_event_loop().time()
        }
        
        await self.send_personal_message(websocket, message)
    
    def get_connection_count(self, journey_id: str) -> int:
        """
        Get number of active connections for a journey
        
        Args:
            journey_id: Journey ID
        
        Returns:
            Connection count
        """
        if journey_id not in self.active_connections:
            return 0
        
        return len(self.active_connections[journey_id])
    
    def get_total_connections(self) -> int:
        """
        Get total number of active connections across all journeys
        
        Returns:
            Total connection count
        """
        return sum(len(conns) for conns in self.active_connections.values())
    
    def get_active_journeys(self) -> list:
        """
        Get list of journey IDs with active connections
        
        Returns:
            List of journey IDs
        """
        return list(self.active_connections.keys())


# Global instance
websocket_manager = ConnectionManager()
