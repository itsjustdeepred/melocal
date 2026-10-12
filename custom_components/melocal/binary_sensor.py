"""Binary sensors for MELocal."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MelocalConfigEntry
from .api import KIND_ATA, KIND_ATW
from .entity import MelocalEntity, MelocalEntityDescription, descriptions_for


@dataclass(frozen=True, kw_only=True)
class MelocalBinarySensorDescription(MelocalEntityDescription, BinarySensorEntityDescription):
    """Binary sensor description."""


def bs(key: str, kinds=(KIND_ATW,), device_class=BinarySensorDeviceClass.RUNNING, enabled=True,
       diag=False) -> MelocalBinarySensorDescription:
    return MelocalBinarySensorDescription(
        key=key,
        translation_key=key,
        kinds=kinds,
        device_class=device_class,
        entity_registry_enabled_default=enabled,
        entity_category=EntityCategory.DIAGNOSTIC if diag else None,
    )


BINARY_SENSORS: tuple[MelocalBinarySensorDescription, ...] = (
    bs("power", kinds=(KIND_ATW, KIND_ATA), device_class=BinarySensorDeviceClass.POWER),
    bs("compressor"),
    bs("defrost"),
    bs("booster_heater_1"),
    bs("booster_heater_2", enabled=False),
    bs("immersion_heater"),
    bs("water_pump_1"),
    bs("water_pump_2"),
    bs("water_pump_3", enabled=False),
    bs("water_pump_4", enabled=False),
    bs("three_way_valve", device_class=None),
    bs("three_way_valve_2", device_class=None, enabled=False),
    bs("in1_thermostat", device_class=None),
    bs("in5_thermostat", device_class=None, enabled=False),
    bs("in6_thermostat", device_class=None, enabled=False),
    bs("dhw_forced", device_class=None),
    bs("holiday", device_class=None),
    bs("prohibit_dhw", device_class=None, diag=True),
    bs("prohibit_heating_z1", device_class=None, diag=True),
    bs("prohibit_cooling_z1", device_class=None, diag=True),
    bs("server_control", device_class=None, diag=True, enabled=False),
    bs("controller_clock_out_of_sync", device_class=BinarySensorDeviceClass.PROBLEM, diag=True),
    bs("operating", kinds=(KIND_ATA,)),
    bs("power_saving", kinds=(KIND_ATA,), device_class=None),
    bs("i_see_sensor", kinds=(KIND_ATA,), device_class=None, diag=True),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelocalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        MelocalBinarySensor(coordinator, d) for d in descriptions_for(coordinator, BINARY_SENSORS)
    )


class MelocalBinarySensor(MelocalEntity, BinarySensorEntity):
    entity_description: MelocalBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        return self.native_data
