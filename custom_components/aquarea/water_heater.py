from __future__ import annotations
import logging

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from homeassistant.components import mqtt
from homeassistant.components.mqtt.client import async_publish

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    STATE_ECO,
    STATE_PERFORMANCE,
)
try:
    from homeassistant.components.water_heater import WaterHeaterEntityDescription
except ImportError:
    # compatibility code for HA < 2025.1
    from homeassistant.components.water_heater import WaterHeaterEntityEntityDescription
    WaterHeaterEntityDescription = WaterHeaterEntityEntityDescription



from .definitions import OperatingMode
from . import build_device_info
from .const import DeviceType

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    discovery_prefix = config_entry.data[
        "discovery_prefix"
    ]  # TODO: handle migration of entities
    _LOGGER.debug(
        f"Starting bootstrap of water heater entities with prefix '{discovery_prefix}'"
    )
    """Set up HeishaMon water heater from config entry."""
    description = WaterHeaterEntityDescription(
        key=f"{discovery_prefix}main/DHW_Target_Temp",
        name="Aquarea Domestic Water Heater",
    )
    async_add_entities([HeishaMonDHW(hass, description, config_entry)])


STATE_SUPERECO = "Super Eco"


class HeishaMonDHW(WaterHeaterEntity):
    """Representation of a HeishaMon sensor that is updated via MQTT."""

    operation_modes_temps = {
        STATE_SUPERECO: [42, range(37, 48)],
        STATE_ECO: [
            49,
            range(48, 55),
        ],  # 49° is the recommended value against legionella
        STATE_PERFORMANCE: [60, range(55, 65)],
    }

    def __init__(
        self,
        hass: HomeAssistant,
        description: WaterHeaterEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the water heater entity."""
        self.config_entry_entry_id = config_entry.entry_id
        self.entity_description = description
        self.hass = hass
        self.discovery_prefix = config_entry.data[
            "discovery_prefix"
        ]  # TODO: handle migration of entities

        slug = slugify(self.entity_description.key.replace("/", "_"))
        self.entity_id = f"climate.{slug}"
        self._attr_unique_id = f"{config_entry.entry_id}.water_heater"

        self._attr_temperature_unit = "°C"
        self._attr_supported_features = (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.ON_OFF
            | WaterHeaterEntityFeature.OPERATION_MODE
        )
        self._attr_current_operation = STATE_ECO
        self._attr_min_temp = 40
        self._attr_max_temp = 65
        self._attr_precision = 1
        self._attr_operation_list = [STATE_SUPERECO, STATE_ECO, STATE_PERFORMANCE]
        self._heat_delta = 0

    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get("temperature")
        _LOGGER.debug(f"Changing {self.name} target temperature to {temperature})")
        payload = str(temperature)
        self.update_temperature_bounds()  # optimistic update
        await async_publish(
            self.hass,
            f"{self.discovery_prefix}commands/SetDHWTemp",
            payload,
            0,
            False,
            "utf-8",
        )

    async def async_set_operation_mode(self, operation_mode: str):
        temp = HeishaMonDHW.operation_modes_temps[operation_mode][0]
        if temp is None:
            _LOGGER.warn(
                f"No target temperature implemented for {operation_mode}, ignoring"
            )
            return
        await self.async_set_temperature(temperature=float(temp))

    def update_temperature_bounds(self) -> None:
        if self._attr_target_temperature is not None:
            self._attr_target_temperature_high = self._attr_target_temperature
            self._attr_target_temperature_low = (
                self._heat_delta + self._attr_target_temperature
            )

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def current_temperature_message_received(message):
            self._attr_current_temperature = float(message.payload)
            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass,
            f"{self.discovery_prefix}main/DHW_Temp",
            current_temperature_message_received,
            1,
        )

        @callback
        def target_temperature_message_received(message):
            self._attr_target_temperature = float(message.payload)
            self.update_temperature_bounds()  # optimistic update
            self._attr_current_operation = "unknown preset"
            for state_name, values in HeishaMonDHW.operation_modes_temps.items():
                if float(message.payload) in values[1]:
                    self._attr_current_operation = state_name
                    break
            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass,
            f"{self.discovery_prefix}main/DHW_Target_Temp",
            target_temperature_message_received,
            1,
        )

        @callback
        def heat_delta_received(message):
            self._heat_delta = int(message.payload)
            self.update_temperature_bounds()
            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass,
            f"{self.discovery_prefix}main/DHW_Heat_Delta",
            heat_delta_received,
            1,
        )

        @callback
        def operating_mode_received(message):
            self._operating_mode = OperatingMode.from_mqtt(message.payload)
            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass,
            f"{self.discovery_prefix}main/Operating_Mode_State",
            operating_mode_received,
            1,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        new_operating_mode = self._operating_mode | OperatingMode.DHW
        await async_publish(
                self.hass,
                f"{self.discovery_prefix}commands/SetOperationMode",
                new_operating_mode.to_mqtt(),
                0,
                False,
                "utf-8",
        )
    async def async_turn_off(self, **kwargs: Any) -> None:
        new_operating_mode = self._operating_mode & ~OperatingMode.DHW
        await async_publish(
                self.hass,
                f"{self.discovery_prefix}commands/SetOperationMode",
                new_operating_mode.to_mqtt(),
                0,
                False,
                "utf-8",
        )

    @property
    def device_info(self):
        return build_device_info(DeviceType.HEATPUMP, self.discovery_prefix)
