"""Value parsers, lookup tables and MQTT writers for HeishaMon topics."""

from __future__ import annotations

import json
import logging
from enum import Flag, auto
from typing import Any, Optional, TypeVar

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from ..models import HEATPUMP_MODELS, HEATPUMP_MODELS_39

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
        mode_mapping = self.modes_to_int()
        if self not in mode_mapping:
            raise ValueError(
                f"Invalid operating mode {self} (value: {self.value}). "
                f"Cannot convert to MQTT value. This may indicate an empty/uninitialized mode."
            )
        return mode_mapping[self]

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
        # heishamon reports Auto as 7/8 (TOP4) while cooling but only accepts 0-6
        # to set it (SET9): Auto is 2 and Auto+DHW is 6 whatever the current state
        value = int(self)
        return str({7: 2, 8: 6}.get(value, value))


def convert_pressure_to_kPa(str_repr: str) -> float:
    return float(str_repr) * 98.0665


def operating_mode_to_state(str_repr: str):
    return OperatingMode.from_str(str_repr).to_mqtt()


def read_enabled_disabled(value: str) -> Optional[bool]:
    if value == "1":
        return True
    if value == "0":
        return False
    return None


def read_bivalent_mode(value: str) -> Optional[str]:
    return BIVALENT_MODES.get(value, None)


BIVALENT_MODES = {
    "0": "Alternative",
    "1": "Parallel",
    "2": "Advanced Parallel",
}


def bivalent_mode_to_mqtt(value: str) -> Optional[str]:
    return lookup_by_value(BIVALENT_MODES, value)


def read_operating_mode_state(value: str) -> str:
    mode = OperatingMode.from_mqtt(value)
    return str(mode)


PUMP_FLOWRATE_MODE = {
    "0": "DeltaT",
    "1": "Maximum flow",
}


def read_pump_flowrate_mode(value: str) -> Optional[str]:
    return PUMP_FLOWRATE_MODE.get(value, None)


def pump_flowrate_mode_to_mqtt(value: str) -> Optional[str]:
    return lookup_by_value(PUMP_FLOWRATE_MODE, value)


def read_liquid_type(value: str) -> Optional[str]:
    if value == "0":
        return "Water"
    if value == "1":
        return "Glycol"
    if value == "-1":
        return None
    _LOGGER.warning(f"Unknown liquid type '{value}', open ticket to maintainer")
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
    if value == "-1":
        return None
    _LOGGER.warning(
        f"Unknown zone sensor type '{value}', please open ticket to maintainer"
    )
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
    if value == "-1":
        return None
    _LOGGER.warning(
        f"Unknown mixing valve request '{value}', please open ticket to maintainer"
    )
    return None


ZONE_STATES_STRING = {
    "0": "Zone 1",
    "1": "Zone 2",
    "2": "Zones 1 + 2",
}


