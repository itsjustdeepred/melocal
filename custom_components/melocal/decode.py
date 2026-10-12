"""Decoders for CN105 frames.

ATW (Ecodan) mapping after gekkekoe/esphome-ecodan-hp and F1p's protocol notes.
ATA (air conditioner) mapping after pymitsubishi.
Byte offsets for ATW are relative to the payload (p[0] = group code),
for ATA relative to the full frame, mirroring the reference projects.
"""

from __future__ import annotations

from typing import Any

ATW_OPERATION = {0: "off", 1: "dhw", 2: "heating", 3: "cooling", 5: "frost_protection", 6: "legionella"}
ATW_ZONE_MODE = {0: "heat_room", 1: "heat_flow", 2: "heat_curve", 3: "cool_room", 4: "cool_flow"}
ATW_DHW_MODE = {0: "normal", 1: "eco"}
ATW_HEAT_SOURCE = {0: "heatpump", 1: "screw_in_heater", 2: "electric_heater", 3: "boiler"}

ATA_MODE = {0: "auto", 1: "heat", 2: "dry", 3: "cool", 7: "fan_only"}
ATA_FAN = {0: "auto", 1: "speed_1", 2: "speed_2", 3: "speed_3", 5: "speed_4", 6: "full"}
ATA_VANE = {0: "auto", 1: "position_1", 2: "position_2", 3: "position_3", 4: "position_4",
            5: "position_5", 7: "swing"}
ATA_WIDE_VANE = {0: "auto", 1: "far_left", 2: "left", 3: "center", 4: "right", 5: "far_right",
                 6: "left_center", 7: "center_right", 8: "left_right", 9: "left_center_right",
                 12: "swing"}
ATA_AUTO_MODE = {0: "off", 1: "switching", 2: "auto_heating", 3: "auto_cooling"}


def _f16(p: bytes, i: int) -> float:
    return ((p[i] << 8) | p[i + 1]) / 100


def _s16(p: bytes, i: int) -> float:
    return int.from_bytes(p[i:i + 2], "big", signed=True) / 100


def _f24(p: bytes, i: int) -> float:
    return round(((p[i] << 8) | p[i + 1]) + p[i + 2] / 100, 2)


def _bit(value: int, bit: int) -> bool:
    return bool(value & (1 << bit))


