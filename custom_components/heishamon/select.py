"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations
import logging

from homeassistant.components import mqtt
from homeassistant.components.mqtt.client import async_publish
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .definitions import build_selects, HeishaMonSelectEntityDescription
from . import build_device_info

_LOGGER = logging.getLogger(__name__)

# async_setup_platform should be defined if one wants to support config via configuration.yaml


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HeishaMon sensors from config entry."""
    discovery_prefix = config_entry.data[
        "discovery_prefix"
    ]  # TODO: handle migration of entities
    _LOGGER.debug(f"Starting bootstrap of select with prefix '{discovery_prefix}'")
    async_add_entities(
        HeishaMonMQTTSelect(hass, description, config_entry)
        for description in build_selects(discovery_prefix)
    )


class HeishaMonMQTTSelect(SelectEntity):
    """Representation of a HeishaMon sensor that is updated via MQTT."""

    entity_description: HeishaMonSelectEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        description: HeishaMonSelectEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self.config_entry_entry_id = config_entry.entry_id
        self.hass = hass
        self.discovery_prefix = config_entry.data[
            "discovery_prefix"
        ]  # TODO: handle migration of entities

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"select.{slug}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}-{description.heishamon_topic_id}"
        )
        self._attr_current_option = None

    async def async_select_option(self, option: str) -> None:
        _LOGGER.debug(
            f"Changing {self.entity_description.name} to {option} (sent to {self.entity_description.command_topic})"
        )
        if self.entity_description.state_to_mqtt is not None:
            payload = self.entity_description.state_to_mqtt(option)
        else:
            payload = option
        await async_publish(
            self.hass,
            self.entity_description.command_topic,
            payload,
            self.entity_description.qos,
            self.entity_description.retain,
            self.entity_description.encoding,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def message_received(message):
            """Handle new MQTT messages."""
            if self.entity_description.state is not None:
                self._attr_current_option = self.entity_description.state(
                    message.payload
                )
            else:
                self._attr_current_option = message.payload

            self.async_write_ha_state()
            if self.entity_description.on_receive is not None:
                self.entity_description.on_receive(
                    self.hass,
                    self,
                    self.config_entry_entry_id,
                    self._attr_current_option,
                )

        await mqtt.async_subscribe(
            self.hass, self.entity_description.key, message_received, 1
        )

    @property
    def device_info(self):
        return build_device_info(self.entity_description.device, self.discovery_prefix)
