"""Sensors are unavailable while HeishaMon is offline (last will on LWT), so
the energy totals (IntegrationSensor) stop instead of adding the last power."""
from types import SimpleNamespace
from unittest.mock import patch

from homeassistant.components.sensor import SensorDeviceClass

from custom_components.aquarea.const import DeviceType
from custom_components.aquarea.definitions.descriptions import (
    HeishaMonSensorEntityDescription,
)
from custom_components.aquarea.sensor import HeishaMonSensor


async def test_sensor_follows_heishamon_lwt(hass):
    config_entry = SimpleNamespace(entry_id="test", data={"discovery_prefix": "prefix/"})
    description = HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP16",
        key="prefix/main/Heat_Power_Consumption",
        name="Heat power consumption",
        native_unit_of_measurement="W",
        device_class=SensorDeviceClass.POWER,
        device=DeviceType.HEATPUMP,
    )
    entity = HeishaMonSensor(hass, description, config_entry)
    entity.async_write_ha_state = lambda: None  # not added to hass

    callbacks = {}

    async def fake_subscribe(hass, topic, msg_callback, qos=0):
        callbacks[topic] = msg_callback
        return lambda: None

    with patch(
        "custom_components.aquarea.sensor.mqtt.async_subscribe",
        side_effect=fake_subscribe,
    ):
        await entity._async_subscribe_lwt()

    assert entity.available
    callbacks["prefix/LWT"](SimpleNamespace(topic="prefix/LWT", payload="Offline"))
    assert not entity.available
    callbacks["prefix/LWT"](SimpleNamespace(topic="prefix/LWT", payload="Online"))
    assert entity.available
