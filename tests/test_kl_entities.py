"""Test K/L-series entities are enabled when model is detected (#419)."""
from unittest.mock import MagicMock

import pytest

from custom_components.aquarea.const import DOMAIN
from custom_components.aquarea.definitions import (
    K_L_SERIES_ENTITY_TOPIC_IDS,
    enable_kl_entities,
    is_kl_series,
    update_device_model,
)


def test_is_kl_series():
    assert is_kl_series("WH-ADC0509L3E5 7 1ph HP - All-In-One L-series")
    assert is_kl_series("WH-SDC0309K3E5 5 1ph HP - split K-series")
    assert not is_kl_series("Unknown model for HeishaMon")
    assert not is_kl_series("WH-MDC05J3E5 - J-series")


KL_MODEL = "WH-ADC0509L3E5 7 1ph HP - All-In-One L-series"
OTHER_MODEL = "Unknown model for HeishaMon"


def _setup_registry(hass, topic_id, disabled_by):
    """Create entity registry entries for all K/L topic ids, with given disabled state for topic_id."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    entity_registry = hass.data.setdefault("entity_registry", None)
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    results = {}
    for tid in K_L_SERIES_ENTITY_TOPIC_IDS:
        platform = "select" if tid == "SET43" else "sensor"
        results[tid] = registry.async_get_or_create(
            platform,
            DOMAIN,
            f"{entry.entry_id}-{tid}",
            disabled_by=disabled_by if tid == topic_id else None,
        )
    return entry.entry_id, results


@pytest.mark.parametrize("disabled_by", ["integration", None])
async def test_kl_entity_enabled(hass, disabled_by):
    from homeassistant.helpers import entity_registry as er

    disabler = (
        er.RegistryEntryDisabler.INTEGRATION if disabled_by == "integration" else None
    )
    entry_id, results = _setup_registry(hass, "TOP115", disabler)
    entity_id = results["TOP115"].entity_id

    enable_kl_entities(hass, entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    updated = registry.async_get(entity_id)
    assert updated.disabled_by is None

    # other entities were not disabled and must stay enabled
    for tid, e in results.items():
        if tid != "TOP115":
            assert registry.async_get(e.entity_id).disabled_by is None


async def test_user_disabled_entity_left_alone(hass):
    from homeassistant.helpers import entity_registry as er

    entry_id, results = _setup_registry(
        hass, "TOP115", er.RegistryEntryDisabler.USER
    )
    entity_id = results["TOP115"].entity_id

    enable_kl_entities(hass, entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert registry.async_get(entity_id).disabled_by == er.RegistryEntryDisabler.USER


async def test_non_kl_model_no_registry_change(hass):
    from homeassistant.helpers import entity_registry as er

    entry_id, results = _setup_registry(
        hass, "TOP115", er.RegistryEntryDisabler.INTEGRATION
    )
    entity_id = results["TOP115"].entity_id

    update_device_model(hass, MagicMock(device_info={"identifiers": {(DOMAIN, "test-device")}}), entry_id, OTHER_MODEL)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert registry.async_get(entity_id).disabled_by == er.RegistryEntryDisabler.INTEGRATION


async def test_kl_model_via_update_device_model(hass):
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    created = {}
    for tid in K_L_SERIES_ENTITY_TOPIC_IDS:
        platform = "select" if tid == "SET43" else "sensor"
        created[tid] = registry.async_get_or_create(
            platform, DOMAIN, f"{entry.entry_id}-{tid}"
        )
        registry.async_update_entity(created[tid].entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)

    update_device_model(hass, MagicMock(device_info={"identifiers": {(DOMAIN, "test-device")}}), entry.entry_id, KL_MODEL)
    await hass.async_block_till_done()

    for tid, e in created.items():
        assert registry.async_get(e.entity_id).disabled_by is None, tid