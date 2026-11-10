"""Select entity descriptions for HeishaMon."""

from __future__ import annotations

from homeassistant.helpers.entity import EntityCategory

from .descriptions import HeishaMonSelectEntityDescription
from .values import (
    BIVALENT_MODES,
    DHW_SENSOR_SELECTION,
    EXTERNAL_PAD_HEATER_TYPE,
    HEATER_STATE,
    HEATING_CONTROL,
    POWERFUL_MODE_TIMES,
    PUMP_FLOWRATE_MODE,
    QUIET_MODE_PRIORITY,
    SMART_DHW,
    SMART_GRID_MODES_STRING,
    ZONE_STATES_STRING,
    OperatingMode,
    bivalent_mode_to_mqtt,
    dhw_sensor_selection_to_mqtt,
    external_pad_heater_type_to_mqtt,
    heater_state_to_mqtt,
    heating_control_to_mqtt,
    operating_mode_to_state,
    pump_flowrate_mode_to_mqtt,
    quiet_mode_priority_to_mqtt,
    read_bivalent_mode,
    read_dhw_sensor_selection,
    read_external_pad_heater_enabled,
    read_heater_state,
    read_heating_control,
    read_operating_mode_state,
    read_power_mode_time,
    read_pump_flowrate_mode,
    read_quiet_mode,
    read_quiet_mode_priority,
    read_smart_dhw,
    read_smart_grid_mode,
    read_zones_state,
    set_power_mode_time,
    smart_dhw_to_mqtt,
    write_quiet_mode,
    write_smart_grid_mode,
    zone_state_to_mqtt,
)


