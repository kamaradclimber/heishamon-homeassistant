"""Config flow to configure HeishaMon integration."""
from __future__ import annotations

from collections.abc import Awaitable
import logging
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.config_entry_flow import DiscoveryFlowHandler
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(_: HomeAssistant) -> bool:
    """MQTT is set as dependency, so that should be sufficient."""
    return True


class HeishaMonFlowHandler(DiscoveryFlowHandler[Awaitable[bool]], domain=DOMAIN):
    """Handle HeishaMon config flow. The MQTT step is inherited from the parent class."""

    VERSION = 2

    def __init__(self) -> None:
        """Set up the config flow."""

        self._prefix: Optional[str] = None
        super().__init__(DOMAIN, "HeishaMon", _async_has_devices)

    async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> FlowResult:
        """Handle a flow initialized by MQTT discovery"""
        _LOGGER.debug(
            f"Starting MQTT discovery for heishamon with {discovery_info.topic}"
        )
        if not discovery_info.topic.endswith("main/Heatpump_State"):
            # not a heishamon message
            return self.async_abort(reason="invalid_discovery_info")
        self._prefix = discovery_info.topic.replace("main/Heatpump_State", "")
        _LOGGER.debug(f"The integration will use prefix '{self._prefix}'")

        unique_id = f"{DOMAIN}-{self._prefix}"
        existing_ids = self._async_current_ids()
        # backward compatibility with < 0.9.0
        if "aquarea" in existing_ids and unique_id == "aquarea-panasonic_heat_pump/":
            existing_ids.add("aquarea-panasonic_heat_pump/")
        if unique_id in existing_ids:
            _LOGGER.debug(
                f"[{self._prefix}] ignoring because it has already been configured"
            )
            return self.async_abort(reason="instance_already_configured")

        await self.async_set_unique_id(unique_id)
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm setup to user and create the entry"""

        if not self._prefix:
            return self.async_abort(reason="unsupported_manual_setup")

        data = {"discovery_prefix": self._prefix}

        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={
                    "discovery_topic": self._prefix,
                },
            )

        return self.async_create_entry(
            title=f"HeishaMon via {self._prefix} topic", data=data
        )
