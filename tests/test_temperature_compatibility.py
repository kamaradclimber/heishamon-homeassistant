"""Exercise climate and DHW temperature state on old and new HA APIs."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from homeassistant.components.climate.const import DATA_COMPONENT as CLIMATE_COMPONENT
from homeassistant.components.water_heater.const import (
    DATA_COMPONENT as WATER_HEATER_COMPONENT,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from custom_components.aquarea.climate import (
    HeishaMonZoneClimate,
    ZoneClimateEntityDescription,
)
from custom_components.aquarea.water_heater import (
    HeishaMonDHW,
    WaterHeaterEntityDescription,
)


@pytest.fixture
def mqtt_callbacks():
    """Capture the MQTT subscriptions without requiring a broker."""
    callbacks = {}

    async def subscribe(hass, topic, callback, qos):
        callbacks[topic] = callback
        return lambda: None

    with patch(
        "custom_components.aquarea.climate.mqtt.async_subscribe", side_effect=subscribe
    ):
        yield callbacks


def send(callbacks, topic, payload):
    callbacks[f"test/{topic}"](
        SimpleNamespace(payload=str(payload), topic=f"test/{topic}")
    )


@pytest.mark.parametrize("fahrenheit", [False, True])
@pytest.mark.parametrize("heater", [False, True])
async def test_climate_temperature_states(
    hass, mqtt_callbacks, caplog, fahrenheit, heater
):
    hass.config.units = US_CUSTOMARY_SYSTEM if fahrenheit else METRIC_SYSTEM
    assert await async_setup_component(hass, "climate", {})
    entry = SimpleNamespace(entry_id="test", data={"discovery_prefix": "test/"})
    description = ZoneClimateEntityDescription(
        key="test/main/Z1_Temp", name="Zone 1", zone_id=1
    )
    entity = HeishaMonZoneClimate(hass, description, entry, heater)
    entity._attr_entity_registry_enabled_default = (
        True  # Cooling is disabled by default.
    )
    with (
        patch.object(entity._store, "async_load", new=AsyncMock(return_value=None)),
        patch.object(
            HeishaMonZoneClimate,
            "device_info",
            new_callable=PropertyMock,
            return_value=None,
        ),
    ):
        await hass.data[CLIMATE_COMPONENT].async_add_entities([entity])

    state = hass.states.get(entity.entity_id)
    assert state.attributes["current_temperature"] is None
    assert state.attributes["temperature"] is None
    assert entity._attr_native_temperature_unit == "°C"

    target_topic = (
        "main/Z1_Heat_Request_Temp" if heater else "main/Z1_Cool_Request_Temp"
    )
    send(mqtt_callbacks, "main/Z1_Temp", 20)
    send(mqtt_callbacks, target_topic, 25)
    state = hass.states.get(entity.entity_id)
    assert state.attributes["current_temperature"] == (68 if fahrenheit else 20)
    assert state.attributes["temperature"] == (77 if fahrenheit else 25)

    # A second update must invalidate HA's cached temperature properties.
    send(mqtt_callbacks, "main/Z1_Temp", 25)
    send(mqtt_callbacks, target_topic, 30)
    state = hass.states.get(entity.entity_id)
    assert state.attributes["current_temperature"] == (77 if fahrenheit else 25)
    assert state.attributes["temperature"] == (86 if fahrenheit else 30)
    assert not any("2027.11" in record.message for record in caplog.records)


@pytest.mark.parametrize("fahrenheit", [False, True])
async def test_dhw_temperature_states_and_bounds(
    hass, mqtt_callbacks, caplog, fahrenheit
):
    hass.config.units = US_CUSTOMARY_SYSTEM if fahrenheit else METRIC_SYSTEM
    assert await async_setup_component(hass, "water_heater", {})
    entry = SimpleNamespace(entry_id="test", data={"discovery_prefix": "test/"})
    description = WaterHeaterEntityDescription(
        key="test/main/DHW_Target_Temp", name="DHW"
    )
    entity = HeishaMonDHW(hass, description, entry)
    with patch.object(
        HeishaMonDHW, "device_info", new_callable=PropertyMock, return_value=None
    ):
        await hass.data[WATER_HEATER_COMPONENT].async_add_entities([entity])

    state = hass.states.get(entity.entity_id)
    assert state.attributes["current_temperature"] is None
    assert state.attributes["temperature"] is None
    assert state.attributes["target_temp_high"] is None
    assert state.attributes["target_temp_low"] is None
    assert entity._attr_native_temperature_unit == "°C"

    send(mqtt_callbacks, "main/DHW_Temp", 45)
    send(mqtt_callbacks, "main/DHW_Target_Temp", 50)
    send(mqtt_callbacks, "main/DHW_Heat_Delta", -5)
    state = hass.states.get(entity.entity_id)
    assert state.attributes["current_temperature"] == (113 if fahrenheit else 45)
    assert state.attributes["temperature"] == (122 if fahrenheit else 50)
    assert state.attributes["target_temp_high"] == (122 if fahrenheit else 50)
    assert state.attributes["target_temp_low"] == (113 if fahrenheit else 45)

    send(mqtt_callbacks, "main/DHW_Temp", 50)
    send(mqtt_callbacks, "main/DHW_Target_Temp", 55)
    state = hass.states.get(entity.entity_id)
    assert state.attributes["current_temperature"] == (122 if fahrenheit else 50)
    assert state.attributes["temperature"] == (131 if fahrenheit else 55)
    assert state.attributes["target_temp_high"] == (131 if fahrenheit else 55)
    assert state.attributes["target_temp_low"] == (122 if fahrenheit else 50)
    assert not any("2027.11" in record.message for record in caplog.records)


@pytest.mark.parametrize("fahrenheit", [False, True])
@pytest.mark.parametrize("domain", ["climate", "water_heater"])
async def test_set_temperature_sends_celsius(hass, mqtt_callbacks, fahrenheit, domain):
    hass.config.units = US_CUSTOMARY_SYSTEM if fahrenheit else METRIC_SYSTEM
    assert await async_setup_component(hass, domain, {})
    entry = SimpleNamespace(entry_id="test", data={"discovery_prefix": "test/"})
    if domain == "climate":
        description = ZoneClimateEntityDescription(
            key="test/main/Z1_Temp", name="Zone 1", zone_id=1
        )
        entity = HeishaMonZoneClimate(hass, description, entry, True)
        with (
            patch.object(entity._store, "async_load", new=AsyncMock(return_value=None)),
            patch.object(
                HeishaMonZoneClimate,
                "device_info",
                new_callable=PropertyMock,
                return_value=None,
            ),
        ):
            await hass.data[CLIMATE_COMPONENT].async_add_entities([entity])
        publish_path = "custom_components.aquarea.climate.async_publish"
        target_topic = "main/Z1_Heat_Request_Temp"
        command_topic = "test/commands/SetZ1HeatRequestTemperature"
        native_target = 30
    else:
        description = WaterHeaterEntityDescription(
            key="test/main/DHW_Target_Temp", name="DHW"
        )
        entity = HeishaMonDHW(hass, description, entry)
        with patch.object(
            HeishaMonDHW, "device_info", new_callable=PropertyMock, return_value=None
        ):
            await hass.data[WATER_HEATER_COMPONENT].async_add_entities([entity])
        publish_path = "custom_components.aquarea.water_heater.async_publish"
        target_topic = "main/DHW_Target_Temp"
        command_topic = "test/commands/SetDHWTemp"
        native_target = 50

    display_target = native_target * 9 / 5 + 32 if fahrenheit else native_target
    with patch(publish_path, new_callable=AsyncMock) as publish:
        await hass.services.async_call(
            domain,
            "set_temperature",
            {"entity_id": entity.entity_id, "temperature": display_target},
            blocking=True,
        )
        assert publish.await_count == 1
        assert publish.await_args.args[1] == command_topic
        assert float(publish.await_args.args[2]) == native_target
        assert entity._pending_command is not None
        send(mqtt_callbacks, target_topic, native_target)
        assert entity._pending_command is None
