"""Switch entity descriptions for HeishaMon."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from ..const import DeviceType
from .descriptions import HeishaMonSwitchEntityDescription
from .values import bit_to_bool, read_holiday_status_to_bool, relay_to_bool


def build_switches(mqtt_prefix: str) -> list[HeishaMonSwitchEntityDescription]:
    return [
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SET1",  # also corresponds to TOP0
            key=f"{mqtt_prefix}main/Heatpump_State",
            command_topic=f"{mqtt_prefix}commands/SetHeatpump",
            name="Aquarea Main Power",
            state=bit_to_bool,
            binary_sensor_device_class=BinarySensorDeviceClass.RUNNING,
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
            state=bit_to_bool,
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SET13",  # corresponds to TOP69
            key=f"{mqtt_prefix}main/Sterilization_State",
            command_topic=f"{mqtt_prefix}commands/SetForceSterilization",
            name="Aquarea Force Sterilization",
            entity_category=EntityCategory.CONFIG,
            binary_sensor_device_class=BinarySensorDeviceClass.RUNNING,
            state=bit_to_bool,
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SET47",  # corresponds to TOP68
            key=f"{mqtt_prefix}main/Force_Heater_State",
            command_topic=f"{mqtt_prefix}commands/SetForceHeater",
            name="Aquarea Force Heater",
            entity_category=EntityCategory.CONFIG,
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
            heishamon_topic_id="SET25",  # corresponds to TOP108
            key=f"{mqtt_prefix}main/Alt_External_Sensor",
            command_topic=f"{mqtt_prefix}commands/SetAltExternalSensor",
            name="Aquarea use external outdoor sensor",
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
            heishamon_topic_id="SET30",  # corresponds to TOP119
            key=f"{mqtt_prefix}main/External_Control",
            command_topic=f"{mqtt_prefix}commands/SetExternalControl",
            name="Aquarea External Control Enabled",
            entity_category=EntityCategory.CONFIG,
            state=bit_to_bool,
            entity_registry_enabled_default=False,
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SET31",  # corresponds to TOP121
            key=f"{mqtt_prefix}main/External_Error_Signal",
            command_topic=f"{mqtt_prefix}commands/SetExternalError",
            name="Aquarea External Error Signal",
            entity_category=EntityCategory.CONFIG,
            state=bit_to_bool,
            entity_registry_enabled_default=False,
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SET32",  # corresponds to TOP122
            key=f"{mqtt_prefix}main/External_Compressor_Control",
            command_topic=f"{mqtt_prefix}commands/SetExternalCompressorControl",
            name="Aquarea External Compressor control",
            entity_category=EntityCategory.CONFIG,
            state=bit_to_bool,
            entity_registry_enabled_default=False,
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SetCompressorState",  # depends on SET32 TOP122
            key=f"{mqtt_prefix}commands/SetCompressorState",
            command_topic=f"{mqtt_prefix}commands/SetCompressorState",
            name="Aquarea Set Compressor state",
            retain=True,  # should be retained since the value is not provided by heat pump data
            entity_category=EntityCategory.CONFIG,
            state=bit_to_bool,
            entity_registry_enabled_default=False,  # hide by default since actual action depends on state of SET32=External_Compressor_Control (only if "ON", this switch has any effect) and on state of Pin3 of SW2 on Main PCB (Pin3=1 Switch Backup Heater OFF; Pin3=0 Switch Compressor OFF)
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SET33",  # corresponds to TOP120
            key=f"{mqtt_prefix}main/External_Heat_Cool_Control",
            command_topic=f"{mqtt_prefix}commands/SetExternalHeatCoolControl",
            name="Aquarea External Heat Cool control",
            entity_category=EntityCategory.CONFIG,
            state=bit_to_bool,
            entity_registry_enabled_default=False,
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="SET34",  # corresponds to TOP129
            key=f"{mqtt_prefix}main/Bivalent_Control",
            command_topic=f"{mqtt_prefix}commands/SetBivalentControl",
            name="Aquarea Bivalent Control",
            state=bit_to_bool,
            entity_registry_enabled_default=True,
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="RELAY01",
            key=f"{mqtt_prefix}gpio/relay/one",
            command_topic=f"{mqtt_prefix}gpio/relay/one",
            name="Relay 1",
            entity_category=EntityCategory.CONFIG,
            device=DeviceType.HEISHAMON,
            state=relay_to_bool,
            retain=True,
            payload_on="on",
            payload_off="off",
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonSwitchEntityDescription(
            heishamon_topic_id="RELAY02",
            key=f"{mqtt_prefix}gpio/relay/two",
            command_topic=f"{mqtt_prefix}gpio/relay/two",
            name="Relay 2",
            entity_category=EntityCategory.CONFIG,
            device=DeviceType.HEISHAMON,
            state=relay_to_bool,
            retain=True,
            payload_on="on",
            payload_off="off",
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
    ]
