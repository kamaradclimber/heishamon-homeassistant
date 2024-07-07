"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations
import re
import logging
import json
import aiohttp
from typing import Optional

from homeassistant.components import mqtt
from homeassistant.components.mqtt.client import async_publish
from homeassistant.components.update.const import UpdateEntityFeature
from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import build_device_info
from .const import DeviceType
from .definitions import HeishaMonEntityDescription, frozendataclass

_LOGGER = logging.getLogger(__name__)
HEISHAMON_REPOSITORY = "Egyras/HeishaMon"

# async_setup_platform should be defined if one wants to support config via configuration.yaml


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HeishaMon updates from config entry."""
    discovery_prefix = config_entry.data["discovery_prefix"]
    _LOGGER.debug(
        f"Starting bootstrap of updates entities with prefix '{discovery_prefix}'"
    )

    firmware_update = HeishaMonUpdateEntityDescription(
        key="heishamon_firmware",
        name="HeishaMon Firmware update",
        heishamon_topic_id=f"{discovery_prefix}stats",
        device_class=UpdateDeviceClass.FIRMWARE,
        device=DeviceType.HEISHAMON,
    )

    async_add_entities([HeishaMonMQTTUpdate(hass, firmware_update, config_entry)])


@frozendataclass
class HeishaMonUpdateEntityDescription(
    HeishaMonEntityDescription, UpdateEntityDescription
):
    pass


class HeishaMonMQTTUpdate(UpdateEntity):
    """Representation of a HeishaMon update that is updated via MQTT."""

    entity_description: HeishaMonUpdateEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        description: HeishaMonUpdateEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        self.entity_description = description
        self.config_entry_entry_id = config_entry.entry_id
        self.hass = hass
        self.discovery_prefix = config_entry.data["discovery_prefix"]

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"update.{slug}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}-{description.heishamon_topic_id}"
        )

        self.marker3_2_topic = f"{self.discovery_prefix}main/Heat_Power_Production"
        self.marker3_1_and_before_topic = (
            f"{self.discovery_prefix}main/Heat_Energy_Production"
        )
        self.stats_firmware_contain_version: Optional[bool] = None

        self._attr_supported_features = (
            UpdateEntityFeature.RELEASE_NOTES | UpdateEntityFeature.INSTALL
        )
        self._attr_release_url = f"https://github.com/{HEISHAMON_REPOSITORY}/releases"
        self._release_notes = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def message_received(message):
            """Handle new MQTT messages."""

            if (
                self.stats_firmware_contain_version == False
                and message.topic == self.marker3_2_topic
            ):
                self._attr_installed_version = "3.2"
            if (
                self.stats_firmware_contain_version == False
                and message.topic == self.marker3_1_and_before_topic
            ):
                self._attr_installed_version = "<= 3.1"
            if message.topic == self.entity_description.heishamon_topic_id:
                field_value = json.loads(message.payload).get("version", None)
                if field_value:
                    self.stats_firmware_contain_version = True
                    if field_value.startswith("alpha"):
                        # otherwise alpha are always considered late
                        self._attr_installed_version = None
                    else:
                        self._attr_installed_version = field_value
                else:
                    self.stats_firmware_contain_version = False
            # we only write value when we know for sure how to get version
            # this avoids having flickering of value when HA start (if we receive a marker3_2_topic message
            # before we get the stats message)
            if self.stats_firmware_contain_version is not None:
                self.async_write_ha_state()

        await mqtt.async_subscribe(self.hass, self.marker3_2_topic, message_received, 1)
        await mqtt.async_subscribe(
            self.hass, self.marker3_1_and_before_topic, message_received, 1
        )
        await mqtt.async_subscribe(
            self.hass, self.entity_description.heishamon_topic_id, message_received, 1
        )

        # TODO(kamaradclimber): schedule this on a regular basis instead of just at startup
        await self._update_latest_release()

    @property
    def device_info(self):
        return build_device_info(self.entity_description.device, self.discovery_prefix)

    async def _update_latest_release(self):
        async with aiohttp.ClientSession() as session:
            resp = await session.get(
                f"https://api.github.com/repos/{HEISHAMON_REPOSITORY}/releases"
            )

            if resp.status != 200:
                _LOGGER.warn(
                    f"Impossible to get latest release from heishamon repository {HEISHAMON_REPOSITORY}"
                )
                return

            releases = await resp.json()
            if len(releases) == 0:
                _LOGGER.warn(
                    f"Not a single release was found for heishamon repository {HEISHAMON_REPOSITORY}"
                )

            last_release = releases[0]
            self._attr_latest_version = re.sub(r"^v", "", last_release["tag_name"])
            self._attr_release_url = last_release["html_url"]
            self._release_notes = last_release["body"]
            self.async_write_ha_state()

    def release_notes(self) -> str | None:
        header = f"⚠ Update is not supported via HA. Update is done via heishamon webui\n\n\n"
        return header + str(self._release_notes)
