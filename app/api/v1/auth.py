"""Authentication endpoints."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Header

from app.dependencies import DatabaseSession
from app.models.schemas import ApiKeyCreate, ApiKeyResponse, ErrorResponse
from app.services.auth_service import ApiKeyService

router = APIRouter()


@router.post(
    "/api-keys",
    response_model=ApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def create_api_key(
    api_key_data: ApiKeyCreate,
    session: DatabaseSession,
    master_key: Optional[str] = Header(None, alias="X-Master-Key")
):
    """
    Create a new API key.
    
    Requires the master API key in X-Master-Key header if MASTER_API_KEY is set in environment.
    """
    # Check if master key protection is enabled
    from app.config import settings
    if settings.MASTER_API_KEY:
        if not master_key or master_key != settings.MASTER_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing master API key"
            )
    try:
        api_key = await ApiKeyService.create_api_key(
            session=session,
            name=api_key_data.name,
            description=api_key_data.description,
            permissions=api_key_data.permissions,
            expires_at=api_key_data.expires_at
        )
        
        return ApiKeyResponse(
            id=api_key.id,
            key=api_key.key,  # Only shown on creation
            name=api_key.name,
            description=api_key.description,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {str(e)}"
        )