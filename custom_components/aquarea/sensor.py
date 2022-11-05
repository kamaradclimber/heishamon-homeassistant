"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations
from string import Template
import logging

from homeassistant.components import mqtt
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.components.template.sensor import SensorTemplate
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers import template as template_helper
from homeassistant.const import (
    CONF_NAME,
    CONF_STATE,
    CONF_DEVICE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers.template_entity import CONF_AVAILABILITY
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DeviceType
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
    # this special sensor will listen to 1wire topics and create new sensors accordingly
    dallas_list_config = SensorEntityDescription(
        key="panasonic_heat_pump/1wire/+",
        name="HeishaMon detected 1wire sensors",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    dallas_listing = DallasListSensor(
        hass, dallas_list_config, config_entry, async_add_entities
    )
    s0_list_config = SensorEntityDescription(
        key="panasonic_heat_pump/s0/Watt/+",
        name="HeishaMon detected s0 sensors",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    s0_listing = S0Detector(hass, s0_list_config, config_entry, async_add_entities)
    async_add_entities([dallas_listing, s0_listing])


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
    heat_power_produced = find_sensor(
        "panasonic_heat_pump/main/Heat_Energy_Production"
    ).entity_id
    cool_power_produced = find_sensor(
        "panasonic_heat_pump/main/Cool_Energy_Production"
    ).entity_id
    production_config = {
        CONF_DEVICE_CLASS: SensorDeviceClass.POWER,
        CONF_NAME: template_helper.Template("Aquarea Energy Production"),
        CONF_UNIT_OF_MEASUREMENT: "W",
        CONF_STATE: template_helper.Template(
            Template(
                """
{{ states('$dhw_power_produced') | int(0) + states('$heat_power_produced') | int(0) + states('$cool_power_produced') | int(0) }}
    """
            )
            .substitute(
                dhw_power_produced=dhw_power_produced, heat_power_produced=heat_power_produced, cool_power_produced=cool_power_produced
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
    heat_power_consumed = find_sensor(
        "panasonic_heat_pump/main/Heat_Energy_Consumption"
    ).entity_id
    cool_power_consumed = find_sensor(
        "panasonic_heat_pump/main/Cool_Energy_Consumption"
    ).entity_id
    consumption_config = {
        CONF_DEVICE_CLASS: SensorDeviceClass.POWER,
        CONF_NAME: template_helper.Template("Aquarea Energy Consumption"),
        CONF_UNIT_OF_MEASUREMENT: "W",
        CONF_STATE: template_helper.Template(
            Template(
                """
{{ states('$dhw_power_consumed') | int(0) + states('$heat_power_consumed') | int(0) + states('$cool_power_consumed') | int(0) }}
    """
            )
            .substitute(
                dhw_power_consumed=dhw_power_consumed, heat_power_consumed=heat_power_consumed, cool_power_consumed=cool_power_consumed
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

    #DHW Energy
    #Heat Energy
    #Coll Energy
    #Total Energy

    return [production, consumption, cop]


class HeishaMonSensorTemplate(SensorTemplate):
    @property
    def device_info(self):
        return build_device_info(DeviceType.HEATPUMP)


class S0Detector(SensorEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        description: SensorEntityDescription,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.hass = hass
        self.entity_description = description
        self.config_entry = config_entry
        self.config_entry_entry_id = config_entry.entry_id

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"sensor.{slug}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}-s0-listing"  # ⚠ we can't have two of this
        )
        self.async_add_entities = async_add_entities
        self._known_s0_sensors = []

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events"""
        await super().async_added_to_hass()

        @callback
        def message_received(message):
            base, s0, sensor_type, device_id = message.topic.split("/")
            if device_id not in self._known_s0_sensors:
                description = HeishaMonSensorEntityDescription(
                    heishamon_topic_id=f"s0-{device_id}-watthour",
                    key="/".join([base, s0, "Watthour", device_id]),
                    name=f"HeishaMon s0 {device_id} WattHour",
                    device_class=SensorDeviceClass.ENERGY,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement="Wh",
                    device=DeviceType.HEISHAMON,
                )
                watt_hour_sensor = HeishaMonSensor(
                    self.hass, description, self.config_entry
                )
                description = HeishaMonSensorEntityDescription(
                    heishamon_topic_id=f"s0-{device_id}-totalwatthour",
                    key="/".join([base, s0, "WatthourTotal", device_id]),
                    name=f"HeishaMon s0 {device_id} WattHourTotal",
                    device_class=SensorDeviceClass.ENERGY,
                    native_unit_of_measurement="Wh",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    device=DeviceType.HEISHAMON,
                )
                total_watt_hour_sensor = HeishaMonSensor(
                    self.hass, description, self.config_entry
                )
                description = HeishaMonSensorEntityDescription(
                    heishamon_topic_id=f"s0-{device_id}-watt",
                    key="/".join([base, s0, "Watt", device_id]),
                    name=f"HeishaMon s0 {device_id} Watt",
                    device_class=SensorDeviceClass.POWER,
                    native_unit_of_measurement="W",
                    state_class=SensorStateClass.MEASUREMENT,
                    device=DeviceType.HEISHAMON,
                )
                watt_sensor = HeishaMonSensor(self.hass, description, self.config_entry)
                _LOGGER.info(
                    f"Detected new s0 sensor with id {device_id}, creating new sensors"
                )
                self.async_add_entities(
                    [watt_hour_sensor, total_watt_hour_sensor, watt_sensor]
                )
                self._known_s0_sensors.append(device_id)
                self._known_s0_sensors.sort()
                self._attr_native_value = ", ".join(self._known_s0_sensors)
                self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass, self.entity_description.key, message_received, 1
        )

    @property
    def device_info(self):
        return build_device_info(DeviceType.HEISHAMON)


class DallasListSensor(SensorEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        description: SensorEntityDescription,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.hass = hass
        self.entity_description = description
        self.config_entry = config_entry
        self.config_entry_entry_id = config_entry.entry_id

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"sensor.{slug}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}-dallas-listing"  # ⚠ we can't have two of this
        )
        self.async_add_entities = async_add_entities
        self._known_1wire = []

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events"""
        await super().async_added_to_hass()

        @callback
        def message_received(message):
            device_id = message.topic.split("/")[-1]
            if device_id not in self._known_1wire:
                description = HeishaMonSensorEntityDescription(
                    heishamon_topic_id=f"1wire-{device_id}",
                    key=message.topic,
                    name=f"HeishaMon 1wire {device_id}",
                    native_unit_of_measurement="°C",  # we assume everything will be temperature
                    device_class=SensorDeviceClass.TEMPERATURE,
                    device=DeviceType.HEISHAMON,
                )
                sensor = HeishaMonSensor(self.hass, description, self.config_entry)
                _LOGGER.info(
                    f"Detected new 1wire sensor with id {device_id}, creating a new sensor"
                )
                sensor._attr_native_value = float(
                    message.payload
                )  # set immediately a known state
                self.async_add_entities([sensor])
                self._known_1wire.append(device_id)
                self._known_1wire.sort()
                self._attr_native_value = ", ".join(self._known_1wire)
                self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass, self.entity_description.key, message_received, 1
        )

    @property
    def device_info(self):
        return build_device_info(DeviceType.HEISHAMON)


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
            f"{config_entry.entry_id}-{description.heishamon_topic_id}"
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

            self.async_write_ha_state()
            if self.entity_description.on_receive is not None:
                self.entity_description.on_receive(
                    self.hass, self, self.config_entry_entry_id, self._attr_native_value
                )

        await mqtt.async_subscribe(
            self.hass, self.entity_description.key, message_received, 1
        )

    @property
    def device_info(self):
        return build_device_info(self.entity_description.device)
