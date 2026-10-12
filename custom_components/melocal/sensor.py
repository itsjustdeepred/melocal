"""Sensors for MELocal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MelocalConfigEntry
from .api import KIND_ATA, KIND_ATW
from .decode import (
    ATA_AUTO_MODE,
    ATA_FAN,
    ATA_MODE,
    ATA_VANE,
    ATA_WIDE_VANE,
    ATW_DHW_MODE,
    ATW_HEAT_SOURCE,
    ATW_OPERATION,
    ATW_ZONE_MODE,
)
from .entity import MelocalEntity, MelocalEntityDescription, descriptions_for

ATW = (KIND_ATW,)
ATA = (KIND_ATA,)
BOTH = (KIND_ATW, KIND_ATA)


@dataclass(frozen=True, kw_only=True)
class MelocalSensorDescription(MelocalEntityDescription, SensorEntityDescription):
    """Sensor description."""


def _two_zones(data: dict[str, Any]) -> bool:
    return bool(data.get("two_zones"))


def _has(key: str):
    return lambda data: key in data


def temp(key: str, kinds=ATW, enabled=True, diag=False, **kw) -> MelocalSensorDescription:
    return MelocalSensorDescription(
        key=key,
        translation_key=key,
        kinds=kinds,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=None if diag else SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=enabled,
        entity_category=EntityCategory.DIAGNOSTIC if diag else None,
        **kw,
    )


def enum(key: str, options: dict, kinds=ATW, **kw) -> MelocalSensorDescription:
    return MelocalSensorDescription(
        key=key,
        translation_key=key,
        kinds=kinds,
        device_class=SensorDeviceClass.ENUM,
        options=list(dict.fromkeys(options.values())),
        **kw,
    )


def energy_day(key: str) -> MelocalSensorDescription:
    return MelocalSensorDescription(
        key=key,
        translation_key=key,
        kinds=ATW,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    )


def cop_day(key: str, consumed: str) -> MelocalSensorDescription:
    return MelocalSensorDescription(
        key=key,
        translation_key=key,
        kinds=ATW,
        suggested_display_precision=2,
        exists_fn=_has(consumed),
    )


DIAG = EntityCategory.DIAGNOSTIC

SENSORS: tuple[MelocalSensorDescription, ...] = (
    # --- Ecodan temperatures
    temp("outside_temp"),
    temp("z1_room_temp"),
    temp("z2_room_temp", exists_fn=_two_zones),
    temp("flow_temp"),
    temp("return_temp"),
    temp("dhw_tank_temp"),
    temp("dhw_secondary_temp", enabled=False),
    temp("z1_flow_temp"),
    temp("z1_return_temp"),
    temp("z2_flow_temp", exists_fn=_two_zones),
    temp("z2_return_temp", exists_fn=_two_zones),
    temp("boiler_flow_temp", enabled=False),
    temp("boiler_return_temp", enabled=False),
    temp("mixing_tank_temp", enabled=False),
    temp("refrigerant_liquid_temp", enabled=False),
    temp("condensing_temp", enabled=False),
    temp("z1_room_temp_target", diag=False),
    temp("z1_flow_temp_target"),
    temp("z2_room_temp_target", exists_fn=_two_zones),
    temp("z2_flow_temp_target", exists_fn=_two_zones),
    temp("dhw_temp_target"),
    temp("legionella_temp", diag=True),
    temp("max_flow_temp", diag=True),
    temp("min_flow_temp", diag=True),
    temp("dhw_temp_drop", diag=True, enabled=False),
    # --- Ecodan state
    enum("operation", ATW_OPERATION),
    enum("z1_mode", ATW_ZONE_MODE),
    enum("z2_mode", ATW_ZONE_MODE, exists_fn=_two_zones),
    enum("dhw_mode", ATW_DHW_MODE),
    enum("heat_source", ATW_HEAT_SOURCE),
    MelocalSensorDescription(
        key="flow_rate",
        translation_key="flow_rate",
        kinds=ATW,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MelocalSensorDescription(
        key="heat_output",
        translation_key="heat_output",
        kinds=ATW,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MelocalSensorDescription(
        key="thermal_power",
        translation_key="thermal_power",
        kinds=ATW,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    MelocalSensorDescription(
        key="power_consumption_estimated",
        translation_key="power_consumption_estimated",
        kinds=ATW,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=_has("energy_consumed_total"),
    ),
    MelocalSensorDescription(
        key="pump_speed",
        translation_key="pump_speed",
        kinds=ATW,
        entity_category=DIAG,
        entity_registry_enabled_default=False,
    ),
    MelocalSensorDescription(
        key="mixing_valve_step",
        translation_key="mixing_valve_step",
        kinds=ATW,
        entity_category=DIAG,
        entity_registry_enabled_default=False,
    ),
    energy_day("consumed_heating_day"),
    energy_day("consumed_cooling_day"),
    energy_day("consumed_dhw_day"),
    energy_day("delivered_heating_day"),
    energy_day("delivered_cooling_day"),
    energy_day("delivered_dhw_day"),
    cop_day("cop_heating_day", "consumed_heating_day"),
    cop_day("cop_cooling_day", "consumed_cooling_day"),
    cop_day("cop_dhw_day", "consumed_dhw_day"),
    MelocalSensorDescription(key="energy_day", translation_key="energy_day", kinds=ATW, entity_category=DIAG),
    MelocalSensorDescription(key="fault_code", translation_key="fault_code", kinds=ATW, entity_category=DIAG),
    MelocalSensorDescription(
        key="controller_time", translation_key="controller_time", kinds=ATW, entity_category=DIAG
    ),
    MelocalSensorDescription(
        key="controller_clock_offset",
        translation_key="controller_clock_offset",
        kinds=ATW,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=DIAG,
        exists_fn=_has("controller_time"),
    ),
    # --- Air conditioner
    temp("room_temp", kinds=ATA),
    temp("target_temp", kinds=ATA),
    temp("outside_temp", kinds=ATA),
    enum("mode", ATA_MODE, kinds=ATA),
    enum("fan_speed", ATA_FAN, kinds=ATA),
    enum("vane_vertical", ATA_VANE, kinds=ATA),
    enum("vane_horizontal", ATA_WIDE_VANE, kinds=ATA),
    enum("auto_mode", ATA_AUTO_MODE, kinds=ATA),
    MelocalSensorDescription(
        key="power_consumption",
        translation_key="power_consumption",
        kinds=ATA,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MelocalSensorDescription(
        key="dehumidification_setting",
        translation_key="dehumidification_setting",
        kinds=ATA,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=DIAG,
        entity_registry_enabled_default=False,
    ),
    MelocalSensorDescription(key="error_code", translation_key="error_code", kinds=ATA, entity_category=DIAG),
    # --- Both
    MelocalSensorDescription(
        key="energy_consumed_total",
        translation_key="energy_consumed_total",
        kinds=BOTH,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    MelocalSensorDescription(
        key="compressor_frequency",
        translation_key="compressor_frequency",
        kinds=BOTH,
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MelocalSensorDescription(
        key="runtime",
        translation_key="runtime",
        kinds=BOTH,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=DIAG,
    ),
    MelocalSensorDescription(
        key="rssi",
        translation_key="rssi",
        kinds=BOTH,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=DIAG,
    ),
    MelocalSensorDescription(
        key="adapter_firmware", translation_key="adapter_firmware", kinds=BOTH, entity_category=DIAG,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelocalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        MelocalSensor(coordinator, d) for d in descriptions_for(coordinator, SENSORS)
    )


class MelocalSensor(MelocalEntity, SensorEntity):
    entity_description: MelocalSensorDescription

    @property
    def native_value(self) -> Any:
        return self.native_data

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key.endswith("_day") and self.entity_description.key != "energy_day":
            return {"day": self.coordinator.data.get("energy_day")}
        return None
