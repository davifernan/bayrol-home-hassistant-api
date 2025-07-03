"""Sensor value handling logic extracted from Home Assistant."""

from typing import Any, Optional, Dict
import logging

from app.core.const import SensorConfig

_LOGGER = logging.getLogger(__name__)


def handle_sensor_value(sensor_config: SensorConfig, value: Any) -> Any:
    """
    Handle incoming sensor value based on the sensor configuration.
    
    This is the core logic extracted from the Home Assistant sensor.py file.
    It processes the raw MQTT values and converts them to human-readable format.
    """
    # Special string-based value mappings
    match str(value):
        case "19.18":
            return "On"
        case "19.19":
            return "Off"
        case "19.195":
            return "Auto"
        case "19.115":
            return "Auto Plus"
        case "19.106":
            return "Constant production"
        case "19.177":
            return "On"
        case "19.176":
            return "Off"
        case "19.257":
            return "Missing"
        case "19.258":
            return "Not Empty"
        case "19.259":
            return "Empty"
    
    # Numeric value mappings
    match value:
        case 7001:
            return "On"
        case 7002:
            return "Off"
        case 7521:
            return "Full"
        case 7522:
            return "Low"
        case 7523:
            return "Empty"
        case 7524:
            return "Ok"
        case 7525:
            return "Info"
        case 7526:
            return "Warning"
        case 7527:
            return "Alarm"
        case _:
            # Apply coefficient if available
            coefficient = sensor_config.get("coefficient")
            if coefficient is not None and coefficient != -1:
                try:
                    return float(value) / coefficient
                except (ValueError, TypeError, ZeroDivisionError):
                    _LOGGER.error(f"Failed to apply coefficient {coefficient} to value {value}")
                    return value
            elif coefficient == -1:
                # Treat as string
                return str(value)
            else:
                # Return as-is
                return value


def format_sensor_value(sensor_config: SensorConfig, value: Any) -> Dict[str, Any]:
    """
    Format a sensor value for storage/display.
    
    Returns a dictionary with:
    - raw_value: The original MQTT value
    - value: The processed value
    - unit: The unit of measurement (if any)
    - formatted_value: String representation with unit
    """
    processed_value = handle_sensor_value(sensor_config, value)
    unit = sensor_config.get("unit_of_measurement", "")
    
    # Format the value with unit
    if unit and processed_value not in ["On", "Off", "Auto", "Auto Plus", "Constant production", 
                                        "Missing", "Not Empty", "Empty", "Full", "Low", 
                                        "Ok", "Info", "Warning", "Alarm"]:
        formatted_value = f"{processed_value} {unit}"
    else:
        formatted_value = str(processed_value)
    
    return {
        "raw_value": value,
        "value": processed_value,
        "unit": unit,
        "formatted_value": formatted_value
    }


def get_mqtt_value_for_select(device_type: str, sensor_id: str, display_value: str) -> Optional[str]:
    """
    Get the MQTT value to send for a select entity based on display value.
    
    This reverses the value mapping for sending commands back to the device.
    """
    from app.core.const import VALUE_TO_MQTT_AUTOMATIC, VALUE_TO_MQTT_PM5
    
    # For Automatic devices (SALT and Cl-pH)
    if device_type in ["Automatic SALT", "Automatic Cl-pH"]:
        return VALUE_TO_MQTT_AUTOMATIC.get(display_value)
    # For PM5 devices
    elif device_type == "PM5 Chlorine":
        return VALUE_TO_MQTT_PM5.get(display_value)
    
    # For numeric selects (pH, Redox targets, etc.), the value is sent directly
    try:
        # Try to parse as float and multiply by coefficient if needed
        sensor_config = _get_sensor_config_for_id(device_type, sensor_id)
        if sensor_config:
            coefficient = sensor_config.get("coefficient", 1)
            if coefficient and coefficient != -1:
                return str(int(float(display_value) * coefficient))
    except (ValueError, TypeError):
        pass
    
    return display_value


def _get_sensor_config_for_id(device_type: str, sensor_id: str) -> Optional[SensorConfig]:
    """Get sensor configuration for a specific sensor ID."""
    from app.core.const import get_sensor_types_for_device
    
    sensor_types = get_sensor_types_for_device(device_type)
    return sensor_types.get(sensor_id)