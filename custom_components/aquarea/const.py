"""Constant values for HeishaMon integration."""

from enum import Enum

DOMAIN = "aquarea"


class DeviceType(Enum):
    HEATPUMP = 1
    HEISHAMON = 2
