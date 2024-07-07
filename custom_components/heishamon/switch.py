"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations
import logging

from homeassistant.components import mqtt
from homeassistant.components.mqtt.client import async_publish
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .definitions import build_switches, HeishaMonSwitchEntityDescription
from . import build_device_info

_LOGGER = logging.getLogger(__name__)

# async_setup_platform should be defined if one wants to support config via configuration.yaml


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HeishaMon switches from config entry."""
    discovery_prefix = config_entry.data[
        "discovery_prefix"
    ]  # TODO: handle migration of entities
    _LOGGER.debug(f"Starting bootstrap of switches with prefix '{discovery_prefix}'")
    async_add_entities(
        HeishaMonMQTTSwitch(hass, description, config_entry)
        for description in build_switches(discovery_prefix)
    )


class HeishaMonMQTTSwitch(SwitchEntity):
    """Representation of a HeishaMon switch that is updated via MQTT."""

    entity_description: HeishaMonSwitchEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        description: HeishaMonSwitchEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        self.entity_description = description
        self.config_entry_entry_id = config_entry.entry_id
        self.hass = hass
        self.discovery_prefix = config_entry.data[
            "discovery_prefix"
        ]  # TODO: handle migration of entities

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"switch.{slug}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}-{description.heishamon_topic_id}"
        )
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
            if self.entity_description.on_receive is not None:
                self.entity_description.on_receive(
                    self.hass, self, self.config_entry_entry_id, self._attr_is_on
                )

        await mqtt.async_subscribe(
            self.hass, self.entity_description.key, message_received, 1
        )

    @property
    def device_info(self):
        return build_device_info(self.entity_description.device, self.discovery_prefix)
