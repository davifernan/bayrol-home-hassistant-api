"""Constants for the Bayrol integration - extracted from Home Assistant."""

from enum import Enum
from typing import Dict, Any, List, Optional

# Domain and keys
DOMAIN = "bayrol"

BAYROL_ACCESS_TOKEN = "bayrol_access_token"
BAYROL_DEVICE_ID = "bayrol_device_id"
BAYROL_DEVICE_TYPE = "bayrol_device_type"
BAYROL_APP_LINK_CODE = "bayrol_app_link_code"

# MQTT Connection (moved to config.py as settings)
# BAYROL_HOST = "www.bayrol-poolaccess.de"
# BAYROL_PORT = 8083


class DeviceType(str, Enum):
    """Supported Bayrol device types."""
    AUTOMATIC_SALT = "Automatic SALT"
    AUTOMATIC_CL_PH = "Automatic Cl-pH"
    PM5_CHLORINE = "PM5 Chlorine"


class SensorDeviceClass(str, Enum):
    """Sensor device classes for categorization."""
    PH = "ph"
    TEMPERATURE = "temperature"
    VOLTAGE = "voltage"
    CURRENT = "current"


class SensorStateClass(str, Enum):
    """Sensor state classes."""
    MEASUREMENT = "measurement"
    TOTAL_INCREASING = "total_increasing"


# MQTT value mappings for AS5 device
VALUE_TO_MQTT_AUTOMATIC = {
    "0.25x": "19.3",
    "0.5x": "19.4",
    "0.75x": "19.5",
    "1.0x": "19.6",
    "1.25x": "19.7",
    "1.5x": "19.8",
    "2x": "19.9",
    "3x": "19.10",
    "5x": "19.11",
    "10x": "19.12",
    "On": "19.17",
    "Off": "19.18",
    "Constant production": "19.106",
    "Auto Plus": "19.115",
    "Auto": "19.195",
    "Full": "19.258",
    "Empty": "19.259",
}

# Reverse mapping for MQTT values to display values
MQTT_TO_VALUE_AUTOMATIC = {v: k for k, v in VALUE_TO_MQTT_AUTOMATIC.items()}

VALUE_TO_MQTT_PM5 = {
    "On": "7408",
    "Off": "7407",
    "Auto": "7427",
}

# Reverse mapping for MQTT values to display values
MQTT_TO_VALUE_PM5 = {v: k for k, v in VALUE_TO_MQTT_PM5.items()}


# Sensor configuration type
SensorConfig = Dict[str, Any]


def create_sensor_config(
    name: str,
    device_class: Optional[str] = None,
    state_class: Optional[str] = None,
    coefficient: Optional[float] = None,
    unit_of_measurement: Optional[str] = None,
    entity_type: str = "sensor",
    options: Optional[List[Any]] = None
) -> SensorConfig:
    """Create a sensor configuration dictionary."""
    config = {
        "name": name,
        "device_class": device_class,
        "state_class": state_class,
        "coefficient": coefficient,
        "unit_of_measurement": unit_of_measurement,
        "entity_type": entity_type,
    }
    if options is not None:
        config["options"] = options
    return config


