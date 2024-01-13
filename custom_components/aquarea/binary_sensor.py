"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations
import logging

from homeassistant.components import mqtt
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .definitions import build_switches, build_binary_sensors, HeishaMonBinarySensorEntityDescription
from . import build_device_info

_LOGGER = logging.getLogger(__name__)

# async_setup_platform should be defined if one wants to support config via configuration.yaml


async def async_setup_entry(
    _: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HeishaMon binary sensors from config entry."""
    discovery_prefix = config_entry.data[
        "discovery_prefix"
    ]  # TODO: handle migration of entities
    _LOGGER.debug(
        f"Starting bootstrap of binary sensors with prefix '{discovery_prefix}'"
    )
    async_add_entities(
        HeishaMonBinarySensor(description, config_entry)
        for description in build_binary_sensors(discovery_prefix)
    )
    # those entities are added for people who want to have "safe" entities visible in their dashboard
    # instead of exposing entities whose state can be modified by mistake. See #151
    readonly_switches = []
    for switch_description in build_switches(discovery_prefix):
        category = switch_description.entity_category
        if category == EntityCategory.CONFIG:
            category = EntityCategory.DIAGNOSTIC
        readonly_switches.append(HeishaMonBinarySensor(
            HeishaMonBinarySensorEntityDescription(
                heishamon_topic_id=switch_description.heishamon_topic_id,
                key=switch_description.key,
                name=f"{switch_description.name} (readonly)",
                entity_category=category,
                device=switch_description.device,
                state=switch_description.state,
                device_class=switch_description.device_class,
                entity_registry_enabled_default=False,
            ), config_entry)
        )
    async_add_entities(readonly_switches)


class HeishaMonBinarySensor(BinarySensorEntity):
    """Representation of a HeishaMon binary sensor that is updated via MQTT."""

    entity_description: HeishaMonBinarySensorEntityDescription

    def __init__(
        self,
        description: HeishaMonBinarySensorEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        self.config_entry_entry_id = config_entry.entry_id
        self.discovery_prefix = config_entry.data[
            "discovery_prefix"
        ]  # TODO: handle migration of entities

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"sensor.{slug}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}-{description.heishamon_topic_id}"
        )

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
