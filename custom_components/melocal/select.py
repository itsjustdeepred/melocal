"""Zone 1 control type for Ecodan: room temperature, flow temperature or curve."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MelocalConfigEntry
from .api import KIND_ATW
from .commands import ATW_ZONE1_MODE, AtwSettings, atw_basic
from .entity import MelocalEntity, MelocalEntityDescription


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelocalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if coordinator.kind == KIND_ATW and coordinator.data.get("z1_mode"):
        async_add_entities([MelocalZoneControl(coordinator)])


class MelocalZoneControl(MelocalEntity, SelectEntity):
    _attr_translation_key = "z1_control"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, MelocalEntityDescription(key="z1_mode", kinds=(KIND_ATW,)))

    @property
    def _heating(self) -> bool:
        return not (self.native_data or "").startswith("cool")

    @property
    def options(self) -> list[str]:
        # No compensation curve in cooling.
        return ["room", "flow", "curve"] if self._heating else ["room", "flow"]

    @property
    def current_option(self) -> str | None:
        return self.native_data.split("_", 1)[1] if self.native_data else None

    async def async_select_option(self, option: str) -> None:
        new_mode = f"{'heat' if self._heating else 'cool'}_{option}"
        data = self.coordinator.data
        settings = AtwSettings.from_data(data)
        settings.z1_mode = new_mode
        if not data.get("two_zones"):
            settings.z2_mode = new_mode
        await self.coordinator.async_send_command(
            atw_basic(settings, ATW_ZONE1_MODE), optimistic={"z1_mode": new_mode}
        )
