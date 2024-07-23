"""Definitions for HeishaMon sensors added to MQTT."""
from __future__ import annotations
from functools import partial, wraps
import json
from enum import Flag, auto

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional, TypeVar, Any
import logging

from homeassistant.const import MAJOR_VERSION
from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.number import NumberEntityDescription, NumberDeviceClass


from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)

from .models import HEATPUMP_MODELS
from .const import DeviceType

_LOGGER = logging.getLogger(__name__)


class OperatingMode(Flag):
    HEAT = auto()
    COOL = auto()
    DHW = auto()
    AUTO = auto()

    @staticmethod
    def modes_to_str():
        return {
            OperatingMode.HEAT: "Heat only",
            OperatingMode.COOL: "Cool only",
            (OperatingMode.HEAT | OperatingMode.AUTO): "Auto(Heat)",
            OperatingMode.DHW: "DHW only",
            (OperatingMode.HEAT | OperatingMode.DHW): "Heat+DHW",
            (OperatingMode.COOL | OperatingMode.DHW): "Cool+DHW",
            (
                OperatingMode.HEAT | OperatingMode.AUTO | OperatingMode.DHW
            ): "Auto(Heat)+DHW",
            (OperatingMode.COOL | OperatingMode.AUTO): "Auto(Cool)",
            (
                OperatingMode.COOL | OperatingMode.AUTO | OperatingMode.DHW
            ): "Auto(Cool)+DHW",
        }

    def __str__(self) -> str:
        return self.modes_to_str().get(self, f"Unknown mode")

    @staticmethod
    def modes_to_int():
        return {
            OperatingMode.HEAT: 0,
            OperatingMode.COOL: 1,
            (OperatingMode.HEAT | OperatingMode.AUTO): 2,
            OperatingMode.DHW: 3,
            (OperatingMode.HEAT | OperatingMode.DHW): 4,
            (OperatingMode.COOL | OperatingMode.DHW): 5,
            (OperatingMode.HEAT | OperatingMode.AUTO | OperatingMode.DHW): 6,
            (OperatingMode.COOL | OperatingMode.AUTO): 7,
            (OperatingMode.COOL | OperatingMode.AUTO | OperatingMode.DHW): 8,
        }

    def __int__(self) -> int:
        return self.modes_to_int()[self]

    @staticmethod
    def from_str(str_repr: str) -> OperatingMode:
        operating_mode = lookup_by_value(OperatingMode.modes_to_str(), str_repr)
        if operating_mode is None:
            raise Exception(
                f"Unable to find the operating mode corresponding to {str_repr}"
            )
        return operating_mode

    @staticmethod
    def from_mqtt(value: str) -> OperatingMode:
        operating_mode = lookup_by_value(OperatingMode.modes_to_int(), int(value))
        if operating_mode is None:
            raise Exception(
                f"Unable to find the operating mode corresponding to {value}"
            )
        return operating_mode

    def to_mqtt(self) -> str:
        return str(int(self))


def operating_mode_to_state(str_repr: str):
    return str(int(OperatingMode.from_str(str_repr)))


def read_operating_mode_state(value: str) -> str:
    mode = OperatingMode.from_mqtt(value)
    return str(mode)


def read_pump_flowrate_mode(value: str) -> Optional[str]:
    if value == "0":
        return "DeltaT"
    if value == "1":
        return "Maximum flow"
    _LOGGER.warn(f"Unknown flow rate mode '{value}', open ticket to maintainer")
    return None


def read_liquid_type(value: str) -> Optional[str]:
    if value == "0":
        return "Water"
    if value == "1":
        return "Glycol"
    _LOGGER.warn(f"Unknown liquid type '{value}', open ticket to maintainer")
    return None


def read_zone_sensor_type(value: str) -> Optional[str]:
    if value == "0":
        return "Water Temperature"
    if value == "1":
        return "External Thermostat"
    if value == "2":
        return "Internal Thermostat"
    if value == "3":
        return "Thermistor"
    _LOGGER.warn(f"Unknown zone sensor type '{value}', open ticket to maintainer")
    return None


EXTERNAL_PAD_HEATER_TYPE = {
    "0": "Disabled",
    "1": "type-A",
    "2": "type-B",
}


def read_external_pad_heater_enabled(value: str) -> Optional[str]:
    return EXTERNAL_PAD_HEATER_TYPE.get(
        value, f"Unknown pad heater type value: {value}"
    )


def external_pad_heater_type_to_mqtt(value: str) -> Optional[str]:
    return lookup_by_value(EXTERNAL_PAD_HEATER_TYPE, value)


def read_mixing_valve_request(value: str) -> Optional[str]:
    if value == "0":
        return "Off"
    if value == "1":
        return "Decrease"
    if value == "2":
        return "Increase"
    _LOGGER.warn(f"Unknown mixing valve request '{value}', open ticket to maintainer")
    return None


ZONE_STATES_STRING = {
    "0": "Zone 1",
    "1": "Zone 2",
    "2": "Zones 1 + 2",
}


def read_zones_state(value):
    return ZONE_STATES_STRING.get(value, f"Unknown zone state value: {value}")


def zone_state_to_mqtt(value: str) -> Optional[str]:
    return lookup_by_value(ZONE_STATES_STRING, value)


POWERFUL_MODE_TIMES = {"0": "Off", "1": "30 min", "2": "60 min", "3": "90 min"}


def read_power_mode_time(value):
    return POWERFUL_MODE_TIMES.get(value, f"Unknown powerful mode: {value}")


def set_power_mode_time(value: str):
    return lookup_by_value(POWERFUL_MODE_TIMES, value)


Key = TypeVar("Key")
Value = TypeVar("Value")


def lookup_by_value(hash: dict[Key, Value], value: Value) -> Optional[Key]:
    options = [key for (key, v) in hash.items() if v == value]
    if len(options) == 0:
        return None
    return options[0]


def read_threeway_valve(value: str) -> Optional[str]:
    if value == "0":
        return "Room"
    elif value == "1":
        return "Tank"
    else:
        _LOGGER.info(f"Reading unhandled value for ThreeWay Valve state: '{value}'")
        return None


