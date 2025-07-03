"""Notification service for sending alarm notifications via webhooks."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID

import aiohttp
from aiohttp import ClientTimeout

from app.config import settings
from app.models.database import Alarm, Device

_LOGGER = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications via webhooks."""
    
    # Circuit breaker configuration
    MAX_FAILURES = 5
    RESET_TIMEOUT = 300  # 5 minutes
    
    def __init__(self):
        """Initialize notification service."""
        self.webhook_failures = {}  # URL -> failure count
        self.webhook_disabled_until = {}  # URL -> datetime
        self.timeout = ClientTimeout(total=30)  # 30 second timeout
    
    def _is_webhook_available(self, url: str) -> bool:
        """Check if webhook is available (circuit breaker)."""
        # Check if webhook is temporarily disabled
        if url in self.webhook_disabled_until:
            if datetime.utcnow() < self.webhook_disabled_until[url]:
                return False
            else:
                # Reset circuit breaker
                del self.webhook_disabled_until[url]
                self.webhook_failures[url] = 0
        
        return True
    
    def _record_failure(self, url: str):
        """Record webhook failure for circuit breaker."""
        self.webhook_failures[url] = self.webhook_failures.get(url, 0) + 1
        
        if self.webhook_failures[url] >= self.MAX_FAILURES:
            self.webhook_disabled_until[url] = datetime.utcnow().replace(
                second=datetime.utcnow().second + self.RESET_TIMEOUT
            )
            _LOGGER.warning(
                f"Webhook {url} disabled for {self.RESET_TIMEOUT} seconds after {self.MAX_FAILURES} failures"
            )
    
    def _record_success(self, url: str):
        """Record webhook success."""
        self.webhook_failures[url] = 0
        if url in self.webhook_disabled_until:
            del self.webhook_disabled_until[url]
    
    async def send_alarm_notification(
        self,
        alarm: Alarm,
        device: Device,
        sensor_data: Dict[str, Any],
        condition_description: str
    ) -> Dict[str, Any]:
        """
        Send alarm notification via configured webhooks.
        
        Returns dict with results for each notification type.
        """
        results = {}
        tasks = []
        
        # Prepare base payload
        base_payload = {
            "alarm": {
                "id": str(alarm.id),
                "name": alarm.name,
                "condition": alarm.condition,
                "threshold_min": alarm.threshold_min,
                "threshold_max": alarm.threshold_max
            },
            "device": {
                "id": str(device.id),
                "device_id": device.device_id,
                "name": device.name,
                "type": device.device_type
            },
            "sensor": {
                "type": sensor_data["sensor_type"],
                "name": sensor_data["sensor_name"],
                "value": sensor_data["value"],
                "formatted_value": sensor_data["formatted_value"],
                "unit": sensor_data.get("unit")
            },
            "condition_met": condition_description,
            "triggered_at": datetime.utcnow().isoformat(),
            "severity": self._determine_severity(alarm, sensor_data["value"])
        }
        
        # Send to alarm-specific webhook if configured
        if alarm.webhook_url and self._is_webhook_available(alarm.webhook_url):
            tasks.append(self._send_webhook(alarm.webhook_url, base_payload, "alarm_webhook"))
        
        # Send to global alarm webhook if configured
        if settings.ALARM_WEBHOOK_URL and self._is_webhook_available(settings.ALARM_WEBHOOK_URL):
            tasks.append(self._send_webhook(settings.ALARM_WEBHOOK_URL, base_payload, "global_webhook"))
        
        # Send email notification via webhook if configured
        if alarm.email and settings.EMAIL_WEBHOOK_URL and self._is_webhook_available(settings.EMAIL_WEBHOOK_URL):
            email_payload = {
                **base_payload,
                "email": {
                    "to": alarm.email,
                    "subject": f"Pool Alarm: {alarm.name}",
                    "template": "alarm_notification",
                    "priority": "high" if self._determine_severity(alarm, sensor_data["value"]) == "critical" else "normal"
                }
            }
            tasks.append(self._send_webhook(settings.EMAIL_WEBHOOK_URL, email_payload, "email"))
        
        # Send all notifications concurrently
        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, (coro, result) in enumerate(zip(tasks, task_results)):
                notification_type = coro.cr_frame.f_locals.get('notification_type', f'notification_{i}')
                if isinstance(result, Exception):
                    results[notification_type] = {
                        "success": False,
                        "error": str(result)
                    }
                else:
                    results[notification_type] = result
        
        return results
    
    async def _send_webhook(
        self,
        url: str,
        payload: Dict[str, Any],
        notification_type: str
    ) -> Dict[str, Any]:
        """Send webhook notification."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Bayrol-Pool-API/1.0",
                        "X-Notification-Type": notification_type
                    }
                ) as response:
                    response_text = await response.text()
                    
                    if response.status >= 200 and response.status < 300:
                        self._record_success(url)
                        _LOGGER.info(f"Successfully sent {notification_type} to {url}")
                        
                        return {
                            "success": True,
                            "status": response.status,
                            "response": response_text[:500]  # Limit response size
                        }
                    else:
                        self._record_failure(url)
                        _LOGGER.error(
                            f"Webhook {notification_type} failed: {response.status} - {response_text}"
                        )
                        
                        return {
                            "success": False,
                            "status": response.status,
                            "error": f"HTTP {response.status}: {response_text[:500]}"
                        }
                        
        except asyncio.TimeoutError:
            self._record_failure(url)
            error_msg = f"Webhook {notification_type} timeout after {self.timeout.total}s"
            _LOGGER.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
            
        except Exception as e:
            self._record_failure(url)
            error_msg = f"Webhook {notification_type} error: {str(e)}"
            _LOGGER.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
    
    async def send_websocket_alarm_notification(
        self,
        device_id: UUID,
        alarm: Alarm,
        sensor_data: Dict[str, Any],
        condition_description: str,
        websocket_connections: Dict[UUID, List[Any]]
    ):
        """Send alarm notification via WebSocket to connected clients."""
        if device_id not in websocket_connections:
            return
        
        message = {
            "type": "alarm_triggered",
            "device_id": str(device_id),
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "alarm": {
                    "id": str(alarm.id),
                    "name": alarm.name,
                    "condition": alarm.condition
                },
                "sensor": sensor_data,
                "condition_met": condition_description,
                "severity": self._determine_severity(alarm, sensor_data["value"])
            }
        }
        
        # Send to all connected WebSocket clients for this device
        disconnected = []
        for ws in websocket_connections[device_id]:
            try:
                await ws.send_json(message)
            except Exception as e:
                _LOGGER.error(f"Failed to send WebSocket alarm notification: {e}")
                disconnected.append(ws)
        
        # Remove disconnected clients
        for ws in disconnected:
            websocket_connections[device_id].remove(ws)
    
    def _determine_severity(self, alarm: Alarm, value: float) -> str:
        """
        Determine alarm severity based on how far the value is from thresholds.
        
        Returns: 'critical', 'warning', or 'info'
        """
        if alarm.condition == "above" and alarm.threshold_max:
            deviation = (value - alarm.threshold_max) / alarm.threshold_max
            if deviation > 0.2:  # 20% above threshold
                return "critical"
            elif deviation > 0.1:  # 10% above threshold
                return "warning"
        
        elif alarm.condition == "below" and alarm.threshold_min:
            deviation = (alarm.threshold_min - value) / alarm.threshold_min
            if deviation > 0.2:  # 20% below threshold
                return "critical"
            elif deviation > 0.1:  # 10% below threshold
                return "warning"
        
        elif alarm.condition == "out_of_range":
            if alarm.threshold_min and alarm.threshold_max:
                range_size = alarm.threshold_max - alarm.threshold_min
                if value < alarm.threshold_min:
                    deviation = (alarm.threshold_min - value) / range_size
                else:
                    deviation = (value - alarm.threshold_max) / range_size
                
                if deviation > 0.2:
                    return "critical"
                elif deviation > 0.1:
                    return "warning"
        
        return "info"


# Global notification service instance
notification_service = NotificationService()