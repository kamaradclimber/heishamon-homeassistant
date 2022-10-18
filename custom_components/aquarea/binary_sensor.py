"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations

from homeassistant.components import mqtt
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from .const import DOMAIN
from .definitions import BINARY_SENSORS, HeishaMonBinarySensorEntityDescription
from . import build_device_info


# async_setup_platform should be defined if one wants to support config via configuration.yaml


async def async_setup_entry(
    _: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HeishaMon sensors from config entry."""
    async_add_entities(
        HeishaMonBinarySensor(description, config_entry)
        for description in BINARY_SENSORS
    )


class HeishaMonBinarySensor(BinarySensorEntity):
    """Representation of a HeishaMon sensor that is updated via MQTT."""

    entity_description: HeishaMonBinarySensorEntityDescription

    def __init__(
        self,
        description: HeishaMonBinarySensorEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"sensor.{slug}"
        self._attr_unique_id = f"{config_entry.entry_id}-{slug}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def message_received(message):
            """Handle new MQTT messages."""
            if self.entity_description.state is not None:
                self._attr_is_on = self.entity_description.state(message.payload)
            else:
                self._attr_is_on = message.payload

            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass, self.entity_description.key, message_received, 1
        )

    @property
    def device_info(self):
        return build_device_info(self.entity_description.device)