def first_positive(values) -> Optional[int]:
    for v in values:
        if v is not None and v >= 0:
            return int(v)
    return None


# TODO(kamaradclimber): this decorator can be simply replaced by @dataclass(frozen=True, kw_only=True) when we stop supporting HA < 2024.1
def frozendataclass(cls):
    def wrapper_dataclass(cls):
        if MAJOR_VERSION > 2023:
            return dataclass(cls, frozen=True, kw_only=True)
        else:
            return dataclass(cls)
    if cls is None:
        # we are called with parens
        return wrapper_dataclass

    # we are called without parens
    return wrapper_dataclass(cls)


@frozendataclass
class HeishaMonEntityDescription:
    heishamon_topic_id: str | None = None

    # a method called when receiving a new value
    state: Callable | None = None

    # device sensor belong to
    device: DeviceType = DeviceType.HEATPUMP

    # a method called when receiving a new value. With a lot of context. Used to update device info for instance
    on_receive: Callable | None = None


@frozendataclass
class HeishaMonSensorEntityDescription(
    HeishaMonEntityDescription, SensorEntityDescription
):
    """Sensor entity description for HeishaMon."""

    pass


@frozendataclass
class MultiMQTTSensorEntityDescription(SensorEntityDescription):
    topics: list[str] | None = None
    # this callable will receive a list with as many entries as topics
    # values in that list will be in the same order as the topics key.
    # For instance, if topics are ["a", "b", "c"], state will receive a list with
    # 3 items, whose values will be the last received value from the topics a, b and c.
    # values will be None when we have not received any value for the corresponding topic yet.
    compute_state: Callable | None = None

    # one of unique_id and heishamon_topic_id must be defined
    unique_id: Optional[str] = None
    heishamon_topic_id: Optional[str] = None


@frozendataclass
class HeishaMonSwitchEntityDescription(
    HeishaMonEntityDescription, SwitchEntityDescription
):
    """Switch entity description for HeishaMon."""

    command_topic: str = "void/topic"
    qos: int = 0
    payload_on: str = "1"
    payload_off: str = "0"
    retain: bool = False
    encoding: str = "utf-8"


@frozendataclass
class HeishaMonBinarySensorEntityDescription(
    HeishaMonEntityDescription, BinarySensorEntityDescription
):
    """Binary sensor entity description for HeishaMon."""

    pass


@frozendataclass
class HeishaMonSelectEntityDescription(
    HeishaMonEntityDescription, SelectEntityDescription
):
    """Select entity description for HeishaMon"""

    command_topic: str = "void/topic"
    retain: bool = False
    encoding: str = "utf-8"
    qos: int = 0
    # function to transform selected option in value sent via mqtt
    state_to_mqtt: Optional[Callable] = None


@frozendataclass
class HeishaMonNumberEntityDescription(
    HeishaMonEntityDescription, NumberEntityDescription
):
    """Number entity description for HeishaMon"""

    command_topic: str = "void/topic"
    retain: bool = False
    encoding: str = "utf-8"
    qos: int = 0
    # function to transform selected option in value sent via mqtt
    state_to_mqtt: Optional[Callable] = None

    # Initial value to set waiting for the first message from MQTT
    # if let empty, no value will be set until first message
    initial_value: Optional[Any] = None


def positive_to_bool(value: str) -> bool:
    return int(value) > 0


def bit_to_bool(value: str) -> Optional[bool]:
    if value == "1":
        return True
    elif value == "0":
        return False
    else:
        return None


def read_demandcontrol(value: str) -> Optional[int]:
    i = int(value)
    if i >= 43 and i <= 234:
        return int((i - 43) / (234 - 43) * 100)
    return None


def write_demandcontrol(value: int) -> str:
    return str(value / 100 * (234 - 43) + 43)


def read_quiet_mode(value: str) -> str:
    # values range from 0 to 4
    if value == "4":
        return "Scheduled"
    elif value == "0":
        return "Off"
    return value


def read_heatpump_model(value: str) -> str:
    return HEATPUMP_MODELS.get(value, "Unknown model for HeishaMon")


def read_solar_mode(value: str) -> str:
    return {"0": "Disabled", "1": "Buffer", "2": "DHW"}.get(
        value, f"Unknown solar mode: {value}"
    )


def write_quiet_mode(selected_value: str):
    if selected_value == "Off":
        return 0
    elif selected_value == "Scheduled":
        return 4
    else:
        return int(selected_value)


def guess_shift_or_direct_and_clamp_min_max_values(
    range1,
    range2,
    hass: HomeAssistant,
    entity: SensorEntity,
    config_entry_id: str,
    native_value: int,
):
    """
    This method clamp min/max values based on the current value.
    It relies on the fact that range1 and range2 are not intersecting.
    ^^^ is false because Cool mode value '5' can mean +5 or 5°.
    """
    # FIXME: we assume entity is of type HeishMonNumberEntity. We should find a way to properly use the type system
    if native_value in range1:  # we always favor range1
        entity.set_range(min(range1), max(range1))
    elif native_value in range2:
        entity.set_range(min(range2), max(range2))
    else:
        _LOGGER.warn(
            f"Received value {native_value} for {entity.entity_description.name}. Impossible to know if we are using 'shift' mode or 'direct' mode, ignoring"
        )


