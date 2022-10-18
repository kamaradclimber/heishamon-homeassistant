"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations
from string import Template
import logging

from homeassistant.helpers.typing import UNDEFINED
from homeassistant.components import mqtt
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.components.template.sensor import SensorTemplate
from homeassistant.helpers import template as template_helper
from homeassistant.const import (
    CONF_NAME,
    CONF_STATE,
    CONF_DEVICE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers.template_entity import CONF_AVAILABILITY
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from .const import DOMAIN, DeviceType
from .definitions import SENSORS, HeishaMonSensorEntityDescription
from . import build_device_info

_LOGGER = logging.getLogger(__name__)

# async_setup_platform should be defined if one wants to support config via configuration.yaml


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HeishaMon sensors from config entry."""
    real_sensors = [
        HeishaMonSensor(hass, description, config_entry) for description in SENSORS
    ]
    all_sensors = real_sensors + build_virtual_sensors(hass, config_entry, real_sensors)
    async_add_entities(all_sensors)


def build_virtual_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    sensors: list[HeishaMonSensor],
) -> list[SensorEntity]:

    # small helper function
    # goal is to be independant from entity_id renaming from the user
    # it will take a restart of HA to work correctly but at least it will work
    def find_sensor(state_topic):
        return next(
            sensor for sensor in sensors if sensor.entity_description.key == state_topic
        )

    dhw_power_produced = find_sensor(
        "panasonic_heat_pump/main/DHW_Energy_Production"
    ).entity_id
    power_produced = find_sensor(
        "panasonic_heat_pump/main/Heat_Energy_Production"
    ).entity_id

    production_config = {
        CONF_DEVICE_CLASS: SensorDeviceClass.POWER,
        CONF_NAME: template_helper.Template("Aquarea Energy Production"),
        CONF_UNIT_OF_MEASUREMENT: "W",
        CONF_STATE: template_helper.Template(
            Template(
                """
{%- if states('$dhw_power_produced') != "0" -%}
  {{ states('$dhw_power_produced') }}
{%- else -%}
  {{ states('$power_produced') }}
{%- endif -%}
    """
            )
            .substitute(
                dhw_power_produced=dhw_power_produced, power_produced=power_produced
            )
            .strip()
        ),
    }
    production = HeishaMonSensorTemplate(
        hass,
        production_config,
        f"{config_entry.entry_id}-heishamon_w_production",
    )
    dhw_power_consumed = find_sensor(
        "panasonic_heat_pump/main/DHW_Energy_Consumption"
    ).entity_id
    power_consumed = find_sensor(
        "panasonic_heat_pump/main/Heat_Energy_Consumption"
    ).entity_id
    consumption_config = {
        CONF_DEVICE_CLASS: SensorDeviceClass.POWER,
        CONF_NAME: template_helper.Template("Aquarea Energy Consumption"),
        CONF_UNIT_OF_MEASUREMENT: "W",
        CONF_STATE: template_helper.Template(
            Template(
                """
{%- if states('$dhw_power_consumed') != "0" -%}
  {{ states('$dhw_power_consumed') }}
{%- else -%}
  {{ states('$power_consumed') }}
{%- endif -%}
    """
            )
            .substitute(
                dhw_power_consumed=dhw_power_consumed, power_consumed=power_consumed
            )
            .strip()
        ),
    }
    consumption = HeishaMonSensorTemplate(
        hass,
        consumption_config,
        f"{config_entry.entry_id}-heishamon_w_consumption",
    )
    cop_config = {
        CONF_NAME: template_helper.Template("Aquarea COP"),
        CONF_UNIT_OF_MEASUREMENT: "x",
        CONF_STATE: template_helper.Template(
            Template(
                """
{%- if states('$consumption') | float(0) > 0 -%}
  {{ '%0.1f' % ((states('$production') | float ) / (states('$consumption') | float )) }}
{%- else -%}
  0.0
{%- endif -%}
    """
            )
            .substitute(
                # FIXME: we should be dynamic instead of hardcoding entity_id and hope user won't change it
                consumption="sensor.aquarea_energy_consumption",
                production="sensor.aquarea_energy_production",
            )
            .strip()
        ),
        CONF_AVAILABILITY: template_helper.Template(
            Template(
                """
        {%- if is_number(states('$consumption')) and is_number(states('$production')) %}
         true
        {%- else %}
         false
        {%- endif %}
                   """
            )
            .substitute(
                # FIXME: we should be dynamic instead of hardcoding entity_id and hope user won't change it
                consumption="sensor.aquarea_energy_consumption",
                production="sensor.aquarea_energy_production",
            )
            .strip()
        ),
    }
    cop = HeishaMonSensorTemplate(
        hass, cop_config, f"{config_entry.entry_id}-heishamon_cop"
    )
    return [production, consumption, cop]


class HeishaMonSensorTemplate(SensorTemplate):
    @property
    def device_info(self):
        return build_device_info(DeviceType.HEATPUMP)


class HeishaMonSensor(SensorEntity):
    """Representation of a HeishaMon sensor that is updated via MQTT."""

    entity_description: HeishaMonSensorEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        description: HeishaMonSensorEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self.entity_description = description
        self.config_entry_entry_id = config_entry.entry_id

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"sensor.{slug}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}-{slug}{description.unique_id_suffix or ''}"
        )
        if description.entity_category is not None:
            self._attr_entity_category = description.entity_category

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events"""
        await super().async_added_to_hass()

        @callback
        def message_received(message):
            """Handle new MQTT messages."""
            if self.entity_description.state is not None:
                self._attr_native_value = self.entity_description.state(message.payload)
            else:
                self._attr_native_value = message.payload

            if self.entity_description.on_receive is not None:
                self.entity_description.on_receive(
                    self.hass, self, self.config_entry_entry_id, self._attr_native_value
                )

            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass, self.entity_description.key, message_received, 1
        )

    @property
    def device_info(self):
        return build_device_info(self.entity_description.device)
