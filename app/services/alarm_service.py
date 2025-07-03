"""Alarm service for monitoring sensor values and triggering notifications."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import Alarm, AlarmHistory, Device
from app.services.redis_service import redis_service
from app.database import async_session_maker

_LOGGER = logging.getLogger(__name__)


class AlarmService:
    """Service for checking alarm conditions and managing notifications."""
    
    @staticmethod
    async def get_active_alarms_for_device(
        device_id: UUID,
        sensor_type: Optional[str] = None,
        use_cache: bool = True
    ) -> List[Alarm]:
        """
        Get active alarms for a device, optionally filtered by sensor type.
        
        Uses Redis cache when available to reduce database queries.
        """
        # Try cache first
        if use_cache:
            cached_alarms = await redis_service.get_device_alarms(str(device_id))
            if cached_alarms is not None:
                # Filter by sensor type if specified
                if sensor_type:
                    return [a for a in cached_alarms if a.get('sensor_type') == sensor_type]
                return cached_alarms
        
        # Fetch from database
        async with async_session_maker() as session:
            query = select(Alarm).where(
                and_(
                    Alarm.device_id == device_id,
                    Alarm.enabled == True
                )
            )
            
            if sensor_type:
                query = query.where(Alarm.sensor_type == sensor_type)
            
            result = await session.execute(query)
            alarms = result.scalars().all()
            
            # Cache all device alarms
            if use_cache and not sensor_type:
                alarm_dicts = [
                    {
                        'id': str(alarm.id),
                        'sensor_type': alarm.sensor_type,
                        'name': alarm.name,
                        'condition': alarm.condition,
                        'threshold_min': alarm.threshold_min,
                        'threshold_max': alarm.threshold_max,
                        'cooldown_minutes': alarm.cooldown_minutes,
                        'last_triggered': alarm.last_triggered.isoformat() if alarm.last_triggered else None,
                        'webhook_url': alarm.webhook_url,
                        'email': alarm.email
                    }
                    for alarm in alarms
                ]
                await redis_service.cache_device_alarms(str(device_id), alarm_dicts, ttl=300)
            
            return alarms
    
    @staticmethod
    async def check_alarm_conditions(
        device_id: UUID,
        sensor_type: str,
        sensor_name: str,
        value: float,
        formatted_value: str
    ) -> List[Tuple[Alarm, str]]:
        """
        Check if any alarms should be triggered for the given sensor value.
        
        Returns list of (alarm, condition_description) tuples for triggered alarms.
        """
        # Get active alarms for this sensor
        alarms = await AlarmService.get_active_alarms_for_device(device_id, sensor_type)
        
        if not alarms:
            return []
        
        triggered_alarms = []
        
        for alarm in alarms:
            # Check cooldown
            if alarm.last_triggered:
                cooldown_until = alarm.last_triggered + timedelta(minutes=alarm.cooldown_minutes)
                if datetime.utcnow() < cooldown_until:
                    _LOGGER.debug(
                        f"Alarm {alarm.id} for {sensor_type} is in cooldown until {cooldown_until}"
                    )
                    continue
            
            # Check conditions
            condition_met = False
            condition_desc = ""
            
            if alarm.condition == "above" and alarm.threshold_max is not None:
                if value > alarm.threshold_max:
                    condition_met = True
                    condition_desc = f"{sensor_name} {formatted_value} > {alarm.threshold_max} (above threshold)"
            
            elif alarm.condition == "below" and alarm.threshold_min is not None:
                if value < alarm.threshold_min:
                    condition_met = True
                    condition_desc = f"{sensor_name} {formatted_value} < {alarm.threshold_min} (below threshold)"
            
            elif alarm.condition == "equals" and alarm.threshold_min is not None:
                if value == alarm.threshold_min:
                    condition_met = True
                    condition_desc = f"{sensor_name} {formatted_value} = {alarm.threshold_min} (equals threshold)"
            
            elif alarm.condition == "out_of_range":
                if alarm.threshold_min is not None and alarm.threshold_max is not None:
                    if value < alarm.threshold_min or value > alarm.threshold_max:
                        condition_met = True
                        condition_desc = f"{sensor_name} {formatted_value} outside range [{alarm.threshold_min}, {alarm.threshold_max}]"
            
            if condition_met:
                triggered_alarms.append((alarm, condition_desc))
                _LOGGER.info(f"Alarm triggered: {alarm.name} - {condition_desc}")
        
        return triggered_alarms
    
    @staticmethod
    async def create_alarm_history(
        alarm: Alarm,
        device_id: UUID,
        sensor_type: str,
        sensor_name: str,
        sensor_value: float,
        formatted_value: str,
        condition_met: str,
        notification_results: Optional[Dict[str, Any]] = None,
        queue_for_batch: bool = True
    ) -> Optional[AlarmHistory]:
        """
        Create alarm history record.
        
        If queue_for_batch is True, adds to Redis queue for batch processing.
        Otherwise, saves directly to database.
        """
        history_data = {
            'alarm_id': str(alarm.id),
            'device_id': str(device_id),
            'sensor_type': sensor_type,
            'sensor_name': sensor_name,
            'sensor_value': sensor_value,
            'formatted_value': formatted_value,
            'condition_met': condition_met,
            'triggered_at': datetime.utcnow().isoformat(),
            'notification_sent': bool(notification_results),
            'notification_types': list(notification_results.keys()) if notification_results else [],
            'notification_results': notification_results
        }
        
        if queue_for_batch:
            # Add to Redis queue for batch processing
            await redis_service.add_alarm_history_queue(history_data)
            _LOGGER.debug(f"Queued alarm history for batch processing: {alarm.id}")
            return None
        else:
            # Save directly to database
            async with async_session_maker() as session:
                history = AlarmHistory(
                    alarm_id=alarm.id,
                    device_id=device_id,
                    sensor_type=sensor_type,
                    sensor_name=sensor_name,
                    sensor_value=sensor_value,
                    formatted_value=formatted_value,
                    condition_met=condition_met,
                    notification_sent=bool(notification_results),
                    notification_types=list(notification_results.keys()) if notification_results else [],
                    notification_results=notification_results
                )
                session.add(history)
                
                # Update alarm last_triggered
                alarm_db = await session.get(Alarm, alarm.id)
                if alarm_db:
                    alarm_db.last_triggered = datetime.utcnow()
                
                await session.commit()
                await session.refresh(history)
                
                # Invalidate cache
                await redis_service.invalidate_device_alarms(str(device_id))
                
                return history
    
    @staticmethod
    async def process_alarm_history_batch():
        """
        Process batch of alarm history from Redis queue.
        
        This should be called periodically by a background task.
        """
        batch = await redis_service.get_alarm_history_batch(batch_size=100)
        
        if not batch:
            return 0
        
        async with async_session_maker() as session:
            # Create history records
            for item in batch:
                history = AlarmHistory(
                    alarm_id=UUID(item['alarm_id']),
                    device_id=UUID(item['device_id']),
                    sensor_type=item['sensor_type'],
                    sensor_name=item.get('sensor_name'),
                    sensor_value=item['sensor_value'],
                    formatted_value=item.get('formatted_value'),
                    condition_met=item['condition_met'],
                    triggered_at=datetime.fromisoformat(item['triggered_at']),
                    notification_sent=item.get('notification_sent', False),
                    notification_types=item.get('notification_types', []),
                    notification_results=item.get('notification_results'),
                    notification_errors=item.get('notification_errors')
                )
                session.add(history)
                
                # Update alarm last_triggered
                alarm = await session.get(Alarm, UUID(item['alarm_id']))
                if alarm:
                    alarm.last_triggered = datetime.fromisoformat(item['triggered_at'])
            
            await session.commit()
            
            # Invalidate caches for affected devices
            unique_devices = set(item['device_id'] for item in batch)
            for device_id in unique_devices:
                await redis_service.invalidate_device_alarms(device_id)
        
        _LOGGER.info(f"Processed {len(batch)} alarm history records")
        return len(batch)
    
    @staticmethod
    async def get_alarm_history(
        alarm_id: Optional[UUID] = None,
        device_id: Optional[UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AlarmHistory]:
        """Get alarm history with filters."""
        async with async_session_maker() as session:
            query = select(AlarmHistory).options(
                selectinload(AlarmHistory.alarm),
                selectinload(AlarmHistory.device)
            )
            
            if alarm_id:
                query = query.where(AlarmHistory.alarm_id == alarm_id)
            if device_id:
                query = query.where(AlarmHistory.device_id == device_id)
            if start_time:
                query = query.where(AlarmHistory.triggered_at >= start_time)
            if end_time:
                query = query.where(AlarmHistory.triggered_at <= end_time)
            
            query = query.order_by(AlarmHistory.triggered_at.desc()).limit(limit)
            
            result = await session.execute(query)
            return result.scalars().all()