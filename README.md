# Bayrol Pool API

A standalone FastAPI application for monitoring and controlling Bayrol pool devices via MQTT. This API provides real-time data access, historical data storage, and device management for Bayrol pool systems.

## Features

- 🏊 **Multi-pool support** - Manage multiple Bayrol devices
- 📊 **Real-time monitoring** - Live sensor data via MQTT
- 📈 **Historical data** - Time-series storage with PostgreSQL/TimescaleDB
- 🔌 **WebSocket support** - Real-time updates for web applications
- 🔐 **API key authentication** - Secure access control
- 📥 **Data export** - CSV and JSON export capabilities
- 🚨 **Alarm system** - Configurable alerts with webhook notifications
- 💾 **Redis caching** - High-performance data access for 200+ pools
- 📧 **Notification webhooks** - Integrate with any notification service

## Supported Devices

- Bayrol Automatic Salt 5 (AS5)
- Bayrol Automatic Cl-pH
- Pool Manager 5 Chlorine (PM5)

## Prerequisites

Before you begin, you'll need:

1. **Bayrol App Link Code** - An 8-character code from your Bayrol Pool Access app
2. **Docker and Docker Compose** - For running the application
3. **Device Type** - Know which Bayrol device you have

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd bayrol-home-hassistant-api
```

### 2. Set Up Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Database
DATABASE_URL=postgresql+asyncpg://bayrol:bayrol@localhost:5432/bayrol_db

# Redis
REDIS_URL=redis://localhost:6379

# API Configuration
SECRET_KEY=your-secret-key-here-change-in-production
MASTER_API_KEY=your-master-api-key-here-change-in-production

# Notification Webhooks (optional)
ALARM_WEBHOOK_URL=https://your-webhook-url.com/alarm
EMAIL_WEBHOOK_URL=https://your-email-service.com/send
```

### 3. Start the Services

```bash
docker-compose up -d
```

This will start:
- PostgreSQL with TimescaleDB (port 5432)
- Redis (port 6379)
- Bayrol API (port 8000)

### 4. Authentication Options

You have two options for API authentication:

#### Option A: Use the Master API Key (Simpler)
If you set `MASTER_API_KEY` in your `.env` file, you can use it directly:

```bash
-H "X-API-Key: your-master-api-key-from-env"
```

#### Option B: Create Additional API Keys
Create additional API keys for different applications/users:

```bash
curl -X POST http://localhost:8000/api/v1/auth/api-keys \
  -H "Content-Type: application/json" \
  -H "X-Master-Key: your-master-api-key-from-env" \
  -d '{
    "name": "Web Portal Key",
    "description": "API key for the web portal"
  }'
```

Save the returned `key` value for use in API requests.

### 5. Add Your Pool Device

To add a Bayrol device, you need:
- Your 8-character app link code from the Bayrol app
- The device type

```bash
curl -X POST http://localhost:8000/api/v1/devices \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "app_link_code": "ABCD1234",
    "device_type": "Automatic SALT",
    "name": "My Pool"
  }'
```

Device types:
- `"Automatic SALT"` - For Automatic Salt devices
- `"Automatic Cl-pH"` - For Automatic Cl-pH devices
- `"PM5 Chlorine"` - For Pool Manager 5 devices

## API Usage

### Authentication

All API requests require an API key in the `X-API-Key` header:

```bash
-H "X-API-Key: your-api-key-here"
```

### Key Endpoints

#### Device Management

```bash
# List all devices
GET /api/v1/devices

# Get device details
GET /api/v1/devices/{device_id}

# Update device
PATCH /api/v1/devices/{device_id}

# Delete device
DELETE /api/v1/devices/{device_id}
```

#### Sensor Data

