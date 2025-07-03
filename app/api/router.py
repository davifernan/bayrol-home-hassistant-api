"""Main API router."""

from fastapi import APIRouter

from app.api.v1 import auth, devices, sensors, websocket, alarms

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(sensors.router, prefix="/sensors", tags=["sensors"])
api_router.include_router(alarms.router, tags=["alarms"])
api_router.include_router(websocket.router, tags=["websocket"])