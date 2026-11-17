"""Tests for readbacks TOP144-TOP169 and commands SET49-SET55."""

from homeassistant.helpers.entity import EntityCategory

from custom_components.aquarea.definitions.binary_sensors import build_binary_sensors
from custom_components.aquarea.definitions.descriptions import (
    HeishaMonBinarySensorEntityDescription,
    HeishaMonNumberEntityDescription,
    HeishaMonSensorEntityDescription,
    HeishaMonSwitchEntityDescription,
)
from custom_components.aquarea.definitions.numbers import build_numbers
from custom_components.aquarea.definitions.sensors import build_sensors
from custom_components.aquarea.definitions.switches import build_switches
from custom_components.aquarea.definitions.values import (
    DHW_CAPACITY_MODES,
    DHW_HEATER_TYPES,
    HEAT_COOL_SWITCH_STATES,
    ZONE_CONFIGURATIONS,
    read_dhw_capacity_mode,
    read_dhw_heater_type,
    read_heat_cool_switch_state,
    read_heater_capacity,
    read_zone_configuration,
)

MQTT_PREFIX = "panasonic_heat_pump/"
READBACK_TOPIC_IDS = [f"TOP{number}" for number in range(144, 170)]

EXPECTED_READBACK_KEYS = {
    "TOP144": "main/Dry_Concrete_State",
    "TOP145": "main/DHW_Capacity_Mode",
    "TOP146": "main/Zone_Configuration",
    "TOP147": "main/Internal_Heater_Capacity",
    "TOP148": "main/DHW_Heater_Type",
    "TOP149": "main/SG_Ready_Control",
    "TOP150": "main/Demand_Control",
    "TOP151": "main/DHW_Defrost",
    "TOP152": "main/Dry_Concrete_Target_Temp",
    "TOP153": "main/Pool_Delta",
    "TOP154": "main/SG_Ready_1_Heat_Capacity",
    "TOP155": "main/SG_Ready_1_DHW_Capacity",
    "TOP156": "main/SG_Ready_2_Heat_Capacity",
    "TOP157": "main/SG_Ready_2_DHW_Capacity",
    "TOP158": "main/Room_Operation_Max_Time",
    "TOP159": "main/DHW_Heatup_Max_Time",
    "TOP160": "main/Quiet_Mode_Actual_State",
    "TOP161": "main/Powerful_Mode_Actual_State",
    "TOP162": "main/Heat_Cool_Switch_State",
    "TOP163": "main/External_Switch_State",
    "TOP164": "main/Bivalent_Boiler_Contact_State",
    "TOP165": "main/Z2_Active",
    "TOP166": "main/Z1_Active",
    "TOP167": "main/Backup_Heater_Enable",
    "TOP168": "main/Cooling_Enable",
    "TOP169": "main/Heat_Request_Temp_With_Buffer",
}

BINARY_SENSOR_TOPICS = {
    "TOP144",
    "TOP149",
    "TOP150",
    "TOP151",
    "TOP160",
    "TOP161",
    "TOP163",
    "TOP164",
    "TOP165",
    "TOP166",
    "TOP167",
    "TOP168",
}

ENABLED_BY_DEFAULT_TOPICS = {
    "TOP158",
    "TOP159",
    "TOP160",
    "TOP161",
    "TOP164",
    "TOP166",
}

# command id -> (command topic, readback key)
EXPECTED_COMMANDS = {
    "SET49": ("SetSterilizationTemp", "main/Sterilization_Temp"),
    "SET50": ("SetSterilizationMaxTime", "main/Sterilization_Max_Time"),
    "SET51": ("SetHeatToCoolTemp", "main/Heat_To_Cool_Temp"),
    "SET52": ("SetCoolToHeatTemp", "main/Cool_To_Heat_Temp"),
    "SET53": ("SetRoomOperationMaxTime", "main/Room_Operation_Max_Time"),
    "SET54": ("SetDHWHeatupMaxTime", "main/DHW_Heatup_Max_Time"),
    "SET55": ("SetQuietModeSchedule", "main/Quiet_Mode_Schedule"),
}


def _readbacks_by_topic():
    descriptions = [
        *build_sensors(MQTT_PREFIX),
        *build_binary_sensors(MQTT_PREFIX),
    ]
    return {
        description.heishamon_topic_id: description
        for description in descriptions
        if description.heishamon_topic_id in READBACK_TOPIC_IDS
    }


def _commands_by_id():
    descriptions = [*build_numbers(MQTT_PREFIX), *build_switches(MQTT_PREFIX)]
    return {
        description.heishamon_topic_id: description
        for description in descriptions
        if description.heishamon_topic_id in EXPECTED_COMMANDS
    }


