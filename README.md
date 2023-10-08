# heishamon-homeassistant

An integration for heatpumps handled by [heishamon](https://github.com/Egyras/HeishaMon).

## Installation

Installation should be done using [hacs](https://hacs.xyz/).
1-click: [![Open in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kamaradclimber&repository=heishamon-homeassistant&category=integration)

## Configuration

Just make sure you have an MQTT integration configured. Heishamon mqtt messages should quickly lead to auto-discovery. There is no way to configure one manually.

ℹ This integration supports any heishamon MQTT topic prefix (defaults to `panasonic_heat_pump`) and multiple heatpumps (experimental).

⚠ By default, all sensors related to less common setups (cooling, buffer, solar or pool) are disabled by default. They can easily enabled when looking at the "Aquarea HeatPump Indoor Unit" device under "entities not shown".

## Alternatives

If you own Panasonic CZ-TAW1 module and have access to Panasonic smart cloud: use https://github.com/cjaliaga/home-assistant-aquarea or https://github.com/ronhks/panasonic-aquarea-smart-cloud-mqtt.

## UI

When using compensation curves method, one can add a nice card to represent the values using [ploty](Plotly Graph Card)

```
type: vertical-stack
cards:
  - type: vertical-stack
    cards:
      - type: horizontal-stack
        cards:
          - type: entities
            entities:
            - entity: number.panasonic_heat_pump_main_z1_heat_curve_outside_low_temp
              name: "x_min: Outside temp lowest point"
            - entity: number.panasonic_heat_pump_main_z1_heat_curve_target_low_temp
              name: "y_min: Target temp lowest point"
      - type: horizontal-stack
        cards:
          - type: entities
            entities:
            - entity: number.panasonic_heat_pump_main_z1_heat_curve_outside_high_temp
              name: "x_max: Outside temp highest point"
            - entity: number.panasonic_heat_pump_main_z1_heat_curve_target_high_temp
              name: "y_max: Target temp highest point"
  - type: custom:plotly-graph
    refresh_interval: 10
    title: Heat curve
    defaults:
      entity:
        show_value: true
        line:
          shape: spline
    layout:
      xaxis:
        type: number
        autorange: true
    entities:
      - entity: ''
        name: Zone 2
        x:
          - >-
            $ex
            hass.states['number.panasonic_heat_pump_main_z2_heat_curve_outside_low_temp'].state
          - >-
            $ex
            hass.states['number.panasonic_heat_pump_main_z2_heat_curve_outside_high_temp'].state
        'y':
          - >-
            $ex
            hass.states['number.panasonic_heat_pump_main_z2_heat_curve_target_high_temp'].state
          - >-
            $ex
            hass.states['number.panasonic_heat_pump_main_z2_heat_curve_target_low_temp'].state
      - entity: ''
        name: Zone 1
        x:
          - >-
            $ex
            hass.states['number.panasonic_heat_pump_main_z1_heat_curve_outside_low_temp'].state
          - >-
            $ex
            hass.states['number.panasonic_heat_pump_main_z1_heat_curve_outside_high_temp'].state
        'y':
          - >-
            $ex
            hass.states['number.panasonic_heat_pump_main_z1_heat_curve_target_high_temp'].state
          - >-
            $ex
            hass.states['number.panasonic_heat_pump_main_z1_heat_curve_target_low_temp'].state
```
