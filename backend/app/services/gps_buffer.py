"""
GPS Buffer Service

Accumulates GPS points and triggers batch processing when:
1. Buffer reaches target size (15-20 points)
2. Timeout expires (40 seconds since last batch)

Maintains overlap between batches for continuity.
"""
from typing import List, Callable, Dict, Optional, Awaitable
from datetime import datetime, timedelta
import asyncio

from app.models.schemas import GPSPoint
from app.config import settings
from app.utils.logger import logger


class GPSBuffer:
    """
    Buffers GPS points for batch processing
    
    Attributes:
        journey_id: Journey identifier
        buffer: List of accumulated GPS points
        last_batch_time: Timestamp of last batch processing
        batch_callback: Async function to call when batch is ready
    """
    
    def __init__(
        self,
        journey_id: str,
        batch_callback: Callable[[str, List[GPSPoint]], Awaitable[None]]
    ):
        """
        Initialize GPS buffer for a journey
        
        Args:
            journey_id: Journey UUID
            batch_callback: Async function to process batch (journey_id, gps_points)
        """
        self.journey_id = journey_id
        self.buffer: List[GPSPoint] = []
        self.last_batch_time = datetime.now()
        self.batch_callback = batch_callback
        self.batch_count = 0
        self.processing_lock = asyncio.Lock()
        
        logger.info(
            f"Initialized GPS buffer for journey {journey_id} "
            f"(batch_size={settings.GPS_BATCH_SIZE}, "
            f"timeout={settings.GPS_BATCH_TIMEOUT}s, "
            f"overlap={settings.GPS_OVERLAP_POINTS})"
        )

    async def add_point(self, gps_point: GPSPoint) -> bool:
        """
        Add a point to the buffer and trigger processing if needed
        
        Args:
            gps_point: GPS point to add
            
        Returns:
            True if batch was processed, False otherwise
        """
        self.buffer.append(gps_point)
        
        # Check if we should process batch
        should_process = False
        
        # Condition 1: Buffer size reached
        if len(self.buffer) >= settings.GPS_BATCH_SIZE:
            logger.debug(f"Buffer size {len(self.buffer)} reached limit for journey {self.journey_id}")
            should_process = True
            
        # Condition 2: Timeout reached (and buffer not empty)
        elif self.buffer and (datetime.now() - self.last_batch_time).total_seconds() >= settings.GPS_BATCH_TIMEOUT:
            logger.debug(f"Buffer timeout reached for journey {self.journey_id}")
            should_process = True
            
        if should_process:
            await self._process_batch()
            return True
            
        return False

    async def _process_safe_batch(self, batch_to_process: List[GPSPoint]) -> None:
        """
        Safely process a batch in the background, ensuring strict order
        """
        async with self.processing_lock:
            try:
                await self.batch_callback(self.journey_id, batch_to_process)
                logger.info(f"Batch #{self.batch_count} processing complete")
            except Exception as e:
                logger.error(
                    f"Error processing batch #{self.batch_count} for journey {self.journey_id}: {e}",
                    exc_info=True
                )
    
    async def _process_batch(self, wait: bool = False) -> None:
        """
        Trigger batch processing.
        
        Args:
            wait: If True, process inline and wait for completion
        """
        if not self.buffer:
            logger.warning(f"Attempted to process empty batch for journey {self.journey_id}")
            return
        
        batch_size = len(self.buffer)
        self.batch_count += 1
        
        logger.info(
            f"Triggering background processing for batch #{self.batch_count} "
            f"for journey {self.journey_id} ({batch_size} points)"
        )
        
        # Make a copy for processing
        batch_to_process = self.buffer.copy()
        
        # Immediately reset buffer for new points, keeping overlap
        overlap_size = min(settings.GPS_OVERLAP_POINTS, batch_size)
        self.buffer = self.buffer[-overlap_size:] if overlap_size > 0 else []
        self.last_batch_time = datetime.now()
        
        # Launch background task by default; flush can wait synchronously
        if wait:
            await self._process_safe_batch(batch_to_process)
        else:
            asyncio.create_task(self._process_safe_batch(batch_to_process))
        
        logger.debug(
            f"Batch {self.batch_count} offloaded to background loop. "
            f"Buffer reset with {len(self.buffer)} overlap points."
        )
    
    async def flush(self) -> None:
        """
        Force process any remaining points in buffer
        
        Called when journey is completed or needs immediate processing
        """
        if self.buffer:
            logger.info(f"Flushing buffer for journey {self.journey_id}")
            await self._process_batch(wait=True)
        else:
            logger.debug(f"No points to flush for journey {self.journey_id}")
    
    def get_buffer_size(self) -> int:
        """
        Get current number of points in buffer
        
        Returns:
            Number of GPS points in buffer
        """
        return len(self.buffer)
    
    def get_batch_count(self) -> int:
        """
        Get number of batches processed
        
        Returns:
            Total batches processed
        """
        return self.batch_count
    
    def get_time_since_last_batch(self) -> float:
        """
        Get seconds since last batch was processed
        
        Returns:
            Seconds elapsed
        """
        return (datetime.now() - self.last_batch_time).total_seconds()


