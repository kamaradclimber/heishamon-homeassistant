"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations
import logging
import aiohttp
import asyncio

from homeassistant.components import mqtt
from homeassistant.components.mqtt.client import async_publish
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .definitions.buttons import build_buttons
from .definitions.descriptions import HeishaMonButtonEntityDescription
from .const import DOMAIN, DeviceType
from .model_catalog import ModelCatalog, ModelRefreshError
from . import build_device_info

_LOGGER = logging.getLogger(__name__)

# async_setup_platform should be defined if one wants to support config via configuration.yaml


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HeishaMon button from config entry."""
    discovery_prefix = config_entry.data[
        "discovery_prefix"
    ]  # TODO: handle migration of entities
    _LOGGER.debug(f"Starting bootstrap of button with prefix '{discovery_prefix}'")
    async_add_entities(
        [
            *(
                HeishaMonMQTTButton(hass, description, config_entry)
                for description in build_buttons(discovery_prefix)
            ),
            RefreshHeatpumpModelsButton(hass, config_entry),
        ]
    )


class RefreshHeatpumpModelsButton(ButtonEntity):
    """Button to manually refresh model definitions from HeishaMon upstream."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:database-refresh"
    _attr_name = "Refresh heat pump models"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.hass = hass
        self.config_entry_entry_id = config_entry.entry_id
        self.discovery_prefix = config_entry.data["discovery_prefix"]
        self._attr_unique_id = f"{config_entry.entry_id}-refresh-heatpump-models"
        self.entity_id = f"button.{slugify(self._attr_unique_id)}"

    async def async_press(self) -> None:
        """Fetch the latest upstream list after explicit user action."""
        catalog: ModelCatalog = self.hass.data[DOMAIN]["model_catalog"]
        try:
            count = await catalog.async_refresh()
        except ModelRefreshError as err:
            _LOGGER.error("Could not refresh heat pump models: %s", err)
            raise HomeAssistantError(str(err)) from err
        _LOGGER.info("Refreshed %d heat pump model signatures", count)

    @property
    def device_info(self):
        return build_device_info(
            self.hass,
            DeviceType.HEISHAMON,
            self.discovery_prefix,
            self.config_entry_entry_id,
        )


class HeishaMonMQTTButton(ButtonEntity):
    """Representation of a HeishaMon switch that is updated via MQTT."""

    entity_description: HeishaMonButtonEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        description: HeishaMonButtonEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the button."""
        self.entity_description = description
        self.config_entry_entry_id = config_entry.entry_id
        self.hass = hass
        self.discovery_prefix = config_entry.data[
            "discovery_prefix"
        ]  # TODO: handle migration of entities

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"button.{slug}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}-{description.heishamon_topic_id}"
        )
        self._inner_state = None

    async def async_press(self) -> None:
        if self.entity_description.command_topic != "void/topic":
            # regular code path
            _LOGGER.info(f"Triggering on heatpump {self.entity_description.name}")
            await async_publish(
                self.hass,
                self.entity_description.command_topic,
                self.entity_description.payload,
                self.entity_description.qos,
                self.entity_description.retain,
                self.entity_description.encoding,
            )
            return

        # alternative code path for reboot management (which does not use mqtt message)
        while self._inner_state is None:
                _LOGGER.warn("Waiting for an mqtt message to get the ip address of heishamon")
                await asyncio.sleep(1)
        _LOGGER.info(f"Pressing on heatpump {self.entity_description.name}")
        async with aiohttp.ClientSession() as session:
            url = f"http://{self._inner_state}/reboot"
            _LOGGER.info(f"GET on {url}")
            resp = await session.get(url)

            if resp.status != 200:
                raise Exception("Impossible to reboot heishamon")
            # we apparently need to read the output to let heishamon reboot
            await resp.text()
            _LOGGER.info("Successfully triggered heishamon reboot")
            return None


    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def message_received(message):
            """Handle new MQTT messages."""
            if self.entity_description.state is not None:
                self._inner_state = self.entity_description.state(message.payload)
            else:
                self._inner_state = message.payload

            self.async_write_ha_state()
            if self.entity_description.on_receive is not None:
                self.entity_description.on_receive(
                    self.hass, self, self.config_entry_entry_id, self._inner_state
                )

        await mqtt.async_subscribe(
            self.hass, self.entity_description.key, message_received, 1
        )

    @property
    def device_info(self):
        return build_device_info(self.hass, self.entity_description.device, self.discovery_prefix, self.config_entry_entry_id)
