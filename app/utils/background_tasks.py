"""Background tasks for the application."""

import asyncio
import logging
from datetime import datetime

from app.services.alarm_service import AlarmService
from app.services.redis_service import redis_service

_LOGGER = logging.getLogger(__name__)


async def process_alarm_history_task():
    """
    Background task to process alarm history from Redis queue.
    
    This should be run periodically to batch insert alarm history records.
    """
    while True:
        try:
            # Process batch
            processed = await AlarmService.process_alarm_history_batch()
            
            if processed > 0:
                _LOGGER.info(f"Processed {processed} alarm history records from queue")
            
            # Check queue length
            queue_length = await redis_service.get_queue_length("alarm_history")
            if queue_length > 1000:
                _LOGGER.warning(f"Alarm history queue is large: {queue_length} items")
                # Process more frequently if queue is backing up
                await asyncio.sleep(5)
            else:
                # Normal interval - every 30 seconds
                await asyncio.sleep(30)
                
        except Exception as e:
            _LOGGER.error(f"Error in alarm history processing task: {e}")
            await asyncio.sleep(60)  # Wait longer on error


async def start_background_tasks():
    """Start all background tasks."""
    tasks = [
        asyncio.create_task(process_alarm_history_task()),
    ]
    
    _LOGGER.info("Started background tasks")
    
    # Keep tasks running
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        _LOGGER.info("Background tasks cancelled")
        for task in tasks:
            task.cancel()


def create_background_task_runner():
    """Create a background task runner that can be started in a thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(start_background_tasks())
    except KeyboardInterrupt:
        _LOGGER.info("Background tasks interrupted")
    finally:
        loop.close()