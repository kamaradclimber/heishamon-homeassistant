"""The HeishaMon component."""

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
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the HeishaMon integration."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the HeishaMon integration."""
    # no data stored in hass.data for now
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def build_device_info(device_type: DeviceType) -> dict:
    """
    This method returns the correct device based
    """
    if device_type == DeviceType.HEATPUMP:
        return {
            "identifiers": {
                (
                    DOMAIN,
                    "panasonic_heat_pump",
                )
            },
            "name": "Aquarea HeatPump Indoor Unit",
            "manufacturer": "Aquarea",
            "via_device": ("aquarea", "heishamon"),
        }
    elif device_type == DeviceType.HEISHAMON:
        return {
            "identifiers": {(DOMAIN, "heishamon")},
            "name": "HeishaMon",
        }
    assert False, f"{device_type} management has not been implemented"
