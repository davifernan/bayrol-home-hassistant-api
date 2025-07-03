"""Device manager for handling multiple Bayrol pool devices."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, List, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.bayrol_mqtt import BayrolMQTTManager
from app.core.const import get_sensor_types_for_device
from app.core.sensor_handler import format_sensor_value
from app.models.database import Device, SensorReading
from app.database import async_session_maker
from app.services.redis_service import redis_service

_LOGGER = logging.getLogger(__name__)


class DeviceManager:
    """Manages multiple Bayrol devices and their MQTT connections."""
    
    def __init__(self):
        """Initialize the device manager."""
        self.devices: Dict[UUID, Dict[str, Any]] = {}
        self._sensor_callbacks: Dict[str, List[Any]] = {}  # device_id -> callbacks
        self._websocket_connections: Dict[UUID, List[Any]] = {}  # device_id -> websockets
        
    async def load_devices_from_db(self):
        """Load all active devices from database and start their MQTT connections."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Device).where(Device.is_active == True)
            )
            devices = result.scalars().all()
            
            for device in devices:
                try:
                    await self.add_device(
                        device_id=device.id,
                        device_serial=device.device_id,
                        access_token=device.access_token,
                        device_type=device.device_type,
                        device_name=device.name
                    )
                except Exception as e:
                    _LOGGER.error(f"Failed to load device {device.device_id}: {e}")
    
    async def add_device(self, device_id: UUID, device_serial: str, 
                        access_token: str, device_type: str, 
                        device_name: Optional[str] = None) -> bool:
        """Add a new device and start its MQTT connection."""
        if device_id in self.devices:
            _LOGGER.warning(f"Device {device_id} already exists")
            return False
        
        try:
            # Create MQTT manager for this device
            mqtt_manager = BayrolMQTTManager(
                device_id=device_serial,
                mqtt_user=access_token,
                callback_handler=self
            )
            
            # Get sensor types for this device
            sensor_types = get_sensor_types_for_device(device_type)
            
            # Store device info
            self.devices[device_id] = {
                'id': device_id,
                'serial': device_serial,
                'name': device_name,
                'type': device_type,
                'mqtt_manager': mqtt_manager,
                'sensors': {},
                'sensor_configs': sensor_types,
                'last_seen': None,
                'is_connected': False
            }
            
            # Subscribe to all sensors for this device
            for sensor_id, sensor_config in sensor_types.items():
                if sensor_config.get("entity_type") == "sensor":
                    # Create callback for this sensor
                    async def sensor_callback(value, dev_id=device_id, s_id=sensor_id):
                        await self._handle_sensor_update(dev_id, s_id, value)
                    
                    mqtt_manager.subscribe(sensor_id, sensor_callback)
            
            # Start MQTT connection
            mqtt_manager.start()
            
            _LOGGER.info(f"Added device {device_serial} (type: {device_type})")
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to add device {device_serial}: {e}")
            if device_id in self.devices:
                del self.devices[device_id]
            return False
    
    async def remove_device(self, device_id: UUID) -> bool:
        """Remove a device and stop its MQTT connection."""
        if device_id not in self.devices:
            return False
        
        device_info = self.devices[device_id]
        mqtt_manager = device_info['mqtt_manager']
        
        # Stop MQTT connection
        mqtt_manager.stop()
        
        # Remove from active devices
        del self.devices[device_id]
        
        # Clean up callbacks and connections
        if str(device_id) in self._sensor_callbacks:
            del self._sensor_callbacks[str(device_id)]
        if device_id in self._websocket_connections:
            del self._websocket_connections[device_id]
        
        _LOGGER.info(f"Removed device {device_info['serial']}")
        return True
    
    def get_device(self, device_id: UUID) -> Optional[Dict[str, Any]]:
        """Get device information."""
        return self.devices.get(device_id)
    
    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Get all active devices."""
        return [
            {
                'id': dev['id'],
                'serial': dev['serial'],
                'name': dev['name'],
                'type': dev['type'],
                'is_connected': dev['is_connected'],
                'last_seen': dev['last_seen']
            }
            for dev in self.devices.values()
        ]
    
    def get_device_sensors(self, device_id: UUID) -> Dict[str, Any]:
        """Get current sensor values for a device."""
        device = self.devices.get(device_id)
        if not device:
            return {}
        
        return device['sensors'].copy()
    
    async def _handle_sensor_update(self, device_id: UUID, sensor_id: str, value: Any):
        """Handle sensor value update from MQTT."""
        device = self.devices.get(device_id)
        if not device:
            return
        
        # Update connection status
        device['last_seen'] = datetime.utcnow()
        device['is_connected'] = True
        
        # Get sensor config
        sensor_config = device['sensor_configs'].get(sensor_id)
        if not sensor_config:
            return
        
        # Format the sensor value
        formatted = format_sensor_value(sensor_config, value)
        
        # Update in-memory state
        device['sensors'][sensor_id] = {
            'sensor_type': sensor_id,
            'sensor_name': sensor_config['name'],
            'value': formatted['value'],
            'formatted_value': formatted['formatted_value'],
            'unit': formatted.get('unit'),
            'timestamp': datetime.utcnow()
        }
        
        # Cache sensor value for quick access
        await redis_service.cache_sensor_value(
            str(device_id), 
            sensor_id, 
            formatted['value'], 
            ttl=60  # 1 minute cache
        )
        
        # Save to database
        await self._save_sensor_reading(device_id, sensor_id, sensor_config['name'], formatted)
        
        # Notify callbacks
        await self._notify_sensor_callbacks(device_id, sensor_id, device['sensors'][sensor_id])
        
        # Check alarms
        await self._check_alarms(device_id, sensor_id, formatted['value'])
    
    async def _save_sensor_reading(self, device_id: UUID, sensor_type: str, 
                                  sensor_name: str, formatted: Dict[str, Any]):
        """Save sensor reading to database."""
        try:
            async with async_session_maker() as session:
                reading = SensorReading(
                    device_id=device_id,
                    sensor_type=sensor_type,
                    sensor_name=sensor_name,
                    raw_value=formatted['raw_value'],
                    value=str(formatted['value']),  # Convert to string
                    formatted_value=formatted['formatted_value'],
                    unit=formatted.get('unit')
                )
                session.add(reading)
                await session.commit()
        except Exception as e:
            _LOGGER.error(f"Failed to save sensor reading: {e}")
    
    async def _notify_sensor_callbacks(self, device_id: UUID, sensor_id: str, data: Dict[str, Any]):
        """Notify registered callbacks about sensor update."""
        # Notify WebSocket connections
        if device_id in self._websocket_connections:
            message = {
                "type": "sensor_update",
                "device_id": str(device_id),
                "timestamp": data['timestamp'].isoformat(),
                "data": {
                    "sensor_type": sensor_id,
                    "sensor_name": data['sensor_name'],
                    "value": data['value'],
                    "formatted_value": data['formatted_value'],
                    "unit": data.get('unit')
                }
            }
            
            for ws in self._websocket_connections[device_id]:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    _LOGGER.error(f"Failed to send WebSocket message: {e}")
    
    async def _check_alarms(self, device_id: UUID, sensor_id: str, value: Any):
        """Check if any alarms should be triggered."""
        from app.services.alarm_service import AlarmService
        from app.services.notification_service import notification_service
        
        device = self.devices.get(device_id)
        if not device:
            return
        
        # Get sensor config for formatting
        sensor_config = device['sensor_configs'].get(sensor_id)
        if not sensor_config:
            return
        
        sensor_name = sensor_config.get('name', sensor_id)
        unit = sensor_config.get('unit_of_measurement', '')
        
        # Format value for display
        if isinstance(value, (int, float)):
            formatted_value = f"{value} {unit}".strip()
        else:
            formatted_value = str(value)
        
        try:
            # Check alarm conditions
            triggered_alarms = await AlarmService.check_alarm_conditions(
                device_id=device_id,
                sensor_type=sensor_id,
                sensor_name=sensor_name,
                value=float(value) if isinstance(value, (int, float)) else 0.0,
                formatted_value=formatted_value
            )
            
            if not triggered_alarms:
                return
            
            # Get device from database for notifications
            async with async_session_maker() as session:
                device_db = await session.get(Device, device_id)
                if not device_db:
                    return
                
                # Process each triggered alarm
                for alarm, condition_desc in triggered_alarms:
                    sensor_data = {
                        'sensor_type': sensor_id,
                        'sensor_name': sensor_name,
                        'value': value,
                        'formatted_value': formatted_value,
                        'unit': unit
                    }
                    
                    # Send notifications
                    notification_results = await notification_service.send_alarm_notification(
                        alarm=alarm,
                        device=device_db,
                        sensor_data=sensor_data,
                        condition_description=condition_desc
                    )
                    
                    # Send WebSocket notification
                    await notification_service.send_websocket_alarm_notification(
                        device_id=device_id,
                        alarm=alarm,
                        sensor_data=sensor_data,
                        condition_description=condition_desc,
                        websocket_connections=self._websocket_connections
                    )
                    
                    # Create alarm history (queued for batch processing)
                    await AlarmService.create_alarm_history(
                        alarm=alarm,
                        device_id=device_id,
                        sensor_type=sensor_id,
                        sensor_name=sensor_name,
                        sensor_value=float(value) if isinstance(value, (int, float)) else 0.0,
                        formatted_value=formatted_value,
                        condition_met=condition_desc,
                        notification_results=notification_results,
                        queue_for_batch=True
                    )
                    
                    _LOGGER.info(
                        f"Alarm '{alarm.name}' triggered for device {device_db.name}: {condition_desc}"
                    )
                    
        except Exception as e:
            _LOGGER.error(f"Error checking alarms for device {device_id}, sensor {sensor_id}: {e}")
    
    def handle_mqtt_message(self, device_serial: str, topic: str, value: Any):
        """Handle MQTT message from BayrolMQTTManager."""
        # Find device by serial
        for device in self.devices.values():
            if device['serial'] == device_serial:
                # Schedule the async handler
                asyncio.create_task(
                    self._handle_sensor_update(device['id'], topic, value)
                )
                break
    
    def register_websocket(self, device_id: UUID, websocket: Any):
        """Register a WebSocket connection for a device."""
        if device_id not in self._websocket_connections:
            self._websocket_connections[device_id] = []
        self._websocket_connections[device_id].append(websocket)
    
    def unregister_websocket(self, device_id: UUID, websocket: Any):
        """Unregister a WebSocket connection."""
        if device_id in self._websocket_connections:
            self._websocket_connections[device_id].remove(websocket)
            if not self._websocket_connections[device_id]:
                del self._websocket_connections[device_id]
    
    async def send_select_value(self, device_id: UUID, sensor_id: str, value: str) -> bool:
        """Send a select value to the device."""
        device = self.devices.get(device_id)
        if not device:
            return False
        
        mqtt_manager = device['mqtt_manager']
        sensor_config = device['sensor_configs'].get(sensor_id)
        
        if not sensor_config or sensor_config.get('entity_type') != 'select':
            return False
        
        # Get MQTT value to send
        from app.core.sensor_handler import get_mqtt_value_for_select
        mqtt_value = get_mqtt_value_for_select(device['type'], sensor_id, value)
        
        if mqtt_value:
            mqtt_manager.publish(sensor_id, mqtt_value)
            return True
        
        return False
    
    async def shutdown(self):
        """Shutdown all device connections."""
        _LOGGER.info("Shutting down device manager...")
        
        # Stop all MQTT connections
        for device_id in list(self.devices.keys()):
            await self.remove_device(device_id)
        
        # Clear all connections
        self._websocket_connections.clear()
        self._sensor_callbacks.clear()