def build_numbers(mqtt_prefix: str) -> list[HeishaMonNumberEntityDescription]:
    numbers = [
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET5",  # also TOP27
            key=f"{mqtt_prefix}main/Z1_Heat_Request_Temp",
            command_topic=f"{mqtt_prefix}commands/SetZ1HeatRequestTemperature",
            # it can be relative (-5 -> +5, or absolute [20, ..[)
            name="Aquarea Zone 1 Heat Requested shift",
            entity_category=EntityCategory.CONFIG,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=-5,
            native_max_value=20,
            state=int,
            state_to_mqtt=int,
            on_receive=partial(
                guess_shift_or_direct_and_clamp_min_max_values,
                range(-5, 6),
                range(7, 61),
            ),
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET6",  # also TOP28
            key=f"{mqtt_prefix}main/Z1_Cool_Request_Temp",
            command_topic=f"{mqtt_prefix}commands/SetZ1CoolRequestTemperature",
            # it can be relative (-5 -> +5, or absolute [20, ..[)
            name="Aquarea Zone 1 Cool Requested shift",
            entity_category=EntityCategory.CONFIG,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=-5,
            native_max_value=25,
            state=int,
            state_to_mqtt=int,
            on_receive=partial(
                guess_shift_or_direct_and_clamp_min_max_values,
                range(-5, 6),
                range(5, 26),
            ),
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET7",  # also TOP34
            key=f"{mqtt_prefix}main/Z2_Heat_Request_Temp",
            command_topic=f"{mqtt_prefix}commands/SetZ2HeatRequestTemperature",
            # it can be relative (-5 -> +5, or absolute [20, ..[)
            name="Aquarea Zone 2 Heat Requested shift",
            entity_category=EntityCategory.CONFIG,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=-5,
            native_max_value=20,
            state=int,
            state_to_mqtt=int,
            on_receive=partial(
                guess_shift_or_direct_and_clamp_min_max_values,
                range(-5, 6),
                range(7, 45),
            ),
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET8",  # also TOP35
            key=f"{mqtt_prefix}main/Z2_Cool_Request_Temp",
            command_topic=f"{mqtt_prefix}commands/SetZ2CoolRequestTemperature",
            # it can be relative (-5 -> +5, or absolute [20, ..[)
            name="Aquarea Zone 2 Cool Requested shift",
            entity_category=EntityCategory.CONFIG,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=-5,
            native_max_value=25,
            state=int,
            state_to_mqtt=int,
            on_receive=partial(
                guess_shift_or_direct_and_clamp_min_max_values,
                range(-5, 6),
                range(5, 26),
            ),
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET11",  # TOP9
            key=f"{mqtt_prefix}main/DHW_Target_Temp",
            command_topic=f"{mqtt_prefix}commands/SetDHWTemp",
            name="DHW Target Temperature",
            entity_category=EntityCategory.CONFIG,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=40,
            native_max_value=65,
            state=int,
            state_to_mqtt=int,
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET15",  # also TOP95
            key=f"{mqtt_prefix}main/Max_Pump_Duty",
            command_topic=f"{mqtt_prefix}commands/SetMaxPumpDuty",
            name="Aquarea Max pump duty configured",
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement="Count",
            native_min_value=64,
            native_max_value=254,
            state=int,
            state_to_mqtt=int,
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET18",  # also corresponds to TOP23
            key=f"{mqtt_prefix}main/Heat_Delta",
            command_topic=f"{mqtt_prefix}commands/SetFloorHeatDelta",
            name="Aquarea Room heating delta",
            entity_category=EntityCategory.CONFIG,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=1,
            native_max_value=15,
            state=int,
            state_to_mqtt=int,
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET19",  # also corresponds to TOP24
            key=f"{mqtt_prefix}main/Cool_Delta",
            command_topic=f"{mqtt_prefix}commands/SetFloorCoolDelta",
            name="Aquarea Room Cooling delta",
            entity_category=EntityCategory.CONFIG,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=1,
            native_max_value=15,
            state=int,
            state_to_mqtt=int,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET20",  # also corresponds to TOP22
            key=f"{mqtt_prefix}main/DHW_Heat_Delta",
            command_topic=f"{mqtt_prefix}commands/SetDHWHeatDelta",
            name="Aquarea DHW heating delta",
            entity_category=EntityCategory.CONFIG,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=-12,
            native_max_value=-2,
            state=int,
            state_to_mqtt=int,
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET21",  # also corresponds to TOP96
            key=f"{mqtt_prefix}main/Heater_Delay_Time",
            command_topic=f"{mqtt_prefix}commands/SetHeaterDelayTime",
            name="Aquarea Heater delay time",
            entity_category=EntityCategory.CONFIG,
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement="min",
            native_min_value=10,
            native_max_value=60,
            state=int,
            state_to_mqtt=int,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET22",  # also corresponds to TOP97
            key=f"{mqtt_prefix}main/Heater_Start_Delta",
            command_topic=f"{mqtt_prefix}commands/SetHeaterStartDelta",
            name="Aquarea Heater start delta",
            entity_category=EntityCategory.CONFIG,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="C",
            native_min_value=-10,
            native_max_value=-2,
            state=int,
            state_to_mqtt=int,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET23",  # also corresponds to TOP98
            key=f"{mqtt_prefix}main/Heater_Stop_Delta",
            command_topic=f"{mqtt_prefix}commands/SetHeaterStopDelta",
            name="Aquarea Heater stop delta",
            entity_category=EntityCategory.CONFIG,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="C",
            native_min_value=-8,
            native_max_value=0,
            state=int,
            state_to_mqtt=int,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET27",  # also corresponds to TOP113
            key=f"{mqtt_prefix}main/Buffer_Tank_Delta",
            command_topic=f"{mqtt_prefix}commands/SetBufferDelta",
            name="Aquarea Buffer tank delta",
            entity_category=EntityCategory.CONFIG,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=0,
            native_max_value=10,
            state=int,
            state_to_mqtt=int,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET29",  # also corresponds to TOP77
            key=f"{mqtt_prefix}main/Heating_Off_Outdoor_Temp",
            command_topic=f"{mqtt_prefix}commands/SetHeatingOffOutdoorTemp",
            name="Aquarea Outdoor temperature heating cutoff",
            entity_category=EntityCategory.CONFIG,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=5,
            native_max_value=35,
            state=int,
            state_to_mqtt=int,
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SetDemandControl",
            key=f"{mqtt_prefix}main/FakeDemandControl",  # FIXME: find how to get real value
            command_topic=f"{mqtt_prefix}commands/SetDemandControl",
            name="Demand Control",
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement="%",
            native_min_value=20,
            native_max_value=100,
            native_step=5,
            state=read_demandcontrol,
            state_to_mqtt=write_demandcontrol,
            entity_registry_enabled_default=False,  # comes from the optional PCB: disabled by default
            initial_value=100,
        ),
    ]
    topic_ids = {
        "1 Heat Target High": "TOP29",
        "1 Heat Target Low": "TOP30",
        "1 Heat Outside High": "TOP31",
        "1 Heat Outside Low": "TOP32",
        "1 Cool Target High": "TOP72",
        "1 Cool Target Low": "TOP73",
        "1 Cool Outside High": "TOP74",
        "1 Cool Outside Low": "TOP75",
        "2 Heat Target High": "TOP82",
        "2 Heat Target Low": "TOP83",
        "2 Heat Outside High": "TOP84",
        "2 Heat Outside Low": "TOP85",
        "2 Cool Target High": "TOP86",
        "2 Cool Target Low": "TOP87",
        "2 Cool Outside High": "TOP88",
        "2 Cool Outside Low": "TOP89",
    }
    ranges = {
        "Heat": {
            "Outside": [-20, 30],
            "Target": [15, 60],
        },
        "Cool": {
            "Outside": [15, 30],
            "Target": [5, 20],
        }
    }

    def dual_location(loc):
        if loc == "Target":
            return "Outside"
        return "Target"

    for zone_id in [1, 2]:
        for action in ["Cool", "Heat"]:
            for point in ["High", "Low"]:
                for loc in ["Target", "Outside"]:
                    numbers.append(
                        HeishaMonNumberEntityDescription(
                            heishamon_topic_id=topic_ids[
                                f"{zone_id} {action} {loc} {point}"
                            ],
                            key=f"{mqtt_prefix}main/Z{zone_id}_{action}_Curve_{loc}_{point}_Temp",
                            command_topic=f"{mqtt_prefix}commands/SetCurves",
                            entity_category=EntityCategory.CONFIG,
                            native_min_value=ranges[action][loc][0],
                            native_max_value=ranges[action][loc][1],
                            name=f"Aquarea Zone {zone_id} {loc} water temperature at {point.lower()}est {dual_location(loc).lower()} temperature on {action.lower()}ing curve",
                            device_class=NumberDeviceClass.TEMPERATURE,
                            native_unit_of_measurement="°C",
                            # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
                            entity_registry_enabled_default=(action == "Heat"),
                            state_to_mqtt=write_curves_gen(zone_id, action, loc, point),
                        )
                    )
    return numbers


