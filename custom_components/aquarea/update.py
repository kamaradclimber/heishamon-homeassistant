"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations
import re
import logging
import json
import aiohttp
import asyncio
from typing import Optional, Any
from io import BufferedReader, BytesIO

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
from .definitions import HeishaMonEntityDescription, frozendataclass, read_board_type

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
            UpdateEntityFeature.RELEASE_NOTES | UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS | UpdateEntityFeature.SPECIFIC_VERSION
        )
        self._attr_release_url = f"https://github.com/{HEISHAMON_REPOSITORY}/releases"
        self._model_type = None
        self._release_notes = None
        self._attr_progress = False

        self._ip_topic = f"{self.discovery_prefix}ip"
        self._heishamon_ip = None

        self._stats_topic = f"{self.discovery_prefix}stats"

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def ip_received(message):
            self._heishamon_ip = message.payload
        await mqtt.async_subscribe(self.hass, self._ip_topic, ip_received, 1)

        @callback
        def read_model(message):
            self._model_type = read_board_type(message.payload)
        await mqtt.async_subscribe(self.hass, self._stats_topic, read_model, 1)


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

    @property
    def model_to_file(self) -> str | None:
        return {
            "ESP32": "model-type-large",
            "ESP8266": "model-type-small",
            None: "UNKNOWN",
        }.get(self._model_type, None)
        

    def release_notes(self) -> str | None:
        return f"⚠️ Automated upgrades will fetch `{self.model_to_file}` binaries.\n\nBeware!\n\n" + str(self._release_notes)

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        if self._model_type is None:
            raise Exception("Impossible to update automatically because we don't know the board version")
        if version is None:
            version = self._attr_latest_version
            _LOGGER.info(f"Will install latest version ({version}) of the firmware")
        else:
            _LOGGER.info(f"Will install version {version} of the firmware")
        self._attr_progress = 0
        async with aiohttp.ClientSession() as session:
            resp = await session.get(
                f"https://github.com/{HEISHAMON_REPOSITORY}/raw/master/binaries/{self.model_to_file}/HeishaMon.ino.d1-v{version}.bin"
            )

            if resp.status != 200:
                _LOGGER.warn(
                    f"Impossible to download version {version} from heishamon repository {HEISHAMON_REPOSITORY}"
                )
                return

            firmware_binary = await resp.read()
            _LOGGER.info(f"Firmware is {len(firmware_binary)} bytes long")
            self._attr_progress = 10
            resp = await session.get(
                f"https://github.com/{HEISHAMON_REPOSITORY}/raw/master/binaries/{self.model_to_file}/HeishaMon.ino.d1-v{version}.md5"
            )

            if resp.status != 200:
                _LOGGER.warn(
                    f"Impossible to fetch checksum of version #{version} from heishamon repository {HEISHAMON_REPOSITORY}"
                )
                return
            checksum = await resp.text()
            self._attr_progress = 20
            _LOGGER.info(f"Downloaded binary and checksum {checksum} of version {version}")

            while self._heishamon_ip is None:
                _LOGGER.warn("Waiting for an mqtt message to get the ip address of heishamon")
                await asyncio.sleep(1)

        def track_progress(current, total):
            self._attr_progress = int(current / total * 100)
            _LOGGER.info(f"Currently read {current} out of {total}: {self._attr_progress}%")


        async with aiohttp.ClientSession() as session:
            _LOGGER.info(f"Starting upgrade of firmware to version {version} on {self._heishamon_ip}")
            to = aiohttp.ClientTimeout(total=300, connect=10)
            try:
                with ProgressReader(firmware_binary, track_progress) as reader:
                    resp = await session.post(
                        f"http://{self._heishamon_ip}/firmware",
                        data={
                            'md5': checksum,
                            # 'firmware': ('firmware.bin', firmware_binary, 'application/octet-stream')
                            'firmware': reader

                        },
                        timeout=to
                    )
            except TimeoutError as e:
                _LOGGER.error(f"Timeout while uploading new firmware")
                raise e
            if resp.status != 200:
                _LOGGER.warn(f"Impossible to perform firmware update to version {version}")
                return
            _LOGGER.info(f"Finished uploading firmware. Heishamon should now be rebooting")

class ProgressReader(BufferedReader):
    def __init__(self, binary_data, read_callback=None):
        self._read_callback = read_callback
        super().__init__(raw=BytesIO(binary_data))
        self.length = len(binary_data)

    def read(self, size=None):
        computed_size = size
        if not computed_size:
            computed_size = self.length - self.tell()
        if self._read_callback:
            self._read_callback(self.tell(), self.length)
        return super(ProgressReader, self).read(size)
