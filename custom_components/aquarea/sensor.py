"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations
import logging
from typing import Any, Optional
from dataclasses import dataclass
from collections.abc import Callable

from homeassistant.components import mqtt
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import (
    CONF_NAME,
    CONF_STATE,
    CONF_DEVICE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
)

_LOGGER = logging.getLogger(__name__)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DeviceType
from .definitions import build_sensors, HeishaMonSensorEntityDescription
from . import build_device_info


# async_setup_platform should be defined if one wants to support config via configuration.yaml


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HeishaMon sensors from config entry."""
    discovery_prefix = config_entry.data[
        "discovery_prefix"
    ]  # TODO: handle migration of entities
    _LOGGER.debug(f"Starting bootstrap of sensors with prefix '{discovery_prefix}'")
    real_sensors = [
        HeishaMonSensor(hass, description, config_entry)
        for description in build_sensors(discovery_prefix)
    ]
    async_add_entities(real_sensors)

    # this special sensor will listen to 1wire topics and create new sensors accordingly
    dallas_list_config = SensorEntityDescription(
        key=f"{discovery_prefix}1wire/+",
        name="HeishaMon detected 1wire sensors",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    dallas_listing = DallasListSensor(
        hass, dallas_list_config, config_entry, async_add_entities
    )
    s0_list_config = SensorEntityDescription(
        key=f"{discovery_prefix}s0/Watt/+",
        name="HeishaMon detected s0 sensors",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    s0_listing = S0Detector(hass, s0_list_config, config_entry, async_add_entities)
    async_add_entities([dallas_listing, s0_listing])

    description = MultiMQTTSensorEntityDescription(
        unique_id=f"{config_entry.entry_id}-heishamon_w_production",
        key=f"{discovery_prefix}/production",
        name=f"Aquarea Pump total production",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
        topics=[
            f"{discovery_prefix}main/DHW_Power_Production",
            f"{discovery_prefix}main/Heat_Power_Production",
            f"{discovery_prefix}main/Cool_Power_Production",
        ],
        compute_state=sum_all_topics,
        suggested_display_precision=0,
    )
    production_sensor = MultiMQTTSensorEntity(hass, config_entry, description)

    description = MultiMQTTSensorEntityDescription(
        unique_id=f"{config_entry.entry_id}-heishamon_w_consumption",
        key=f"{discovery_prefix}/consumption",
        name=f"Aquarea Pump total consumption",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
        topics=[
            f"{discovery_prefix}main/DHW_Power_Consumption",
            f"{discovery_prefix}main/Heat_Power_Consumption",
            f"{discovery_prefix}main/Cool_Power_Consumption",
        ],
        compute_state=sum_all_topics,
        suggested_display_precision=0,
    )
    consumption_sensor = MultiMQTTSensorEntity(hass, config_entry, description)
    description = MultiMQTTSensorEntityDescription(
        unique_id=f"{config_entry.entry_id}-heishamon_cop",
        key=f"{discovery_prefix}/cop",
        name=f"Aquarea COP",
        native_unit_of_measurement="x",
        state_class=SensorStateClass.MEASUREMENT,
        topics=[
            f"{discovery_prefix}main/DHW_Power_Production",
            f"{discovery_prefix}main/Heat_Power_Production",
            f"{discovery_prefix}main/Cool_Power_Production",
            f"{discovery_prefix}main/DHW_Power_Consumption",
            f"{discovery_prefix}main/Heat_Power_Consumption",
            f"{discovery_prefix}main/Cool_Power_Consumption",
        ],
        compute_state=compute_cop,
    )
    cop_sensor = MultiMQTTSensorEntity(hass, config_entry, description)
    async_add_entities([production_sensor, consumption_sensor, cop_sensor])


def compute_cop(values) -> Optional[float]:
    assert len(values) == 6
    production = sum([el for el in values[0:3] if el is not None])
    consumption = sum([el for el in values[3:6] if el is not None])
    if consumption == 0:
        return 0
    cop = production / consumption
    if (
        cop > 10
    ):  # this value is obviously incorrect. We probably don't have all consumption yet
        return 0
    return round(cop, 2)


def sum_all_topics(values):
    return sum(filter(lambda el: el is not None, values))


@dataclass
class MultiMQTTSensorEntityDescription(SensorEntityDescription):
    topics: list[str] | None = None
    # this callable will receive a list with as many entries as topics
    # values in that list will be in the same order as the topics key.
    # For instance, if topics are ["a", "b", "c"], state will receive a list with
    # 3 items, whose values will be the last received value from the topics a, b and c.
    # values will be None when we have not received any value for the corresponding topic yet.
    compute_state: Callable | None = None
    unique_id: Optional[str] = None


class MultiMQTTSensorEntity(SensorEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        description: MultiMQTTSensorEntityDescription,
    ) -> None:
        self.hass = hass
        self.entity_description = description
        self.config_entry = config_entry
        self.config_entry_entry_id = config_entry.entry_id
        self.discovery_prefix = config_entry.data["discovery_prefix"]
        self.compute_state = description.compute_state

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"sensor.{slug}"
        self._attr_unique_id = description.unique_id
        if (
            self.entity_description.topics is None
            or len(self.entity_description.topics) == 0
        ):
            raise ValueError("topics should be defined")
        self._received_values: list[Optional[float]] = [None] * len(
            self.entity_description.topics
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events"""
        await super().async_added_to_hass()

        @callback
        def message_received(message):
            assert self.entity_description.topics is not None
            if message.topic not in self.entity_description.topics:
                _LOGGER.warn(
                    f"Received a message for topic {message.topic} which is not in the list of expected topics"
                )
            index = self.entity_description.topics.index(message.topic)
            self._received_values[index] = float(message.payload)
            assert self.compute_state is not None
            self._attr_native_value = self.compute_state(self._received_values)
            self.async_write_ha_state()

        for topic in self.entity_description.topics or []:
            await mqtt.async_subscribe(self.hass, topic, message_received, 1)

    @property
    def device_info(self):
        return build_device_info(DeviceType.HEATPUMP, self.discovery_prefix)


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
        self.discovery_prefix = config_entry.data[
            "discovery_prefix"
        ]  # TODO: handle migration of entities

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
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    unit_of_measurement="kWh",
                    native_unit_of_measurement="Wh",
                    suggested_display_precision=0,
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
                    unit_of_measurement="kWh",
                    native_unit_of_measurement="Wh",
                    suggested_display_precision=0,
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
        return build_device_info(DeviceType.HEISHAMON, self.discovery_prefix)


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
        self.discovery_prefix = config_entry.data[
            "discovery_prefix"
        ]  # TODO: handle migration of entities

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
        return build_device_info(DeviceType.HEISHAMON, self.discovery_prefix)


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
        self.discovery_prefix = config_entry.data[
            "discovery_prefix"
        ]  # TODO: handle migration of entities

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
        return build_device_info(self.entity_description.device, self.discovery_prefix)
