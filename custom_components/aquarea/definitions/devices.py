"""Device registry helpers and K/L-series entity handling."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _get_device_identifiers(device_info):
    """Return device identifiers, supporting old and new Home Assistant versions."""
    if device_info is None:
        return None
    if isinstance(device_info, dict):
        # Home Assistant < 2026.11 represented DeviceInfo as a TypedDict.
        return device_info.get("identifiers")
    return device_info.identifiers


def update_device_ip(
    hass: HomeAssistant, entity: SensorEntity, config_entry_id: str, ip: str
):
    _LOGGER.debug(f"Received ip address: {ip}")
    device_registry = dr.async_get(hass)
    identifiers = _get_device_identifiers(entity.device_info)
    device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers=identifiers,
        configuration_url=f"http://{ip}",
    )


K_L_SERIES_ENTITY_TOPIC_IDS = ["TOP115", "TOP116", "TOP117", "TOP118", "SET43"]


def is_kl_series(model: str) -> bool:
    """Return True if heatpump model belongs to K or L series."""
    return "K-series" in model or "L-series" in model


def update_device_model(
    hass: HomeAssistant, entity: SensorEntity, config_entry_id: str, model: str
):
    _LOGGER.debug("Set model")

    device_registry = dr.async_get(hass)
    identifiers = _get_device_identifiers(entity.device_info)
    device_registry.async_get_or_create(
        config_entry_id=config_entry_id, identifiers=identifiers, model=model
    )

    if is_kl_series(model):
        enable_kl_entities(hass, config_entry_id)


def enable_kl_entities(hass: HomeAssistant, config_entry_id: str):
    """Enable by default K/L-series entities still disabled by the integration.

    Entities the user disabled explicitly (disabled_by=USER) are left alone.
    """
    entity_registry = er.async_get(hass)
    reload_entry = False
    for topic_id in K_L_SERIES_ENTITY_TOPIC_IDS:
        unique_id = f"{config_entry_id}-{topic_id}"
        entry = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id) or \
            entity_registry.async_get_entity_id("select", DOMAIN, unique_id)
        if entry is None:
            continue
        registry_entry = entity_registry.async_get(entry)
        if registry_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
            entity_registry.async_update_entity(entry, disabled_by=None)
            reload_entry = True
            _LOGGER.info(
                "Detected K/L-series heatpump model, enabling entity %s", entry
            )
    if reload_entry:
        hass.async_create_task(hass.config_entries.async_reload(config_entry_id))