class GPSBufferManager:
    """
    Manages GPS buffers for multiple active journeys
    """
    
    def __init__(self, batch_callback: Callable[[str, List[GPSPoint]], Awaitable[None]]):
        """
        Initialize buffer manager
        
        Args:
            batch_callback: Async function to call when batch is ready
        """
        self.buffers: Dict[str, GPSBuffer] = {}
        self.batch_callback = batch_callback
        logger.info("Initialized GPS Buffer Manager")
    
    def get_or_create_buffer(self, journey_id: str) -> GPSBuffer:
        """
        Get existing buffer or create new one for journey
        
        Args:
            journey_id: Journey UUID
        
        Returns:
            GPS buffer for the journey
        """
        if journey_id not in self.buffers:
            self.buffers[journey_id] = GPSBuffer(journey_id, self.batch_callback)
            logger.info(f"Created new GPS buffer for journey {journey_id}")
        
        return self.buffers[journey_id]
    
    async def add_point(self, journey_id: str, gps_point: GPSPoint) -> bool:
        """
        Add GPS point to appropriate buffer
        
        Args:
            journey_id: Journey UUID
            gps_point: GPS point to add
        
        Returns:
            True if batch was processed
        """
        buffer = self.get_or_create_buffer(journey_id)
        return await buffer.add_point(gps_point)
    
    async def flush_buffer(self, journey_id: str) -> None:
        """
        Force process remaining points for a journey
        
        Args:
            journey_id: Journey UUID
        """
        if journey_id in self.buffers:
            await self.buffers[journey_id].flush()
        else:
            logger.warning(f"No buffer found to flush for journey {journey_id}")
    
    def remove_buffer(self, journey_id: str) -> None:
        """
        Remove buffer for completed journey
        
        Args:
            journey_id: Journey UUID
        """
        if journey_id in self.buffers:
            del self.buffers[journey_id]
            logger.info(f"Removed GPS buffer for journey {journey_id}")
    
    def get_active_buffer_count(self) -> int:
        """
        Get number of active buffers
        
        Returns:
            Number of journey buffers
        """
        return len(self.buffers)
    
    def get_buffer_stats(self, journey_id: str) -> Optional[Dict]:
        """
        Get statistics for a specific buffer
        
        Args:
            journey_id: Journey UUID
        
        Returns:
            Dictionary with buffer stats or None if not found
        """
        if journey_id not in self.buffers:
            return None
        
        buffer = self.buffers[journey_id]
        return {
            "buffer_size": buffer.get_buffer_size(),
            "batch_count": buffer.get_batch_count(),
            "time_since_last_batch": buffer.get_time_since_last_batch()
        }
