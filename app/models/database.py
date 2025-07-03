"""SQLAlchemy database models."""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import Column, String, DateTime, Float, Boolean, Text, ForeignKey, Index, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Device(Base):
    """Device model for storing Bayrol pool devices."""
    
    __tablename__ = "devices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(255), unique=True, nullable=False, index=True)
    device_type = Column(String(50), nullable=False)
    name = Column(String(255), nullable=True)
    access_token = Column(Text, nullable=False)
    app_link_code = Column(String(8), nullable=True)
    client_id = Column(String(100), nullable=True, index=True)  # Custom client identifier
    is_active = Column(Boolean, default=True)
    device_metadata = Column(JSON, nullable=True)  # Store additional device info
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sensor_readings = relationship("SensorReading", back_populates="device", cascade="all, delete-orphan")
    alarms = relationship("Alarm", back_populates="device", cascade="all, delete-orphan")


class SensorReading(Base):
    """Time-series data for sensor readings."""
    
    __tablename__ = "sensor_readings"
    __table_args__ = (
        Index('idx_device_sensor_time', 'device_id', 'sensor_type', 'time'),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey('devices.id'), nullable=False)
    sensor_type = Column(String(50), nullable=False, index=True)
    sensor_name = Column(String(255), nullable=True)
    raw_value = Column(Float, nullable=True)
    value = Column(Text, nullable=True)
    formatted_value = Column(Text, nullable=True)
    unit = Column(String(50), nullable=True)
    
    # Relationship
    device = relationship("Device", back_populates="sensor_readings")


class Alarm(Base):
    """Alarm configuration for monitoring sensor values."""
    
    __tablename__ = "alarms"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey('devices.id'), nullable=False)
    sensor_type = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    condition = Column(String(20), nullable=False)  # 'above', 'below', 'equals', 'out_of_range'
    threshold_min = Column(Float, nullable=True)
    threshold_max = Column(Float, nullable=True)
    enabled = Column(Boolean, default=True)
    webhook_url = Column(Text, nullable=True)
    email = Column(String(255), nullable=True)
    cooldown_minutes = Column(Integer, default=60)  # Prevent spam
    last_triggered = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    device = relationship("Device", back_populates="alarms")


class ApiKey(Base):
    """API Key for authentication."""
    
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    permissions = Column(JSON, nullable=True)  # Store permission scopes
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)


class AlarmHistory(Base):
    """History of alarm triggers."""
    
    __tablename__ = "alarm_history"
    __table_args__ = (
        Index('idx_alarm_device_time', 'alarm_id', 'device_id', 'triggered_at'),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alarm_id = Column(UUID(as_uuid=True), ForeignKey('alarms.id'), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey('devices.id'), nullable=False)
    sensor_type = Column(String(50), nullable=False)
    sensor_name = Column(String(255), nullable=True)
    sensor_value = Column(Float, nullable=False)
    formatted_value = Column(String(255), nullable=True)
    condition_met = Column(String(50), nullable=False)  # e.g., "pH 6.5 < 7.0 (below threshold)"
    triggered_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Notification status
    notification_sent = Column(Boolean, default=False)
    notification_types = Column(JSON, nullable=True)  # ["webhook", "email", "websocket"]
    notification_results = Column(JSON, nullable=True)  # {"webhook": {"status": 200, "response": "..."}}
    notification_errors = Column(JSON, nullable=True)  # {"email": "Connection timeout"}
    
    # Relationships
    alarm = relationship("Alarm", back_populates="history")
    device = relationship("Device")


# Update Alarm model to include relationship
Alarm.history = relationship("AlarmHistory", back_populates="alarm", cascade="all, delete-orphan", order_by="AlarmHistory.triggered_at.desc()")


# Note: For TimescaleDB, you would create a hypertable for sensor_readings
# This would be done in a migration script:
# SELECT create_hypertable('sensor_readings', 'time');