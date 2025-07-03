"""MQTT Manager for Bayrol integration - extracted from Home Assistant."""

from __future__ import annotations

import logging
import threading
import paho.mqtt.client as paho
import json
from typing import Dict, Callable, Optional, Any
import asyncio

from app.config import settings

_LOGGER = logging.getLogger(__name__)


class BayrolMQTTManager:
    """Manage the Bayrol MQTT connection."""

    def __init__(self, device_id: str, mqtt_user: str, callback_handler: Optional[Any] = None):
        """Initialize the Bayrol MQTT manager."""
        self.mqtt_user = mqtt_user
        self.device_id = device_id
        self.callback_handler = callback_handler
        self.client = None
        self.thread = None
        self._subscribers: Dict[str, Callable] = {}
        self._loop = asyncio.get_event_loop()

    def subscribe(self, topic: str, callback: Callable):
        """Subscribe to a topic with a callback."""
        self._subscribers[topic] = callback
        if self.client and self.client.is_connected():
            self.client.subscribe(f"d02/{self.device_id}/v/{topic}")
            # Push to receive initial value
            self.client.publish(f"d02/{self.device_id}/g/{topic}")

    def unsubscribe(self, topic: str):
        """Unsubscribe from a topic."""
        if topic in self._subscribers:
            del self._subscribers[topic]
            if self.client and self.client.is_connected():
                self.client.unsubscribe(f"d02/{self.device_id}/v/{topic}")

    def publish(self, topic: str, value: Any):
        """Publish a value to a topic."""
        if self.client and self.client.is_connected():
            payload = json.dumps({"v": value})
            self.client.publish(f"d02/{self.device_id}/s/{topic}", payload)

    def _on_connect(self, client, userdata, flags, rc):
        """Handle the connection to the MQTT broker."""
        if rc == 0:
            _LOGGER.info("Connected to Bayrol MQTT broker with result code 0 (Success)")
            # Resubscribe to all topics
            for topic in self._subscribers:
                client.subscribe(f"d02/{self.device_id}/v/{topic}")
                client.publish(f"d02/{self.device_id}/g/{topic}")
        else:
            _LOGGER.error("Failed to connect to MQTT broker, result code: %s", rc)

    def _on_message(self, client, userdata, msg):
        """Handle the incoming messages from the MQTT broker."""
        _LOGGER.debug("Received message from topic: %s", msg.topic)

        # Just get the last part of the topic
        topic_parts = msg.topic.split("/")
        topic = topic_parts[-1]

        if topic in self._subscribers:
            try:
                payload = msg.payload
                value = json.loads(payload)["v"]
                
                # If we have a callback handler, notify it
                if self.callback_handler:
                    # Use thread-safe method to call the handler
                    self._loop.call_soon_threadsafe(
                        self.callback_handler.handle_mqtt_message,
                        self.device_id,
                        topic,
                        value
                    )
                
                # Also call the direct subscriber callback
                callback = self._subscribers[topic]
                if asyncio.iscoroutinefunction(callback):
                    self._loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(callback(value))
                    )
                else:
                    self._loop.call_soon_threadsafe(
                        lambda: callback(value)
                    )
                    
            except Exception as e:
                _LOGGER.error("Invalid payload for %s: %s", msg.topic, e)
        else:
            _LOGGER.warning("Received message for unknown topic: %s", msg.topic)

    def _on_disconnect(self, client, userdata, rc):
        """Handle disconnection from the MQTT broker."""
        if rc != 0:
            _LOGGER.warning("Unexpected disconnection from MQTT broker, result code: %s", rc)

    def _start(self):
        """Start the MQTT manager."""
        self.client = paho.Client(transport="websockets")
        self.client.username_pw_set(self.mqtt_user, "1")
        self.client.tls_set()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        try:
            self.client.connect(settings.BAYROL_MQTT_HOST, settings.BAYROL_MQTT_PORT, 60)
            _LOGGER.debug("MQTT connect() called for %s:%s", settings.BAYROL_MQTT_HOST, settings.BAYROL_MQTT_PORT)
        except Exception as e:
            _LOGGER.error("MQTT connect() failed: %s", e)
            return
            
        self.client.loop_forever()

    def start(self):
        """Start the MQTT manager."""
        _LOGGER.debug("Starting MQTT manager for device %s", self.device_id)
        if not self.thread or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._start, daemon=True)
            self.thread.start()

    def stop(self):
        """Stop the MQTT manager."""
        _LOGGER.debug("Stopping MQTT manager for device %s", self.device_id)
        if self.client:
            self.client.disconnect()
            self.client.loop_stop()
        if self.thread:
            self.thread.join(timeout=5)

    def is_connected(self) -> bool:
        """Check if the MQTT client is connected."""
        return self.client is not None and self.client.is_connected()