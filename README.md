# heishamon-homeassistant

An integration for heatpumps handled by [heishamon](https://github.com/Egyras/HeishaMon).
It's currently in development, expect sensors to be renamed.

## Installation
Installation should be done using https://hacs.xyz/ as a custom repository.

## Configuration

Just make sure you have an MQTT integration configured. Heishamon mqtt messages should quickly lead to auto-discovery. There is no way to configure one manually.

ℹ This integration supports any heishamon MQTT topic prefix (defaults to `panasonic_heat_pump`) and multiple heatpumps (experimental).

⚠ By default, all sensors related to less common setups (cooling, buffer, solar or pool) are disabled by default. They can easily enabled when looking at the "Aquarea HeatPump Indoor Unit" device under "entities not shown".

## Alternatives

If you own Panasonic CZ-TAW1 module and have access to Panasonic smart cloud: use https://github.com/cjaliaga/home-assistant-aquarea or https://github.com/ronhks/panasonic-aquarea-smart-cloud-mqtt.
