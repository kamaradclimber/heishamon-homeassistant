"""The HeishaMon component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the HeishaMon integration."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the HeishaMon integration."""
    # no data stored in hass.data for now
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def build_device_info() -> dict:
    return {
        "identifiers": {
            (
                DOMAIN,
                "panasonic_heat_pump",
            )  # we use the mqtt topic used. TODO: inject it
        },
        "name": "Aquarea HeatPump",
        "manufacturer": "Aquarea",
        "via_device": ("mqtt", "panasonic_heat_pump"),
    }
