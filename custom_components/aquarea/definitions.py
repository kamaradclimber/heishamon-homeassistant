"""Definitions for HeishaMon sensors added to MQTT."""
from __future__ import annotations
from functools import partial, reduce
import json

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional
import logging

from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers import device_registry as dr
from homeassistant.components.switch import SwitchEntityDescription, SwitchDeviceClass


from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.const import (
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_KILO_WATT,
    VOLUME_CUBIC_METERS,
)

from .models import HEATPUMP_MODELS
from .const import DeviceType

_LOGGER = logging.getLogger(__name__)


def read_operating_mode_state(value):
    values = {
        "0": "Heat",
        "1": "Cool",
        "2": "Auto",
        "3": "DHW",
        "4": "Heat+DWH",
        "5": "Cool+DHW",
        "6": "Auto+DHW",
    }
    return values.get(value, f"Unknown operating mode value")


def read_power_mode_time(value):
    return int(value) * 30


def read_threeway_valve(value: str) -> Optional[str]:
    if value == "0":
        return "Room"
    elif value == "1":
        return "Tank"
    else:
        _LOGGER.info(f"Reading unhandled value for ThreeWay Valve state: '{value}'")
        return None


@dataclass
class HeishaMonSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description for HeishaMon."""

    # a method called when receiving a new value
    state: Callable | None = None

    # a method called when receiving a new value. With a lot of context. Used to update device info for instance
    on_receive: Callable | None = None

    # for fields using the same mqtt topic
    unique_id_suffix: str | None = None

    # device sensor belong to
    device: DeviceType = DeviceType.HEATPUMP


@dataclass
class HeishaMonSwitchEntityDescription(SwitchEntityDescription):
    """Switch entity description for HeishaMon."""

    command_topic: str = "void/topic"
    qos: int = 0
    payload_on: str = "1"
    payload_off: str = "0"
    retain: bool = False
    encoding: str = "utf-8"
    # a method called when receiving a new value
    state: Callable | None = None
    # device sensor belong to
    device: DeviceType = DeviceType.HEATPUMP


@dataclass
class HeishaMonBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Binary sensor entity description for HeishaMon."""

    state: Callable | None = None

    # device sensor belong to
    device: DeviceType = DeviceType.HEATPUMP


def bit_to_bool(value: str) -> Optional[bool]:
    if value == "1":
        return True
    elif value == "0":
        return False
    else:
        return None


def read_quiet_mode(value: str) -> Optional[bool]:
    if value == "4":
        return True  # Scheduled
    elif value == "0":
        return False
    _LOGGER.info(f"Reading unhandled quiet mode: '{value}'")
    return None


def read_heatpump_model(value: str) -> str:
    return HEATPUMP_MODELS.get(value, "Unknown model for HeishaMon")


