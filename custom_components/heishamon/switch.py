"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations
import logging

from homeassistant.components import mqtt
from homeassistant.components.mqtt.client import async_publish
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from .const import DOMAIN
from .definitions import MQTT_SWITCHES, HeishaMonSwitchEntityDescription
from . import build_device_info

_LOGGER = logging.getLogger(__name__)

# async_setup_platform should be defined if one wants to support config via configuration.yaml


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HeishaMon sensors from config entry."""
    async_add_entities(
        HeishaMonMQTTSwitch(hass, description, config_entry)
        for description in MQTT_SWITCHES
    )


class HeishaMonMQTTSwitch(SwitchEntity):
    """Representation of a HeishaMon sensor that is updated via MQTT."""

    entity_description: HeishaMonSwitchEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        description: HeishaMonSwitchEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self.hass = hass

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"sensor.{slug}"
        self._attr_unique_id = f"{config_entry.entry_id}-{slug}"
        self._optimistic = True  # for now we hardcode this

    async def async_turn_on(self) -> None:
        _LOGGER.info(f"Turning on heatpump {self.entity_description.name}")
        await async_publish(
            self.hass,
            self.entity_description.command_topic,
            self.entity_description.payload_on,
            self.entity_description.qos,
            self.entity_description.retain,
            self.entity_description.encoding,
        )
        if self._optimistic:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        _LOGGER.info(f"Turning off heatpump {self.entity_description.name}")
        await async_publish(
            self.hass,
            self.entity_description.command_topic,
            self.entity_description.payload_off,
            self.entity_description.qos,
            self.entity_description.retain,
            self.entity_description.encoding,
        )
        if self._optimistic:
            self._state = False
            self.async_write_ha_state()

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
        return build_device_info()
