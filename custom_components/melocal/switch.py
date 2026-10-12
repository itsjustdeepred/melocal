"""Switches for MELocal."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MelocalConfigEntry
from .api import KIND_ATW
from .commands import ATW_FORCED_DHW, ATW_POWER, AtwSettings, atw_basic, atw_controller
from .coordinator import MelocalCoordinator
from .entity import MelocalEntity, MelocalEntityDescription, descriptions_for


async def _forced_dhw(coordinator: MelocalCoordinator, on: bool) -> None:
    await coordinator.async_send_command(
        atw_controller(ATW_FORCED_DHW, on), optimistic={"dhw_forced": on}
    )


async def _atw_power(coordinator: MelocalCoordinator, on: bool) -> None:
    settings = AtwSettings.from_data(coordinator.data)
    settings.power = on
    await coordinator.async_send_command(atw_basic(settings, ATW_POWER), optimistic={"power": on})


@dataclass(frozen=True, kw_only=True)
class MelocalSwitchDescription(MelocalEntityDescription, SwitchEntityDescription):
    set_fn: Callable[[MelocalCoordinator, bool], Awaitable[None]]


SWITCHES: tuple[MelocalSwitchDescription, ...] = (
    MelocalSwitchDescription(
        key="dhw_forced",
        translation_key="dhw_forced",
        kinds=(KIND_ATW,),
        set_fn=_forced_dhw,
    ),
    MelocalSwitchDescription(
        key="power",
        translation_key="system_power",
        kinds=(KIND_ATW,),
        entity_category=EntityCategory.CONFIG,
        set_fn=_atw_power,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelocalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        MelocalSwitch(coordinator, d) for d in descriptions_for(coordinator, SWITCHES)
    )


class MelocalSwitch(MelocalEntity, SwitchEntity):
    entity_description: MelocalSwitchDescription

    @property
    def is_on(self) -> bool | None:
        return self.native_data

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.entity_description.set_fn(self.coordinator, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.set_fn(self.coordinator, False)