# Common sensor types for Automatic devices
SENSOR_TYPES_AUTOMATIC: Dict[str, SensorConfig] = {
    "4.2": create_sensor_config(
        name="pH Target",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=10,
        entity_type="select",
        options=[6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 7.0, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 8.0, 8.1, 8.2]
    ),
    "4.3": create_sensor_config(
        name="pH Alert Max",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=10,
        entity_type="select",
        options=[7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 8.0, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7]
    ),
    "4.4": create_sensor_config(
        name="pH Alert Min",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=10,
        entity_type="select",
        options=[5.7, 5.8, 5.9, 6.0, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 7.0, 7.1, 7.2]
    ),
    "4.5": create_sensor_config(
        name="pH Dosing Control Time Interval",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="min"
    ),
    "4.7": create_sensor_config(
        name="Minutes Counter / Reset every hour",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="min"
    ),
    "4.26": create_sensor_config(
        name="Redox Alert Max",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="mV",
        entity_type="select",
        options=list(range(995, 495, -5))
    ),
    "4.27": create_sensor_config(
        name="Redox Alert Min",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="mV",
        entity_type="select",
        options=list(range(850, 195, -5))
    ),
    "4.28": create_sensor_config(
        name="Redox Target",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="mV",
        entity_type="select",
        options=list(range(950, 395, -5))
    ),
    "4.34": create_sensor_config(
        name="Minimal Approach to Control the pH",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=100
    ),
    "4.37": create_sensor_config(
        name="Start Delay",
        coefficient=1,
        unit_of_measurement="min",
        entity_type="select",
        options=list(range(1, 61))
    ),
    "4.38": create_sensor_config(
        name="pH Dosing Cycle",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="s"
    ),
    "4.47": create_sensor_config(
        name="pH Dosing Speed",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="%"
    ),
    "4.67": create_sensor_config(
        name="SW Version",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=100
    ),
    "4.68": create_sensor_config(
        name="SW Date",
        coefficient=-1  # Treat result as string
    ),
    "4.69": create_sensor_config(
        name="Hourly Counter / Reset every 24h",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="h"
    ),
    "4.82": create_sensor_config(
        name="Redox",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="mV"
    ),
    "4.89": create_sensor_config(
        name="pH Dosing Rate",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="%"
    ),
    "4.98": create_sensor_config(
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=10,
        unit_of_measurement="°C"
    ),
    "4.102": create_sensor_config(
        name="Conductivity",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=10,
        unit_of_measurement="mS/cm"
    ),
    "4.107": create_sensor_config(
        name="Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=100,
        unit_of_measurement="V"
    ),
    "4.182": create_sensor_config(
        name="pH",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=10
    ),
    "5.3": create_sensor_config(
        name="pH Production Rate",
        entity_type="select",
        options=["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2x", "3x", "5x", "10x"]
    ),
    "5.80": create_sensor_config(
        name="pH Minus Canister Status"
    ),
    "5.98": create_sensor_config(
        name="Filtration"
    ),
}

# Additional sensor types for Automatic SALT
SENSOR_TYPES_AUTOMATIC_SALT: Dict[str, SensorConfig] = {
    **SENSOR_TYPES_AUTOMATIC,  # Include all base sensors
    "4.51": create_sensor_config(
        name="Polarity Reversal Times",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="min"
    ),
    "4.66": create_sensor_config(
        name="Minimum Redox Produktion",
        coefficient=1,
        unit_of_measurement="%",
        entity_type="select",
        options=[100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35, 30, 25, 20, 15]
    ),
    "4.91": create_sensor_config(
        name="Electrolyzer Production Rate",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="%"
    ),
    "4.100": create_sensor_config(
        name="Salt",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=10,
        unit_of_measurement="g/l"
    ),
    "4.104": create_sensor_config(
        name="Electrolyzer Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=10,
        unit_of_measurement="V"
    ),
    "4.105": create_sensor_config(
        name="Electrolyzer Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=10,
        unit_of_measurement="A"
    ),
    "4.112": create_sensor_config(
        name="Time Before Next Polarity Reversal",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="s"
    ),
    "4.119": create_sensor_config(
        name="Time Since Polarity Reversal",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="s"
    ),
    "4.144": create_sensor_config(
        name="Salt Preferred Level",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=10,
        unit_of_measurement="g/l",
        entity_type="select",
        options=[round(x * 0.1, 1) for x in range(10, 51)]  # 1.0 to 5.0
    ),
    "5.40": create_sensor_config(
        name="Redox ON / OFF",
        entity_type="select",
        options=["On", "Off"]
    ),
    "5.41": create_sensor_config(
        name="Redox Mode",
        entity_type="select",
        options=["Auto", "Auto Plus", "Constant production"]
    ),
}

