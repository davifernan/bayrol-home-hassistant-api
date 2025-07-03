"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import asyncio

from app.config import settings
from app.api.router import api_router
from app.database import init_db

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Import here to avoid circular imports
    from app.core.device_manager import DeviceManager
    from app.services.redis_service import redis_service
    
    # Create device manager instance
    app.state.device_manager = DeviceManager()
    
    # Startup
    logger.info("Starting up Bayrol Pool API...")
    
    # Initialize database
    await init_db()
    
    # Initialize Redis
    await redis_service.connect()
    
    # Load existing devices from database
    await app.state.device_manager.load_devices_from_db()
    
    # Start background tasks
    from app.utils.background_tasks import process_alarm_history_task
    app.state.background_tasks = [
        asyncio.create_task(process_alarm_history_task())
    ]
    
    yield
    
    # Shutdown
    logger.info("Shutting down Bayrol Pool API...")
    
    # Cancel background tasks
    for task in app.state.background_tasks:
        task.cancel()
    
    await app.state.device_manager.shutdown()
    await redis_service.disconnect()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Bayrol Pool API",
        "version": "0.1.0",
        "docs": f"{settings.API_V1_STR}/docs"
    }