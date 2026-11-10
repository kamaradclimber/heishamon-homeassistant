"""Tests for entity device classes."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.switch import SwitchDeviceClass

from custom_components.aquarea.definitions import (
    build_binary_sensors,
    build_switches,
)

MQTT_PREFIX = "panasonic_heat_pump/"


def _descriptions_by_topic(descriptions):
    return {description.heishamon_topic_id: description for description in descriptions}


def test_switches_only_use_switch_device_classes():
    """Switch entities must not use binary sensor device classes."""
    for description in build_switches(MQTT_PREFIX):
        assert description.device_class in (
            None,
            SwitchDeviceClass.OUTLET,
            SwitchDeviceClass.SWITCH,
        )


def test_readonly_switch_mirrors_have_their_own_device_class():
    """Readonly mirrors get their device class from a dedicated field."""
    switches = _descriptions_by_topic(build_switches(MQTT_PREFIX))

    assert (
        switches["SET1"].binary_sensor_device_class
        == BinarySensorDeviceClass.RUNNING
    )
    assert switches["SET12"].binary_sensor_device_class is None
    assert (
        switches["SET13"].binary_sensor_device_class
        == BinarySensorDeviceClass.RUNNING
    )
    assert switches["SET47"].binary_sensor_device_class is None


def test_no_heat_device_class_for_heater_states():
    """HEAT means 'hot', not 'a heater is active'."""
    binary_sensors = _descriptions_by_topic(build_binary_sensors(MQTT_PREFIX))

    for topic_id in ("TOP58", "TOP59", "TOP60", "TOP61", "TOP68"):
        assert binary_sensors[topic_id].device_class != BinarySensorDeviceClass.HEAT

    assert (
        binary_sensors["TOP60"].device_class == BinarySensorDeviceClass.RUNNING
    )
    assert (
        binary_sensors["TOP61"].device_class == BinarySensorDeviceClass.RUNNING
    )
    assert binary_sensors["TOP68"].device_class is None
