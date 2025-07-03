"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, validator


# Device schemas
class DeviceBase(BaseModel):
    """Base device schema."""
    device_type: Literal["Automatic SALT", "Automatic Cl-pH", "PM5 Chlorine"]
    name: Optional[str] = None
    client_id: Optional[str] = None
    device_metadata: Optional[Dict[str, Any]] = None


class DeviceCreate(BaseModel):
    """Schema for creating a new device."""
    app_link_code: str = Field(..., min_length=8, max_length=8, description="8-character Bayrol app link code")
    device_type: Literal["Automatic SALT", "Automatic Cl-pH", "PM5 Chlorine"]
    name: Optional[str] = None
    client_id: Optional[str] = Field(None, max_length=100, description="Custom client identifier for organization")


class DeviceUpdate(BaseModel):
    """Schema for updating a device."""
    name: Optional[str] = None
    client_id: Optional[str] = Field(None, max_length=100, description="Custom client identifier")
    is_active: Optional[bool] = None
    device_metadata: Optional[Dict[str, Any]] = None


class DeviceResponse(DeviceBase):
    """Device response schema."""
    id: UUID
    device_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DeviceDetailResponse(DeviceResponse):
    """Detailed device response with connection status."""
    is_connected: bool
    last_seen: Optional[datetime] = None
    active_alarms: int = 0


# Sensor schemas
class SensorReading(BaseModel):
    """Single sensor reading."""
    sensor_type: str
    sensor_name: str
    value: Any
    formatted_value: str
    unit: Optional[str] = None
    timestamp: datetime


class SensorCurrentResponse(BaseModel):
    """Current sensor values response."""
    device_id: UUID
    device_name: Optional[str]
    last_update: datetime
    sensors: Dict[str, SensorReading]


class SensorHistoryQuery(BaseModel):
    """Query parameters for sensor history."""
    sensor_types: Optional[List[str]] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(1000, le=10000)
    aggregation: Optional[Literal["raw", "1min", "5min", "15min", "1hour", "1day"]] = "raw"


class SensorHistoryResponse(BaseModel):
    """Sensor history response."""
    device_id: UUID
    query: SensorHistoryQuery
    data: List[Dict[str, Any]]


# Alarm schemas
class AlarmBase(BaseModel):
    """Base alarm schema."""
    sensor_type: str
    name: str
    condition: Literal["above", "below", "equals", "out_of_range"]
    threshold_min: Optional[float] = None
    threshold_max: Optional[float] = None
    webhook_url: Optional[str] = None
    email: Optional[str] = None
    cooldown_minutes: int = Field(60, ge=1, le=1440)
    
    @validator('threshold_min', 'threshold_max')
    def validate_thresholds(cls, v, values):
        condition = values.get('condition')
        if condition == 'above' and values.get('threshold_max') is None:
            raise ValueError('threshold_max is required for "above" condition')
        if condition == 'below' and values.get('threshold_min') is None:
            raise ValueError('threshold_min is required for "below" condition')
        if condition == 'out_of_range' and (values.get('threshold_min') is None or values.get('threshold_max') is None):
            raise ValueError('Both threshold_min and threshold_max are required for "out_of_range" condition')
        return v


class AlarmCreate(AlarmBase):
    """Schema for creating an alarm."""
    enabled: bool = True


class AlarmUpdate(BaseModel):
    """Schema for updating an alarm."""
    name: Optional[str] = None
    condition: Optional[Literal["above", "below", "equals", "out_of_range"]] = None
    threshold_min: Optional[float] = None
    threshold_max: Optional[float] = None
    webhook_url: Optional[str] = None
    email: Optional[str] = None
    cooldown_minutes: Optional[int] = Field(None, ge=1, le=1440)
    enabled: Optional[bool] = None


class AlarmResponse(AlarmBase):
    """Alarm response schema."""
    id: UUID
    device_id: UUID
    enabled: bool
    last_triggered: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# WebSocket schemas
class WebSocketMessage(BaseModel):
    """WebSocket message schema."""
    type: Literal["sensor_update", "alarm_triggered", "connection_status", "error"]
    device_id: UUID
    timestamp: datetime
    data: Dict[str, Any]


# API Key schemas
class ApiKeyCreate(BaseModel):
    """Schema for creating an API key."""
    name: str
    description: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None


class ApiKeyResponse(BaseModel):
    """API key response schema."""
    id: UUID
    key: str  # Only shown on creation
    name: str
    description: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Alarm History schemas
class AlarmHistoryResponse(BaseModel):
    """Alarm history response schema."""
    id: UUID
    alarm_id: UUID
    alarm_name: Optional[str] = None
    device_id: UUID
    device_name: Optional[str] = None
    sensor_type: str
    sensor_name: Optional[str]
    sensor_value: float
    formatted_value: Optional[str]
    condition_met: str
    triggered_at: datetime
    notification_sent: bool
    notification_types: Optional[List[str]] = []
    notification_results: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


# Error schemas
class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str
    code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)