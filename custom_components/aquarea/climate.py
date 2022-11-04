"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from enum import Enum, Flag, auto

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
from .definitions import lookup_by_value, OperatingMode
from . import build_device_info
from .const import DeviceType

_LOGGER = logging.getLogger(__name__)


class ZoneState(Flag):
    ZONE1 = auto()
    ZONE2 = auto()

    @staticmethod
    def from_id(id: int) -> ZoneState:
        if id == 1:
            return ZoneState.ZONE1
        elif id == 2:
            return ZoneState.ZONE2
        else:
            raise Exception(f"No zone with id {id}")

    def to_mqtt(self) -> str:
        return str(
            {
                ZoneState.ZONE1: 0,
                ZoneState.ZONE2: 1,
                (ZoneState.ZONE1 | ZoneState.ZONE2): 2,
            }[self]
        )

    @staticmethod
    def from_mqtt(value: str) -> ZoneState:
        return {
            0: ZoneState.ZONE1,
            1: ZoneState.ZONE2,
            2: (ZoneState.ZONE1 | ZoneState.ZONE2),
        }[int(value)]


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
    description_zone1 = ZoneClimateEntityDescription(
        key="panasonic_heat_pump/main/Z1_Temp",
        name="Aquarea Zone 1 climate",
        zone_id=1,
    )
    zone1_climate = HeishaMonZoneClimate(hass, description_zone1, config_entry)
    description_zone2 = ZoneClimateEntityDescription(
        name="Aquarea Zone 2 climate",
        key="panasonic_heat_pump/main/Z2_Temp",
        zone_id=2,
    )
    zone2_climate = HeishaMonZoneClimate(hass, description_zone2, config_entry)
    async_add_entities([zone1_climate, zone2_climate])


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
        self._attr_min_temp = 40
        self._attr_max_temp = 65
        self._attr_target_temperature_step = 1
        self._operating_mode = OperatingMode(0)  # i.e None
        self._attr_preset_modes = [PRESET_ECO, PRESET_COMFORT]
        self._attr_preset_mode = PRESET_ECO

        self._heatpump_state = False

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

        def guess_hvac_mode() -> HVACMode:
            if OperatingMode.DHW in self._operating_mode and self._heatpump_state:
                return HVACMode.HEAT
            else:
                return HVACMode.OFF

        @callback
        def heatpump_state_message_received(message):
            self._heatpump_state = bool(int(message.payload))
            self._attr_hvac_mode = guess_hvac_mode()
            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass,
            "panasonic_heat_pump/main/Heatpump_State",
            heatpump_state_message_received,
            1,
        )

        @callback
        def operating_state_message_received(message):
            self._operating_mode = OperatingMode.from_mqtt(message.payload)
            self._attr_hvac_mode = guess_hvac_mode()
            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass,
            "panasonic_heat_pump/main/Operating_Mode_State",
            operating_state_message_received,
            1,
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        new_heatpump_state = self._heatpump_state
        if hvac_mode == HVACMode.HEAT:
            new_operating_mode = self._operating_mode | OperatingMode.DHW
            new_heatpump_state = True
        elif hvac_mode == HVACMode.OFF:
            new_operating_mode = self._operating_mode & ~OperatingMode.DHW
            if new_operating_mode == OperatingMode(0):  # i.e "none"
                new_heatpump_state = False
        else:
            raise NotImplemented(
                f"Mode {hvac_mode} has not been implemented by this entity"
            )
        if (
            new_operating_mode != OperatingMode(0)
            and new_operating_mode != self._operating_mode
        ):
            await async_publish(
                self.hass,
                "panasonic_heat_pump/commands/SetOperationMode",
                new_operating_mode.to_mqtt(),
                0,
                False,
                "utf-8",
            )
        if new_heatpump_state != self._heatpump_state:
            await async_publish(
                self.hass,
                "panasonic_heat_pump/commands/SetHeatpump",
                str(int(new_heatpump_state)),
                0,
                False,
                "utf-8",
            )
        self._attr_hvac_mode = hvac_mode  # let's be optimistic
        self.async_write_ha_state()

    @property
    def device_info(self):
        return build_device_info(DeviceType.HEATPUMP)


@dataclass
class ZoneClimateEntityDescription(ClimateEntityDescription):
    zone_id: int = 1


class ZoneClimateMode(Enum):
    COMPENSATION = 1
    DIRECT = 2