def build_selects(mqtt_prefix: str) -> list[HeishaMonSelectEntityDescription]:
    return [
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET3",  # also corresponds to TOP18
            key=f"{mqtt_prefix}main/Quiet_Mode_Level",
            command_topic=f"{mqtt_prefix}commands/SetQuietMode",
            name="Aquarea Quiet Mode",
            entity_category=EntityCategory.CONFIG,
            state=read_quiet_mode,
            state_to_mqtt=write_quiet_mode,
            options=["Off", "1", "2", "3", "Scheduled"],
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET4",  # also corresponds to TOP17
            key=f"{mqtt_prefix}main/Powerful_Mode_Time",
            command_topic=f"{mqtt_prefix}commands/SetPowerfulMode",
            name="Aquarea Powerful Mode",
            state=read_power_mode_time,
            state_to_mqtt=set_power_mode_time,
            options=list(POWERFUL_MODE_TIMES.values()),
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET9",  # also corresponds to TOP4
            key=f"{mqtt_prefix}main/Operating_Mode_State",
            command_topic=f"{mqtt_prefix}commands/SetOperationMode",
            name="Aquarea Mode",
            state=read_operating_mode_state,
            state_to_mqtt=operating_mode_to_state,
            options=list(OperatingMode.modes_to_str().values()),
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET17",  # also TOP94
            key=f"{mqtt_prefix}main/Zones_State",
            command_topic=f"{mqtt_prefix}commands/SetZones",
            name="Active zones",
            state=read_zones_state,
            state_to_mqtt=zone_state_to_mqtt,
            options=list(ZONE_STATES_STRING.values()),
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET26",  # also TOP114
            key=f"{mqtt_prefix}main/External_Pad_Heater",
            command_topic=f"{mqtt_prefix}commands/SetExternalPadHeater",
            name="Aquarea External Pad Heater type",
            state=read_external_pad_heater_enabled,
            state_to_mqtt=external_pad_heater_type_to_mqtt,
            options=list(EXTERNAL_PAD_HEATER_TYPE.values()),
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET35",  # also TOP130
            key=f"{mqtt_prefix}main/Bivalent_Mode",
            command_topic=f"{mqtt_prefix}commands/SetBivalentMode",
            name="Aquarea Bivalent Mode",
            state=read_bivalent_mode,
            state_to_mqtt=bivalent_mode_to_mqtt,
            options=list(BIVALENT_MODES.values()),
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET39",  # corresponds to TOP139
            key=f"{mqtt_prefix}main/Heating_Control",
            command_topic=f"{mqtt_prefix}commands/SetHeatingControl",
            name="Aquarea Heating Control",
            entity_category=EntityCategory.CONFIG,
            state=read_heating_control,
            state_to_mqtt=heating_control_to_mqtt,
            options=list(HEATING_CONTROL.values()),
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET40",  # corresponds to TOP140
            key=f"{mqtt_prefix}main/Smart_DHW",
            command_topic=f"{mqtt_prefix}commands/SetSmartDHW",
            name="Aquarea Smart DHW",
            entity_category=EntityCategory.CONFIG,
            state=read_smart_dhw,
            state_to_mqtt=smart_dhw_to_mqtt,
            options=list(SMART_DHW.values()),
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET41",  # corresponds to TOP141
            key=f"{mqtt_prefix}main/Quiet_Mode_Priority",
            command_topic=f"{mqtt_prefix}commands/SetQuietModePriority",
            name="Aquarea Quiet Mode Priority",
            entity_category=EntityCategory.CONFIG,
            state=read_quiet_mode_priority,
            state_to_mqtt=quiet_mode_priority_to_mqtt,
            options=list(QUIET_MODE_PRIORITY.values()),
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET42",  # corresponds to TOP106
            key=f"{mqtt_prefix}main/Pump_Flowrate_Mode",
            command_topic=f"{mqtt_prefix}commands/SetPumpFlowrateMode",
            name="Aquarea Pump Flowrate Mode",
            entity_category=EntityCategory.CONFIG,
            state=read_pump_flowrate_mode,
            state_to_mqtt=pump_flowrate_mode_to_mqtt,
            options=list(PUMP_FLOWRATE_MODE.values()),
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SetSmartGridMode",
            key=f"{mqtt_prefix}commands/SetSmartGridMode",
            command_topic=f"{mqtt_prefix}commands/SetSmartGridMode",
            retain=True,
            name="Smart Grid Mode",
            entity_category=EntityCategory.CONFIG,
            state=read_smart_grid_mode,
            state_to_mqtt=write_smart_grid_mode,
            options=list(SMART_GRID_MODES_STRING.values()),
            entity_registry_enabled_default=False,  # comes from the optional PCB: disabled by default
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET43",  # corresponds to TOP143
            key=f"{mqtt_prefix}main/DHW_Sensor_Selection",
            command_topic=f"{mqtt_prefix}commands/SetDHWSensorSelection",
            name="Aquarea DHW Sensor Selection",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:thermometer-water",
            state=read_dhw_sensor_selection,
            state_to_mqtt=dhw_sensor_selection_to_mqtt,
            options=list(DHW_SENSOR_SELECTION.values()),
            entity_registry_enabled_default=False,  # only applicable to K/L series All-In-One units
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET44", # corresponds to TOP58
            key=f"{mqtt_prefix}main/DHW_Heater_State",
            command_topic=f"{mqtt_prefix}commands/SetDHWHeaterState",
            name="Aquarea DHW Heater State",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:thermometer-water",
            state=read_heater_state,
            state_to_mqtt=heater_state_to_mqtt,
            options=list(HEATER_STATE.values()),
        ),
        HeishaMonSelectEntityDescription(
            heishamon_topic_id="SET45", # corresponds to TOP59
            key=f"{mqtt_prefix}main/Room_Heater_State",
            command_topic=f"{mqtt_prefix}commands/SetRoomHeaterState",
            name="Aquarea Room Heater State",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:thermometer-water",
            state=read_heater_state,
            state_to_mqtt=heater_state_to_mqtt,
            options=list(HEATER_STATE.values()),
        ),
    ]
