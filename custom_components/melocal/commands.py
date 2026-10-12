"""CN105 SET (0x41) packet builders.

ATA after pymitsubishi (``GeneralStates.generate_general_command``).
ATW after pymitsubishi ``mitsubishi_atw`` and gekkekoe/esphome-ecodan-hp: every
0x32 packet repeats the unit's current values and flags only the changed field,
so nothing else moves even if the FTC acted on an unflagged byte.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .decode import ATA_FAN, ATA_MODE, ATA_VANE, ATA_WIDE_VANE, ATW_DHW_MODE, ATW_ZONE_MODE

SET_REQUEST = 0x41


def _frame(body: bytes) -> bytes:
    assert len(body) == 20
    return b"\xfc" + body + bytes([(0x100 - sum(body) % 0x100) % 0x100])


def _code(mapping: dict[int, str], value: str) -> int:
    for code, name in mapping.items():
        if name == value:
            return code
    raise ValueError(f"unknown value {value!r}")


# --- Air-to-air ---------------------------------------------------------------

ATA_POWER = 0x0100
ATA_MODE_FLAG = 0x0200
ATA_TEMP = 0x0400
ATA_FAN_FLAG = 0x0800
ATA_VANE_FLAG = 0x1000
ATA_WIDE_VANE_FLAG = 0x0001
ATA_OUTSIDE_CONTROL = 0x0002


@dataclass
class AtaSettings:
    power: bool
    mode: str
    target_temp: float
    fan_speed: str
    vane_vertical: str
    vane_horizontal: str

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> AtaSettings:
        return cls(
            power=data["power"],
            mode=data["mode"],
            target_temp=data["target_temp"],
            fan_speed=data["fan_speed"],
            vane_vertical=data["vane_vertical"],
            vane_horizontal=data["vane_horizontal"],
        )


def ata_general(settings: AtaSettings, flags: int) -> bytes:
    body = bytearray(20)
    body[0:5] = bytes([SET_REQUEST, 0x01, 0x30, 0x10, 0x01])
    body[5:7] = (flags | ATA_OUTSIDE_CONTROL).to_bytes(2, "big")
    body[7] = 1 if settings.power else 0
    body[8] = _code(ATA_MODE, settings.mode)
    body[9] = 31 - int(settings.target_temp)
    body[10] = _code(ATA_FAN, settings.fan_speed)
    body[11] = _code(ATA_VANE, settings.vane_vertical)
    body[17] = _code(ATA_WIDE_VANE, settings.vane_horizontal)
    body[18] = 0x80 + int(round(settings.target_temp * 2))
    body[19] = 0x41
    return _frame(bytes(body))


# --- Air-to-water (Ecodan) ----------------------------------------------------

ATW_POWER = 0x0001
ATW_DHW_MODE_FLAG = 0x0004
ATW_ZONE1_MODE = 0x0008
ATW_ZONE2_MODE = 0x0010
ATW_DHW_TEMP = 0x0020
ATW_ZONE1_TEMP = 0x0080
ATW_ZONE2_TEMP = 0x0200

ATW_FORCED_DHW = 0x01
ATW_HOLIDAY = 0x02


def _atw(payload: list[int]) -> bytes:
    assert len(payload) == 16
    return _frame(bytes([SET_REQUEST, 0x02, 0x7A, 0x10, *payload]))


def _u16(value: float) -> tuple[int, int]:
    raw = int(round(value * 100))
    return (raw >> 8) & 0xFF, raw & 0xFF


@dataclass
class AtwSettings:
    power: bool
    dhw_mode: str
    z1_mode: str
    z2_mode: str
    dhw_temp_target: float
    z1_target: float
    z2_target: float

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> AtwSettings:
        return cls(
            power=data["power"],
            dhw_mode=data["dhw_mode"],
            z1_mode=data["z1_mode"],
            z2_mode=data.get("z2_mode") or data["z1_mode"],
            dhw_temp_target=data["dhw_temp_target"],
            z1_target=zone_target(data, 1),
            z2_target=zone_target(data, 2),
        )


def zone_target(data: dict[str, Any], zone: int) -> float:
    """The setpoint that matters for the zone's control mode."""
    mode = data.get(f"z{zone}_mode") or data.get("z1_mode")
    if mode in ("heat_room", "cool_room"):
        return data[f"z{zone}_room_temp_target"]
    return data[f"z{zone}_flow_temp_target"]


def atw_basic(settings: AtwSettings, flags: int) -> bytes:
    """SET 0x32: power, DHW mode, zone modes and setpoints."""
    return _atw(
        [
            0x32,
            flags & 0xFF,
            (flags >> 8) & 0xFF,
            1 if settings.power else 0,
            0,
            _code(ATW_DHW_MODE, settings.dhw_mode),
            _code(ATW_ZONE_MODE, settings.z1_mode),
            _code(ATW_ZONE_MODE, settings.z2_mode),
            *_u16(settings.dhw_temp_target),
            *_u16(settings.z1_target),
            *_u16(settings.z2_target),
            0,
            0,
        ]
    )


def atw_controller(flag: int, on: bool) -> bytes:
    """SET 0x34: forced DHW (byte 3) or holiday mode (byte 4)."""
    payload = [0x34, flag] + [0] * 14
    payload[3 if flag == ATW_FORCED_DHW else 4] = 1 if on else 0
    return _atw(payload)
