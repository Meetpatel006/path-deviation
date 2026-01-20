"""
WebSocket API Endpoints

Provides real-time WebSocket connections for journey tracking.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import asyncio

from app.services.websocket_manager import websocket_manager
from app.utils.logger import logger


router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/journey/{journey_id}")
async def websocket_journey_endpoint(
    websocket: WebSocket,
    journey_id: str,
    client_id: Optional[str] = Query(default="web_client")
):
    """
    WebSocket endpoint for real-time journey updates
    
    Clients connect to this endpoint to receive:
    - GPS location updates
    - Deviation detection alerts
    - Route probability changes
    - Batch processing notifications
    
    Args:
        websocket: WebSocket connection
        journey_id: Journey UUID to track
        client_id: Optional client identifier
    
    Message Types Sent to Client:
    
    1. connection_ack:
       {
           "type": "connection_ack",
           "journey_id": "uuid",
           "message": "Connected successfully"
       }
    
    2. gps_update:
       {
           "type": "gps_update",
           "journey_id": "uuid",
           "location": {
               "lat": 18.5246,
               "lng": 73.8786,
               "timestamp": "2026-01-20T12:00:00Z",
               "speed": 60.0,
               "bearing": 270.0
           }
       }
    
    3. deviation_update:
       {
           "type": "deviation_update",
           "journey_id": "uuid",
           "timestamp": "2026-01-20T12:00:00Z",
           "deviation": {
               "spatial": "ON_ROUTE",
               "temporal": "ON_TIME",
               "directional": "TOWARD_DEST",
               "severity": "normal"
           },
           "metrics": {
               "distance_from_route": 0.0,
               "time_deviation": 0.0
           },
           "route_probabilities": {
               "route_0": 0.7,
               "route_1": 0.3
           }
       }
    
    4. batch_processed:
       {
           "type": "batch_processed",
           "journey_id": "uuid",
           "batch_number": 5,
           "points_processed": 18,
           "map_matched": true
       }
    
    5. ping (heartbeat):
       {
           "type": "ping",
           "timestamp": 1234567890.123
       }
    
    6. error:
       {
           "type": "error",
           "message": "Error description"
       }
    
    Message Types Received from Client:
    
    1. pong (heartbeat response):
       {
           "type": "pong",
           "timestamp": 1234567890.123
       }
    
    2. subscribe_events (optional - for filtering):
       {
           "type": "subscribe_events",
           "events": ["deviation_update", "gps_update"]
       }
    """
    client_id_str = client_id if client_id is not None else "web_client"
    await websocket_manager.connect(websocket, journey_id, client_id_str)
    
    try:
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client with timeout
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=30.0
                )
                
                # Handle client messages
                message_type = data.get("type")
                
                if message_type == "pong":
                    # Client responded to heartbeat
                    logger.debug(f"Received pong from client {client_id_str} for journey {journey_id}")
                
                elif message_type == "subscribe_events":
                    # Client wants to filter events (future enhancement)
                    events = data.get("events", [])
                    logger.debug(f"Client {client_id_str} subscribed to events: {events}")
                    # TODO: Store event filters per client
                
                else:
                    logger.warning(
                        f"Unknown message type from client {client_id_str}: {message_type}"
                    )
                
            except asyncio.TimeoutError:
                # No message received, send heartbeat
                await websocket_manager.heartbeat(websocket)
                
    except WebSocketDisconnect:
        logger.info(f"Client {client_id_str} disconnected from journey {journey_id}")
        websocket_manager.disconnect(websocket)
        
    except Exception as e:
        logger.error(
            f"WebSocket error for client {client_id_str}, journey {journey_id}: {e}",
            exc_info=True
        )
        websocket_manager.disconnect(websocket)


@router.get("/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics
    
    Returns:
        Statistics about active connections
    """
    return {
        "total_connections": websocket_manager.get_total_connections(),
        "active_journeys": websocket_manager.get_active_journeys(),
        "journey_details": {
            journey_id: websocket_manager.get_connection_count(journey_id)
            for journey_id in websocket_manager.get_active_journeys()
        }
    }