SMART_GRID_MODES_STRING = {
    "0": "Normal",
    "1": "Capacity 1",
    "2": "HP/DHW off",
    "3": "Capacity 2",
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


def read_twoway_valve(value: str) -> Optional[str]:
    if value == "0":
        return "Cooling"
    elif value == "1":
        return "Heating"
    else:
        _LOGGER.info(f"Reading unhandled value for TwoWay Valve state: '{value}'")
        return None


def first_positive(values) -> Optional[int]:
    for v in values:
        if v is not None and v >= 0:
            return int(v)
    return None


def positive_to_bool(value: str) -> bool:
    return int(value) > 0


def bit_to_bool(value: str) -> Optional[bool]:
    if value == "1":
        return True
    elif value == "0":
        return False
    else:
        return None


def relay_to_bool(value: str) -> Optional[bool]:
    if value in ["1", "on", "enable", "true"]:
        return True
    elif value in ["0", "off", "disable", "false"]:
        return False
    return None


def read_demandcontrol(value: str) -> Optional[int]:
    i = float(value)
    if i >= 43 and i <= 234:
        i = (i - 43) / (234 - 43)
        return round(i * 95) + 5
    return None


def write_demandcontrol(value: int) -> str:
    value = (value - 5) / 95  # 5% -> 100% to 0% -> 95% for remapping
    return str(int(value * (234 - 43) + 43))


def read_smart_grid_mode(value: str) -> str:
    return SMART_GRID_MODES_STRING.get(value, f"Unknown smart grid mode: {value}")


def write_smart_grid_mode(value: str) -> str:
    return lookup_by_value(SMART_GRID_MODES_STRING, value)


def read_quiet_mode(value: str) -> str:
    # values range from 0 to 4
    if value == "4":
        return "Scheduled"
    elif value == "0":
        return "Off"
    return value


def read_heatpump_model(value: str) -> str:
    if len(value) < 8:
        # heishamon < 3.9
        return HEATPUMP_MODELS.get(value, "Unknown model for HeishaMon")
    return HEATPUMP_MODELS_39.get(value, "Unknown model for HeishaMon")


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


def write_curves_gen(zone_id: int, action: str, loc: str, point: str):
    def write_curves(value: int) -> str:
        json_doc = {
            f"zone{zone_id}": {
                action.lower(): {loc.lower(): {point.lower(): int(value)}}
            }
        }
        return json.dumps(json_doc)

    return write_curves


def read_holiday_status(value: str) -> str:
    if value == "0":
        return "Off"
    elif value == "1":
        return "Scheduled"
    else:
        return "Active"


def read_holiday_status_to_bool(value: str) -> bool:
    return value != "0"


def online_to_bool(value: str) -> Optional[bool]:
    if value == "Online":
        return True
    elif value == "Offline":
        return False
    else:
        return None


def read_heating_mode(value: str) -> Optional[str]:
    if value == "0":
        return "compensation curve"
    elif value == "1":
        return "direct"
    return None


HEATING_CONTROL = {
    "0": "Comfort",
    "1": "Efficiency",
}


def read_heating_control(value: str) -> Optional[str]:
    return HEATING_CONTROL.get(value, None)


def heating_control_to_mqtt(value: str) -> Optional[str]:
    return lookup_by_value(HEATING_CONTROL, value)


SMART_DHW = {
    "0": "Variable",
    "1": "Standard",
}


def read_smart_dhw(value: str) -> Optional[str]:
    return SMART_DHW.get(value, None)


def smart_dhw_to_mqtt(value: str) -> Optional[str]:
    return lookup_by_value(SMART_DHW, value)


QUIET_MODE_PRIORITY = {
    "0": "Sound",
    "1": "Capacity",
}


def read_quiet_mode_priority(value: str) -> Optional[str]:
    return QUIET_MODE_PRIORITY.get(value, None)


def quiet_mode_priority_to_mqtt(value: str) -> Optional[str]:
    return lookup_by_value(QUIET_MODE_PRIORITY, value)


DHW_SENSOR_SELECTION = {
    "0": "Top",
    "1": "Center",
}


def read_dhw_sensor_selection(value: str) -> Optional[str]:
    return DHW_SENSOR_SELECTION.get(value, None)


def dhw_sensor_selection_to_mqtt(value: str) -> Optional[str]:
    return lookup_by_value(DHW_SENSOR_SELECTION, value)


HEATER_STATE = {
    "0": "blocked",
    "1": "free",
}


def read_heater_state(value: str) -> Optional[str]:
    return HEATER_STATE.get(value, None)


def heater_state_to_mqtt(value: str) -> Optional[str]:
    return lookup_by_value(HEATER_STATE, value)


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


def read_board_type(json_doc: str) -> Optional[str]:
    j = json.loads(json_doc)
    if "board" in j:
        return j["board"]
    if "voltage" in j:
        # ESP32 has a static 3.3V and more than 64k free heap
        if j["voltage"] != 3.3:
            return "ESP8266"
        if "free heap" in j:
            if float(j["free heap"]) > 65535:
                return "ESP32"
    return None


def ms_to_secs(value: Optional[float]) -> Optional[float]:
    if value:
        return value / 1000
    return None
