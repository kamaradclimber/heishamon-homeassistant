"""Tests for HeishaMon 4.4.0 readback entities (TOP170-TOP198)."""

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from custom_components.aquarea.definitions.binary_sensors import build_binary_sensors
from custom_components.aquarea.definitions.descriptions import (
    HeishaMonBinarySensorEntityDescription,
    HeishaMonSensorEntityDescription,
)
from custom_components.aquarea.definitions.sensors import build_sensors
from custom_components.aquarea.definitions.values import (
    BIVALENT_OPERATING_MODES,
    EXTRA_PUMP_USE,
    HEAT_PUMP_TYPES,
    bit_to_bool,
    read_bivalent_operating_mode,
    read_enabled_disabled,
    read_extra_pump_use,
    read_heat_pump_type,
    read_heating_control,
)

MQTT_PREFIX = "panasonic_heat_pump/"
NEW_TOPIC_IDS = [f"TOP{number}" for number in range(170, 199)]

EXPECTED_KEYS = {
    "TOP170": "main/Static_Pressure",
    "TOP171": "main/Heating_On_Outdoor_Temp",
    "TOP172": "main/Heating_On_Delay",
    "TOP173": "main/DHW_Booster_Delay",
    "TOP174": "main/Efficiency_Stage1_Time",
    "TOP175": "main/Efficiency_Stage2_Time",
    "TOP176": "main/Efficiency_Stage3_Time",
    "TOP177": "main/Sensor_Offset_Remote_Th1",
    "TOP178": "main/Sensor_Offset_Outdoor",
    "TOP179": "main/Anti_Stick_Mode",
    "TOP180": "main/Bivalent_Operating_Mode",
    "TOP181": "main/Bivalent_External_Pump",
    "TOP182": "main/Extra_Pump_Use",
    "TOP183": "main/Extra_Pump_Mode",
    "TOP184": "main/SG_Ready_1_DHW_Power",
    "TOP185": "main/SG_Ready_1_Heat_Power",
    "TOP186": "main/SG_Ready_1_Cool_Power",
    "TOP187": "main/SG_Ready_2_DHW_Power",
    "TOP188": "main/SG_Ready_2_Heat_Power",
    "TOP189": "main/SG_Ready_2_Cool_Power",
    "TOP190": "main/SG_Ready_Stop_Power",
    "TOP191": "main/SG_Ready_1_Cool_Capacity",
    "TOP192": "main/SG_Ready_2_Cool_Capacity",
    "TOP193": "main/Sensor_Offset_Return",
    "TOP194": "main/Defrost_Signal",
    "TOP195": "main/Sensor_Offset_DHW_Tank",
    "TOP196": "main/Sensor_Offset_Flow",
    "TOP197": "main/Heat_Pump_Capacity",
    "TOP198": "main/Heat_Pump_Type",
}

BINARY_SENSOR_TOPICS = {"TOP170", "TOP179", "TOP181", "TOP194"}

DISABLED_BY_DEFAULT_TOPICS = {
    "TOP170",
    "TOP171",
    "TOP172",
    "TOP173",
    "TOP174",
    "TOP175",
    "TOP176",
    "TOP177",
    "TOP178",
    "TOP179",
    "TOP182",
    "TOP183",
    "TOP184",
    "TOP185",
    "TOP186",
    "TOP187",
    "TOP188",
    "TOP189",
    "TOP190",
    "TOP191",
    "TOP192",
    "TOP193",
    "TOP194",
    "TOP195",
    "TOP196",
}


def _descriptions_by_topic():
    descriptions = [
        *build_sensors(MQTT_PREFIX),
        *build_binary_sensors(MQTT_PREFIX),
    ]
    return {description.heishamon_topic_id: description for description in descriptions}


def test_all_v4_4_topics_are_exposed_once():
    descriptions = [
        *build_sensors(MQTT_PREFIX),
        *build_binary_sensors(MQTT_PREFIX),
    ]
    new_descriptions = [
        description
        for description in descriptions
        if description.heishamon_topic_id in NEW_TOPIC_IDS
    ]

    assert len(new_descriptions) == len(NEW_TOPIC_IDS)
    assert {description.heishamon_topic_id for description in new_descriptions} == set(
        NEW_TOPIC_IDS
    )


def test_v4_4_topics_use_upstream_keys():
    descriptions = _descriptions_by_topic()

    for topic_id, key in EXPECTED_KEYS.items():
        assert descriptions[topic_id].key == f"{MQTT_PREFIX}{key}"


def test_v4_4_boolean_settings_are_binary_sensors():
    descriptions = _descriptions_by_topic()

    for topic_id in BINARY_SENSOR_TOPICS:
        assert isinstance(
            descriptions[topic_id], HeishaMonBinarySensorEntityDescription
        )
    for topic_id in set(EXPECTED_KEYS) - BINARY_SENSOR_TOPICS:
        assert isinstance(descriptions[topic_id], HeishaMonSensorEntityDescription)


def test_v4_4_installer_and_sg_ready_entities_are_disabled_by_default():
    descriptions = _descriptions_by_topic()

    for topic_id in DISABLED_BY_DEFAULT_TOPICS:
        assert descriptions[topic_id].entity_registry_enabled_default is False
    for topic_id in {"TOP180", "TOP181", "TOP197", "TOP198"}:
        assert descriptions[topic_id].entity_registry_enabled_default is True


def test_v4_4_read_only_entities_use_supported_categories():
    descriptions = _descriptions_by_topic()

    for topic_id in NEW_TOPIC_IDS:
        assert descriptions[topic_id].entity_category != EntityCategory.CONFIG


def test_v4_4_energy_settings_use_kilowatts():
    descriptions = _descriptions_by_topic()

    for topic_id in {
        "TOP184",
        "TOP185",
        "TOP186",
        "TOP187",
        "TOP188",
        "TOP189",
        "TOP190",
        "TOP197",
    }:
        description = descriptions[topic_id]
        assert description.device_class == SensorDeviceClass.POWER
        assert description.native_unit_of_measurement == "kW"


def test_v4_4_enum_readers_use_upstream_wording():
    assert read_bivalent_operating_mode("0") == "Auto"
    assert read_bivalent_operating_mode("1") == "SG ready"
    assert read_bivalent_operating_mode("2") == "Intelligent"
    assert read_bivalent_operating_mode("-1") is None
    assert set(BIVALENT_OPERATING_MODES.values()) == {
        "Auto",
        "SG ready",
        "Intelligent",
    }

    assert read_extra_pump_use("0") == "Not used"
    assert read_extra_pump_use("1") == "Heating"
    assert read_extra_pump_use("2") == "DHW"
    assert read_extra_pump_use("-1") is None
    assert set(EXTRA_PUMP_USE.values()) == {"Not used", "Heating", "DHW"}

    assert read_heating_control("0") == "Comfort"
    assert read_heating_control("1") == "Efficiency"
    assert read_heating_control("-1") is None

    assert read_heat_pump_type("0") == "Standard"
    assert read_heat_pump_type("1") == "T-CAP"
    assert read_heat_pump_type("-1") is None
    assert set(HEAT_PUMP_TYPES.values()) == {"Standard", "T-CAP"}


def test_v4_4_boolean_readers():
    assert read_enabled_disabled("1") is True
    assert read_enabled_disabled("0") is False
    assert read_enabled_disabled("-1") is None

    assert bit_to_bool("1") is True
    assert bit_to_bool("0") is False
    assert bit_to_bool("-1") is None
