"""Runtime model catalog with explicit, persistent upstream refreshes."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .model_source import SIGNATURE_RE, SOURCE_URL, parse_heatpump_models
from .models import HEATPUMP_MODELS_39

_LOGGER = logging.getLogger(__name__)
SIGNAL_MODEL_CATALOG_UPDATED = f"{DOMAIN}_model_catalog_updated"
STORE_VERSION = 1
STORE_KEY = f"{DOMAIN}_model_catalog"


class ModelRefreshError(HomeAssistantError):
    """Raised when an explicit model catalog refresh fails."""


class ModelCatalog:
    """The bundled and user-refreshed heat pump model definitions."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store = Store(hass, STORE_VERSION, STORE_KEY)
        self._models = dict(HEATPUMP_MODELS_39)
        self._last_refreshed: datetime | None = None
        self._loaded = False
        self._load_lock = asyncio.Lock()
        self._refresh_lock = asyncio.Lock()

    @property
    def models(self) -> dict[str, str]:
        """Return the active 3.9+ model catalog."""
        return self._models

    @property
    def last_refreshed(self) -> datetime | None:
        """Return when the user last refreshed the upstream catalog."""
        return self._last_refreshed

    async def async_load(self) -> None:
        """Load any previously refreshed catalog without making a network request."""
        async with self._load_lock:
            if self._loaded:
                return
            self._loaded = True
            try:
                data = await self._store.async_load()
            except Exception:
                _LOGGER.exception("Could not load the saved heat pump model catalog")
                return

            if not isinstance(data, dict):
                return
            cached_models = data.get("models")
            if not _valid_model_map(cached_models):
                _LOGGER.warning("Ignoring invalid saved heat pump model catalog")
                return

            self._models = {**HEATPUMP_MODELS_39, **cached_models}
            refreshed = data.get("last_refreshed")
            if isinstance(refreshed, str):
                self._last_refreshed = dt_util.parse_datetime(refreshed)

    async def async_refresh(self) -> int:
        """Fetch, validate, persist, then activate the latest upstream model list."""
        async with self._refresh_lock:
            session = async_get_clientsession(self.hass)
            try:
                async with session.get(
                    SOURCE_URL, timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response.raise_for_status()
                    markdown = await response.text(encoding="utf-8")
            except (aiohttp.ClientError, asyncio.TimeoutError, UnicodeError) as err:
                raise ModelRefreshError(f"Could not fetch the upstream model list: {err}") from err

            try:
                refreshed_models = parse_heatpump_models(markdown)
            except ValueError as err:
                raise ModelRefreshError(f"Could not parse the upstream model list: {err}") from err

            refreshed_at = dt_util.utcnow()
            try:
                await self._store.async_save(
                    {
                        "models": refreshed_models,
                        "last_refreshed": refreshed_at.isoformat(),
                    }
                )
            except Exception as err:
                raise ModelRefreshError(
                    f"Could not save the refreshed model list: {err}"
                ) from err

            self._models = {**HEATPUMP_MODELS_39, **refreshed_models}
            self._last_refreshed = refreshed_at
            async_dispatcher_send(self.hass, SIGNAL_MODEL_CATALOG_UPDATED)
            _LOGGER.info(
                "Refreshed heat pump models from upstream (%d model signatures)",
                len(refreshed_models),
            )
            return len(refreshed_models)


def _valid_model_map(value: Any) -> bool:
    """Check a model map loaded from disk before using it."""
    if not isinstance(value, dict) or not value:
        return False
    return all(
        isinstance(signature, str)
        and isinstance(label, str)
        and SIGNATURE_RE.fullmatch(signature) is not None
        and bool(label.strip())
        for signature, label in value.items()
    )