def test_all_readbacks_are_exposed_once():
    descriptions = [
        *build_sensors(MQTT_PREFIX),
        *build_binary_sensors(MQTT_PREFIX),
    ]
    topic_ids = [
        description.heishamon_topic_id
        for description in descriptions
        if description.heishamon_topic_id in READBACK_TOPIC_IDS
    ]

    assert sorted(topic_ids) == sorted(READBACK_TOPIC_IDS)


def test_readbacks_use_upstream_keys():
    descriptions = _readbacks_by_topic()

    for topic_id, key in EXPECTED_READBACK_KEYS.items():
        assert descriptions[topic_id].key == f"{MQTT_PREFIX}{key}"


def test_boolean_readbacks_are_binary_sensors():
    descriptions = _readbacks_by_topic()

    for topic_id in BINARY_SENSOR_TOPICS:
        assert isinstance(
            descriptions[topic_id], HeishaMonBinarySensorEntityDescription
        )
    for topic_id in set(READBACK_TOPIC_IDS) - BINARY_SENSOR_TOPICS:
        assert isinstance(descriptions[topic_id], HeishaMonSensorEntityDescription)


def test_less_common_readbacks_are_disabled_by_default():
    descriptions = _readbacks_by_topic()

    for topic_id in ENABLED_BY_DEFAULT_TOPICS:
        assert descriptions[topic_id].entity_registry_enabled_default is True
    for topic_id in set(READBACK_TOPIC_IDS) - ENABLED_BY_DEFAULT_TOPICS:
        assert descriptions[topic_id].entity_registry_enabled_default is False


def test_readbacks_use_supported_categories():
    descriptions = _readbacks_by_topic()

    for topic_id in READBACK_TOPIC_IDS:
        assert descriptions[topic_id].entity_category != EntityCategory.CONFIG


def test_commands_use_upstream_topics():
    commands = _commands_by_id()

    assert set(commands) == set(EXPECTED_COMMANDS)
    for command_id, (command, key) in EXPECTED_COMMANDS.items():
        description = commands[command_id]
        assert description.command_topic == f"{MQTT_PREFIX}commands/{command}"
        assert description.key == f"{MQTT_PREFIX}{key}"
        assert description.entity_category == EntityCategory.CONFIG


def test_command_entity_types():
    commands = _commands_by_id()

    assert isinstance(commands["SET55"], HeishaMonSwitchEntityDescription)
    for command_id in set(EXPECTED_COMMANDS) - {"SET55"}:
        assert isinstance(commands[command_id], HeishaMonNumberEntityDescription)


def test_number_ranges():
    commands = _commands_by_id()
    expected = {
        "SET49": (55, 75, 1),
        "SET50": (5, 60, 5),
        "SET51": (11, 25, 1),
        "SET52": (5, 24, 1),
        "SET53": (30, 600, 30),
        "SET54": (5, 240, 1),
    }

    for command_id, (minimum, maximum, step) in expected.items():
        description = commands[command_id]
        assert description.native_min_value == minimum
        assert description.native_max_value == maximum
        assert description.native_step == step
        assert description.state_to_mqtt(float(minimum)) == minimum


def test_enum_readers():
    assert read_dhw_capacity_mode("0") == "Standard"
    assert read_dhw_capacity_mode("1") == "Variable"
    assert read_dhw_capacity_mode("-1") is None
    assert set(DHW_CAPACITY_MODES.values()) == {"Standard", "Variable"}

    assert read_zone_configuration("21") == "One zone, zone 1 room"
    assert read_zone_configuration("25") == "One zone, zone 1 pool"
    assert read_zone_configuration("22") == "Two zones, zone 2 room"
    assert read_zone_configuration("38") == "Two zones, zone 2 pool"
    assert read_zone_configuration("0") is None
    assert len(ZONE_CONFIGURATIONS) == 4

    assert read_dhw_heater_type("0") == "Internal"
    assert read_dhw_heater_type("1") == "External"
    assert read_dhw_heater_type("-1") is None
    assert set(DHW_HEATER_TYPES.values()) == {"Internal", "External"}

    assert read_heat_cool_switch_state("0") == "Heat"
    assert read_heat_cool_switch_state("1") == "Cool"
    assert read_heat_cool_switch_state("-1") is None
    assert set(HEAT_COOL_SWITCH_STATES.values()) == {"Heat", "Cool"}


def test_heater_capacity_reader():
    assert read_heater_capacity("3") == 3
    assert read_heater_capacity("6") == 6
    assert read_heater_capacity("9") == 9
    assert read_heater_capacity("-1") is None
    assert read_heater_capacity("") is None
