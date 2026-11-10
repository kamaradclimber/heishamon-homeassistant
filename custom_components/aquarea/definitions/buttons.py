"""Button entity descriptions for HeishaMon."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass
from homeassistant.helpers.entity import EntityCategory

from ..const import DeviceType
from .descriptions import (
    HeishaMonBinarySensorEntityDescription,
    HeishaMonButtonEntityDescription,
)
from .devices import update_device_ip


def build_buttons(
    mqtt_prefix: str,
) -> list[HeishaMonBinarySensorEntityDescription]:
    return [
        HeishaMonButtonEntityDescription(
            heishamon_topic_id="Reboot",
            key=f"{mqtt_prefix}ip",
            name="Reboot",
            device=DeviceType.HEISHAMON,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=ButtonDeviceClass.RESTART,
            on_receive=update_device_ip,
        ),
        HeishaMonButtonEntityDescription(
            heishamon_topic_id="SET48",
            key=f"{mqtt_prefix}commands/SetReset",
            command_topic=f"{mqtt_prefix}commands/SetReset",
            name="Reset fault code",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ]