MQTT_SWITCHES: tuple[HeishaMonSwitchEntityDescription, ...] = (
    HeishaMonSwitchEntityDescription(
        key="panasonic_heat_pump/main/Holiday_Mode_State",
        command_topic="panasonic_heat_pump/main/Holiday_Mode_State",
        name="Aquarea Holiday Mode",
        state=bit_to_bool,  # FIXME: support this
    ),
    HeishaMonSwitchEntityDescription(
        key="panasonic_heat_pump/main/Heatpump_State",
        command_topic="panasonic_heat_pump/commands/SetHeatpump",
        name="Aquarea Main Power",
        state=bit_to_bool,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    HeishaMonSwitchEntityDescription(
        key="panasonic_heat_pump/main/Force_DHW_State",
        command_topic="panasonic_heat_pump/commands/SetForceDHW",
        name="Aquarea Force DHW Mode",
        state=bit_to_bool,
    ),
)

BINARY_SENSORS: tuple[HeishaMonBinarySensorEntityDescription, ...] = (
    HeishaMonBinarySensorEntityDescription(
        key="panasonic_heat_pump/main/Quiet_Mode_Level",
        name="Aquarea Quiet Mode",
        state=read_quiet_mode,
        # state_class=SensorStateClass.MEASUREMENT,
        # icon= "mdi:on"
        # entity_registry_enabled_default=True,
        # native_unit_of_measurement="L/min",
    ),
    HeishaMonBinarySensorEntityDescription(
        key="panasonic_heat_pump/main/Defrosting_State",
        name="Aquarea Defrost State",
        state=bit_to_bool,
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    HeishaMonBinarySensorEntityDescription(
        key="panasonic_heat_pump/main/DHW_Heater_State",
        name="Aquarea Tank Heater Enabled",
        state=bit_to_bool,
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    HeishaMonBinarySensorEntityDescription(
        key="panasonic_heat_pump/main/Room_Heater_State",
        name="Aquarea Room Heater Enabled",
        state=bit_to_bool,
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    HeishaMonBinarySensorEntityDescription(
        key="panasonic_heat_pump/main/Internal_Heater_State",
        name="Aquarea Internal Heater State",
        state=bit_to_bool,
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    HeishaMonBinarySensorEntityDescription(
        key="panasonic_heat_pump/main/External_Heater_State",
        name="Aquarea External Heater State",
        state=bit_to_bool,
        device_class=BinarySensorDeviceClass.HEAT,
    ),
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


def read_stats_json(field_name: str, json_doc: str) -> Optional[float]:
    field_value = json.loads(json_doc).get(field_name, None)
    if field_value:
        return float(field_value)
    return None


def ms_to_secs(value: Optional[float]) -> Optional[float]:
    if value:
        return value / 1000
    return None


SENSORS: tuple[HeishaMonSensorEntityDescription, ...] = (
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Pump_Flow",
        name="Aquarea Pump Flow",
        native_unit_of_measurement="L/min",
        # state_class=SensorStateClass.MEASUREMENT,
        # device_class=SensorDeviceClass.ENERGY,
        # icon= "mdi:on"
        # entity_registry_enabled_default=True,
        # native_unit_of_measurement="L/min",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Operating_Mode_State",
        name="Aquarea Mode",
        # state_class=SensorStateClass.MEASUREMENT,
        # device_class=SensorDeviceClass.ENERGY,
        # icon= "mdi:on"
        # entity_registry_enabled_default=True,
        # native_unit_of_measurement="L/min",
        state=read_operating_mode_state,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Main_Inlet_Temp",
        name="Aquarea Inlet Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Main_Outlet_Temp",
        name="Aquarea Outlet Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Main_Target_Temp",
        name="Aquarea Outlet Target Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Compressor_Freq",
        name="Aquarea Compressor Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement="Hz",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/DHW_Target_Temp",
        name="Aquarea Tank Set Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/DHW_Temp",
        name="Aquarea Tank Actual Tank Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Operations_Hours",
        name="Aquarea Compressor Operating Hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="Hours",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Operations_Counter",
        name="Aquarea Compressor Start/Stop Counter",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Outside_Temp",
        name="Aquarea Outdoor Ambient",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Heat_Energy_Production",
        name="Aquarea Power Produced",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
        # original template states "force_update" FIXME
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Heat_Energy_Consumption",
        name="Aquarea Power Consumed",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
        # original template states "force_update" FIXME
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Powerful_Mode_Time",
        name="Aquarea Powerful Mode",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="Min",
        state=read_power_mode_time,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/ThreeWay_Valve_State",
        name="Aquarea 3-way Valve",
        state=read_threeway_valve,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Outside_Pipe_Temp",
        name="Aquarea Outdoor Pipe Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Z1_Heat_Request_Temp",
        name="Aquarea Heatshift Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/DHW_Energy_Production",
        name="Aquarea DHW Power Produced",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
        # original template states "force_update" FIXME
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/DHW_Energy_Consumption",
        name="Aquarea DHW Power Consumed",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
        # original template states "force_update" FIXME
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Error",
        name="Aquarea Last Error",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Main_Hex_Outlet_Temp",
        name="Aquarea Main HEX Outlet Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Discharge_Temp",
        name="Aquarea Discharge Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Inside_Pipe_Temp",
        name="Aquarea Inside Pipe Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Defrost_Temp",
        name="Aquarea Defrost Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Eva_Outlet_Temp",
        name="Aquarea Eva Outlet Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Bypass_Outlet_Temp",
        name="Aquarea Bypass Outlet Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Ipm_Temp",
        name="Aquarea Ipm Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Fan1_Motor_Speed",
        name="Aquarea Fan 1 Speed",
        native_unit_of_measurement="R/min",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Fan2_Motor_Speed",
        name="Aquarea Fan 2 Speed",
        native_unit_of_measurement="R/min",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/High_Pressure",
        name="Aquarea High pressure",
        native_unit_of_measurement="Kgf/cm2",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Pump_Speed",
        name="Aquarea Pump Speed",
        native_unit_of_measurement="R/min",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Low_Pressure",
        name="Aquarea Low Pressure",
        native_unit_of_measurement="Kgf/cm2",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Compressor_Current",
        name="Aquarea Compressor Current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement="A",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Heat_Pump_Model",
        name="Aquarea Heatpump model",
        state=read_heatpump_model,
        on_receive=update_device_model,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/stats",
        name="HeishaMon RSSI",
        state=partial(read_stats_json, "wifi"),
        device=DeviceType.HEISHAMON,
        native_unit_of_measurement="%",
        unique_id_suffix="_rssi",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/stats",
        name="HeishaMon Uptime",
        state=lambda json_doc: ms_to_secs(read_stats_json("uptime", json_doc)),
        device=DeviceType.HEISHAMON,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="s",
        unique_id_suffix="_uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/stats",
        name="HeishaMon Total reads",
        state=partial(read_stats_json, "total reads"),
        device=DeviceType.HEISHAMON,
        unique_id_suffix="_total_reads",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/stats",
        name="HeishaMon Good reads",
        state=partial(read_stats_json, "good reads"),
        device=DeviceType.HEISHAMON,
        unique_id_suffix="_good_reads",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/stats",
        name="HeishaMon bad CRC reads",
        state=partial(read_stats_json, "bad crc reads"),
        device=DeviceType.HEISHAMON,
        unique_id_suffix="_badcrc_reads",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/stats",
        name="HeishaMon bad header reads",
        state=partial(read_stats_json, "bad header reads"),
        device=DeviceType.HEISHAMON,
        unique_id_suffix="_badheader_reads",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/stats",
        name="HeishaMon too short reads",
        state=partial(read_stats_json, "too short reads"),
        device=DeviceType.HEISHAMON,
        unique_id_suffix="_tooshort_reads",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/stats",
        name="HeishaMon too long reads",
        state=partial(read_stats_json, "too long reads"),
        device=DeviceType.HEISHAMON,
        unique_id_suffix="_toolong_reads",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/stats",
        name="HeishaMon timeout reads",
        state=partial(read_stats_json, "timeout reads"),
        device=DeviceType.HEISHAMON,
        unique_id_suffix="_timeout_reads",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/stats",
        name="HeishaMon voltage",
        state=partial(read_stats_json, "voltage"),
        device=DeviceType.HEISHAMON,
        unique_id_suffix="_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/stats",
        name="HeishaMon free memory",
        state=partial(read_stats_json, "free memory"),
        device=DeviceType.HEISHAMON,
        unique_id_suffix="_freememory",
        native_unit_of_measurement="%",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/stats",
        name="HeishaMon free heap",
        state=partial(read_stats_json, "free heap"),
        unique_id_suffix="_freeheap",
        device=DeviceType.HEISHAMON,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/stats",
        name="HeishaMon mqtt reconnects",
        state=partial(read_stats_json, "mqtt reconnects"),
        device=DeviceType.HEISHAMON,
        unique_id_suffix="_mqttreconnects",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)
