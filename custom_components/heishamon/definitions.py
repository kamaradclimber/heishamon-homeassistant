"""Definitions for HeishaMon sensors added to MQTT."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
)
from homeassistant.const import (
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_KILO_WATT,
    VOLUME_CUBIC_METERS,
)


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


@dataclass
class HeishaMonSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description for HeishaMon."""

    # a method called when receiving a new value
    state: Callable | None = None


def bit_to_bool(value: str) -> Optional[bool]:
    if value == "1":
        return True
    elif value == "0":
        return False
    else:
        return None


BINARY_SENSORS: tuple[HeishaMonSensorEntityDescription, ...] = (
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Heatpump_State",
        name="Aquarea Power State",
        state=bit_to_bool,
        device_class=BinarySensorDeviceClass.RUNNING,
        # state_class=SensorStateClass.MEASUREMENT,
        # icon= "mdi:on"
        # entity_registry_enabled_default=True,
        # native_unit_of_measurement="L/min",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Force_DHW_State",
        name="Aquarea Force DHW Mode",
        state=bit_to_bool,
    ),
)

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
        native_unit_of_measurement="C°",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Main_Outlet_Temp",
        name="Aquarea Outlet Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="C°",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Main_Target_Temp",
        name="Aquarea Outlet Target Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="C°",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Compressor_Freq",
        name="Aquarea Compressor Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement="Hz",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/DHW_Target_Temp",
        name="Aquarea Tank Set Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="C°",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/DHW_Temp",
        name="Aquarea Tank Actual Tank Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="C°",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Operations_Hours",
        name="Aquarea Compressor Operating Hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="Hours",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Operations_Counter",
        name="Aquarea Compressor Start/Stop Counter",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Outside_Temp",
        name="Aquarea Outdoor Ambient",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="C°",
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
)
