"""EnergyIntegrationEntity builds against the installed IntegrationSensor."""
from datetime import timedelta

from homeassistant.components.integration.const import METHOD_LEFT
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfTime

from custom_components.aquarea.sensor import EnergyIntegrationEntity


def test_energy_integration_entity_construction():
    # Same arguments as async_setup_entry in sensor.py.
    entity = EnergyIntegrationEntity(
        None,
        integration_method=METHOD_LEFT,
        name="Aquarea Heat Power Consumed Total",
        round_digits=3,
        source_entity="sensor.aquarea_heat_power_consumed",
        unique_id="aquarea_heat_power_consumed_integration",
        unit_prefix="k",
        unit_time=UnitOfTime.HOURS,
        max_sub_interval=timedelta(minutes=5),
    )

    assert entity.unique_id == "aquarea_heat_power_consumed_integration"
    assert entity.device_class == SensorDeviceClass.ENERGY
