"""WebSocket endpoints for real-time updates."""

from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select

from app.database import async_session_maker
from app.models.database import Device, ApiKey
from app.dependencies import get_device_manager
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/{device_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    device_id: UUID,
    api_key: str = Query(...)
):
    """
    WebSocket endpoint for real-time sensor updates.
    
    Connect with: ws://localhost:8000/api/v1/ws/{device_id}?api_key=your_key
    """
    # Validate API key
    async with async_session_maker() as session:
        result = await session.execute(
            select(ApiKey).where(
                ApiKey.key == api_key,
                ApiKey.is_active == True
            )
        )
        key = result.scalar_one_or_none()
        
        if not key:
            await websocket.close(code=4001, reason="Invalid API key")
            return
        
        # Verify device exists
        result = await session.execute(
            select(Device).where(Device.id == device_id)
        )
        device = result.scalar_one_or_none()
        
        if not device:
            await websocket.close(code=4004, reason="Device not found")
            return
    
    # Accept connection
    await websocket.accept()
    
    # Register WebSocket with device manager
    device_manager.register_websocket(device_id, websocket)
    
    try:
        # Send initial connection status
        await websocket.send_json({
            "type": "connection_status",
            "device_id": str(device_id),
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "status": "connected",
                "message": "WebSocket connected successfully"
            }
        })
        
        # Send current sensor values
        current_sensors = device_manager.get_device_sensors(device_id)
        if current_sensors:
            await websocket.send_json({
                "type": "sensor_update",
                "device_id": str(device_id),
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "sensors": current_sensors
                }
            })
        
        # Keep connection alive
        while True:
            # Wait for any message from client (ping/pong)
            data = await websocket.receive_text()
            # Could implement commands here in the future
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for device {device_id}")
    except Exception as e:
        logger.error(f"WebSocket error for device {device_id}: {e}")
    finally:
        # Unregister WebSocket
        device_manager.unregister_websocket(device_id, websocket)