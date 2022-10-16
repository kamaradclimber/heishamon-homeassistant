"""Definitions for HeishaMon sensors added to MQTT."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_KILO_WATT,
    VOLUME_CUBIC_METERS,
)
from homeassistant.util import dt as dt_util

def read_operating_mode_state(value):
    values = {
      "0": "Heat",
      "1": "Cool",
      "2": "Auto",
      "3": "DHW",
      "4": "Heat+DWH",
      "5": "Cool+DHW",
      "6": "Auto+DHW"
    }
    values.get(value, "Unknown operating mode")


@dataclass
class HeishaMonSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description for HeishaMon."""

    # a method called when receiving a new value
    state: Callable | None = None


SENSORS: tuple[HeishaMonSensorEntityDescription, ...] = (
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Heatpump_State",
        name="Aquarea Power State",
        # state_class=SensorStateClass.MEASUREMENT,
        # device_class=SensorDeviceClass.ENERGY,
        # icon= "mdi:on"
        # entity_registry_enabled_default=True,
        # native_unit_of_measurement="L/min",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Pump_Flow",
        name="Aquarea Pump Flow",
        native_unit_of_measurement="L/min",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Force_DHW_State",
        name="Aquarea Force DHW Mode",
    ),
    HeishaMonSensorEntityDescription(
        key="panasonic_heat_pump/main/Operating_Mode_State",
        name="Aquarea Mode",
        # state_class=SensorStateClass.MEASUREMENT,
        # device_class=SensorDeviceClass.ENERGY,
        # icon= "mdi:on"
        # entity_registry_enabled_default=True,
        # native_unit_of_measurement="L/min",
        state=read_operating_mode_state
    ),
)