def write_curves_gen(zone_id: int, action: str, loc: str, point: str):
    def write_curves(value: int) -> str:
        json_doc = {
            f"zone{zone_id}": {
                action.lower(): {loc.lower(): {point.lower(): int(value)}}
            }
        }
        return json.dumps(json_doc)

    return write_curves


def build_selects(mqtt_prefix: str) -> list[HeishaMonSelectEntityDescription]:
    return [
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET3",  # also corresponds to TOP18
            key=f"{mqtt_prefix}main/Quiet_Mode_Level",
            command_topic=f"{mqtt_prefix}commands/SetQuietMode",
            name="Aquarea Quiet Mode",
            entity_category=EntityCategory.CONFIG,
            state=read_quiet_mode,
            state_to_mqtt=write_quiet_mode,
            options=["Off", "1", "2", "3", "Scheduled"],
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET4",  # also corresponds to TOP17
            key=f"{mqtt_prefix}main/Powerful_Mode_Time",
            command_topic=f"{mqtt_prefix}commands/SetPowerfulMode",
            name="Aquarea Powerful Mode",
            state=read_power_mode_time,
            state_to_mqtt=set_power_mode_time,
            options=list(POWERFUL_MODE_TIMES.values()),
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET9",  # also corresponds to TOP4
            key=f"{mqtt_prefix}main/Operating_Mode_State",
            command_topic=f"{mqtt_prefix}commands/SetOperationMode",
            name="Aquarea Mode",
            state=read_operating_mode_state,
            state_to_mqtt=operating_mode_to_state,
            options=list(OperatingMode.modes_to_str().values()),
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET17",  # also TOP94
            key=f"{mqtt_prefix}main/Zones_State",
            command_topic=f"{mqtt_prefix}commands/SetZones",
            name="Active zones",
            state=read_zones_state,
            state_to_mqtt=zone_state_to_mqtt,
            options=list(ZONE_STATES_STRING.values()),
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET26",  # also TOP114
            key=f"{mqtt_prefix}main/External_Pad_Heater",
            command_topic=f"{mqtt_prefix}/commands/SetExternalPadHeater",
            name="Aquarea External Pad Heater type",
            state=read_external_pad_heater_enabled,
            state_to_mqtt=external_pad_heater_type_to_mqtt,
            options=list(EXTERNAL_PAD_HEATER_TYPE.values()),
        ),
    ]


def read_holiday_status(value: str) -> str:
    if value == "0":
        return "Off"
    elif value == "1":
        return "Scheduled"
    else:
        return "Active"


def read_holiday_status_to_bool(value: str) -> bool:
    return value != "0"


