"""Device management endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy import select

from app.dependencies import CurrentApiKey, DatabaseSession, get_device_manager
from app.models.database import Device
from app.models.schemas import (
    DeviceCreate, DeviceUpdate, DeviceResponse, 
    DeviceDetailResponse, ErrorResponse
)
from app.services.auth_service import BayrolAuthService

router = APIRouter()


@router.post(
    "/",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def create_device(
    device_data: DeviceCreate,
    session: DatabaseSession,
    api_key: CurrentApiKey,
    device_manager = Depends(get_device_manager)
):
    """
    Add a new Bayrol device using the app link code.
    
    The app link code is used to fetch the device credentials from Bayrol API.
    """
    try:
        # Get device credentials from Bayrol API
        credentials = await BayrolAuthService.get_device_credentials(device_data.app_link_code)
        
        # Check if device already exists
        result = await session.execute(
            select(Device).where(Device.device_id == credentials["device_serial"])
        )
        existing_device = result.scalar_one_or_none()
        
        if existing_device:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Device {credentials['device_serial']} already exists"
            )
        
        # Create device in database
        device = Device(
            device_id=credentials["device_serial"],
            device_type=device_data.device_type,
            name=device_data.name or f"{device_data.device_type} - {credentials['device_serial'][-4:]}",
            access_token=credentials["access_token"],
            app_link_code=device_data.app_link_code,
            client_id=device_data.client_id,
            device_metadata=credentials.get("raw_response", {})
        )
        
        session.add(device)
        await session.commit()
        await session.refresh(device)
        
        # Add device to device manager
        success = await device_manager.add_device(
            device_id=device.id,
            device_serial=device.device_id,
            access_token=device.access_token,
            device_type=device.device_type,
            device_name=device.name
        )
        
        if not success:
            # Rollback database changes if device manager fails
            await session.delete(device)
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize device connection"
            )
        
        return DeviceResponse.from_orm(device)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create device: {str(e)}"
        )


@router.get(
    "/",
    response_model=List[DeviceDetailResponse],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"}
    }
)
async def list_devices(
    session: DatabaseSession,
    api_key: CurrentApiKey,
    device_manager = Depends(get_device_manager),
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[str] = None
):
    """List all devices, optionally filtered by client_id."""
    query = select(Device)
    
    # Filter by client_id if provided
    if client_id:
        query = query.where(Device.client_id == client_id)
    
    result = await session.execute(
        query
        .offset(skip)
        .limit(limit)
        .order_by(Device.created_at.desc())
    )
    devices = result.scalars().all()
    
    # Enhance with connection status from device manager
    response = []
    for device in devices:
        device_info = device_manager.get_device(device.id)
        
        detail = DeviceDetailResponse(
            id=device.id,
            device_id=device.device_id,
            device_type=device.device_type,
            name=device.name,
            is_active=device.is_active,
            created_at=device.created_at,
            updated_at=device.updated_at,
            is_connected=device_info['is_connected'] if device_info else False,
            last_seen=device_info['last_seen'] if device_info else None
        )
        
        # Count active alarms
        detail.active_alarms = len([a for a in device.alarms if a.enabled])
        
        response.append(detail)
    
    return response


@router.get(
    "/{device_id}",
    response_model=DeviceDetailResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Device not found"}
    }
)
async def get_device(
    device_id: UUID,
    session: DatabaseSession,
    api_key: CurrentApiKey,
    device_manager = Depends(get_device_manager)
):
    """Get device details."""
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Get connection status from device manager
    device_info = device_manager.get_device(device.id)
    
    detail = DeviceDetailResponse(
        id=device.id,
        device_id=device.device_id,
        device_type=device.device_type,
        name=device.name,
        is_active=device.is_active,
        created_at=device.created_at,
        updated_at=device.updated_at,
        is_connected=device_info['is_connected'] if device_info else False,
        last_seen=device_info['last_seen'] if device_info else None,
        active_alarms=len([a for a in device.alarms if a.enabled])
    )
    
    return detail


@router.patch(
    "/{device_id}",
    response_model=DeviceResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Device not found"}
    }
)
async def update_device(
    device_id: UUID,
    device_update: DeviceUpdate,
    session: DatabaseSession,
    api_key: CurrentApiKey,
    device_manager = Depends(get_device_manager)
):
    """Update device information."""
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Update fields
    update_data = device_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(device, field, value)
    
    # Handle activation/deactivation
    if "is_active" in update_data:
        if update_data["is_active"] and device.id not in device_manager.devices:
            # Reactivate device
            await device_manager.add_device(
                device_id=device.id,
                device_serial=device.device_id,
                access_token=device.access_token,
                device_type=device.device_type,
                device_name=device.name
            )
        elif not update_data["is_active"] and device.id in device_manager.devices:
            # Deactivate device
            await device_manager.remove_device(device.id)
    
    await session.commit()
    await session.refresh(device)
    
    return DeviceResponse.from_orm(device)


@router.delete(
    "/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Device not found"}
    }
)
async def delete_device(
    device_id: UUID,
    session: DatabaseSession,
    api_key: CurrentApiKey,
    device_manager = Depends(get_device_manager)
):
    """Delete a device."""
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Remove from device manager
    if device.id in device_manager.devices:
        await device_manager.remove_device(device.id)
    
    # Delete from database (cascade will handle related records)
    await session.delete(device)
    await session.commit()