class HeishaMonZoneClimate(ClimateEntity):
    """Representation of a HeishaMon climate entity that is updated via MQTT."""

    def __init__(
        self,
        hass: HomeAssistant,
        description: ZoneClimateEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the climate entity."""
        self.config_entry_entry_id = config_entry.entry_id
        self.entity_description = description
        self.hass = hass

        self.zone_id = description.zone_id
        slug = slugify(self.entity_description.key.replace("/", "_"))
        self.entity_id = f"climate.{slug}"
        self._attr_unique_id = f"{config_entry.entry_id}-{self.zone_id}"

        self._attr_temperature_unit = "°C"
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        self._attr_hvac_mode = HVACMode.OFF

        self._zone_state = ZoneState(0)  # i.e None
        self._operating_mode = OperatingMode(0)  # i.e None

        self._mode = ZoneClimateMode.DIRECT
        # this line should be last since it leads to write state so object must be completely ready
        self.change_mode(ZoneClimateMode.DIRECT)


    def change_mode(self, mode: ZoneClimateMode):
        _LOGGER.warn(f"Changing mode to {mode} for zone {self.zone_id}")
        self._mode = mode
        if mode == ZoneClimateMode.COMPENSATION:
            self._attr_min_temp = -5
            self._attr_max_temp = 5
            self._attr_target_temperature_step = 1
        else:
            self._attr_min_temp = 15
            self._attr_max_temp = 25
            self._attr_target_temperature_step = 1
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get("temperature")

        if self._mode == ZoneClimateMode.COMPENSATION:
            _LOGGER.info(
                f"Changing {self.name} temperature offset to {temperature} for zone {self.zone_id}"
            )
        elif self._mode == ZoneClimateMode.DIRECT:
            _LOGGER.info(
                f"Changing {self.name} target temperature to {temperature} for zone {self.zone_id}"
            )
        else:
            raise Exception(f"Unknown climate mode: {self._mode}")
        payload = str(temperature)

        _LOGGER.debug(
            f"sending {payload} as temperature command for zone {self.zone_id}"
        )
        await async_publish(
            self.hass,
            f"panasonic_heat_pump/commands/SetZ{self.zone_id}HeatRequestTemperature",
            payload,
            0,
            False,
            "utf-8",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def mode_received(message):
            if message.payload == "0":
                mode = ZoneClimateMode.COMPENSATION
            elif message.payload == "1":
                mode = ZoneClimateMode.DIRECT
            else:
                assert False, f"Mode received is not a known value"
            if mode != self._mode:
                self.change_mode(mode)

        await mqtt.async_subscribe(
            self.hass,
            f"panasonic_heat_pump/main/Heating_Mode",
            mode_received,
            1,
        )

        @callback
        def current_temperature_message_received(message):
            self._attr_current_temperature = float(message.payload)
            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass,
            f"panasonic_heat_pump/main/Z{self.zone_id}_Temp",
            current_temperature_message_received,
            1,
        )

        @callback
        def target_temperature_message_received(message):
            self._attr_target_temperature = float(message.payload)
            _LOGGER.debug(f"Received target temperature for {self.zone_id}: {self._attr_target_temperature}")
            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass,
            f"panasonic_heat_pump/main/Z{self.zone_id}_Heat_Request_Temp",
            target_temperature_message_received,
            1,
        )

        def guess_hvac_mode() -> HVACMode:
            global_heating = OperatingMode.HEAT in self._operating_mode
            zone_heating = ZoneState.from_id(self.zone_id) in self._zone_state
            if global_heating and zone_heating:
                return HVACMode.HEAT
            else:
                return HVACMode.OFF

        @callback
        def heating_conf_message_received(message):
            if message.topic == "panasonic_heat_pump/main/Zones_State":
                self._zone_state = ZoneState.from_mqtt(message.payload)
            elif message.topic == "panasonic_heat_pump/main/Operating_Mode_State":
                self._operating_mode = OperatingMode.from_mqtt(message.payload)
            self._attr_hvac_mode = guess_hvac_mode()
            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass,
            "panasonic_heat_pump/main/Zones_State",
            heating_conf_message_received,
            1,
        )
        await mqtt.async_subscribe(
            self.hass,
            "panasonic_heat_pump/main/Operating_Mode_State",
            heating_conf_message_received,
            1,
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.HEAT:
            new_zone_state = self._zone_state | ZoneState.from_id(self.zone_id)
            new_operating_mode = self._operating_mode | OperatingMode.HEAT
        elif hvac_mode == HVACMode.OFF:
            new_zone_state = self._zone_state & ~ZoneState.from_id(self.zone_id)
            new_operating_mode = self._operating_mode
            if new_zone_state == ZoneState(0):
                new_operating_mode = self._operating_mode & ~OperatingMode.HEAT
        else:
            raise NotImplemented(
                f"Mode {hvac_mode} has not been implemented by this entity"
            )
        if new_operating_mode != self._operating_mode:
            _LOGGER.debug(
                f"Setting operation mode {new_operating_mode} for zone {self.zone_id}"
            )
            await async_publish(
                self.hass,
                "panasonic_heat_pump/commands/SetOperationMode",
                new_operating_mode.to_mqtt(),
                0,
                False,
                "utf-8",
            )
        if new_zone_state not in [self._zone_state, ZoneState(0)]:
            _LOGGER.debug(
                f"Setting operation mode {new_zone_state} for zone {self.zone_id}"
            )
            await async_publish(
                self.hass,
                "panasonic_heat_pump/commands/SetZones",
                new_zone_state.to_mqtt(),
                0,
                False,
                "utf-8",
            )
        self._attr_hvac_mode = hvac_mode  # let's be optimistic
        self.async_write_ha_state()

    @property
    def device_info(self):
        return build_device_info(DeviceType.HEATPUMP)
