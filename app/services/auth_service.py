"""Authentication service for Bayrol API integration."""

import json
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.database import ApiKey

_LOGGER = logging.getLogger(__name__)


class BayrolAuthService:
    """Service for authenticating with Bayrol API and getting device credentials."""
    
    @staticmethod
    async def get_device_credentials(app_link_code: str) -> Dict[str, Any]:
        """
        Get device credentials from Bayrol API using app link code.
        
        Args:
            app_link_code: 8-character code from Bayrol app
            
        Returns:
            Dict containing accessToken and deviceSerial
            
        Raises:
            ValueError: If the API returns invalid data
            aiohttp.ClientError: If the API request fails
        """
        if len(app_link_code) != 8:
            raise ValueError("App link code must be exactly 8 characters")
        
        url = f"{settings.BAYROL_API_URL}?code={app_link_code}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    # Get response text regardless of status code (like original HA code)
                    data = await response.text()
                    
                    # Parse JSON response
                    try:
                        data_json = json.loads(data)
                    except json.JSONDecodeError as e:
                        _LOGGER.error(f"Failed to parse Bayrol API response (HTTP {response.status}): {data}")
                        if response.status == 401:
                            raise ValueError("Invalid or expired app link code")
                        else:
                            raise ValueError("Invalid response from Bayrol API")
                    
                    # Check for error in response even if HTTP status is not error
                    if response.status != 200:
                        _LOGGER.error(f"Bayrol API returned HTTP {response.status}: {data_json}")
                        if response.status == 401:
                            raise ValueError("Invalid or expired app link code")
                        else:
                            raise ValueError(f"Bayrol API error: HTTP {response.status}")
                    
                    # Extract required fields
                    access_token = data_json.get("accessToken")
                    device_serial = data_json.get("deviceSerial")
                    
                    if not access_token or not device_serial:
                        _LOGGER.error(f"Missing required fields in API response: {data_json}")
                        # Check if response contains error message
                        if "error" in data_json:
                            raise ValueError(f"Bayrol API error: {data_json['error']}")
                        else:
                            raise ValueError("Invalid app link code - no device credentials returned")
                    
                    _LOGGER.info(f"Successfully retrieved credentials for device {device_serial}")
                    
                    return {
                        "access_token": access_token,
                        "device_serial": device_serial,
                        "raw_response": data_json  # Include full response for debugging
                    }
                    
            except aiohttp.ClientError as e:
                _LOGGER.error(f"Failed to connect to Bayrol API: {e}")
                raise ValueError(f"Network error connecting to Bayrol API: {str(e)}")
            except ValueError:
                # Re-raise ValueError as is
                raise
            except Exception as e:
                _LOGGER.error(f"Unexpected error getting device credentials: {e}")
                raise ValueError(f"Unexpected error: {str(e)}")


class ApiKeyService:
    """Service for managing API keys."""
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure API key."""
        return secrets.token_urlsafe(settings.API_KEY_LENGTH)
    
    @staticmethod
    async def create_api_key(
        session: AsyncSession,
        name: str,
        description: Optional[str] = None,
        permissions: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None
    ) -> ApiKey:
        """Create a new API key."""
        api_key = ApiKey(
            key=ApiKeyService.generate_api_key(),
            name=name,
            description=description,
            permissions=permissions or {},
            expires_at=expires_at
        )
        
        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)
        
        _LOGGER.info(f"Created API key '{name}' with ID {api_key.id}")
        
        return api_key
    
    @staticmethod
    async def validate_api_key(session: AsyncSession, key: str) -> Optional[ApiKey]:
        """
        Validate an API key and return the key object if valid.
        
        Also updates the last_used timestamp.
        """
        result = await session.execute(
            select(ApiKey).where(
                ApiKey.key == key,
                ApiKey.is_active == True
            )
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            return None
        
        # Check expiration
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            _LOGGER.warning(f"API key {api_key.id} has expired")
            return None
        
        # Update last used
        api_key.last_used = datetime.utcnow()
        await session.commit()
        
        return api_key
    
    @staticmethod
    async def revoke_api_key(session: AsyncSession, key_id: str) -> bool:
        """Revoke an API key."""
        result = await session.execute(
            select(ApiKey).where(ApiKey.id == key_id)
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            return False
        
        api_key.is_active = False
        await session.commit()
        
        _LOGGER.info(f"Revoked API key {api_key.id}")
        
        return True