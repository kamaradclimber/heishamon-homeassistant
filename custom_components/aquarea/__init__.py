"""The HeishaMon component."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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
    Platform.BUTTON,
]
_LOGGER = logging.getLogger(__name__)

DEFAULT_MQTT_TOPIC = "panasonic_heat_pump/"


def _compute_identifiers(mqtt_topic: str) -> dict[DeviceType, tuple[str, str]]:
    if mqtt_topic == DEFAULT_MQTT_TOPIC:  # backward compatibility
        return {
            DeviceType.HEATPUMP: (DOMAIN, "panasonic_heat_pump"),
            DeviceType.HEISHAMON: (DOMAIN, "heishamon"),
        }
    return {
        DeviceType.HEATPUMP: (DOMAIN, mqtt_topic),
        DeviceType.HEISHAMON: (DOMAIN, f"heishamon-{mqtt_topic}"),
    }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the HeishaMon integration."""
    mqtt_topic = entry.data["discovery_prefix"]
    identifiers = _compute_identifiers(mqtt_topic)

    device_registry = dr.async_get(hass)

    heishamon_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={identifiers[DeviceType.HEISHAMON]},
        name="HeishaMon",
    )
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={identifiers[DeviceType.HEATPUMP]},
        name="Aquarea HeatPump",
        manufacturer="Aquarea",
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"heishamon_device_id": heishamon_device.id}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the HeishaMon integration."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def build_device_info(hass: HomeAssistant, device_type: DeviceType, mqtt_topic: str, config_entry_id: str) -> dict:
    """Return device info dict for the given device type."""
    identifiers = _compute_identifiers(mqtt_topic)
    if device_type == DeviceType.HEATPUMP:
        via_device_id = hass.data.get(DOMAIN, {}).get(config_entry_id, {}).get("heishamon_device_id")
        return {
            "identifiers": {identifiers[DeviceType.HEATPUMP]},
            "name": "Aquarea HeatPump",
            "manufacturer": "Aquarea",
            "via_device_id": via_device_id,
        }
    elif device_type == DeviceType.HEISHAMON:
        return {
            "identifiers": {identifiers[DeviceType.HEISHAMON]},
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
        hass.config_entries.async_update_entry(config_entry, data=new, version=2)
        _LOGGER.info(f"Migration to version {config_entry.version} successful")
    return True
