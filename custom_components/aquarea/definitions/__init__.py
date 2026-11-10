"""HeishaMon entity definitions, split by concern.

Submodules:

- ``values``: value parsers, lookup tables and MQTT writers
- ``descriptions``: ``HeishaMon*EntityDescription`` dataclasses
- ``devices``: device registry helpers and K/L-series handling
- ``numbers``, ``selects``, ``switches``, ``binary_sensors``,
  ``sensors``, ``buttons``: per-platform entity descriptions

Import directly from the submodule that defines the name, e.g.::

    from .definitions.sensors import build_sensors
    from .definitions.values import bit_to_bool
"""