def build_switches(mqtt_prefix: str) -> list[HeishaMonSwitchEntityDescription]:
    return [
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SET1",  # also corresponds to TOP0
            key=f"{mqtt_prefix}main/Heatpump_State",
            command_topic=f"{mqtt_prefix}commands/SetHeatpump",
            name="Aquarea Main Power",
            state=bit_to_bool,
            device_class=BinarySensorDeviceClass.RUNNING,
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SET2",  # TOP19
            key=f"{mqtt_prefix}main/Holiday_Mode_State",
            command_topic=f"{mqtt_prefix}commands/SetHolidayMode",
            name="Aquarea Holiday Mode",
            entity_category=EntityCategory.CONFIG,
            state=read_holiday_status_to_bool,
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SET10",  # also corresponds to TOP2
            key=f"{mqtt_prefix}main/Force_DHW_State",
            command_topic=f"{mqtt_prefix}commands/SetForceDHW",
            name="Aquarea Force DHW Mode",
            entity_category=EntityCategory.CONFIG,
            state=bit_to_bool,
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SET12",  # corresponds to TOP26
            key=f"{mqtt_prefix}main/Defrosting_State",
            command_topic=f"{mqtt_prefix}commands/SetForceDefrost",
            name="Aquarea Defrost routine",
            entity_category=EntityCategory.CONFIG,
            device_class=BinarySensorDeviceClass.HEAT,
            state=bit_to_bool,
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SET13",  # corresponds to TOP69
            key=f"{mqtt_prefix}main/Sterilization_State",
            command_topic=f"{mqtt_prefix}commands/SetForceSterilization",
            name="Aquarea Force Sterilization",
            entity_category=EntityCategory.CONFIG,
            device_class=BinarySensorDeviceClass.RUNNING,
            state=bit_to_bool,
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SET24",  # corresponds to "TOP13"
            key=f"{mqtt_prefix}main/Main_Schedule_State",
            command_topic=f"{mqtt_prefix}commands/SetMainSchedule",
            name="Aquarea Main thermostat schedule",
            entity_category=EntityCategory.CONFIG,
            state=bit_to_bool,
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SET28",  # corresponds to TOP99
            key=f"{mqtt_prefix}main/Buffer_Installed",
            command_topic=f"{mqtt_prefix}commands/SetBuffer",
            name="Aquarea Buffer tank",
            entity_category=EntityCategory.CONFIG,
            state=bit_to_bool,
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="RELAY01",
            key=f"{mqtt_prefix}gpio/relay/one",
            command_topic=f"{mqtt_prefix}gpio/relay/one",
            name="Relay 1",
            entity_category=EntityCategory.CONFIG,
            device=DeviceType.HEISHAMON,
            state=bit_to_bool,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="RELAY02",
            key=f"{mqtt_prefix}gpio/relay/two",
            command_topic=f"{mqtt_prefix}gpio/relay/two",
            name="Relay 2",
            entity_category=EntityCategory.CONFIG,
            device=DeviceType.HEISHAMON,
            state=bit_to_bool,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
    ]


def online_to_bool(value: str) -> Optional[bool]:
    if value == "Online":
        return True
    elif value == "Offline":
        return False
    else:
        return None


def build_binary_sensors(
    mqtt_prefix: str,
) -> list[HeishaMonBinarySensorEntityDescription]:
    return [
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="LWT",
            key=f"{mqtt_prefix}LWT",
            name="HeatPump online",
            entity_category=EntityCategory.DIAGNOSTIC,
            device=DeviceType.HEISHAMON,
            state=online_to_bool,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP3",
            key=f"{mqtt_prefix}main/Quiet_Mode_Schedule",
            name="Aquarea Quiet Mode Schedule",
            state=bit_to_bool,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP58",
            key=f"{mqtt_prefix}main/DHW_Heater_State",
            name="Aquarea Tank Heater Enabled",
            state=bit_to_bool,
            device_class=BinarySensorDeviceClass.HEAT,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP59",
            key=f"{mqtt_prefix}main/Room_Heater_State",
            name="Aquarea Room Heater Enabled",
            state=bit_to_bool,            
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP60",
            key=f"{mqtt_prefix}main/Internal_Heater_State",
            name="Aquarea Internal Heater State",
            state=bit_to_bool,
            device_class=BinarySensorDeviceClass.HEAT,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP61",
            key=f"{mqtt_prefix}main/External_Heater_State",
            name="Aquarea External Heater State",
            state=bit_to_bool,
            device_class=BinarySensorDeviceClass.HEAT,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP68",
            key=f"{mqtt_prefix}main/Force_Heater_State",
            name="Aquarea Force heater status",
            state=bit_to_bool,            
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP93",
            key=f"{mqtt_prefix}main/Pump_Duty",
            name="Aquarea Pump Running",
            # TODO(kamaradclimber): it seems value is showing something more than just "on/off". Tests show value of 120 when running and slowly decreasing to 100
            state=positive_to_bool,
            device_class=BinarySensorDeviceClass.RUNNING,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP100",
            key=f"{mqtt_prefix}main/DHW_Installed",
            name="Aquarea DHW Installed",
            state=bit_to_bool,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP108",
            key=f"{mqtt_prefix}main/Alt_External_Sensor",
            name="Aquarea external outdoor sensor selected",
            state=bit_to_bool,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP109",
            key=f"{mqtt_prefix}main/Anti_Freeze_Mode",
            name="Aquarea anti freeze mode",
            state=bit_to_bool,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP110",
            key=f"{mqtt_prefix}main/Optional_PCB",
            name="Aquarea optional PCB enabled",
            state=bit_to_bool,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="OPT0",
            key=f"{mqtt_prefix}optional/Z1_Water_Pump",
            name="Aquarea Zone 1 water pump action request",
            state=bit_to_bool,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="OPT2",
            key=f"{mqtt_prefix}optional/Z2_Water_Pump",
            name="Aquarea Zone 2 water pump action request",
            state=bit_to_bool,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="OPT4",
            key=f"{mqtt_prefix}optional/Pool_Water_Pump",
            name="Aquarea pool water pump action request",
            state=bit_to_bool,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="OPT5",
            key=f"{mqtt_prefix}optional/Solar_Water_Pump",
            name="Aquarea solar water pump action request",
            state=bit_to_bool,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="OPT6",
            key=f"{mqtt_prefix}optional/Alarm_State",
            name="Aquarea Alarm State",
            state=bit_to_bool,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
    ]


def update_device_ip(
    hass: HomeAssistant, entity: SensorEntity, config_entry_id: str, ip: str
):
    _LOGGER.debug(f"Received ip address: {ip}")
    device_registry = dr.async_get(hass)
    identifiers = None
    if entity.device_info is not None and "identifiers" in entity.device_info:
        identifiers = entity.device_info["identifiers"]
    device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers=identifiers,
        configuration_url=f"http://{ip}",
    )


