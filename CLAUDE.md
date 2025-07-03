# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Home Assistant custom integration for Bayrol Pool Access devices (Automatic Salt 5, Automatic Cl-pH, Pool Manager 5 Chlorine). It connects to Bayrol Cloud via MQTT WebSocket to provide real-time monitoring of pool water quality metrics.

## Development Commands

### Validation
- **HACS Validation**: Triggered automatically via GitHub Actions on push/PR (`.github/workflows/validate.yaml`)
- **Home Assistant Validation**: Triggered automatically via GitHub Actions on push/PR (`.github/workflows/hassfest.yml`)

### Testing
No explicit test framework is configured. Manual testing should be done with a Home Assistant development environment.

## Architecture

### Core Components

1. **Integration Entry Point** (`custom_components/bayrol/__init__.py`):
   - Sets up the integration and coordinates platforms
   - Manages the MQTT connection lifecycle

2. **Configuration Flow** (`custom_components/bayrol/config_flow.py`):
   - UI-based setup using an 8-character app link code
   - Fetches credentials from Bayrol API: `https://www.bayrol-poolaccess.de/webview/api/getaccessdata`
   - Stores access token and device configuration

3. **MQTT Manager** (`custom_components/bayrol/mqtt_manager.py`):
   - Manages WebSocket MQTT connection to `mqtt.bayrol-poolaccess.de:9001`
   - Uses threading for non-blocking operation
   - Topic patterns:
     - Subscribe: `d02/{device_id}/v/{sensor_id}`
     - Publish: `d02/{device_id}/g/{sensor_id}`

4. **Entity Platforms**:
   - **Sensors** (`custom_components/bayrol/sensor.py`): Read-only water quality metrics
   - **Selects** (`custom_components/bayrol/select.py`): Configurable pool settings

### Data Flow

1. User provides app link code → API call retrieves access token and device ID
2. MQTT manager connects using credentials
3. Entities subscribe to their respective MQTT topics
4. Real-time updates arrive via MQTT messages
5. Values are converted using coefficients defined in `const.py`

### Key Constants (`custom_components/bayrol/const.py`)

- Device-specific sensor definitions (30+ metrics per device type)
- Coefficient mappings for value conversion
- Select entity value-to-MQTT mappings
- Supported metrics include: pH, Redox, Salt levels, Temperature, Flow rates, etc.

## Important Considerations

- **Minimum Home Assistant Version**: 2025.1.0
- **IoT Class**: `cloud_polling` (real-time updates via MQTT)
- **Dependencies**: `paho-mqtt` for MQTT communication, `aiohttp` for API calls
- **Thread Safety**: MQTT callbacks use `hass.add_job()` for thread-safe execution
- **Value Conversion**: Most sensor values require coefficient-based conversion (defined in `const.py`)

## API Development

### Running the API
```bash
# Development with Docker
docker-compose up

# Or run locally
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### API Structure
- **Authentication**: API Key based (X-API-Key header)
- **Base URL**: `http://localhost:8000/api/v1`
- **Database**: PostgreSQL with TimescaleDB for time-series data
- **Real-time**: WebSocket support at `/ws/{device_id}`

### Key Endpoints
- `POST /auth/api-keys` - Create API key
- `POST /devices` - Add device with app link code
- `GET /devices` - List all devices
- `GET /sensors/{device_id}/current` - Current sensor values
- `GET /sensors/{device_id}/history` - Historical data with aggregation
- `PUT /sensors/{device_id}/select/{sensor_type}` - Update select sensors

## Common Development Tasks

### Adding New Sensors
1. Add sensor definition to appropriate device type in `app/core/const.py`
2. Include coefficient mapping if value conversion is needed
3. Sensor will be automatically created based on device type

### Modifying MQTT Topics
- Subscribe topics: Update in `app/core/bayrol_mqtt.py`
- Topic structure is hardcoded to Bayrol's format: `d02/{device_id}/{action}/{sensor_id}`

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

### Debugging MQTT Connection
- MQTT manager logs connection status and errors
- Check WebSocket connection to `mqtt.bayrol-poolaccess.de:8083`
- Verify access token validity in device manager