"""FastAPI dependencies for dependency injection."""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.auth_service import ApiKeyService
from app.models.database import ApiKey


async def get_api_key(
    x_api_key: Annotated[Optional[str], Header()] = None,
    session: AsyncSession = Depends(get_db)
) -> ApiKey:
    """
    Validate API key from request header.
    
    Expects the API key in the X-API-Key header.
    Also accepts the master API key if configured.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Check if it's the master key
    from app.config import settings
    if settings.MASTER_API_KEY and x_api_key == settings.MASTER_API_KEY:
        # Create a virtual ApiKey object for the master key
        from app.models.database import ApiKey
        import uuid
        master_key = ApiKey()
        master_key.id = uuid.UUID('00000000-0000-0000-0000-000000000000')
        master_key.key = x_api_key
        master_key.name = "Master API Key"
        master_key.is_active = True
        master_key.permissions = {"admin": True}
        return master_key
    
    # Otherwise validate as regular API key
    api_key = await ApiKeyService.validate_api_key(session, x_api_key)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return api_key


# Type alias for dependency injection
CurrentApiKey = Annotated[ApiKey, Depends(get_api_key)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


def get_device_manager(request: Request):
    """Get device manager from app state."""
    return request.app.state.device_manager