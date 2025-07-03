"""Alarm management endpoints."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.dependencies import CurrentApiKey, DatabaseSession, get_device_manager
from app.models.database import Device, Alarm, AlarmHistory
from app.models.schemas import (
    AlarmCreate, AlarmUpdate, AlarmResponse, AlarmHistoryResponse, ErrorResponse
)
from app.services.alarm_service import AlarmService
from app.services.redis_service import redis_service
from app.core.const import get_sensor_types_for_device

router = APIRouter()


@router.post(
    "/devices/{device_id}/alarms",
    response_model=AlarmResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Device not found"}
    }
)
async def create_alarm(
    device_id: UUID,
    alarm_data: AlarmCreate,
    session: DatabaseSession,
    api_key: CurrentApiKey
):
    """Create a new alarm for a device."""
    # Verify device exists
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Verify sensor type is valid for device
    sensor_types = get_sensor_types_for_device(device.device_type)
    if alarm_data.sensor_type not in sensor_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sensor type '{alarm_data.sensor_type}' for device type '{device.device_type}'"
        )
    
    # Create alarm
    alarm = Alarm(
        device_id=device_id,
        sensor_type=alarm_data.sensor_type,
        name=alarm_data.name,
        condition=alarm_data.condition,
        threshold_min=alarm_data.threshold_min,
        threshold_max=alarm_data.threshold_max,
        enabled=alarm_data.enabled,
        webhook_url=alarm_data.webhook_url,
        email=alarm_data.email,
        cooldown_minutes=alarm_data.cooldown_minutes
    )
    
    session.add(alarm)
    await session.commit()
    await session.refresh(alarm)
    
    # Invalidate cache
    await redis_service.invalidate_device_alarms(str(device_id))
    
    return AlarmResponse.from_orm(alarm)


@router.get(
    "/devices/{device_id}/alarms",
    response_model=List[AlarmResponse],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Device not found"}
    }
)
async def list_device_alarms(
    device_id: UUID,
    session: DatabaseSession,
    api_key: CurrentApiKey,
    enabled_only: bool = Query(False, description="Only return enabled alarms")
):
    """List all alarms for a device."""
    # Verify device exists
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Query alarms
    query = select(Alarm).where(Alarm.device_id == device_id)
    
    if enabled_only:
        query = query.where(Alarm.enabled == True)
    
    query = query.order_by(Alarm.created_at.desc())
    
    result = await session.execute(query)
    alarms = result.scalars().all()
    
    return [AlarmResponse.from_orm(alarm) for alarm in alarms]


@router.get(
    "/alarms/{alarm_id}",
    response_model=AlarmResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Alarm not found"}
    }
)
async def get_alarm(
    alarm_id: UUID,
    session: DatabaseSession,
    api_key: CurrentApiKey
):
    """Get alarm details."""
    alarm = await session.get(Alarm, alarm_id)
    
    if not alarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found"
        )
    
    return AlarmResponse.from_orm(alarm)


@router.put(
    "/alarms/{alarm_id}",
    response_model=AlarmResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Alarm not found"}
    }
)
async def update_alarm(
    alarm_id: UUID,
    alarm_update: AlarmUpdate,
    session: DatabaseSession,
    api_key: CurrentApiKey
):
    """Update an alarm."""
    alarm = await session.get(Alarm, alarm_id)
    
    if not alarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found"
        )
    
    # Update fields
    update_data = alarm_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(alarm, field, value)
    
    await session.commit()
    await session.refresh(alarm)
    
    # Invalidate cache
    await redis_service.invalidate_device_alarms(str(alarm.device_id))
    
    return AlarmResponse.from_orm(alarm)


@router.delete(
    "/alarms/{alarm_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Alarm not found"}
    }
)
async def delete_alarm(
    alarm_id: UUID,
    session: DatabaseSession,
    api_key: CurrentApiKey
):
    """Delete an alarm."""
    alarm = await session.get(Alarm, alarm_id)
    
    if not alarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found"
        )
    
    device_id = alarm.device_id
    
    await session.delete(alarm)
    await session.commit()
    
    # Invalidate cache
    await redis_service.invalidate_device_alarms(str(device_id))


@router.get(
    "/alarms/{alarm_id}/history",
    response_model=List[AlarmHistoryResponse],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Alarm not found"}
    }
)
async def get_alarm_history(
    alarm_id: UUID,
    session: DatabaseSession,
    api_key: CurrentApiKey,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(100, le=1000)
):
    """Get alarm trigger history."""
    # Verify alarm exists
    alarm = await session.get(Alarm, alarm_id)
    if not alarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found"
        )
    
    # Get history
    history = await AlarmService.get_alarm_history(
        alarm_id=alarm_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit
    )
    
    # Format response
    response = []
    for record in history:
        item = AlarmHistoryResponse.from_orm(record)
        item.alarm_name = alarm.name
        if hasattr(record, 'device') and record.device:
            item.device_name = record.device.name
        response.append(item)
    
    return response


@router.get(
    "/devices/{device_id}/alarm-history",
    response_model=List[AlarmHistoryResponse],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Device not found"}
    }
)
async def get_device_alarm_history(
    device_id: UUID,
    session: DatabaseSession,
    api_key: CurrentApiKey,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    sensor_type: Optional[str] = Query(None),
    limit: int = Query(100, le=1000)
):
    """Get all alarm history for a device."""
    # Verify device exists
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Build query
    query = select(AlarmHistory).where(AlarmHistory.device_id == device_id)
    
    if sensor_type:
        query = query.where(AlarmHistory.sensor_type == sensor_type)
    if start_time:
        query = query.where(AlarmHistory.triggered_at >= start_time)
    if end_time:
        query = query.where(AlarmHistory.triggered_at <= end_time)
    
    query = query.order_by(AlarmHistory.triggered_at.desc()).limit(limit)
    
    result = await session.execute(query)
    history = result.scalars().all()
    
    # Get alarm names
    alarm_ids = list(set(record.alarm_id for record in history))
    if alarm_ids:
        alarms_result = await session.execute(
            select(Alarm).where(Alarm.id.in_(alarm_ids))
        )
        alarms = {alarm.id: alarm.name for alarm in alarms_result.scalars().all()}
    else:
        alarms = {}
    
    # Format response
    response = []
    for record in history:
        item = AlarmHistoryResponse.from_orm(record)
        item.alarm_name = alarms.get(record.alarm_id)
        item.device_name = device.name
        response.append(item)
    
    return response


@router.post(
    "/alarms/test/{alarm_id}",
    response_model=Dict[str, Any],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Alarm not found"}
    }
)
async def test_alarm(
    alarm_id: UUID,
    session: DatabaseSession,
    api_key: CurrentApiKey,
    test_value: float = Query(..., description="Test sensor value to trigger alarm")
):
    """Test an alarm by simulating a sensor value."""
    from app.services.notification_service import notification_service
    
    # Get alarm with device
    query = select(Alarm).where(Alarm.id == alarm_id).options(selectinload(Alarm.device))
    result = await session.execute(query)
    alarm = result.scalar_one_or_none()
    
    if not alarm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found"
        )
    
    # Get sensor info
    sensor_types = get_sensor_types_for_device(alarm.device.device_type)
    sensor_config = sensor_types.get(alarm.sensor_type, {})
    sensor_name = sensor_config.get('name', alarm.sensor_type)
    unit = sensor_config.get('unit_of_measurement', '')
    
    # Format test value
    formatted_value = f"{test_value} {unit}".strip()
    
    # Create test condition description
    if alarm.condition == "above":
        condition_desc = f"TEST: {sensor_name} {formatted_value} > {alarm.threshold_max} (above threshold)"
    elif alarm.condition == "below":
        condition_desc = f"TEST: {sensor_name} {formatted_value} < {alarm.threshold_min} (below threshold)"
    elif alarm.condition == "equals":
        condition_desc = f"TEST: {sensor_name} {formatted_value} = {alarm.threshold_min} (equals threshold)"
    else:  # out_of_range
        condition_desc = f"TEST: {sensor_name} {formatted_value} outside range [{alarm.threshold_min}, {alarm.threshold_max}]"
    
    # Send test notifications
    sensor_data = {
        'sensor_type': alarm.sensor_type,
        'sensor_name': sensor_name,
        'value': test_value,
        'formatted_value': formatted_value,
        'unit': unit
    }
    
    notification_results = await notification_service.send_alarm_notification(
        alarm=alarm,
        device=alarm.device,
        sensor_data=sensor_data,
        condition_description=condition_desc
    )
    
    return {
        "alarm": {
            "id": str(alarm.id),
            "name": alarm.name
        },
        "test_condition": condition_desc,
        "notification_results": notification_results
    }