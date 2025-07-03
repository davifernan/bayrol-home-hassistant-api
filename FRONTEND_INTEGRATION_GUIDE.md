# Frontend Integration Guide

Complete guide for integrating the Bayrol Pool API into your frontend application.

## Table of Contents
- [Authentication](#authentication)
- [Core Endpoints](#core-endpoints)
- [Data Types](#data-types)
- [WebSocket Integration](#websocket-integration)
- [Alarm System](#alarm-system)
- [Client Management](#client-management)
- [Error Handling](#error-handling)
- [Frontend Examples](#frontend-examples)

---

## Authentication

All API requests require an API key in the `X-API-Key` header.

### API Key Types
1. **Master API Key** - Full admin access (set in `.env` file)
2. **Generated API Keys** - Created via API for specific applications

### Getting an API Key
```bash
# Create a new API key using master key
curl -X POST http://localhost:8000/api/v1/auth/api-keys \
  -H "Content-Type: application/json" \
  -H "X-Master-Key: your-master-key" \
  -d '{
    "name": "Frontend App",
    "description": "API key for React frontend"
  }'
```

### Using API Keys
```javascript
// JavaScript example
const headers = {
  'Content-Type': 'application/json',
  'X-API-Key': 'your-api-key-here'
};
```

---

## Core Endpoints

### Device Management

#### List Devices
```http
GET /api/v1/devices?client_id=optional&skip=0&limit=100
```

**Response:**
```json
[
  {
    "id": "4b039366-e24a-45d2-8a73-665f0b3e5eb7",
    "device_id": "DFEB08564F18",
    "device_type": "PM5 Chlorine",
    "name": "Pool 1",
    "client_id": "customer-123",
    "is_active": true,
    "is_connected": true,
    "last_seen": "2025-07-02T23:40:00Z",
    "active_alarms": 2,
    "created_at": "2025-07-02T20:00:00Z",
    "updated_at": "2025-07-02T23:40:00Z"
  }
]
```

#### Get Device Details
```http
GET /api/v1/devices/{device_id}
```

#### Register New Device
```http
POST /api/v1/devices/
Content-Type: application/json

{
  "app_link_code": "A-UyQs9h",
  "device_type": "PM5 Chlorine",
  "name": "Pool 1",
  "client_id": "customer-123"
}
```

#### Update Device
```http
PATCH /api/v1/devices/{device_id}
Content-Type: application/json

{
  "name": "Updated Pool Name",
  "client_id": "new-client-456",
  "is_active": true
}
```

### Sensor Data

#### Get Current Values (Most Important for Dashboard)
```http
GET /api/v1/sensors/{device_id}/current
```

**Response:**
```json
{
  "device_id": "4b039366-e24a-45d2-8a73-665f0b3e5eb7",
  "device_name": "Pool 1",
  "last_update": "2025-07-02T23:40:38.996334",
  "sensors": {
    "4.4001": {
      "sensor_type": "4.4001",
      "sensor_name": "pH",
      "value": 7.03,
      "formatted_value": "7.03",
      "unit": null,
      "timestamp": "2025-07-02T23:34:41.335939"
    },
    "4.4022": {
      "sensor_type": "4.4022",
      "sensor_name": "Redox",
      "value": 802.0,
      "formatted_value": "802.0 mV",
      "unit": "mV",
      "timestamp": "2025-07-02T23:34:41.353838"
    },
    "5.6012": {
      "sensor_type": "5.6012",
      "sensor_name": "pH Pump",
      "value": "Off",
      "formatted_value": "Off",
      "unit": null,
      "timestamp": "2025-07-02T23:34:41.379100"
    }
  }
}
```

#### Get Historical Data
```http
GET /api/v1/sensors/{device_id}/history?start_time=2024-01-01T00:00:00&end_time=2024-01-02T00:00:00&aggregation=1hour&sensor_types=4.4001,4.4022
```

**Query Parameters:**
- `start_time` (ISO 8601): Start of time range
- `end_time` (ISO 8601): End of time range  
- `aggregation` (optional): `raw`, `1min`, `5min`, `1hour`, `1day`
- `sensor_types` (optional): Comma-separated sensor types to include

#### Control Devices (Set Target Values)
```http
PUT /api/v1/sensors/{device_id}/select/4.2
Content-Type: text/plain

7.2
```

**Select Sensor Types:**
- `4.2` - pH Target
- `4.28` - Redox Target  
- `5.3` - pH Production Rate

---

## Data Types

### Device Types
- `"Automatic SALT"` - Bayrol Automatic Salt devices
- `"Automatic Cl-pH"` - Bayrol Automatic Cl-pH devices
- `"PM5 Chlorine"` - Pool Manager 5 devices

### Sensor Types by Device

#### Common Sensors (All Devices)
| Sensor Type | Name | Value Type | Unit | Description |
|-------------|------|------------|------|-------------|
| `4.4001` | pH | `number` | - | pH value (6.8 - 8.2) |
| `4.4022` | Redox | `number` | `mV` | Oxidation potential |
| `4.4033` | Water Temperature | `number` | `°C` | Pool water temperature |
| `4.4069` | Air Temperature | `number` | `°C` | Ambient air temperature |
| `4.4132` | Active Alarms | `number` | - | Number of active device alarms |

#### PM5 Chlorine Specific
| Sensor Type | Name | Value Type | Unit | Description |
|-------------|------|------------|------|-------------|
| `5.6012` | pH Pump | `string` | - | `"Off"`, `"On"`, `"Auto"` |
| `5.6015` | Redox Pump Status | `string` | - | `"Off"`, `"On"`, `"Auto"` |
| `5.6064` | pH Canister Level | `string` | - | `"Full"`, `"Low"`, `"Empty"` |
| `5.6065` | pH Status | `string` | - | `"Ok"`, `"Info"`, `"Warning"`, `"Alarm"` |
| `5.6068` | Redox Canister Level | `string` | - | `"Full"`, `"Low"`, `"Empty"` |
| `5.6069` | Redox Status | `string` | - | `"Ok"`, `"Info"`, `"Warning"`, `"Alarm"` |

#### Automatic SALT Specific
| Sensor Type | Name | Value Type | Unit | Description |
|-------------|------|------------|------|-------------|
| `4.100` | Salt Level | `number` | `g/l` | Salt concentration |
| `4.91` | Electrolyzer Production | `number` | `%` | Production rate |
| `5.40` | Redox ON/OFF | `string` | - | `"On"`, `"Off"` |
| `5.41` | Redox Mode | `string` | - | Operating mode |

#### Select Sensors (Configurable)
| Sensor Type | Name | Value Type | Unit | Description |
|-------------|------|------------|------|-------------|
| `4.2` | pH Target | `number` | - | Target pH value |
| `4.28` | Redox Target | `number` | `mV` | Target redox value |
| `5.3` | pH Production Rate | `number` | `%` | pH dosing rate |

### Status Values
| Status | Color Suggestion | Description |
|--------|-----------------|-------------|
| `"Ok"` | 🟢 Green | Normal operation |
| `"Info"` | 🔵 Blue | Informational |
| `"Warning"` | 🟡 Yellow | Attention needed |
| `"Alarm"` | 🔴 Red | Critical issue |
| `"Off"` | ⚫ Gray | Device/pump disabled |
| `"On"` | 🟢 Green | Device/pump active |
| `"Auto"` | 🔵 Blue | Automatic mode |
| `"Full"` | 🟢 Green | Canister full |
| `"Low"` | 🟡 Yellow | Canister low |
| `"Empty"` | 🔴 Red | Canister empty |

---

## WebSocket Integration

### Connecting
```javascript
class PoolDataManager {
  constructor(deviceId, apiKey) {
    this.deviceId = deviceId;
    this.apiKey = apiKey;
    this.ws = null;
    this.listeners = new Map();
  }

  connect() {
    const wsUrl = `ws://localhost:8000/api/v1/ws/${this.deviceId}?api_key=${this.apiKey}`;
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log('Connected to pool data stream');
    };
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleSensorUpdate(data);
    };
    
    this.ws.onclose = () => {
      console.log('Disconnected from pool data stream');
      // Auto-reconnect after 5 seconds
      setTimeout(() => this.connect(), 5000);
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  handleSensorUpdate(data) {
    // Emit to registered listeners
    const listeners = this.listeners.get(data.sensor_type) || [];
    listeners.forEach(callback => callback(data));
    
    // Emit to global listeners
    const globalListeners = this.listeners.get('*') || [];
    globalListeners.forEach(callback => callback(data));
  }

  // Register listener for specific sensor type
  onSensorUpdate(sensorType, callback) {
    if (!this.listeners.has(sensorType)) {
      this.listeners.set(sensorType, []);
    }
    this.listeners.get(sensorType).push(callback);
  }

  // Register listener for all sensor updates
  onAnySensorUpdate(callback) {
    this.onSensorUpdate('*', callback);
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}
```

### WebSocket Message Format
```json
{
  "device_id": "4b039366-e24a-45d2-8a73-665f0b3e5eb7",
  "sensor_type": "4.4001",
  "sensor_name": "pH",
  "value": 7.03,
  "formatted_value": "7.03",
  "unit": null,
  "timestamp": "2025-07-02T23:34:41.335939"
}
```

### Usage Example
```javascript
// Initialize connection
const poolManager = new PoolDataManager('4b039366-e24a-45d2-8a73-665f0b3e5eb7', 'your-api-key');
poolManager.connect();

// Listen for pH updates
poolManager.onSensorUpdate('4.4001', (data) => {
  document.getElementById('ph-value').textContent = data.formatted_value;
  updatePhChart(data.value, data.timestamp);
});

// Listen for temperature updates
poolManager.onSensorUpdate('4.4033', (data) => {
  document.getElementById('temp-value').textContent = data.formatted_value;
});

// Listen for all updates
poolManager.onAnySensorUpdate((data) => {
  console.log(`${data.sensor_name}: ${data.formatted_value}`);
  updateLastSeenTimestamp(data.timestamp);
});
```

---

## Alarm System

### Alarm Conditions
- `"below"` - Trigger when value < `threshold_min`
- `"above"` - Trigger when value > `threshold_max`
- `"equals"` - Trigger when value = `threshold_min`
- `"out_of_range"` - Trigger when value outside [`threshold_min`, `threshold_max`]

### Creating Alarms
```http
POST /api/v1/devices/{device_id}/alarms
Content-Type: application/json

{
  "name": "pH Too Low",
  "sensor_type": "4.4001",
  "condition": "below",
  "threshold_min": 7.0,
  "enabled": true,
  "cooldown_minutes": 60,
  "webhook_url": "https://your-app.com/api/alarm-webhook",
  "email": "admin@yourpool.com"
}
```

### Webhook Integration
When an alarm triggers, a POST request is sent to your webhook URL:

```json
{
  "alarm_id": "alarm-uuid",
  "device_id": "device-uuid",
  "device_name": "Pool 1",
  "alarm_name": "pH Too Low",
  "sensor_type": "4.4001",
  "sensor_name": "pH",
  "sensor_value": 6.8,
  "formatted_value": "6.8",
  "condition_met": "pH 6.8 < 7.0 (below threshold)",
  "triggered_at": "2025-07-02T23:45:00Z",
  "threshold_min": 7.0,
  "threshold_max": null,
  "cooldown_minutes": 60
}
```

### Frontend Alarm Handling
```javascript
// Listen for alarm notifications via WebSocket
poolManager.onAnySensorUpdate((data) => {
  // Check if this sensor has alarms
  checkAlarmsForSensor(data.sensor_type, data.value);
});

async function checkAlarmsForSensor(sensorType, value) {
  try {
    const response = await fetch(`/api/v1/devices/${deviceId}/alarms`, {
      headers: { 'X-API-Key': apiKey }
    });
    const alarms = await response.json();
    
    const relevantAlarms = alarms.filter(alarm => 
      alarm.sensor_type === sensorType && alarm.enabled
    );
    
    relevantAlarms.forEach(alarm => {
      if (checkAlarmCondition(alarm, value)) {
        showAlarmNotification(alarm, value);
      }
    });
  } catch (error) {
    console.error('Error checking alarms:', error);
  }
}

function checkAlarmCondition(alarm, value) {
  switch (alarm.condition) {
    case 'below':
      return value < alarm.threshold_min;
    case 'above':
      return value > alarm.threshold_max;
    case 'equals':
      return Math.abs(value - alarm.threshold_min) < 0.01;
    case 'out_of_range':
      return value < alarm.threshold_min || value > alarm.threshold_max;
    default:
      return false;
  }
}
```

---

## Client Management

Use client IDs to organize devices by customer, location, or application:

### Register Device with Client ID
```javascript
async function registerDevice(appLinkCode, deviceType, name, clientId) {
  const response = await fetch('/api/v1/devices/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey
    },
    body: JSON.stringify({
      app_link_code: appLinkCode,
      device_type: deviceType,
      name: name,
      client_id: clientId
    })
  });
  
  if (!response.ok) {
    throw new Error(`Registration failed: ${response.status}`);
  }
  
  return await response.json();
}
```

### Filter Devices by Client
```javascript
async function getDevicesForClient(clientId) {
  const response = await fetch(`/api/v1/devices?client_id=${clientId}`, {
    headers: { 'X-API-Key': apiKey }
  });
  
  return await response.json();
}
```

---

## Error Handling

### HTTP Status Codes
- `200` - Success
- `201` - Created successfully
- `400` - Bad request (invalid data)
- `401` - Unauthorized (invalid API key)
- `404` - Resource not found
- `422` - Validation error
- `500` - Internal server error

### Error Response Format
```json
{
  "detail": "Error message describing what went wrong"
}
```

### Validation Error Format
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "app_link_code"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

### Error Handling Example
```javascript
async function apiCall(url, options = {}) {
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'X-API-Key': apiKey,
        'Content-Type': 'application/json',
        ...options.headers
      }
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new ApiError(response.status, error.detail);
    }
    
    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(0, 'Network error or server unavailable');
  }
}

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}
```

---

## Frontend Examples

### React Dashboard Component
```jsx
import React, { useState, useEffect } from 'react';

const PoolDashboard = ({ deviceId, apiKey }) => {
  const [sensorData, setSensorData] = useState({});
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [lastUpdate, setLastUpdate] = useState(null);

  useEffect(() => {
    // Initial data load
    loadCurrentData();
    
    // WebSocket connection
    const ws = new WebSocket(`ws://localhost:8000/api/v1/ws/${deviceId}?api_key=${apiKey}`);
    
    ws.onopen = () => setConnectionStatus('connected');
    ws.onclose = () => setConnectionStatus('disconnected');
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      updateSensorData(data);
    };
    
    return () => ws.close();
  }, [deviceId, apiKey]);

  const loadCurrentData = async () => {
    try {
      const response = await fetch(`/api/v1/sensors/${deviceId}/current`, {
        headers: { 'X-API-Key': apiKey }
      });
      const data = await response.json();
      setSensorData(data.sensors);
      setLastUpdate(new Date(data.last_update));
    } catch (error) {
      console.error('Failed to load current data:', error);
    }
  };

  const updateSensorData = (update) => {
    setSensorData(prev => ({
      ...prev,
      [update.sensor_type]: update
    }));
    setLastUpdate(new Date(update.timestamp));
  };

  const getSensorValue = (sensorType) => {
    return sensorData[sensorType]?.formatted_value || '--';
  };

  const getSensorStatus = (sensorType) => {
    const value = sensorData[sensorType]?.value;
    if (sensorType === '5.6065' || sensorType === '5.6069') {
      // Status sensors
      switch (value) {
        case 'Ok': return 'status-ok';
        case 'Warning': return 'status-warning';
        case 'Alarm': return 'status-alarm';
        default: return 'status-info';
      }
    }
    return 'status-normal';
  };

  return (
    <div className="pool-dashboard">
      <div className="connection-status">
        <span className={`status-indicator ${connectionStatus}`}>
          {connectionStatus === 'connected' ? '🟢' : '🔴'} 
          {connectionStatus}
        </span>
        {lastUpdate && (
          <span className="last-update">
            Last update: {lastUpdate.toLocaleTimeString()}
          </span>
        )}
      </div>

      <div className="sensor-grid">
        <div className="sensor-card">
          <h3>pH Level</h3>
          <div className="sensor-value">
            {getSensorValue('4.4001')}
          </div>
          <div className={`sensor-status ${getSensorStatus('5.6065')}`}>
            {getSensorValue('5.6065')}
          </div>
        </div>

        <div className="sensor-card">
          <h3>Redox</h3>
          <div className="sensor-value">
            {getSensorValue('4.4022')}
          </div>
          <div className={`sensor-status ${getSensorStatus('5.6069')}`}>
            {getSensorValue('5.6069')}
          </div>
        </div>

        <div className="sensor-card">
          <h3>Water Temperature</h3>
          <div className="sensor-value">
            {getSensorValue('4.4033')}
          </div>
        </div>

        <div className="sensor-card">
          <h3>pH Pump</h3>
          <div className="sensor-value">
            {getSensorValue('5.6012')}
          </div>
          <div className="canister-level">
            Canister: {getSensorValue('5.6064')}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PoolDashboard;
```

### CSS for Status Indicators
```css
.status-indicator.connected { color: #22c55e; }
.status-indicator.disconnected { color: #ef4444; }

.sensor-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  background: white;
}

.sensor-value {
  font-size: 2rem;
  font-weight: bold;
  margin: 8px 0;
}

.status-ok { color: #22c55e; }
.status-warning { color: #f59e0b; }
.status-alarm { color: #ef4444; }
.status-info { color: #3b82f6; }
.status-normal { color: #6b7280; }
```

### Vue.js Example
```vue
<template>
  <div class="pool-dashboard">
    <div class="sensor-grid">
      <sensor-card
        v-for="sensor in displaySensors"
        :key="sensor.type"
        :sensor="sensor"
        :data="sensorData[sensor.type]"
      />
    </div>
  </div>
</template>

<script>
export default {
  name: 'PoolDashboard',
  props: ['deviceId', 'apiKey'],
  data() {
    return {
      sensorData: {},
      ws: null,
      displaySensors: [
        { type: '4.4001', name: 'pH', icon: '🧪' },
        { type: '4.4022', name: 'Redox', icon: '⚡' },
        { type: '4.4033', name: 'Temperature', icon: '🌡️' },
        { type: '5.6012', name: 'pH Pump', icon: '💧' }
      ]
    };
  },
  mounted() {
    this.connectWebSocket();
    this.loadCurrentData();
  },
  beforeUnmount() {
    if (this.ws) this.ws.close();
  },
  methods: {
    connectWebSocket() {
      const wsUrl = `ws://localhost:8000/api/v1/ws/${this.deviceId}?api_key=${this.apiKey}`;
      this.ws = new WebSocket(wsUrl);
      
      this.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        this.$set(this.sensorData, data.sensor_type, data);
      };
    },
    async loadCurrentData() {
      try {
        const response = await fetch(`/api/v1/sensors/${this.deviceId}/current`, {
          headers: { 'X-API-Key': this.apiKey }
        });
        const data = await response.json();
        this.sensorData = data.sensors;
      } catch (error) {
        console.error('Failed to load data:', error);
      }
    }
  }
};
</script>
```

---

## Performance Tips

1. **Caching**: Cache device lists and sensor data locally
2. **Rate Limiting**: Don't poll the API too frequently - use WebSocket for real-time data
3. **Batch Requests**: Load multiple devices in one request when possible
4. **Error Recovery**: Implement automatic reconnection for WebSocket
5. **Pagination**: Use `skip` and `limit` parameters for large device lists

## Security Considerations

1. **API Key Storage**: Store API keys securely (environment variables, secure storage)
2. **HTTPS**: Use HTTPS in production
3. **Input Validation**: Validate all user inputs before sending to API
4. **Error Messages**: Don't expose sensitive information in error messages
5. **Rate Limiting**: Implement client-side rate limiting to prevent abuse

---

This guide provides everything needed to integrate the Bayrol Pool API into your frontend application. For additional examples or specific use cases, refer to the main API documentation or contact support.