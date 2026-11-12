from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.aquarea.const import DOMAIN
from custom_components.aquarea.model_catalog import (
    ModelCatalog,
    ModelRefreshError,
    SIGNAL_MODEL_CATALOG_UPDATED,
)
from custom_components.aquarea.definitions.descriptions import HeishaMonSensorEntityDescription
from custom_components.aquarea.models import HEATPUMP_MODELS_39
from custom_components.aquarea.sensor import (
    HeishaMonSensor,
    ModelCatalogLastRefreshSensor,
)


MARKDOWN = """
| Value | Bytes 129 - 138 | IDU | ODU | KIT | Power [kW] | 1ph/3ph | T-CAP/HP |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | AA 01 02 03 04 05 06 07 08 09 | Monoblock | WH-MDC05H3E5 | Monoblock | 5 | 1ph | HP |
"""


class FakeResponse:
    def __init__(self, text):
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def raise_for_status(self):
        return None

    async def text(self, encoding=None):
        return self._text


@pytest.fixture
async def model_store():
    store = SimpleNamespace(
        async_load=AsyncMock(return_value=None),
        async_save=AsyncMock(),
    )
    with patch("custom_components.aquarea.model_catalog.Store", return_value=store):
        yield store


async def test_load_uses_persisted_catalog_without_network(hass, model_store):
    refreshed_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    model_store.async_load.return_value = {
        "models": {"AA 01 02 03 04 05 06 07 08 09": "WH-MDC05H3E5 5 1ph HP"},
        "last_refreshed": refreshed_at.isoformat(),
    }
    catalog = ModelCatalog(hass)

    with patch("custom_components.aquarea.model_catalog.async_get_clientsession") as get_session:
        await catalog.async_load()

    get_session.assert_not_called()
    assert catalog.models["AA 01 02 03 04 05 06 07 08 09"] == "WH-MDC05H3E5 5 1ph HP"
    assert catalog.last_refreshed == refreshed_at


async def test_refresh_persists_then_activates_and_notifies(hass, model_store):
    catalog = ModelCatalog(hass)
    await catalog.async_load()
    hass.data.setdefault(DOMAIN, {})["model_catalog"] = catalog
    notifications = []
    async_dispatcher_connect(
        hass, SIGNAL_MODEL_CATALOG_UPDATED, lambda: notifications.append(True)
    )
    session = SimpleNamespace(get=MagicMock(return_value=FakeResponse(MARKDOWN)))

    with patch(
        "custom_components.aquarea.model_catalog.async_get_clientsession",
        return_value=session,
    ):
        count = await catalog.async_refresh()

    signature = "AA 01 02 03 04 05 06 07 08 09"
    assert count == 1
    assert catalog.models[signature] == "WH-MDC05H3E5 5 1ph HP"
    assert catalog.last_refreshed is not None
    assert model_store.async_save.await_count == 1
    assert model_store.async_save.await_args.args[0]["models"][signature]
    assert notifications == [True]


async def test_malformed_upstream_data_keeps_existing_catalog(hass, model_store):
    catalog = ModelCatalog(hass)
    await catalog.async_load()
    original_models = dict(catalog.models)
    session = SimpleNamespace(get=MagicMock(return_value=FakeResponse("not a table")))

    with patch(
        "custom_components.aquarea.model_catalog.async_get_clientsession",
        return_value=session,
    ):
        with pytest.raises(ModelRefreshError, match="Could not parse"):
            await catalog.async_refresh()

    assert catalog.models == original_models
    model_store.async_save.assert_not_awaited()


async def test_storage_failure_does_not_activate_fetched_catalog(hass, model_store):
    catalog = ModelCatalog(hass)
    await catalog.async_load()
    original_models = dict(catalog.models)
    model_store.async_save.side_effect = OSError("disk full")
    session = SimpleNamespace(get=MagicMock(return_value=FakeResponse(MARKDOWN)))

    with patch(
        "custom_components.aquarea.model_catalog.async_get_clientsession",
        return_value=session,
    ):
        with pytest.raises(ModelRefreshError, match="Could not save"):
            await catalog.async_refresh()

    assert catalog.models == original_models
    assert catalog.last_refreshed is None


def test_refresh_status_sensor_has_a_standard_sensor_description(hass):
    sensor = ModelCatalogLastRefreshSensor(
        hass,
        SimpleNamespace(entry_id="test", data={"discovery_prefix": "test/"}),
    )

    assert sensor.entity_description.native_unit_of_measurement is None


def test_model_sensor_recalculates_current_signature_from_active_catalog(hass):
    signature = "AA 01 02 03 04 05 06 07 08 09"
    hass.data.setdefault(DOMAIN, {})["model_catalog"] = SimpleNamespace(
        models={signature: "Newly recognized heat pump"}
    )
    description = HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP92",
        key="test/main/Heat_Pump_Model",
        name="Heat pump model",
    )
    sensor = HeishaMonSensor(
        hass,
        description,
        SimpleNamespace(entry_id="test", data={"discovery_prefix": "test/"}),
    )
    sensor._raw_model_signature = signature

    with patch.object(sensor, "async_write_ha_state"):
        sensor._refresh_heatpump_model()

    assert sensor.native_value == "Newly recognized heat pump"
