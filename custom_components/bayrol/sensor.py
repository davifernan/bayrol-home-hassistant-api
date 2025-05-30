"""Support for Bayrol sensors."""

from __future__ import annotations

import logging
import threading
import paho.mqtt.client as paho
import json

from homeassistant.components.sensor import (
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN,
    SENSOR_TYPES_AS5,
    SENSOR_TYPES_PM5_CHLORINE,
    BAYROL_HOST,
    BAYROL_PORT,
    BAYROL_ACCESS_TOKEN,
    BAYROL_DEVICE_ID,
    BAYROL_DEVICE_TYPE,
)

_LOGGER = logging.getLogger(__name__)

BROKER_PASS = "1"
MQTT_TOPIC_PREFIX = None


class BayrolMQTTManager:
    """Manage the Bayrol MQTT connection."""

    def __init__(self, hass, sensors, device_id, mqtt_user):
        """Initialize the Bayrol MQTT manager."""
        self.hass = hass
        self.sensors = sensors
        self.mqtt_user = mqtt_user
        self.device_id = device_id
        self.client = None
        self.thread = None

    def _on_connect(self, client, userdata, flags, rc):
        """Handle the connection to the MQTT broker."""
        if rc == 0:
            _LOGGER.info("Connected to Bayrol MQTT broker with result code 0 (Success)")
        else:
            _LOGGER.debug("Failed to connect to MQTT broker, result code: %s", rc)
        for topic in self.sensors:
            client.subscribe("d02/" + self.device_id + "/v/" + topic)
            _LOGGER.debug("Subscribed to topic: %s", topic)
            # Push to receive initial value
            client.publish("d02/" + self.device_id + "/g/" + topic)

    def _on_message(self, client, userdata, msg):
        """Handle the incoming messages from the MQTT broker."""
        _LOGGER.debug("Received message from topic: %s", msg.topic)

        # Just get the last part of the topic
        topic_parts = msg.topic.split("/")
        sensor = self.sensors.get(topic_parts[-1])

        if sensor:
            try:
                payload = msg.payload
                value = json.loads(payload)["v"]
                match value:
                    case "19.3":
                        sensor._attr_native_value = "0.25"
                    case "19.4":
                        sensor._attr_native_value = "0.5"
                    case "19.5":
                        sensor._attr_native_value = "0.75"
                    case "19.6":
                        sensor._attr_native_value = "1.0"
                    case "19.7":
                        sensor._attr_native_value = "1.25"
                    case "19.8":
                        sensor._attr_native_value = "1.5"
                    case "19.9":
                        sensor._attr_native_value = "2"
                    case "19.10":
                        sensor._attr_native_value = "3"
                    case "19.11":
                        sensor._attr_native_value = "5"
                    case "19.12":
                        sensor._attr_native_value = "10"
                    case "19.18":
                        sensor._attr_native_value = "On"
                    case "19.19":
                        sensor._attr_native_value = "Off"
                    case "19.195":
                        sensor._attr_native_value = "Auto"
                    case "19.115":
                        sensor._attr_native_value = "Auto Plus  "
                    case "19.106":
                        sensor._attr_native_value = "Constant production"
                    case "19.177":
                        sensor._attr_native_value = "On"
                    case "19.176":
                        sensor._attr_native_value = "Off"
                    case 7001:
                        sensor._attr_native_value = "On"
                    case 7002:
                        sensor._attr_native_value = "Off"
                    case 7521:
                        sensor._attr_native_value = "Full"
                    case 7522:
                        sensor._attr_native_value = "Low"
                    case 7523:
                        sensor._attr_native_value = "Empty"
                    case 7524:
                        sensor._attr_native_value = "Ok"
                    case 7525:
                        sensor._attr_native_value = "Info"
                    case 7526:
                        sensor._attr_native_value = "Warning"
                    case 7527:
                        sensor._attr_native_value = "Alarm"
                    case _:
                        if (
                            sensor._sensor_config["coefficient"] is not None
                            and sensor._sensor_config["coefficient"] != -1
                        ):
                            sensor._attr_native_value = (
                                value / sensor._sensor_config["coefficient"]
                            )
                        elif sensor._sensor_config["coefficient"] == -1:
                            sensor._attr_native_value = str(value)
                        else:
                            sensor._attr_native_value = value

                sensor.schedule_update_ha_state()

            except Exception as e:
                _LOGGER.error("Invalid payload for %s: %s", msg.topic, e)
        else:
            _LOGGER.warning("Received message for unknown topic: %s", msg.topic)

    def _start(self):
        """Start the MQTT manager."""
        self.client = paho.Client(transport="websockets")
        self.client.username_pw_set(self.mqtt_user, BROKER_PASS)
        self.client.tls_set()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        try:
            self.client.connect(BAYROL_HOST, BAYROL_PORT, 60)
            _LOGGER.debug("MQTT connect() called for %s:%s", BAYROL_HOST, BAYROL_PORT)
        except Exception as e:
            _LOGGER.error("MQTT connect() failed: %s", e)
        self.client.loop_forever()

    def start(self):
        """Start the MQTT manager."""
        _LOGGER.debug("Starting MQTT manager")
        if not self.thread:
            self.thread = threading.Thread(target=self._start, daemon=True)
            self.thread.start()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Bayrol sensor."""
    sensors = {}
    entities = []
    mqtt_user = config_entry.data[BAYROL_ACCESS_TOKEN]
    _LOGGER.debug("mqtt_user: %s", mqtt_user)

    device_type = config_entry.data[BAYROL_DEVICE_TYPE]
    _LOGGER.debug("device_type: %s", device_type)
    if device_type == "AS5":
        for sensor_type, sensor_config in SENSOR_TYPES_AS5.items():
            topic = sensor_type
            sensor = BayrolSensor(config_entry, sensor_type, sensor_config, topic)
            sensors[topic] = sensor
            entities.append(sensor)
    elif device_type == "PM5 Chlorine":
        for sensor_type, sensor_config in SENSOR_TYPES_PM5_CHLORINE.items():
            topic = sensor_type
            sensor = BayrolSensor(config_entry, sensor_type, sensor_config, topic)
            sensors[topic] = sensor
            entities.append(sensor)

    mqtt_manager = BayrolMQTTManager(
        hass, sensors, config_entry.data[BAYROL_DEVICE_ID], mqtt_user
    )
    mqtt_manager.start()
    async_add_entities(entities)


class BayrolSensor(SensorEntity):
    """Representation of a Bayrol sensor."""

    def __init__(self, config_entry, sensor_type, sensor_config, topic):
        """Initialize the sensor."""
        self._config_entry = config_entry
        self._sensor_type = sensor_type
        self._sensor_config = sensor_config
        self._state_topic = topic
        self._attr_name = sensor_config["name"]
        self._attr_device_class = sensor_config["device_class"]
        self._attr_state_class = sensor_config["state_class"]
        self._attr_native_unit_of_measurement = sensor_config["unit_of_measurement"]
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"
        self.entity_id = (
            "sensor.bayrol_"
            + config_entry.data[BAYROL_DEVICE_ID]
            + "_"
            + sensor_config["name"]
        )
        if sensor_config["coefficient"] == 1:
            self._attr_suggested_display_precision = 0
        elif sensor_config["coefficient"] == 10:
            self._attr_suggested_display_precision = 1
        elif sensor_config["coefficient"] == 100:
            self._attr_display_precision = 2
        self._attr_native_value = None
        self._mqtt_manager = None

    def set_mqtt_manager(self, manager):
        """Set the MQTT manager."""
        self._mqtt_manager = manager

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        pass

    @property
    def device_info(self) -> DeviceInfo:
        """Device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.data[BAYROL_DEVICE_ID])},
            manufacturer="Bayrol",
        )