def decode_atw(frames: dict[int, bytes]) -> dict[str, Any]:
    s: dict[str, Any] = {}

    def payload(group: int) -> bytes | None:
        frame = frames.get(group)
        return frame[5:-1] if frame else None

    if p := payload(0x01):
        s["controller_time"] = f"20{p[1]:02d}-{p[2]:02d}-{p[3]:02d} {p[4]:02d}:{p[5]:02d}:{p[6]:02d}"
        s["controller_firmware"] = f"{p[7]:02X}.{p[8]:02X}"
    if p := payload(0x02):
        s["defrost"] = p[3] != 0
    if p := payload(0x03):
        num = (p[2] << 8) | p[3]
        s["fault_code"] = "none" if num == 0x8000 else (
            f"{chr(p[4]) if p[4] > 0x20 else ''}{chr(p[5]) if p[5] > 0x20 else ''}{num}")
        s["refrigerant_error_code"] = p[1]
    if p := payload(0x04):
        s["compressor_frequency"] = p[1]
    if p := payload(0x05):
        s["heat_source"] = ATW_HEAT_SOURCE.get(p[6])
    if p := payload(0x07):
        s["heat_output"] = p[6]
        s["energy_consumed_total"] = ((p[11] << 8) | p[12]) / 10
    if p := payload(0x09):
        s["z1_room_temp_target"] = _f16(p, 1)
        s["z2_room_temp_target"] = _f16(p, 3)
        s["z1_flow_temp_target"] = _f16(p, 5)
        s["z2_flow_temp_target"] = _f16(p, 7)
        s["legionella_temp"] = _f16(p, 9)
        s["dhw_temp_drop"] = (p[11] - 40) / 2
        s["max_flow_temp"] = (p[12] - 40) / 2
        s["min_flow_temp"] = (p[13] - 40) / 2
    if p := payload(0x0B):
        # 0xF0 marks a sensor that is not installed
        s["z1_room_temp"] = _f16(p, 1) if p[1] != 0xF0 else None
        s["z2_room_temp"] = _f16(p, 3) if p[3] != 0xF0 else None
        s["refrigerant_liquid_temp"] = _s16(p, 8)
        s["outside_temp"] = p[11] / 2 - 40
    if p := payload(0x0C):
        s["flow_temp"] = _f16(p, 1)
        s["return_temp"] = _f16(p, 4)
        s["dhw_tank_temp"] = _f16(p, 7)
        s["dhw_secondary_temp"] = _f16(p, 10)
    if p := payload(0x0D):
        s["z1_flow_temp"] = _f16(p, 1)
        s["z1_return_temp"] = _f16(p, 4)
        s["z2_flow_temp"] = _f16(p, 7)
        s["z2_return_temp"] = _f16(p, 10)
    if p := payload(0x0E):
        s["boiler_flow_temp"] = _f16(p, 1)
        s["boiler_return_temp"] = _f16(p, 4)
    if p := payload(0x0F):
        s["mixing_tank_temp"] = _f16(p, 1)
        s["condensing_temp"] = _s16(p, 4)
    if p := payload(0x10):
        s["in1_thermostat"] = p[1] != 0
        s["in6_thermostat"] = p[2] != 0
        s["in5_thermostat"] = p[3] != 0
    if p := payload(0x11):
        sw2, sw3 = p[3], p[5]
        s["two_zones"] = (_bit(sw3, 5) and not _bit(sw2, 6)) or (_bit(sw2, 5) and _bit(sw2, 6))
        s["has_cooling"] = _bit(sw2, 3)  # SW2-4
    if p := payload(0x13):
        s["compressor"] = p[1] != 0
        s["runtime"] = ((p[4] << 8) | p[5]) * 100 + p[3]
    if p := payload(0x14):
        s["booster_heater_1"] = p[2] != 0
        s["booster_heater_2"] = p[3] != 0
        s["immersion_heater"] = p[5] != 0
        s["flow_rate"] = p[12]
    if p := payload(0x15):
        s["water_pump_1"] = p[1] != 0
        s["pump_speed"] = {52: 1, 41: 2, 31: 3, 20: 4, 0: 5}.get(p[2], 0)
        s["water_pump_2"] = p[4] != 0
        s["water_pump_3"] = p[5] != 0
        s["three_way_valve"] = p[6] != 0
        s["three_way_valve_2"] = p[7] != 0
        s["mixing_valve_step"] = p[10]
    if p := payload(0x16):
        s["water_pump_4"] = p[1] != 0
    if p := payload(0x26):
        s["power"] = p[3] == 1
        s["operation"] = ATW_OPERATION.get(p[4])
        s["dhw_mode"] = ATW_DHW_MODE.get(p[5])
        s["z1_mode"] = ATW_ZONE_MODE.get(p[6])
        s["z2_mode"] = ATW_ZONE_MODE.get(p[7])
        s["dhw_temp_target"] = _f16(p, 8)
    if p := payload(0x28):
        for i, key in enumerate(("dhw_forced", "holiday", "prohibit_dhw", "prohibit_heating_z1",
                                 "prohibit_cooling_z1", "prohibit_heating_z2",
                                 "prohibit_cooling_z2", "server_control"), start=3):
            s[key] = p[i] != 0
    if p := payload(0xA1):
        s["energy_day"] = f"20{p[1]:02d}-{p[2]:02d}-{p[3]:02d}"
        s["consumed_heating_day"] = _f24(p, 4)
        s["consumed_cooling_day"] = _f24(p, 7)
        s["consumed_dhw_day"] = _f24(p, 10)
    if p := payload(0xA2):
        s["delivered_heating_day"] = _f24(p, 4)
        s["delivered_cooling_day"] = _f24(p, 7)
        s["delivered_dhw_day"] = _f24(p, 10)
    for mode in ("heating", "cooling", "dhw"):
        consumed = s.get(f"consumed_{mode}_day")
        delivered = s.get(f"delivered_{mode}_day")
        if consumed is not None and delivered is not None:
            s[f"cop_{mode}_day"] = round(delivered / consumed, 2) if consumed > 0 else None
    return s


def decode_ata(frames: dict[int, bytes]) -> dict[str, Any]:
    s: dict[str, Any] = {}
    half = lambda b: (b - 0x80) / 2  # noqa: E731

    if d := frames.get(0x02):
        s["power"] = d[8] == 1
        s["mode"] = ATA_MODE.get(d[9] & 0x07)
        s["i_see_sensor"] = bool(d[9] & 0x08)
        s["target_temp"] = half(d[16]) if d[16] else 31 - d[10]
        s["fan_speed"] = ATA_FAN.get(d[11])
        s["vane_vertical"] = ATA_VANE.get(d[12])
        s["vane_horizontal"] = ATA_WIDE_VANE.get(d[15] & 0x7F)
        s["dehumidification_setting"] = d[17]
        s["power_saving"] = d[18] > 0
    if d := frames.get(0x03):
        s["room_temp"] = half(d[11])
        s["outside_temp"] = half(d[10]) if d[10] >= 0x80 else None
        s["runtime"] = round(int.from_bytes(d[15:19], "big") / 60, 1)
    if d := frames.get(0x04):
        code = int.from_bytes(d[9:11], "big")
        s["error_code"] = "none" if code == 0x8000 else f"{code:04x}"
    if d := frames.get(0x06):
        s["compressor_frequency"] = d[8]
        s["operating"] = bool(d[9])
        s["power_consumption"] = int.from_bytes(d[10:12], "big")
        s["energy_consumed_total"] = int.from_bytes(d[12:14], "big") / 10
    if d := frames.get(0x09):
        s["auto_mode"] = ATA_AUTO_MODE.get(d[10])
    return s
