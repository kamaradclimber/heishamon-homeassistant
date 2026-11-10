"""Binary sensor entity descriptions for HeishaMon."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from ..const import DeviceType
from .descriptions import HeishaMonBinarySensorEntityDescription
from .values import bit_to_bool, online_to_bool, positive_to_bool, read_enabled_disabled


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
        # deprecated since we have a switch now
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP58",
            key=f"{mqtt_prefix}main/DHW_Heater_State",
            name="Aquarea Tank Heater Enabled",
            state=bit_to_bool,
        ),
        # deprecated since we have a switch now
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
            device_class=BinarySensorDeviceClass.RUNNING,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP61",
            key=f"{mqtt_prefix}main/External_Heater_State",
            name="Aquarea External Heater State",
            state=bit_to_bool,
            device_class=BinarySensorDeviceClass.RUNNING,
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
            heishamon_topic_id="TOP109",
            key=f"{mqtt_prefix}main/Anti_Freeze_Mode",
            name="Aquarea anti freeze mode",
            state=bit_to_bool,
            device_class=BinarySensorDeviceClass.RUNNING,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP110",
            key=f"{mqtt_prefix}main/Optional_PCB",
            name="Aquarea optional PCB enabled",
            state=bit_to_bool,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP132",
            key=f"{mqtt_prefix}main/Bivalent_Advanced_Heat",
            name="Aquarea Bivalent Advanced Heat",
            state=read_enabled_disabled,
            entity_registry_enabled_default=True,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP133",
            key=f"{mqtt_prefix}main/Bivalent_Advanced_DHW",
            name="Aquarea Bivalent Advanced DHW",
            state=read_enabled_disabled,
            entity_registry_enabled_default=True,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP123",
            key=f"{mqtt_prefix}main/Z1_Pump_State",
            name="Aquarea Zone 1 Pump State",
            state=bit_to_bool,
            device_class=BinarySensorDeviceClass.RUNNING,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="TOP124",
            key=f"{mqtt_prefix}main/Z2_Pump_State",
            name="Aquarea Zone 2 Pump State",
            state=bit_to_bool,
            device_class=BinarySensorDeviceClass.RUNNING,
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="OPT0",
            key=f"{mqtt_prefix}optional/Z1_Water_Pump",
            name="Aquarea Zone 1 water pump action request",
            state=bit_to_bool,
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="OPT2",
            key=f"{mqtt_prefix}optional/Z2_Water_Pump",
            name="Aquarea Zone 2 water pump action request",
            state=bit_to_bool,
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="OPT4",
            key=f"{mqtt_prefix}optional/Pool_Water_Pump",
            name="Aquarea pool water pump action request",
            state=bit_to_bool,
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="OPT5",
            key=f"{mqtt_prefix}optional/Solar_Water_Pump",
            name="Aquarea solar water pump action request",
            state=bit_to_bool,
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonBinarySensorEntityDescription(
            heishamon_topic_id="OPT6",
            key=f"{mqtt_prefix}optional/Alarm_State",
            name="Aquarea Alarm State",
            state=bit_to_bool,
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
    ]
