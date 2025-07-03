"""Redis service for caching and queue management."""

import json
import logging
from typing import Any, Optional, List, Dict
from datetime import timedelta

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

from app.config import settings

_LOGGER = logging.getLogger(__name__)


class RedisService:
    """Service for Redis operations."""
    
    def __init__(self):
        """Initialize Redis service."""
        self.pool: Optional[ConnectionPool] = None
        self.client: Optional[redis.Redis] = None
        
    async def connect(self):
        """Connect to Redis."""
        try:
            self.pool = ConnectionPool.from_url(
                str(settings.REDIS_URL),
                decode_responses=True,
                max_connections=50
            )
            self.client = redis.Redis(connection_pool=self.pool)
            await self.client.ping()
            _LOGGER.info("Connected to Redis successfully")
        except Exception as e:
            _LOGGER.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.client:
            await self.client.close()
        if self.pool:
            await self.pool.disconnect()
        _LOGGER.info("Disconnected from Redis")
    
    # Cache operations
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        try:
            return await self.client.get(key)
        except Exception as e:
            _LOGGER.error(f"Redis GET error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache with optional TTL in seconds."""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            if ttl:
                await self.client.setex(key, ttl, value)
            else:
                await self.client.set(key, value)
        except Exception as e:
            _LOGGER.error(f"Redis SET error for key {key}: {e}")
    
    async def delete(self, key: str):
        """Delete key from cache."""
        try:
            await self.client.delete(key)
        except Exception as e:
            _LOGGER.error(f"Redis DELETE error for key {key}: {e}")
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            _LOGGER.error(f"Redis EXISTS error for key {key}: {e}")
            return False
    
    # Hash operations for complex data
    async def hget(self, key: str, field: str) -> Optional[str]:
        """Get field from hash."""
        try:
            return await self.client.hget(key, field)
        except Exception as e:
            _LOGGER.error(f"Redis HGET error for key {key}, field {field}: {e}")
            return None
    
    async def hset(self, key: str, field: str, value: Any):
        """Set field in hash."""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            await self.client.hset(key, field, value)
        except Exception as e:
            _LOGGER.error(f"Redis HSET error for key {key}, field {field}: {e}")
    
    async def hgetall(self, key: str) -> Dict[str, str]:
        """Get all fields from hash."""
        try:
            return await self.client.hgetall(key) or {}
        except Exception as e:
            _LOGGER.error(f"Redis HGETALL error for key {key}: {e}")
            return {}
    
    async def hdel(self, key: str, *fields: str):
        """Delete fields from hash."""
        try:
            await self.client.hdel(key, *fields)
        except Exception as e:
            _LOGGER.error(f"Redis HDEL error for key {key}: {e}")
    
    # List operations for queues
    async def lpush(self, key: str, *values: Any):
        """Push values to the left of list."""
        try:
            json_values = []
            for value in values:
                if isinstance(value, (dict, list)):
                    json_values.append(json.dumps(value))
                else:
                    json_values.append(value)
            await self.client.lpush(key, *json_values)
        except Exception as e:
            _LOGGER.error(f"Redis LPUSH error for key {key}: {e}")
    
    async def rpop(self, key: str) -> Optional[str]:
        """Pop value from the right of list."""
        try:
            return await self.client.rpop(key)
        except Exception as e:
            _LOGGER.error(f"Redis RPOP error for key {key}: {e}")
            return None
    
    async def llen(self, key: str) -> int:
        """Get length of list."""
        try:
            return await self.client.llen(key) or 0
        except Exception as e:
            _LOGGER.error(f"Redis LLEN error for key {key}: {e}")
            return 0
    
    # Alarm-specific cache methods
    async def cache_device_alarms(self, device_id: str, alarms: List[Dict[str, Any]], ttl: int = 300):
        """Cache active alarms for a device (5 minutes default TTL)."""
        key = f"alarms:device:{device_id}"
        await self.set(key, alarms, ttl)
    
    async def get_device_alarms(self, device_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached alarms for a device."""
        key = f"alarms:device:{device_id}"
        data = await self.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None
    
    async def invalidate_device_alarms(self, device_id: str):
        """Invalidate alarm cache for a device."""
        key = f"alarms:device:{device_id}"
        await self.delete(key)
    
    async def cache_sensor_value(self, device_id: str, sensor_type: str, value: Any, ttl: int = 60):
        """Cache sensor value for quick alarm checks (1 minute default TTL)."""
        key = f"sensor:{device_id}:{sensor_type}"
        await self.set(key, value, ttl)
    
    async def get_sensor_value(self, device_id: str, sensor_type: str) -> Optional[Any]:
        """Get cached sensor value."""
        key = f"sensor:{device_id}:{sensor_type}"
        value = await self.get(key)
        if value:
            try:
                return json.loads(value) if value.startswith('{') or value.startswith('[') else value
            except (json.JSONDecodeError, AttributeError):
                return value
        return None
    
    async def add_alarm_history_queue(self, alarm_data: Dict[str, Any]):
        """Add alarm history to processing queue."""
        await self.lpush("queue:alarm_history", alarm_data)
    
    async def get_alarm_history_batch(self, batch_size: int = 100) -> List[Dict[str, Any]]:
        """Get batch of alarm history from queue."""
        items = []
        for _ in range(batch_size):
            item = await self.rpop("queue:alarm_history")
            if not item:
                break
            try:
                items.append(json.loads(item))
            except json.JSONDecodeError:
                _LOGGER.error(f"Invalid JSON in alarm history queue: {item}")
        return items
    
    async def get_queue_length(self, queue_name: str) -> int:
        """Get length of a queue."""
        return await self.llen(f"queue:{queue_name}")


# Global Redis instance
redis_service = RedisService()