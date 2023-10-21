"""The HeishaMon component."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, DeviceType

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.CLIMATE,
    Platform.WATER_HEATER,
    Platform.UPDATE,
]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the HeishaMon integration."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the HeishaMon integration."""
    # no data stored in hass.data for now
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


DEFAULT_MQTT_TOPIC = "panasonic_heat_pump/"


def build_device_info(device_type: DeviceType, mqtt_topic: str) -> dict:
    """
    This method returns the correct device based
    """
    if mqtt_topic == DEFAULT_MQTT_TOPIC:  # backward compatibility
        heatpump_id = (DOMAIN, "panasonic_heat_pump")
        heishamon_id = (DOMAIN, "heishamon")
    else:
        heatpump_id = (DOMAIN, mqtt_topic)
        heishamon_id = (DOMAIN, f"heishamon-{mqtt_topic}")
    if device_type == DeviceType.HEATPUMP:
        return {
            "identifiers": {heatpump_id},
            "name": "Aquarea HeatPump Indoor Unit",
            "manufacturer": "Aquarea",
            "via_device": heishamon_id,
        }
    elif device_type == DeviceType.HEISHAMON:
        return {
            "identifiers": {heishamon_id},
            "name": "HeishaMon",
        }
    assert False, f"{device_type} management has not been implemented"


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    if config_entry.version == 1:
        _LOGGER.warn(
            f"config_entry version is {config_entry.version}, migrating to version 2"
        )
        # we need to add the discovery prefix
        new = {**config_entry.data}
        new[
            "discovery_prefix"
        ] = DEFAULT_MQTT_TOPIC  # it was hardcoded in version 1 of the config_entry schema
        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=new)
        _LOGGER.info(f"Migration to version {config_entry.version} successful")
    return True
