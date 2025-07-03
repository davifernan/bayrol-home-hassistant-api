"""Core functionality module."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.device_manager import DeviceManager

# Global device manager instance
# Will be set during app startup
device_manager: 'DeviceManager' = None


def get_device_manager() -> 'DeviceManager':
    """Get the global device manager instance."""
    if device_manager is None:
        raise RuntimeError("Device manager not initialized")
    return device_manager