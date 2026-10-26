"""Ensure DHW mode change spaces out MQTT commands (#417)."""
from unittest.mock import patch

import pytest

from homeassistant.components.water_heater.const import STATE_ECO
from custom_components.aquarea.water_heater import HeishaMonDHW


async def test_set_operation_mode_waits_between_commands(hass):
    from types import SimpleNamespace

    config_entry = SimpleNamespace(entry_id="test", data={"discovery_prefix": "prefix/"})
    description = SimpleNamespace(
        key="main/DHW_Target_Temp", has_entity_name=False, name="DHW"
    )
    entity = HeishaMonDHW(None, description, config_entry)
    entity.hass = hass
    entity.async_write_ha_state = lambda: None  # not added to hass
    entity._heatpump_state = None
    entity._operating_mode = __import__(
        "custom_components.aquarea.definitions", fromlist=["OperatingMode"]
    ).OperatingMode(0)
    entity._heat_delta = 0
    entity._attr_target_temperature = None
    entity._attr_current_operation = None

    sleeps = []
    publishes = []

    async def fake_publish(hass, topic, payload, *args, **kwargs):
        publishes.append(topic)

    def fake_sleep(delay):
        sleeps.append(delay)

    entity.hass = None
    with patch(
        "custom_components.aquarea.water_heater.async_publish", side_effect=fake_publish
    ):
        with patch("asyncio.sleep", side_effect=fake_sleep):
            await entity.async_set_operation_mode(STATE_ECO)

    if entity._retry_task:
        entity._retry_task.cancel()
    await hass.async_block_till_done()

    # two commands sent: SetHeatpump (turn on) and SetDHWTemp
    assert publishes == [
        f"{entity.discovery_prefix}commands/SetHeatpump",
        f"{entity.discovery_prefix}commands/SetOperationMode",
        f"{entity.discovery_prefix}commands/SetDHWTemp",
    ] or publishes[-1] == f"{entity.discovery_prefix}commands/SetDHWTemp"
    assert 1.0 in sleeps