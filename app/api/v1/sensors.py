"""Sensor data endpoints."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Query, Depends
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from app.dependencies import CurrentApiKey, DatabaseSession, get_device_manager
from app.models.database import Device, SensorReading
from app.models.schemas import (
    SensorCurrentResponse, SensorHistoryQuery, SensorHistoryResponse,
    SensorReading as SensorReadingSchema, ErrorResponse
)
from app.core.sensor_handler import get_mqtt_value_for_select

router = APIRouter()


@router.get(
    "/{device_id}/current",
    response_model=SensorCurrentResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Device not found"}
    }
)
async def get_current_sensors(
    device_id: UUID,
    session: DatabaseSession,
    api_key: CurrentApiKey,
    device_manager = Depends(get_device_manager)
):
    """Get current sensor values for a device."""
    # Verify device exists
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Get current values from device manager
    current_sensors = device_manager.get_device_sensors(device_id)
    
    if not current_sensors:
        # Device might not be connected, try to get latest from DB
        result = await session.execute(
            select(SensorReading)
            .where(SensorReading.device_id == device_id)
            .order_by(SensorReading.time.desc())
            .limit(100)  # Get last 100 readings to cover all sensor types
        )
        readings = result.scalars().all()
        
        # Group by sensor type to get latest of each
        latest_by_type = {}
        for reading in readings:
            if reading.sensor_type not in latest_by_type:
                latest_by_type[reading.sensor_type] = reading
        
        # Convert to response format
        sensors = {}
        last_update = None
        
        for sensor_type, reading in latest_by_type.items():
            sensors[sensor_type] = SensorReadingSchema(
                sensor_type=reading.sensor_type,
                sensor_name=reading.sensor_name or sensor_type,
                value=reading.value,
                formatted_value=reading.formatted_value or str(reading.value),
                unit=reading.unit,
                timestamp=reading.time
            )
            if not last_update or reading.time > last_update:
                last_update = reading.time
    else:
        # Convert current values to response format
        sensors = {}
        last_update = datetime.utcnow()
        
        for sensor_type, sensor_data in current_sensors.items():
            sensors[sensor_type] = SensorReadingSchema(
                sensor_type=sensor_type,
                sensor_name=sensor_data['sensor_name'],
                value=sensor_data['value'],
                formatted_value=sensor_data['formatted_value'],
                unit=sensor_data.get('unit'),
                timestamp=sensor_data['timestamp']
            )
    
    return SensorCurrentResponse(
        device_id=device_id,
        device_name=device.name,
        last_update=last_update or datetime.utcnow(),
        sensors=sensors
    )


@router.get(
    "/{device_id}/history",
    response_model=SensorHistoryResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Device not found"}
    }
)
async def get_sensor_history(
    device_id: UUID,
    session: DatabaseSession,
    api_key: CurrentApiKey,
    sensor_types: Optional[List[str]] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(1000, le=10000),
    aggregation: Optional[str] = Query("raw", regex="^(raw|1min|5min|15min|1hour|1day)$")
):
    """Get historical sensor data for a device."""
    # Verify device exists
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Build query
    query = select(SensorReading).where(SensorReading.device_id == device_id)
    
    # Apply filters
    if sensor_types:
        query = query.where(SensorReading.sensor_type.in_(sensor_types))
    
    if start_time:
        query = query.where(SensorReading.time >= start_time)
    else:
        # Default to last 24 hours
        start_time = datetime.utcnow() - timedelta(days=1)
        query = query.where(SensorReading.time >= start_time)
    
    if end_time:
        query = query.where(SensorReading.time <= end_time)
    
    # Apply aggregation if requested
    if aggregation != "raw":
        # Use PostgreSQL time_bucket for aggregation
        interval_map = {
            "1min": "1 minute",
            "5min": "5 minutes",
            "15min": "15 minutes",
            "1hour": "1 hour",
            "1day": "1 day"
        }
        interval = interval_map[aggregation]
        
        # Aggregate query using time_bucket
        query = (
            select(
                func.time_bucket(interval, SensorReading.time).label('time'),
                SensorReading.sensor_type,
                SensorReading.sensor_name,
                func.avg(SensorReading.value).label('value'),
                func.max(SensorReading.formatted_value).label('formatted_value'),
                func.max(SensorReading.unit).label('unit')
            )
            .where(SensorReading.device_id == device_id)
            .group_by('time', SensorReading.sensor_type, SensorReading.sensor_name)
        )
        
        if sensor_types:
            query = query.where(SensorReading.sensor_type.in_(sensor_types))
        if start_time:
            query = query.where(SensorReading.time >= start_time)
        if end_time:
            query = query.where(SensorReading.time <= end_time)
    
    # Order and limit
    query = query.order_by(SensorReading.time.desc()).limit(limit)
    
    # Execute query
    result = await session.execute(query)
    readings = result.all()
    
    # Format response
    data = []
    for reading in readings:
        if aggregation != "raw":
            # Aggregated data
            data.append({
                "time": reading.time,
                "sensor_type": reading.sensor_type,
                "sensor_name": reading.sensor_name,
                "value": float(reading.value) if reading.value is not None else None,
                "formatted_value": reading.formatted_value,
                "unit": reading.unit
            })
        else:
            # Raw data
            data.append({
                "time": reading.time,
                "sensor_type": reading.sensor_type,
                "sensor_name": reading.sensor_name,
                "value": reading.value,
                "formatted_value": reading.formatted_value,
                "unit": reading.unit
            })
    
    return SensorHistoryResponse(
        device_id=device_id,
        query=SensorHistoryQuery(
            sensor_types=sensor_types,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            aggregation=aggregation
        ),
        data=data
    )


@router.put(
    "/{device_id}/select/{sensor_type}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Device or sensor not found"},
        400: {"model": ErrorResponse, "description": "Invalid value or sensor type"}
    }
)
async def update_select_sensor(
    device_id: UUID,
    sensor_type: str,
    value: str,
    session: DatabaseSession,
    api_key: CurrentApiKey,
    device_manager = Depends(get_device_manager)
):
    """Update a select sensor value (e.g., pH target, production mode)."""
    # Verify device exists
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Check if device is connected
    device_info = device_manager.get_device(device_id)
    if not device_info or not device_info['is_connected']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device is not connected"
        )
    
    # Verify this is a select sensor
    sensor_config = device_info['sensor_configs'].get(sensor_type)
    if not sensor_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor {sensor_type} not found for this device"
        )
    
    if sensor_config.get('entity_type') != 'select':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sensor {sensor_type} is not a select entity"
        )
    
    # Validate value is in options
    options = sensor_config.get('options', [])
    if options:
        # Convert value to appropriate type
        try:
            if isinstance(options[0], (int, float)):
                typed_value = float(value)
            else:
                typed_value = value
                
            if typed_value not in options:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid value. Must be one of: {options}"
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid value type. Expected {type(options[0]).__name__}"
            )
    
    # Send value to device
    success = await device_manager.send_select_value(device_id, sensor_type, value)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update sensor value"
        )


@router.get(
    "/{device_id}/export",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Device not found"}
    }
)
async def export_sensor_data(
    device_id: UUID,
    session: DatabaseSession,
    api_key: CurrentApiKey,
    sensor_types: Optional[List[str]] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    format: str = Query("csv", regex="^(csv|json)$")
):
    """Export sensor data in CSV or JSON format."""
    from fastapi.responses import StreamingResponse
    import csv
    import io
    import json
    
    # Verify device exists
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Build query
    query = select(SensorReading).where(SensorReading.device_id == device_id)
    
    if sensor_types:
        query = query.where(SensorReading.sensor_type.in_(sensor_types))
    
    if start_time:
        query = query.where(SensorReading.time >= start_time)
    else:
        start_time = datetime.utcnow() - timedelta(days=7)  # Default to last week
        query = query.where(SensorReading.time >= start_time)
    
    if end_time:
        query = query.where(SensorReading.time <= end_time)
    
    query = query.order_by(SensorReading.time.asc())
    
    # Execute query
    result = await session.execute(query)
    readings = result.scalars().all()
    
    if format == "csv":
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['timestamp', 'sensor_type', 'sensor_name', 'value', 'unit', 'formatted_value'])
        
        # Data
        for reading in readings:
            writer.writerow([
                reading.time.isoformat(),
                reading.sensor_type,
                reading.sensor_name or '',
                reading.value,
                reading.unit or '',
                reading.formatted_value or ''
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=bayrol_{device.device_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
    
    else:  # JSON
        data = []
        for reading in readings:
            data.append({
                "timestamp": reading.time.isoformat(),
                "sensor_type": reading.sensor_type,
                "sensor_name": reading.sensor_name,
                "value": reading.value,
                "unit": reading.unit,
                "formatted_value": reading.formatted_value
            })
        
        return StreamingResponse(
            io.BytesIO(json.dumps(data, indent=2).encode()),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=bayrol_{device.device_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            }
        )