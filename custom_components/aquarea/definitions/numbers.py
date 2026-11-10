"""Number entity descriptions for HeishaMon."""

from __future__ import annotations

from functools import partial

from homeassistant.components.number import NumberDeviceClass
from homeassistant.helpers.entity import EntityCategory

from .descriptions import HeishaMonNumberEntityDescription
from .values import (
    guess_shift_or_direct_and_clamp_min_max_values,
    read_demandcontrol,
    write_curves_gen,
    write_demandcontrol,
)


def build_numbers(mqtt_prefix: str) -> list[HeishaMonNumberEntityDescription]:
    numbers = [
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET5",  # also TOP27
            key=f"{mqtt_prefix}main/Z1_Heat_Request_Temp",
            command_topic=f"{mqtt_prefix}commands/SetZ1HeatRequestTemperature",
            # it can be relative (-5 -> +5, or absolute [20, ..[)
            name="Aquarea Zone 1 Heat Requested shift",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=-5,
            native_max_value=20,
            state=int,
            state_to_mqtt=int,
            on_receive=partial(
                guess_shift_or_direct_and_clamp_min_max_values,
                range(-5, 6),
                range(7, 61),
            ),
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET6",  # also TOP28
            key=f"{mqtt_prefix}main/Z1_Cool_Request_Temp",
            command_topic=f"{mqtt_prefix}commands/SetZ1CoolRequestTemperature",
            # it can be relative (-5 -> +5, or absolute [20, ..[)
            name="Aquarea Zone 1 Cool Requested shift",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=-5,
            native_max_value=25,
            state=int,
            state_to_mqtt=int,
            on_receive=partial(
                guess_shift_or_direct_and_clamp_min_max_values,
                range(-5, 6),
                range(5, 36),
            ),
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET7",  # also TOP34
            key=f"{mqtt_prefix}main/Z2_Heat_Request_Temp",
            command_topic=f"{mqtt_prefix}commands/SetZ2HeatRequestTemperature",
            # it can be relative (-5 -> +5, or absolute [20, ..[)
            name="Aquarea Zone 2 Heat Requested shift",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=-5,
            native_max_value=20,
            state=int,
            state_to_mqtt=int,
            on_receive=partial(
                guess_shift_or_direct_and_clamp_min_max_values,
                range(-5, 6),
                range(7, 45),
            ),
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET8",  # also TOP35
            key=f"{mqtt_prefix}main/Z2_Cool_Request_Temp",
            command_topic=f"{mqtt_prefix}commands/SetZ2CoolRequestTemperature",
            # it can be relative (-5 -> +5, or absolute [20, ..[)
            name="Aquarea Zone 2 Cool Requested shift",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=-5,
            native_max_value=25,
            state=int,
            state_to_mqtt=int,
            on_receive=partial(
                guess_shift_or_direct_and_clamp_min_max_values,
                range(-5, 6),
                range(5, 36),
            ),
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET11",  # TOP9
            key=f"{mqtt_prefix}main/DHW_Target_Temp",
            command_topic=f"{mqtt_prefix}commands/SetDHWTemp",
            name="DHW Target Temperature",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=40,
            native_max_value=65,
            state=int,
            state_to_mqtt=int,
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET15",  # also TOP95
            key=f"{mqtt_prefix}main/Max_Pump_Duty",
            command_topic=f"{mqtt_prefix}commands/SetMaxPumpDuty",
            name="Aquarea Max pump duty configured",
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement="Count",
            native_min_value=64,
            native_max_value=254,
            state=int,
            state_to_mqtt=int,
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET18",  # also corresponds to TOP23
            key=f"{mqtt_prefix}main/Heat_Delta",
            command_topic=f"{mqtt_prefix}commands/SetFloorHeatDelta",
            name="Aquarea Room heating delta",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE_DELTA,
            native_unit_of_measurement="K",
            native_min_value=1,
            native_max_value=15,
            state=int,
            state_to_mqtt=int,
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET19",  # also corresponds to TOP24
            key=f"{mqtt_prefix}main/Cool_Delta",
            command_topic=f"{mqtt_prefix}commands/SetFloorCoolDelta",
            name="Aquarea Room Cooling delta",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE_DELTA,
            native_unit_of_measurement="K",
            native_min_value=1,
            native_max_value=15,
            state=int,
            state_to_mqtt=int,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET20",  # also corresponds to TOP22
            key=f"{mqtt_prefix}main/DHW_Heat_Delta",
            command_topic=f"{mqtt_prefix}commands/SetDHWHeatDelta",
            name="Aquarea DHW heating delta",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE_DELTA,
            native_unit_of_measurement="K",
            native_min_value=-12,
            native_max_value=-2,
            state=int,
            state_to_mqtt=int,
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET21",  # also corresponds to TOP96
            key=f"{mqtt_prefix}main/Heater_Delay_Time",
            command_topic=f"{mqtt_prefix}commands/SetHeaterDelayTime",
            name="Aquarea Heater delay time",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement="min",
            native_min_value=10,
            native_max_value=60,
            state=int,
            state_to_mqtt=int,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET22",  # also corresponds to TOP97
            key=f"{mqtt_prefix}main/Heater_Start_Delta",
            command_topic=f"{mqtt_prefix}commands/SetHeaterStartDelta",
            name="Aquarea Heater start delta",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE_DELTA,
            native_unit_of_measurement="K",
            native_min_value=-10,
            native_max_value=-2,
            state=int,
            state_to_mqtt=int,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET23",  # also corresponds to TOP98
            key=f"{mqtt_prefix}main/Heater_Stop_Delta",
            command_topic=f"{mqtt_prefix}commands/SetHeaterStopDelta",
            name="Aquarea Heater stop delta",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE_DELTA,
            native_unit_of_measurement="K",
            native_min_value=-8,
            native_max_value=0,
            state=int,
            state_to_mqtt=int,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET27",  # also corresponds to TOP113
            key=f"{mqtt_prefix}main/Buffer_Tank_Delta",
            command_topic=f"{mqtt_prefix}commands/SetBufferDelta",
            name="Aquarea Buffer tank delta",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE_DELTA,
            native_unit_of_measurement="K",
            native_min_value=0,
            native_max_value=10,
            state=int,
            state_to_mqtt=int,
            entity_registry_enabled_default=False,  # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET29",  # also corresponds to TOP77
            key=f"{mqtt_prefix}main/Heating_Off_Outdoor_Temp",
            command_topic=f"{mqtt_prefix}commands/SetHeatingOffOutdoorTemp",
            name="Aquarea Outdoor temperature heating cutoff",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=5,
            native_max_value=35,
            state=int,
            state_to_mqtt=int,
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET46",  # corresponds to TOP78
            key=f"{mqtt_prefix}main/Heater_On_Outdoor_Temp",
            command_topic=f"{mqtt_prefix}commands/SetHeaterOnOutdoorTemp",
            name="Aquarea Outdoor temperature backup heater power on",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=-15,
            native_max_value=20,
            native_step=1,
            state=int,
            state_to_mqtt=int,
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SetDemandControl",
            key=f"{mqtt_prefix}commands/SetDemandControl",
            command_topic=f"{mqtt_prefix}commands/SetDemandControl",
            retain=True,
            name="Demand Control",
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement="%",
            native_min_value=5,
            native_max_value=100,
            native_step=5,
            state=read_demandcontrol,
            state_to_mqtt=write_demandcontrol,
            entity_registry_enabled_default=False,  # comes from the optional PCB: disabled by default
            initial_value=100,
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET36",  # corresponds to TOP131
            key=f"{mqtt_prefix}main/Bivalent_Start_Temp",
            command_topic=f"{mqtt_prefix}commands/SetBivalentStartTemp",
            retain=True,
            name="Aquarea Bivalent Start Temp",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=-15,
            native_max_value=35,
            native_step=1,
            state=int,
            state_to_mqtt=int,
            entity_registry_enabled_default=True,
            initial_value=0,
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET37",  # corresponds to TOP134
            key=f"{mqtt_prefix}main/Bivalent_Advanced_Start_Temp",
            command_topic=f"{mqtt_prefix}commands/SetBivalentAStartTemp",
            name="Aquarea Bivalent Advanced Start Temp",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=-15,
            native_max_value=35,
            native_step=1,
            state=int,
            state_to_mqtt=int,
            entity_registry_enabled_default=True,
            initial_value=0,
        ),
        HeishaMonNumberEntityDescription(
            heishamon_topic_id="SET38",  # corresponds to TOP135
            key=f"{mqtt_prefix}main/Bivalent_Advanced_Stop_Temp",
            command_topic=f"{mqtt_prefix}commands/SetBivalentAStopTemp",
            name="Aquarea Bivalent Advanced Stop Temp",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
            native_min_value=-15,
            native_max_value=35,
            native_step=1,
            state=int,
            state_to_mqtt=int,
            entity_registry_enabled_default=True,
            initial_value=0,
        ),
    ]
    topic_ids = {
        "1 Heat Target High": "TOP29",
        "1 Heat Target Low": "TOP30",
        "1 Heat Outside High": "TOP31",
        "1 Heat Outside Low": "TOP32",
        "1 Cool Target High": "TOP72",
        "1 Cool Target Low": "TOP73",
        "1 Cool Outside High": "TOP74",
        "1 Cool Outside Low": "TOP75",
        "2 Heat Target High": "TOP82",
        "2 Heat Target Low": "TOP83",
        "2 Heat Outside High": "TOP84",
        "2 Heat Outside Low": "TOP85",
        "2 Cool Target High": "TOP86",
        "2 Cool Target Low": "TOP87",
        "2 Cool Outside High": "TOP88",
        "2 Cool Outside Low": "TOP89",
    }
    ranges = {
        "Heat": {
            "Outside": [-20, 30],
            "Target": [15, 75],
        },
        "Cool": {
            "Outside": [15, 30],
            "Target": [5, 20],
        },
    }

    def dual_location(loc):
        if loc == "Target":
            return "Outside"
        return "Target"

    for zone_id in [1, 2]:
        for action in ["Cool", "Heat"]:
            for point in ["High", "Low"]:
                for loc in ["Target", "Outside"]:
                    numbers.append(
                        HeishaMonNumberEntityDescription(
                            heishamon_topic_id=topic_ids[
                                f"{zone_id} {action} {loc} {point}"
                            ],
                            key=f"{mqtt_prefix}main/Z{zone_id}_{action}_Curve_{loc}_{point}_Temp",
                            command_topic=f"{mqtt_prefix}commands/SetCurves",
                            entity_category=EntityCategory.CONFIG,
                            native_min_value=ranges[action][loc][0],
                            native_max_value=ranges[action][loc][1],
                            name=f"Aquarea Zone {zone_id} {loc} water temperature at {point.lower()}est {dual_location(loc).lower()} temperature on {action.lower()}ing curve",
                            device_class=NumberDeviceClass.TEMPERATURE,
                            native_unit_of_measurement="°C",
                            # by default we hide all options related to less common setup (cooling, buffer, solar and pool)
                            entity_registry_enabled_default=(action == "Heat"),
                            state=float,
                            state_to_mqtt=write_curves_gen(zone_id, action, loc, point),
                        )
                    )
    return numbers
