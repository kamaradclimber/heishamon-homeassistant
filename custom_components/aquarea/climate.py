"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations
import logging

from homeassistant.components import mqtt
from homeassistant.components.mqtt.client import async_publish
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from homeassistant.components.climate import ClimateEntityDescription
from homeassistant.components.climate.const import (
    PRESET_ECO,
    PRESET_COMFORT,
    PRESET_NONE,
)
from .definitions import lookup_by_value
from . import build_device_info
from .const import DeviceType

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HeishaMon climates from config entry."""
    description = ClimateEntityDescription(
        key="panasonic_heat_pump/main/DHW_Target_Temp",
        name="Aquarea Domestic Water Heater",
    )
    async_add_entities([HeishaMonDHWClimate(hass, description, config_entry)])


class HeishaMonDHWClimate(ClimateEntity):
    """Representation of a HeishaMon sensor that is updated via MQTT."""

    preset_mode_temps = {
        "52": PRESET_ECO,
        "60": PRESET_COMFORT,
    }

    def __init__(
        self,
        hass: HomeAssistant,
        description: ClimateEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the climate entity."""
        self.config_entry_entry_id = config_entry.entry_id
        self.entity_description = description
        self.hass = hass

        slug = slugify(self.entity_description.key.replace("/", "_"))
        self.entity_id = f"climate.{slug}"
        self._attr_unique_id = f"{config_entry.entry_id}"

        self._attr_temperature_unit = "°C"
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        )
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_min_temp = 50
        self._attr_max_temp = 65
        self._operating_mode = -1
        self._attr_preset_modes = [PRESET_ECO, PRESET_COMFORT]
        self._attr_preset_mode = PRESET_ECO

    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get("temperature")
        _LOGGER.debug(f"Changing {self.name} target temperature to {temperature})")
        payload = str(temperature)
        await async_publish(
            self.hass,
            "panasonic_heat_pump/commands/SetDHWTemp",
            payload,
            0,
            False,
            "utf-8",
        )

    async def async_set_preset_mode(self, preset_mode: str):
        temp = lookup_by_value(HeishaMonDHWClimate.preset_mode_temps, preset_mode)
        if temp is None:
            _LOGGER.warn(
                f"No target temperature implemented for {preset_mode}, ignoring"
            )
            return
        await self.async_set_temperature(temperature=float(temp))

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def current_temperature_message_received(message):
            self._attr_current_temperature = float(message.payload)
            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass,
            "panasonic_heat_pump/main/DHW_Temp",
            current_temperature_message_received,
            1,
        )

        @callback
        def target_temperature_message_received(message):
            self._attr_target_temperature = float(message.payload)
            self._attr_preset_mode = HeishaMonDHWClimate.preset_mode_temps.get(
                str(int(self._attr_target_temperature)), PRESET_NONE
            )
            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass,
            "panasonic_heat_pump/main/DHW_Target_Temp",
            target_temperature_message_received,
            1,
        )

        @callback
        def operating_state_message_received(message):
            value = int(message.payload)
            self._operating_mode = value
            if value in [3, 4, 5, 6, 8]:
                self._attr_hvac_mode = HVACMode.HEAT
            else:
                self._attr_hvac_mode = HVACMode.OFF
            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass,
            "panasonic_heat_pump/main/Operating_Mode_State",
            operating_state_message_received,
            1,
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.HEAT:
            value = {
                "0": "4",
                "1": "5",
                "2": "6",
                "3": "3",
                "4": "4",
                "5": "5",
                "6": "6",
                "7": "8",
                "8": "8",
            }[str(self._operating_mode)]
        elif hvac_mode == HVACMode.OFF:
            value = {
                "0": "0",
                "1": "1",
                "2": "2",
                "3": "3",  # we don't have a way to completely shut down DHW, so it should be different than 3
                "4": "1",
                "5": "2",
                "6": "2",
                "7": "7",
                "8": "7",
            }[str(self._operating_mode)]
            if value == 3:
                _LOGGER.warn(
                    f"Impossible to set {hvac_mode} on this heatpump, we can't disable water heater when heating/cooling is already disabled"
                )
        else:
            raise NotImplemented(
                f"Mode {hvac_mode} has not been implemented by this entity"
            )
        await async_publish(
            self.hass,
            "panasonic_heat_pump/commands/SetOperationMode",
            value,
            0,
            False,
            "utf-8",
        )
        self._attr_hvac_mode = hvac_mode  # let's be optimistic
        self.async_write_ha_state()

    @property
    def device_info(self):
        return build_device_info(DeviceType.HEATPUMP)