```bash
# Get current sensor values
GET /api/v1/sensors/{device_id}/current

# Get historical data
GET /api/v1/sensors/{device_id}/history?start_time=2024-01-01T00:00:00&aggregation=1hour

# Update a select sensor (e.g., pH target)
PUT /api/v1/sensors/{device_id}/select/{sensor_type}
Content-Type: text/plain
Body: 7.2

# Export data
GET /api/v1/sensors/{device_id}/export?format=csv
```

#### Real-time Updates

Connect to WebSocket for live updates:

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/{device_id}?api_key=your-key');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Sensor update:', data);
};
```

## Common Sensor Types

### All Devices
- `4.182` - pH value
- `4.82` - Redox (mV)
- `4.98` - Temperature (°C)

### Automatic SALT Specific
- `4.100` - Salt level (g/l)
- `4.91` - Electrolyzer production rate (%)
- `5.40` - Redox ON/OFF (select)
- `5.41` - Redox Mode (select)

### Select Sensors (Configurable)
- `4.2` - pH Target
- `4.28` - Redox Target
- `5.3` - pH Production Rate

## Alarm System

### Creating Alarms

```bash
# Create pH low alarm
curl -X POST http://localhost:8000/api/v1/devices/{device-id}/alarms \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "pH Too Low",
    "sensor_type": "4.182",
    "condition": "below",
    "threshold_min": 7.0,
    "enabled": true,
    "cooldown_minutes": 60
  }'

# Create salt level alarm
curl -X POST http://localhost:8000/api/v1/devices/{device-id}/alarms \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Salt Level Critical",
    "sensor_type": "4.100",
    "condition": "below",
    "threshold_min": 2.5,
    "webhook_url": "https://discord.com/api/webhooks/...",
    "enabled": true
  }'
```

### Alarm Conditions
- `below` - Trigger when value drops below threshold_min
- `above` - Trigger when value exceeds threshold_max
- `equals` - Trigger when value equals threshold_min
- `out_of_range` - Trigger when outside [threshold_min, threshold_max]

### Notifications
Alarms can send notifications to:
- **Global webhook** - Set `ALARM_WEBHOOK_URL` in .env
- **Alarm-specific webhook** - Set per alarm
- **Email webhook** - Set `EMAIL_WEBHOOK_URL` in .env
- **WebSocket** - Real-time to connected clients

### Managing Alarms

```bash
# List device alarms
GET /api/v1/devices/{device-id}/alarms

# Update alarm
PUT /api/v1/alarms/{alarm-id}

# View alarm history
GET /api/v1/alarms/{alarm-id}/history

# Test alarm (simulate trigger)
POST /api/v1/alarms/test/{alarm-id}?test_value=6.5
```

## Docker Management

```bash
# View logs
docker-compose logs -f app

# Stop services
docker-compose down

# Reset database
docker-compose down -v
docker-compose up -d
```

## Development

### Running without Docker

1. Install PostgreSQL with TimescaleDB
2. Install Redis
3. Install Python dependencies:

```bash
pip install -r requirements.txt
```

4. Run migrations:

```bash
alembic upgrade head
```

5. Start the API:

```bash
uvicorn app.main:app --reload
```

### API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc

## Troubleshooting

### Device Not Connecting

1. Check the app link code is correct (8 characters)
2. Verify the device type matches your hardware
3. Check logs: `docker-compose logs app`

### No Sensor Data

1. Ensure your pool device is powered on
2. Check MQTT connection in logs
3. Verify the device appears as "connected" in `/api/v1/devices`

### Database Issues

Reset the database:

```bash
docker-compose down -v
docker-compose up -d
```

## Production Deployment

For production deployment:

1. Use a strong `SECRET_KEY` in `.env`
2. Set up proper PostgreSQL backups
3. Use HTTPS with a reverse proxy (nginx/traefik)
4. Implement rate limiting
5. Monitor with the included health endpoints

## License

[Your License Here]

## Support

For issues with:
- This API: Open a GitHub issue
- Bayrol devices: Contact Bayrol support
- Home Assistant integration: See the original project in `/old-has`