def update_device_model(
    hass: HomeAssistant, entity: SensorEntity, config_entry_id: str, model: str
):
    _LOGGER.debug("Set model")

    device_registry = dr.async_get(hass)
    identifiers = None
    if entity.device_info is not None and "identifiers" in entity.device_info:
        identifiers = entity.device_info["identifiers"]
    device_registry.async_get_or_create(
        config_entry_id=config_entry_id, identifiers=identifiers, model=model
    )


def read_heating_mode(value: str) -> Optional[str]:
    if value == "0":
        return "compensation curve"
    elif value == "1":
        return "direct"
    return None

def read_temp(value: str) -> Optional[Any]:
    v = int(value)
    if v == -128:
        return None
    return value

def read_stats_json(field_name: str, json_doc: str) -> Optional[float]:
    field_value = json.loads(json_doc).get(field_name, None)
    if field_value:
        return float(field_value)
    return None


def ms_to_secs(value: Optional[float]) -> Optional[float]:
    if value:
        return value / 1000
    return None


def build_sensors(mqtt_prefix: str) -> list[HeishaMonSensorEntityDescription]:
    return [
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP1",
            key=f"{mqtt_prefix}main/Pump_Flow",
            name="Aquarea Pump Flow",
            native_unit_of_measurement="L/min",
            state_class=SensorStateClass.MEASUREMENT,
            # device_class=SensorDeviceClass.ENERGY,
            # icon= "mdi:on"
            # entity_registry_enabled_default = False, # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
            # native_unit_of_measurement="L/min",
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP5",
            key=f"{mqtt_prefix}main/Main_Inlet_Temp",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Inlet Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP6",
            key=f"{mqtt_prefix}main/Main_Outlet_Temp",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Outlet Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP7",
            key=f"{mqtt_prefix}main/Main_Target_Temp",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Outlet Target Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP8",
            key=f"{mqtt_prefix}main/Compressor_Freq",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Compressor Frequency",
            device_class=SensorDeviceClass.FREQUENCY,
            native_unit_of_measurement="Hz",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP10",
            key=f"{mqtt_prefix}main/DHW_Temp",
            name="Aquarea Tank Actual Tank Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP11",
            key=f"{mqtt_prefix}main/Operations_Hours",
            name="Aquarea Compressor Operating Hours",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement="h",
            state_class=SensorStateClass.TOTAL_INCREASING,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP12",
            key=f"{mqtt_prefix}main/Operations_Counter",
            name="Aquarea Compressor Start/Stop Counter",
            state_class=SensorStateClass.TOTAL_INCREASING,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP14",
            key=f"{mqtt_prefix}main/Outside_Temp",
            name="Aquarea Outdoor Ambient",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        MultiMQTTSensorEntityDescription(
            heishamon_topic_id="TOP15",
            key=f"{mqtt_prefix}main/Heat_Power_Production",
            topics=[
                f"{mqtt_prefix}extra/Heat_Power_Production_Extra",  # XTOP3, fw >= 3.2.3
                f"{mqtt_prefix}extra/Heat_Power_Production",  # XTOP3
                f"{mqtt_prefix}main/Heat_Power_Production",
                f"{mqtt_prefix}main/Heat_Energy_Production",
            ],
            compute_state=first_positive,
            name="Aquarea Heat Power Produced",
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement="W",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        MultiMQTTSensorEntityDescription(
            heishamon_topic_id="TOP16",
            key=f"{mqtt_prefix}main/Heat_Power_Consumption",
            topics=[
                f"{mqtt_prefix}extra/Heat_Power_Consumption_Extra",  # XTOP3, fw >= 3.2.3
                f"{mqtt_prefix}extra/Heat_Power_Consumption",  # XTOP0
                f"{mqtt_prefix}main/Heat_Power_Consumption",
                f"{mqtt_prefix}main/Heat_Energy_Consumption",
            ],
            compute_state=first_positive,
            name="Aquarea Heat Power Consumed",
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement="W",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP20",
            key=f"{mqtt_prefix}main/ThreeWay_Valve_State",
            name="Aquarea 3-way Valve",
            state=read_threeway_valve,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP21",
            key=f"{mqtt_prefix}main/Outside_Pipe_Temp",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Outdoor Pipe Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP23",
            key=f"{mqtt_prefix}main/Heat_Delta",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Heat delta",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP24",
            key=f"{mqtt_prefix}main/Cool_Delta",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Cool delta",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP25",
            key=f"{mqtt_prefix}main/DHW_Holiday_Shift_Temp",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea DHW Holiday shift temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP33",
            key=f"{mqtt_prefix}main/Room_Thermostat_Temp",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Remote control thermostat temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP36",
            key=f"{mqtt_prefix}main/Z1_Water_Temp",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Zone 1 water outlet temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state=read_temp,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP37",
            key=f"{mqtt_prefix}main/Z2_Water_Temp",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Zone 2 water outlet temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state=read_temp,
        ),
        MultiMQTTSensorEntityDescription(
            heishamon_topic_id="TOP38",
            key=f"{mqtt_prefix}main/Cool_Power_Production",
            topics=[
                f"{mqtt_prefix}extra/Cool_Power_Production_Extra",  # XTOP4, fw >= 3.2.3
                f"{mqtt_prefix}extra/Cool_Power_Production",  # XTOP4
                f"{mqtt_prefix}main/Cool_Power_Production",
                f"{mqtt_prefix}main/Cool_Energy_Production",
            ],
            compute_state=first_positive,
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Thermal Cooling power production",
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement="W",
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        MultiMQTTSensorEntityDescription(
            heishamon_topic_id="TOP39",
            key=f"{mqtt_prefix}main/Cool_Power_Consumption",
            topics=[
                f"{mqtt_prefix}extra/Cool_Power_Consumption_Extra",  # XTOP1, fw >= 3.2.3
                f"{mqtt_prefix}extra/Cool_Power_Consumption",  # XTOP1
                f"{mqtt_prefix}main/Cool_Power_Consumption",
                f"{mqtt_prefix}main/Cool_Energy_Consumption",
            ],
            compute_state=first_positive,
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Thermal Cooling power consumption",
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement="W",
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        MultiMQTTSensorEntityDescription(
            heishamon_topic_id="TOP40",
            key=f"{mqtt_prefix}main/DHW_Power_Production",
            topics=[
                f"{mqtt_prefix}extra/DHW_Power_Production_Extra",  # XTOP5, fw >= 3.2.3
                f"{mqtt_prefix}extra/DHW_Power_Production",  # XTOP5
                f"{mqtt_prefix}main/DHW_Power_Production",
                f"{mqtt_prefix}main/DHW_Energy_Production",
            ],
            compute_state=first_positive,
            name="Aquarea DHW Power Produced",
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement="W",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        MultiMQTTSensorEntityDescription(
            heishamon_topic_id="TOP41",
            key=f"{mqtt_prefix}main/DHW_Power_Consumption",
            topics=[
                f"{mqtt_prefix}extra/DHW_Power_Consumption_Extra",  # XTOP2, fw >= 3.2.3
                f"{mqtt_prefix}extra/DHW_Power_Consumption",  # XTOP2
                f"{mqtt_prefix}main/DHW_Power_Consumption",
                f"{mqtt_prefix}main/DHW_Energy_Consumption",
            ],
            compute_state=first_positive,
            name="Aquarea DHW Power Consumed",
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement="W",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP42",
            key=f"{mqtt_prefix}main/Z1_Water_Target_Temp",
            name="Aquarea Zone 1 water target temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP43",
            key=f"{mqtt_prefix}main/Z2_Water_Target_Temp",
            name="Aquarea Zone 2 water target temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP44",
            key=f"{mqtt_prefix}main/Error",
            name="Aquarea Last Error",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP45",
            key=f"{mqtt_prefix}main/Room_Holiday_Shift_Temp",
            name="Aquarea Room heating Holiday shift temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP46",
            key=f"{mqtt_prefix}main/Buffer_Temp",
            name="Aquarea Actual Buffer temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP47",
            key=f"{mqtt_prefix}main/Solar_Temp",
            name="Aquarea Actual Solar temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP48",
            key=f"{mqtt_prefix}main/Pool_Temp",
            name="Aquarea Actual Pool temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP49",
            key=f"{mqtt_prefix}main/Main_Hex_Outlet_Temp",
            name="Aquarea Main HEX Outlet Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP50",
            key=f"{mqtt_prefix}main/Discharge_Temp",
            name="Aquarea Discharge Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP51",
            key=f"{mqtt_prefix}main/Inside_Pipe_Temp",
            name="Aquarea Inside Pipe Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP52",
            key=f"{mqtt_prefix}main/Defrost_Temp",
            name="Aquarea Defrost Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP53",
            key=f"{mqtt_prefix}main/Eva_Outlet_Temp",
            name="Aquarea Eva Outlet Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP54",
            key=f"{mqtt_prefix}main/Bypass_Outlet_Temp",
            name="Aquarea Bypass Outlet Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP55",
            key=f"{mqtt_prefix}main/Ipm_Temp",
            name="Aquarea Ipm Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP56",
            key=f"{mqtt_prefix}main/Z1_Temp",
            name="Aquarea Zone1: Actual Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP57",
            key=f"{mqtt_prefix}main/Z2_Temp",
            name="Aquarea Zone2: Actual Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP62",
            key=f"{mqtt_prefix}main/Fan1_Motor_Speed",
            name="Aquarea Fan 1 Speed",
            native_unit_of_measurement="R/min",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP63",
            key=f"{mqtt_prefix}main/Fan2_Motor_Speed",
            name="Aquarea Fan 2 Speed",
            native_unit_of_measurement="R/min",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP64",
            key=f"{mqtt_prefix}main/High_Pressure",
            name="Aquarea High pressure",
            native_unit_of_measurement="Kgf/cm2",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP65",
            key=f"{mqtt_prefix}main/Pump_Speed",
            name="Aquarea Pump Speed",
            native_unit_of_measurement="R/min",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP66",
            key=f"{mqtt_prefix}main/Low_Pressure",
            name="Aquarea Low Pressure",
            native_unit_of_measurement="Kgf/cm2",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP67",
            key=f"{mqtt_prefix}main/Compressor_Current",
            name="Aquarea Compressor Current",
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement="A",
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP70",
            key=f"{mqtt_prefix}main/Sterilization_Temp",
            name="Aquarea Sterilization Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP71",
            key=f"{mqtt_prefix}main/Sterilization_Max_Time",
            name="Aquarea Sterilization maximum time",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement="min",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP76",
            key=f"{mqtt_prefix}main/Heating_Mode",
            name="Aquarea Heating Mode",
            state=read_heating_mode,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP78",
            key=f"{mqtt_prefix}main/Heater_On_Outdoor_Temp",
            name="Aquarea Outdoor temperature backup heater power on",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP79",
            key=f"{mqtt_prefix}main/Heat_To_Cool_Temp",
            name="Aquarea Outdoor temperature heat->cool threshold",  # when in "auto" mode
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP80",
            key=f"{mqtt_prefix}main/Cool_To_Heat_Temp",
            name="Aquarea Outdoor temperature cool->heat threshold",  # when in "auto" mode
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP81",
            key=f"{mqtt_prefix}main/Cooling_Mode",
            name="Aquarea Cooling Mode",
            state=read_heating_mode,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP90",
            key=f"{mqtt_prefix}main/Room_Heater_Operations_Hours",
            name="Aquarea Electric heater operating time for Room",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement="h",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP91",
            key=f"{mqtt_prefix}main/DHW_Heater_Operations_Hours",
            name="Aquarea Electric heater operating time for DHW",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement="h",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP92",
            key=f"{mqtt_prefix}main/Heat_Pump_Model",
            name="Aquarea Heatpump model",
            state=read_heatpump_model,
            on_receive=update_device_model,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP93",
            key=f"{mqtt_prefix}main/Pump_Duty",
            name="Aquarea Pump Duty",
            native_unit_of_measurement="Count",
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP101",
            key=f"{mqtt_prefix}main/Solar_Mode",
            name="Aquarea Solar Mode",
            state=read_solar_mode,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP102",
            key=f"{mqtt_prefix}main/Solar_On_Delta",
            name="Aquarea Solar delta on",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state=int,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP103",
            key=f"{mqtt_prefix}main/Solar_Off_Delta",
            name="Aquarea Solar delta off",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state=int,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP104",
            key=f"{mqtt_prefix}main/Solar_Frost_Protection",
            name="Aquarea Solar frost protection temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state=int,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP105",
            key=f"{mqtt_prefix}main/Solar_High_Limit",
            name="Aquarea Solar max temperature limit",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            state=int,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP106",
            key=f"{mqtt_prefix}main/Pump_Flowrate_Mode",
            name="Aquarea Pump flowrate mode",
            state=read_pump_flowrate_mode,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP107",
            key=f"{mqtt_prefix}main/Liquid_Type",
            name="Aquarea Liquid Type",
            state=read_liquid_type,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP111",
            key=f"{mqtt_prefix}main/Z2_Sensor_Settings",
            name="Aquarea Zone 2 sensor setting",
            state=read_zone_sensor_type,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP112",
            key=f"{mqtt_prefix}main/Z1_Sensor_Settings",
            name="Aquarea Zone 1 sensor setting",
            state=read_zone_sensor_type,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP113",
            key=f"{mqtt_prefix}main/Buffer_Tank_Delta",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Buffer tank delta",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP115",
            key=f"{mqtt_prefix}main/Water_Pressure",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Water Pressure",
            device_class=SensorDeviceClass.PRESSURE,
            native_unit_of_measurement="bar",
            entity_registry_enabled_default=False, # K/L Series
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP116",
            key=f"{mqtt_prefix}main/Second_Inlet_Temp",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Inlet 2 Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            entity_registry_enabled_default=False, # K/L Series
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP117",
            key=f"{mqtt_prefix}main/Economizer_Outlet_Temp",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Economizer Outlet Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            entity_registry_enabled_default=False, # K/L Series
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="TOP118",
            key=f"{mqtt_prefix}main/Second_Room_Thermostat_Temp",
            state_class=SensorStateClass.MEASUREMENT,
            name="Aquarea Remote control 2 thermostat temp",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            entity_registry_enabled_default=False, # K/L Series
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="STAT1_rssi",
            key=f"{mqtt_prefix}stats",
            name="HeishaMon RSSI",
            state=partial(read_stats_json, "wifi"),
            device=DeviceType.HEISHAMON,
            native_unit_of_measurement="%",
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="STAT1_uptime",
            key=f"{mqtt_prefix}stats",
            name="HeishaMon Uptime",
            state=lambda json_doc: ms_to_secs(read_stats_json("uptime", json_doc)),
            device=DeviceType.HEISHAMON,
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement="s",
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="STAT1_total_reads",
            key=f"{mqtt_prefix}stats",
            name="HeishaMon Total reads",
            state=partial(read_stats_json, "total reads"),
            device=DeviceType.HEISHAMON,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="STAT1_good_reads",
            key=f"{mqtt_prefix}stats",
            name="HeishaMon Good reads",
            state=partial(read_stats_json, "good reads"),
            device=DeviceType.HEISHAMON,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="STAT1_badcrc_reads",
            key=f"{mqtt_prefix}stats",
            name="HeishaMon bad CRC reads",
            state=partial(read_stats_json, "bad crc reads"),
            device=DeviceType.HEISHAMON,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="STAT1_badheader_reads",
            key=f"{mqtt_prefix}stats",
            name="HeishaMon bad header reads",
            state=partial(read_stats_json, "bad header reads"),
            device=DeviceType.HEISHAMON,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="STAT1_tooshort_reads",
            key=f"{mqtt_prefix}stats",
            name="HeishaMon too short reads",
            state=partial(read_stats_json, "too short reads"),
            device=DeviceType.HEISHAMON,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="STAT1_toolong_reads",
            key=f"{mqtt_prefix}stats",
            name="HeishaMon too long reads",
            state=partial(read_stats_json, "too long reads"),
            device=DeviceType.HEISHAMON,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="STAT1_timeout_reads",
            key=f"{mqtt_prefix}stats",
            name="HeishaMon timeout reads",
            state=partial(read_stats_json, "timeout reads"),
            device=DeviceType.HEISHAMON,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="STAT1_voltage",
            key=f"{mqtt_prefix}stats",
            name="HeishaMon voltage",
            state=partial(read_stats_json, "voltage"),
            device=DeviceType.HEISHAMON,
            native_unit_of_measurement="V",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="STAT1_freememory",
            key=f"{mqtt_prefix}stats",
            name="HeishaMon free memory",
            state=partial(read_stats_json, "free memory"),
            device=DeviceType.HEISHAMON,
            native_unit_of_measurement="%",
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="STAT1_freeheap",
            key=f"{mqtt_prefix}stats",
            name="HeishaMon free heap",
            state=partial(read_stats_json, "free heap"),
            device=DeviceType.HEISHAMON,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="STAT1-mqttreconnects",
            key=f"{mqtt_prefix}stats",
            name="HeishaMon mqtt reconnects",
            state=partial(read_stats_json, "mqtt reconnects"),
            device=DeviceType.HEISHAMON,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="STAT1-active-rules",
            key=f"{mqtt_prefix}stats",
            name="HeishaMon Active rules",
            state=partial(read_stats_json, "rules active"),
            device=DeviceType.HEISHAMON,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="INFO_ip",
            key=f"{mqtt_prefix}ip",
            name="HeishaMon IP Address",
            device=DeviceType.HEISHAMON,
            entity_category=EntityCategory.DIAGNOSTIC,
            on_receive=update_device_ip,
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="OPT1",
            key=f"{mqtt_prefix}optional/Z1_Mixing_Valve",
            name="Aquarea Zone 1 mixing valve request",
            state=read_mixing_valve_request,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSensorEntityDescription(
            heishamon_topic_id="OPT3",
            key=f"{mqtt_prefix}optional/Z2_Mixing_Valve",
            name="Aquarea Zone 2 mixing valve request",
            state=read_mixing_valve_request,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
    ]
