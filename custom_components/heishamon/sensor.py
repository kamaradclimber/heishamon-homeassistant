"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations
import logging
from typing import Any, Optional
from dataclasses import dataclass
from collections.abc import Callable
from datetime import timedelta

from homeassistant.components import mqtt
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.components.integration.const import METHOD_LEFT
from homeassistant.components.integration.sensor import IntegrationSensor
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import (
    CONF_NAME,
    CONF_STATE,
    CONF_DEVICE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
    UnitOfTime,
)

_LOGGER = logging.getLogger(__name__)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DeviceType
from .definitions import (
    build_sensors,
    HeishaMonSensorEntityDescription,
    MultiMQTTSensorEntityDescription,
    bit_to_bool,
)
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
    sensors = []
    for description in build_sensors(discovery_prefix):
        match description:
            case MultiMQTTSensorEntityDescription():
                s = MultiMQTTSensorEntity(hass, config_entry, description)
            case _:
                s = HeishaMonSensor(hass, description, config_entry)
        sensors.append(s)

    # this special sensor will listen to 1wire topics and create new sensors accordingly
    dallas_list_config = SensorEntityDescription(
        key=f"{discovery_prefix}1wire/+",
        name="HeishaMon detected 1wire sensors",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    dallas_listing = DallasListSensor(
        hass, dallas_list_config, config_entry, async_add_entities
    )
    sensors.append(dallas_listing)
    s0_list_config = SensorEntityDescription(
        key=f"{discovery_prefix}s0/Watt/+",
        name="HeishaMon detected s0 sensors",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    s0_listing = S0Detector(hass, s0_list_config, config_entry, async_add_entities)
    sensors.append(s0_listing)

    description = MultiMQTTSensorEntityDescription(
        unique_id=f"{config_entry.entry_id}-heishamon_w_production",
        key=f"{discovery_prefix}/production",
        name=f"Aquarea Pump total production",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
        topics=[
            # K & L models, fw >= 3.2.3
            f"{discovery_prefix}extra/DHW_Power_Production_Extra",
            f"{discovery_prefix}extra/Heat_Power_Production_Extra",
            f"{discovery_prefix}extra/Cool_Power_Production_Extra",
            # K & L models, 3.2 <= fw < 3.2.3
            f"{discovery_prefix}extra/DHW_Power_Production",
            f"{discovery_prefix}extra/Heat_Power_Production",
            f"{discovery_prefix}extra/Cool_Power_Production",
            # new topics, for firmware >= 3.2
            f"{discovery_prefix}main/DHW_Power_Production",
            f"{discovery_prefix}main/Heat_Power_Production",
            f"{discovery_prefix}main/Cool_Power_Production",
            # legacy topics, for firmwares < 3.2
            f"{discovery_prefix}main/DHW_Energy_Production",
            f"{discovery_prefix}main/Heat_Energy_Production",
            f"{discovery_prefix}main/Cool_Energy_Production",
        ],
        compute_state=extract_sum,
        suggested_display_precision=0,
    )
    production_sensor = MultiMQTTSensorEntity(hass, config_entry, description)
    sensors.append(production_sensor)

    description = MultiMQTTSensorEntityDescription(
        unique_id=f"{config_entry.entry_id}-heishamon_w_consumption",
        key=f"{discovery_prefix}/consumption",
        name=f"Aquarea Pump total consumption",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
        topics=[
            # K & L models, fw >= 3.2.3
            f"{discovery_prefix}extra/DHW_Power_Consumption_Extra",
            f"{discovery_prefix}extra/Heat_Power_Consumption_Extra",
            f"{discovery_prefix}extra/Cool_Power_Consumption_Extra",
            # K & L models, 3.2.0 <= fw < 3.2.3
            f"{discovery_prefix}extra/DHW_Power_Consumption",
            f"{discovery_prefix}extra/Heat_Power_Consumption",
            f"{discovery_prefix}extra/Cool_Power_Consumption",
            # new topics, for firmwares >= 3.2
            f"{discovery_prefix}main/DHW_Power_Consumption",
            f"{discovery_prefix}main/Heat_Power_Consumption",
            f"{discovery_prefix}main/Cool_Power_Consumption",
            # legacy topics, for firmwares < 3.2
            f"{discovery_prefix}main/DHW_Energy_Consumption",
            f"{discovery_prefix}main/Heat_Energy_Consumption",
            f"{discovery_prefix}main/Cool_Energy_Consumption",
        ],
        compute_state=extract_sum,
        suggested_display_precision=0,
    )
    consumption_sensor = MultiMQTTSensorEntity(hass, config_entry, description)
    sensors.append(consumption_sensor)
    description = MultiMQTTSensorEntityDescription(
        unique_id=f"{config_entry.entry_id}-heishamon_cop",
        key=f"{discovery_prefix}/cop",
        name=f"Aquarea COP",
        native_unit_of_measurement="x",
        state_class=SensorStateClass.MEASUREMENT,
        topics=[
            f"{discovery_prefix}main/Defrosting_State",
            f"{discovery_prefix}main/DHW_Power_Production",
            f"{discovery_prefix}main/Heat_Power_Production",
            f"{discovery_prefix}main/Cool_Power_Production",
            f"{discovery_prefix}main/DHW_Power_Consumption",
            f"{discovery_prefix}main/Heat_Power_Consumption",
            f"{discovery_prefix}main/Cool_Power_Consumption",
            # legacy topics, for firmwares < 3.2
            f"{discovery_prefix}main/DHW_Energy_Production",
            f"{discovery_prefix}main/Heat_Energy_Production",
            f"{discovery_prefix}main/Cool_Energy_Production",
            f"{discovery_prefix}main/DHW_Energy_Consumption",
            f"{discovery_prefix}main/Heat_Energy_Consumption",
            f"{discovery_prefix}main/Cool_Energy_Consumption",
            # K & L models, firmware 3.2.0 <= x < 3.2.3
            f"{discovery_prefix}extra/DHW_Power_Production",
            f"{discovery_prefix}extra/Heat_Power_Production",
            f"{discovery_prefix}extra/Cool_Power_Production",
            f"{discovery_prefix}extra/DHW_Power_Consumption",
            f"{discovery_prefix}extra/Heat_Power_Consumption",
            f"{discovery_prefix}extra/Cool_Power_Consumption",
            # K & L models, firmware >= 3.2.3
            f"{discovery_prefix}extra/DHW_Power_Production_Extra",
            f"{discovery_prefix}extra/Heat_Power_Production_Extra",
            f"{discovery_prefix}extra/Cool_Power_Production_Extra",
            f"{discovery_prefix}extra/DHW_Power_Consumption_Extra",
            f"{discovery_prefix}extra/Heat_Power_Consumption_Extra",
            f"{discovery_prefix}extra/Cool_Power_Consumption_Extra",
        ],
        compute_state=compute_cop,
    )
    cop_sensor = MultiMQTTSensorEntity(hass, config_entry, description)
    sensors.append(cop_sensor)
    async_add_entities(sensors)
    integration_sensors = []
    for sensor in sensors:
        if sensor.entity_description.native_unit_of_measurement == "W":
            integration_sensors.append(EnergyIntegrationEntity(
                integration_method=METHOD_LEFT,
                name=f"{sensor.entity_description.name} Total",
                round_digits=3,
                source_entity=sensor.entity_id,
                unique_id=f"{sensor._attr_unique_id}_integration",
                unit_prefix="k",
                unit_time=UnitOfTime.HOURS,
                # update integral at least once every 5 minutes, even if source does not change
                max_sub_interval=timedelta(minutes=5),
                device_info=sensor.device_info,
            ))
    async_add_entities(integration_sensors)


def compute_cop(values) -> Optional[float]:
    # read defrost and cancel COP if defrost is on
    if bit_to_bool(values[0]):
        _LOGGER.debug("Defrost is in progress, cannot compute COP, it would not make sense")
        return -1
    values = values[1:]
    assert len(values) == 24
    production = extract_sum(values[18:21] + values[12:15] + values[0:3] + values[6:9])
    consumption = extract_sum(
        values[21:24] + values[15:18] + values[3:6] + values[9:12]
    )
    if consumption == 0:
        return 0
    cop = production / consumption
    if (
        cop > 15
    ):  # this value is obviously incorrect. We probably don't have all consumption yet
        return 0
    return round(cop, 2)


def extract_sum(values):
    def chunks3(lst):
        for i in range(0, len(lst), 3):
            yield lst[i : i + 3]

    for i, candidate in enumerate(chunks3(values)):
        if len(list(filter(lambda el: el is not None, candidate))) > 0:
            return sum(filter(lambda el: el is not None, candidate))
    _LOGGER.debug(f"No values at all, here the values: {values}, assuming sum is 0")
    return 0

class EnergyIntegrationEntity(IntegrationSensor):
    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    @property
    def device_class(self):
        return SensorDeviceClass.ENERGY

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
        if description.heishamon_topic_id is not None:
            self._attr_unique_id = (
                f"{config_entry.entry_id}-{description.heishamon_topic_id}"
            )
        else:
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
                    state_class=SensorStateClass.MEASUREMENT,
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
