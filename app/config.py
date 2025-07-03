"""Application configuration."""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, RedisDsn


class Settings(BaseSettings):
    """Application settings."""
    
    # API Configuration
    PROJECT_NAME: str = "Bayrol Pool API"
    API_V1_STR: str = "/api/v1"
    API_KEY_LENGTH: int = 32
    
    # Database
    DATABASE_URL: PostgresDsn
    
    # Redis
    REDIS_URL: RedisDsn
    
    # MQTT Configuration
    BAYROL_MQTT_HOST: str = "www.bayrol-poolaccess.de"
    BAYROL_MQTT_PORT: int = 8083
    
    # Bayrol API
    BAYROL_API_URL: str = "https://www.bayrol-poolaccess.de/api/"
    
    # Security
    SECRET_KEY: str
    MASTER_API_KEY: Optional[str] = None
    
    # Notifications
    ALARM_WEBHOOK_URL: Optional[str] = None
    EMAIL_WEBHOOK_URL: Optional[str] = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()