# Additional sensor types for Automatic Cl-pH
SENSOR_TYPES_AUTOMATIC_CL_PH: Dict[str, SensorConfig] = {
    **SENSOR_TYPES_AUTOMATIC,  # Include all base sensors
    "4.90": create_sensor_config(
        name="Cl Dosing Rate",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="%"
    ),
    "5.175": create_sensor_config(
        name="Cl Adjust Dosing Amount",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="%",
        entity_type="select",
        options=["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2x", "3x", "5x", "10x"]
    ),
    "5.169": create_sensor_config(
        name="Cl Canister Status"
    ),
}

# Sensor types for PM5 Chlorine
SENSOR_TYPES_PM5_CHLORINE: Dict[str, SensorConfig] = {
    "4.3001": create_sensor_config(
        name="pH Target",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=100,
        entity_type="select",
        options=[6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 7.0, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 8.0, 8.1, 8.2]
    ),
    "4.3002": create_sensor_config(
        name="pH Alert Min",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=100,
        entity_type="select",
        options=[5.7, 5.8, 5.9, 6.0, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 7.0, 7.1, 7.2]
    ),
    "4.3003": create_sensor_config(
        name="pH Alert Max",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=100,
        entity_type="select",
        options=[7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 8.0, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7]
    ),
    "4.3049": create_sensor_config(
        name="Redox Target",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="mV",
        entity_type="select",
        options=list(range(950, 395, -5))
    ),
    "4.3051": create_sensor_config(
        name="Redox Alert Min",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="mV",
        entity_type="select",
        options=list(range(850, 195, -5))
    ),
    "4.3053": create_sensor_config(
        name="Redox Alert Max",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="mV",
        entity_type="select",
        options=list(range(995, 495, -5))
    ),
    "4.4001": create_sensor_config(
        name="pH",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=100
    ),
    "4.4022": create_sensor_config(
        name="Redox",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1,
        unit_of_measurement="mV"
    ),
    "4.4033": create_sensor_config(
        name="Water Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=10,
        unit_of_measurement="°C"
    ),
    "4.4069": create_sensor_config(
        name="Air Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=10,
        unit_of_measurement="°C"
    ),
    "4.4132": create_sensor_config(
        name="Active Alarms",
        state_class=SensorStateClass.MEASUREMENT,
        coefficient=1
    ),
    "5.5433": create_sensor_config(
        name="Out 1",
        entity_type="select",
        options=["On", "Off", "Auto"]
    ),
    "5.5434": create_sensor_config(
        name="Out 2",
        entity_type="select",
        options=["On", "Off", "Auto"]
    ),
    "5.5435": create_sensor_config(
        name="Out 3",
        entity_type="select",
        options=["On", "Off", "Auto"]
    ),
    "5.5436": create_sensor_config(
        name="Out 4",
        entity_type="select",
        options=["On", "Off", "Auto"]
    ),
    "5.6012": create_sensor_config(
        name="pH Pump"
    ),
    "5.6015": create_sensor_config(
        name="Redox Pump Status"
    ),
    "5.6064": create_sensor_config(
        name="pH Canister Level"
    ),
    "5.6065": create_sensor_config(
        name="pH Status"
    ),
    "5.6068": create_sensor_config(
        name="Redox Canister Level"
    ),
    "5.6069": create_sensor_config(
        name="Redox Status"
    ),
}


def get_sensor_types_for_device(device_type: str) -> Dict[str, SensorConfig]:
    """Get the sensor types for a specific device type."""
    if device_type == DeviceType.AUTOMATIC_SALT:
        return SENSOR_TYPES_AUTOMATIC_SALT
    elif device_type == DeviceType.AUTOMATIC_CL_PH:
        return SENSOR_TYPES_AUTOMATIC_CL_PH
    elif device_type == DeviceType.PM5_CHLORINE:
        return SENSOR_TYPES_PM5_CHLORINE
    else:
        return {}