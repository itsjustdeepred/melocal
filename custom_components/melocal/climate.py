"""Climate entities: air conditioner and Ecodan zone 1."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MelocalConfigEntry
from .api import KIND_ATA, KIND_ATW
from .commands import (
    ATA_FAN_FLAG,
    ATA_MODE_FLAG,
    ATA_POWER,
    ATA_TEMP,
    ATA_VANE_FLAG,
    ATA_WIDE_VANE_FLAG,
    ATW_ZONE1_MODE,
    ATW_ZONE1_TEMP,
    AtaSettings,
    AtwSettings,
    ata_general,
    atw_basic,
    zone_target,
)
from .decode import ATA_FAN, ATA_VANE, ATA_WIDE_VANE
from .entity import MelocalEntity, MelocalEntityDescription

ATA_HVAC = {
    "auto": HVACMode.HEAT_COOL,
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "dry": HVACMode.DRY,
    "fan_only": HVACMode.FAN_ONLY,
}
ATA_ACTION = {
    "heat": HVACAction.HEATING,
    "cool": HVACAction.COOLING,
    "dry": HVACAction.DRYING,
    "fan_only": HVACAction.FAN,
}

# Zone control type ("room", "flow", "curve") per HVAC mode.
ZONE_MODES = {
    (HVACMode.HEAT, "room"): "heat_room",
    (HVACMode.HEAT, "flow"): "heat_flow",
    (HVACMode.HEAT, "curve"): "heat_curve",
    (HVACMode.COOL, "room"): "cool_room",
    (HVACMode.COOL, "flow"): "cool_flow",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelocalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if coordinator.kind == KIND_ATA:
        async_add_entities([MelocalAirConditioner(coordinator)])
    elif coordinator.kind == KIND_ATW and coordinator.data.get("z1_mode"):
        async_add_entities([MelocalEcodanZone(coordinator)])


class _Climate(MelocalEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class MelocalAirConditioner(_Climate):
    _attr_name = None
    _attr_translation_key = "air_conditioner"
    _attr_hvac_modes = [HVACMode.OFF, *ATA_HVAC.values()]
    _attr_fan_modes = list(ATA_FAN.values())
    _attr_swing_modes = list(ATA_VANE.values())
    _attr_swing_horizontal_modes = list(ATA_WIDE_VANE.values())
    _attr_min_temp = 16
    _attr_max_temp = 31
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.SWING_HORIZONTAL_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, MelocalEntityDescription(key="climate", kinds=(KIND_ATA,)))

    @property
    def _data(self) -> dict[str, Any]:
        return self.coordinator.data

    @property
    def hvac_mode(self) -> HVACMode | None:
        if not self._data.get("power"):
            return HVACMode.OFF
        return ATA_HVAC.get(self._data.get("mode"))

    @property
    def hvac_action(self) -> HVACAction | None:
        if not self._data.get("power"):
            return HVACAction.OFF
        if not self._data.get("operating"):
            return HVACAction.IDLE
        mode = self._data.get("mode")
        if mode == "auto":
            return {"auto_heating": HVACAction.HEATING, "auto_cooling": HVACAction.COOLING}.get(
                self._data.get("auto_mode"), HVACAction.IDLE
            )
        return ATA_ACTION.get(mode)

    @property
    def current_temperature(self) -> float | None:
        return self._data.get("room_temp")

    @property
    def target_temperature(self) -> float | None:
        return self._data.get("target_temp")

    @property
    def fan_mode(self) -> str | None:
        return self._data.get("fan_speed")

    @property
    def swing_mode(self) -> str | None:
        return self._data.get("vane_vertical")

    @property
    def swing_horizontal_mode(self) -> str | None:
        return self._data.get("vane_horizontal")

    async def _send(self, flags: int, **changes: Any) -> None:
        settings = AtaSettings.from_data(self._data)
        for key, value in changes.items():
            setattr(settings, key, value)
        await self.coordinator.async_send_command(
            ata_general(settings, flags), optimistic=changes
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self._send(ATA_POWER, power=False)
            return
        mode = next(k for k, v in ATA_HVAC.items() if v == hvac_mode)
        await self._send(ATA_POWER | ATA_MODE_FLAG, power=True, mode=mode)

    async def async_turn_on(self) -> None:
        await self._send(ATA_POWER, power=True)

    async def async_turn_off(self) -> None:
        await self._send(ATA_POWER, power=False)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(hvac_mode)
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._send(ATA_TEMP, target_temp=round(float(temp) * 2) / 2)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self._send(ATA_FAN_FLAG, fan_speed=fan_mode)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        await self._send(ATA_VANE_FLAG, vane_vertical=swing_mode)

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        await self._send(ATA_WIDE_VANE_FLAG, vane_horizontal=swing_horizontal_mode)


class MelocalEcodanZone(_Climate):
    """Zone 1 heating/cooling. Off is not offered: it would stop hot water too."""

    _attr_translation_key = "zone_1"
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, MelocalEntityDescription(key="zone_1", kinds=(KIND_ATW,)))

    @property
    def _data(self) -> dict[str, Any]:
        return self.coordinator.data

    @property
    def _mode(self) -> str:
        return self._data.get("z1_mode") or "heat_flow"

    @property
    def _control(self) -> str:
        return self._mode.split("_", 1)[1]

    @property
    def hvac_modes(self) -> list[HVACMode]:
        if self._data.get("has_cooling"):
            return [HVACMode.HEAT, HVACMode.COOL]
        return [HVACMode.HEAT]

    @property
    def supported_features(self) -> ClimateEntityFeature:
        # Compensation curve: the FTC computes the flow target itself.
        if self._control == "curve":
            return ClimateEntityFeature(0)
        return ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.COOL if self._mode.startswith("cool") else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        if not self._data.get("power"):
            return HVACAction.OFF
        operation = self._data.get("operation")
        if operation == "heating":
            return HVACAction.HEATING
        if operation == "cooling":
            return HVACAction.COOLING
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        if self._control == "flow":
            return self._data.get("flow_temp")
        return self._data.get("z1_room_temp")

    @property
    def target_temperature(self) -> float | None:
        if self._control == "curve":
            return None
        return zone_target(self._data, 1)

    @property
    def min_temp(self) -> float:
        if self._control == "room":
            return 10
        return 5 if self.hvac_mode == HVACMode.COOL else self._data.get("min_flow_temp") or 20

    @property
    def max_temp(self) -> float:
        if self._control == "room":
            return 30
        return 25 if self.hvac_mode == HVACMode.COOL else self._data.get("max_flow_temp") or 60

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        control = self._control
        if hvac_mode == HVACMode.COOL and control == "curve":
            control = "flow"
        new_mode = ZONE_MODES[(hvac_mode, control)]
        settings = AtwSettings.from_data(self._data)
        settings.z1_mode = new_mode
        if not self._data.get("two_zones"):
            settings.z2_mode = new_mode
        await self.coordinator.async_send_command(
            atw_basic(settings, ATW_ZONE1_MODE), optimistic={"z1_mode": new_mode}
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        temp = round(float(temp) * 2) / 2
        settings = AtwSettings.from_data(self._data)
        settings.z1_target = temp
        key = "z1_room_temp_target" if self._control == "room" else "z1_flow_temp_target"
        await self.coordinator.async_send_command(
            atw_basic(settings, ATW_ZONE1_TEMP), optimistic={key: temp}
        )
