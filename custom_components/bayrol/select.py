"""Support for Bayrol select entities."""

from __future__ import annotations

import logging
import json

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN,
    SENSOR_TYPES_AS5,
    SENSOR_TYPES_PM5_CHLORINE,
    BAYROL_DEVICE_ID,
    BAYROL_DEVICE_TYPE,
    VALUE_TO_MQTT_AS5,
    MQTT_TO_VALUE_AS5,
    VALUE_TO_MQTT_PM5,
    MQTT_TO_VALUE_PM5,
)

_LOGGER = logging.getLogger(__name__)


def _handle_select_value(select, value):
    """Handle incoming select value."""

    if value in MQTT_TO_VALUE_AS5:
        select._attr_current_option = MQTT_TO_VALUE_AS5[value]
    elif value in MQTT_TO_VALUE_PM5:
        select._attr_current_option = MQTT_TO_VALUE_PM5[value]
    else:
        # Try to find the value in the custom mappings
        for mqtt_value, display_value in select._mqtt_to_value.items():
            if str(value) == str(mqtt_value):
                select._attr_current_option = display_value
                break
        else:
            # If no mapping found, try to convert using coefficient
            try:
                coefficient = select._select_config.get("coefficient")
                if coefficient is not None and coefficient != -1:
                    converted_value = float(value) / coefficient
                    # Find the closest option
                    if coefficient == 1:
                        converted_value = int(converted_value)
                        options = [int(opt) for opt in select._attr_options]
                    else:
                        converted_value = float(converted_value)
                        options = [float(opt) for opt in select._attr_options]
                    closest_option = min(
                        options, key=lambda x: abs(x - converted_value)
                    )
                    select._attr_current_option = str(closest_option)
                else:
                    _LOGGER.warning("Unknown value received for select: %s", value)
            except (ValueError, TypeError):
                _LOGGER.warning("Unknown value received for select: %s", value)
    select.schedule_update_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Bayrol select entities."""
    entities = []
    device_type = config_entry.data[BAYROL_DEVICE_TYPE]
    _LOGGER.debug("device_type: %s", device_type)

    # Get the shared MQTT manager
    mqtt_manager = hass.data[DOMAIN]["mqtt_manager"]

    if device_type == "AS5":
        for select_type, select_config in SENSOR_TYPES_AS5.items():
            if select_config.get("entity_type") == "select":
                topic = select_type
                select = BayrolSelect(config_entry, select_type, select_config, topic)
                mqtt_manager.subscribe(
                    topic, lambda v, s=select: _handle_select_value(s, v)
                )
                entities.append(select)
    elif device_type == "PM5 Chlorine":
        for select_type, select_config in SENSOR_TYPES_PM5_CHLORINE.items():
            if select_config.get("entity_type") == "select":
                topic = select_type
                select = BayrolSelect(config_entry, select_type, select_config, topic)
                mqtt_manager.subscribe(
                    topic, lambda v, s=select: _handle_select_value(s, v)
                )
                entities.append(select)

    async_add_entities(entities)


class BayrolSelect(SelectEntity):
    """Representation of a Bayrol select entity."""

    def __init__(self, config_entry, select_type, select_config, topic):
        """Initialize the select entity."""
        self._config_entry = config_entry
        self._select_type = select_type
        self._select_config = select_config
        self._state_topic = topic
        self._attr_name = select_config.get("name", select_type)
        self._attr_unique_id = f"{config_entry.entry_id}_{select_type}"
        self.entity_id = (
            "select.bayrol_"
            + config_entry.data[BAYROL_DEVICE_ID]
            + "_"
            + select_config.get("name", select_type)
        )
        self._attr_current_option = None

        # Get options from config and convert to strings
        self._attr_options = [str(opt) for opt in select_config.get("options", [])]

        # Create custom mappings if provided
        self._mqtt_to_value = {}
        if "mqtt_values" in select_config:
            self._mqtt_to_value = select_config["mqtt_values"]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in self._attr_options:
            _LOGGER.error("Invalid option: %s", option)
            return

        # First try standard mapping
        if self._config_entry.data[BAYROL_DEVICE_TYPE] == "PM5 Chlorine":
            mqtt_value = VALUE_TO_MQTT_PM5.get(option)
        else:
            mqtt_value = VALUE_TO_MQTT_AS5.get(option)

        if mqtt_value is None:
            # Then try custom mapping
            mqtt_value = self._select_config.get("mqtt_values", {}).get(option)
            if mqtt_value is None:
                # If no mapping found, try to convert using coefficient
                try:
                    coefficient = self._select_config.get("coefficient")
                    if coefficient is not None and coefficient != -1:
                        # Convert option to float, multiply by coefficient, and convert to integer
                        mqtt_value = int(float(option) * coefficient)
                    else:
                        _LOGGER.error("No MQTT value mapping for option: %s", option)
                        return
                except (ValueError, TypeError):
                    _LOGGER.error("Invalid option value: %s", option)
                    return

        # Publish the new value to the MQTT topic
        topic = f"d02/{self._config_entry.data[BAYROL_DEVICE_ID]}/s/{self._state_topic}"
        payload = f'{{"t":"{self._state_topic}","v":{mqtt_value}}}'
        self.hass.data[DOMAIN]["mqtt_manager"].client.publish(topic, payload)

    @property
    def device_info(self) -> DeviceInfo:
        """Device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.data[BAYROL_DEVICE_ID])},
            manufacturer="Bayrol",
        )
