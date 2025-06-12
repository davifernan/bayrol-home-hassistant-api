[![Static Badge](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=white)](https://github.com/hacs/integration) 
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/0xQuantumHome/bayrol-home-hassistant?style=for-the-badge) 
![GitHub Release Date](https://img.shields.io/github/release-date/0xQuantumHome/bayrol-home-hassistant?style=for-the-badge&label=Latest%20Release) [![GitHub Release](https://img.shields.io/github/v/release/0xQuantumHome/bayrol-home-hassistant?style=for-the-badge)](https://github.com/greghesp/ha-bambulab/releases)


# Bayrol Pool Access Integration for Home Assistant

This custom integration allows you to monitor your Bayrol Pool Access device in Home Assistant. It uses a direct MQTT connection to the Bayrol Cloud.

## Features

- Monitors 30 pool water quality metrics (including pH, Redox, Salt levels, etc.)
- Real-time updates via MQTT connection

## Tested Devices

- Bayrol Automatic Salt 5 (AS5)
- Bayrol Automatic Cl-pH
- Pool Manager 5 Chlorine

## Installation

### HACS (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed
2. Search for "Bayrol" and install the integration
3. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/bayrol_cloud` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings -> Devices & Services
2. Click "Add Integration" and search for "Bayrol"
3. Enter your Bayrol App Link Code (found in the Bayrol Pool Access Web App)

## Support

If you encounter any issues or have questions, please open an issue on GitHub.
