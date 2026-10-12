"""Ecodan domestic hot water tank."""

from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MelocalConfigEntry
from .api import KIND_ATW
from .commands import (
    ATW_DHW_MODE_FLAG,
    ATW_DHW_TEMP,
    ATW_HOLIDAY,
    AtwSettings,
    atw_basic,
    atw_controller,
)
from .entity import MelocalEntity, MelocalEntityDescription

# Mitsubishi "normal" heats faster at higher power; HA calls that performance.
TO_HA = {"normal": STATE_PERFORMANCE, "eco": STATE_ECO}
FROM_HA = {v: k for k, v in TO_HA.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelocalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if coordinator.kind == KIND_ATW and coordinator.data.get("dhw_temp_target") is not None:
        async_add_entities([MelocalHotWater(coordinator)])


class MelocalHotWater(MelocalEntity, WaterHeaterEntity):
    _attr_translation_key = "hot_water"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_operation_list = list(TO_HA.values())
    _attr_min_temp = 40
    _attr_max_temp = 60
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.AWAY_MODE
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, MelocalEntityDescription(key="hot_water", kinds=(KIND_ATW,)))

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.data.get("dhw_tank_temp")

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.data.get("dhw_temp_target")

    @property
    def current_operation(self) -> str | None:
        return TO_HA.get(self.coordinator.data.get("dhw_mode"))

    @property
    def is_away_mode_on(self) -> bool | None:
        return self.coordinator.data.get("holiday")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        settings = AtwSettings.from_data(self.coordinator.data)
        settings.dhw_temp_target = round(float(temp) * 2) / 2
        await self.coordinator.async_send_command(
            atw_basic(settings, ATW_DHW_TEMP),
            optimistic={"dhw_temp_target": settings.dhw_temp_target},
        )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        settings = AtwSettings.from_data(self.coordinator.data)
        settings.dhw_mode = FROM_HA[operation_mode]
        await self.coordinator.async_send_command(
            atw_basic(settings, ATW_DHW_MODE_FLAG), optimistic={"dhw_mode": settings.dhw_mode}
        )

    async def async_turn_away_mode_on(self) -> None:
        await self.coordinator.async_send_command(
            atw_controller(ATW_HOLIDAY, True), optimistic={"holiday": True}
        )

    async def async_turn_away_mode_off(self) -> None:
        await self.coordinator.async_send_command(
            atw_controller(ATW_HOLIDAY, False), optimistic={"holiday": False}
        )
