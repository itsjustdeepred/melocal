"""Decoder tests against captured adapter answers (no Home Assistant needed)."""

import importlib
from pathlib import Path
import sys
import types

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"

# Import the HA-free modules without running the package __init__ (needs HA).
_pkg = types.ModuleType("melocal_lib")
_pkg.__path__ = [str(ROOT / "custom_components" / "melocal")]
sys.modules["melocal_lib"] = _pkg


def _load(name):
    return importlib.import_module(f"melocal_lib.{name}")


api = _load("api")
decode = _load("decode")


def _state(name):
    return api.AdapterState.from_xml((FIXTURES / f"{name}.xml").read_text())


def test_crypto_roundtrip():
    text = "<CSV><CONNECT>ON</CONNECT></CSV>"
    assert api.decrypt(api.encrypt(text)) == text


def test_atw_adapter_info():
    state = _state("atw")
    assert state.kind == api.KIND_ATW
    assert state.mac == "00:11:22:33:44:55"
    assert state.rssi == -85
    assert 0x0C in state.frames and 0xA2 in state.frames


def test_atw_values():
    d = decode.decode_atw(_state("atw").frames)
    assert d["dhw_tank_temp"] == 55.5
    assert d["dhw_temp_target"] == 55.0
    assert d["z1_room_temp"] == 30.0
    assert d["z2_room_temp"] is None
    assert d["z1_flow_temp_target"] == 15.0
    assert d["boiler_flow_temp"] == 25.0
    assert d["condensing_temp"] == 40.57
    assert d["operation"] == "cooling"
    assert d["z1_mode"] == "cool_flow"
    assert d["two_zones"] is False
    assert d["fault_code"] == "none"
    assert d["consumed_cooling_day"] == 6.97
    assert d["delivered_cooling_day"] == 29.12
    assert d["consumed_dhw_day"] == 3.31
    assert d["cop_cooling_day"] == round(29.12 / 6.97, 2)
    assert d["cop_heating_day"] is None
    assert d["energy_consumed_total"] > 2700


def test_ata_values():
    state = _state("ata")
    assert state.kind == api.KIND_ATA
    d = decode.decode_ata(state.frames)
    assert d["power"] is False
    assert d["mode"] == "cool"
    assert d["target_temp"] == 23.0
    assert d["room_temp"] == 23.5
    assert d["outside_temp"] is None
    assert d["energy_consumed_total"] == 1530.9
    assert d["power_consumption"] == 1
    assert d["error_code"] == "none"


def test_unsupported_response():
    try:
        api.AdapterState.from_xml("<LSV></LSV>")
    except api.MelocalUnsupported:
        return
    raise AssertionError("expected MelocalUnsupported")


def test_power_estimator():
    est = _load("estimator").EnergyRateEstimator()
    assert est.update(100.0, 0) is None  # baseline
    assert est.update(100.1, 100) is None  # first step only syncs
    assert est.update(100.2, 460) == 1000  # 0.1 kWh in 360 s = 1 kW
    assert est.update(100.2, 820) == 1000  # still within one step
    assert est.update(100.2, 1180) == 500  # no step for 720 s: at most 500 W
    assert est.update(100.3, 1200) == 486  # 0.1 kWh since the step at 460 s
    assert est.update(5.0, 1300) is None  # counter reset


commands = _load("commands")


def test_ata_command_matches_pymitsubishi():
    settings = commands.AtaSettings(
        power=True, mode="cool", target_temp=24.0, fan_speed="full",
        vane_vertical="position_1", vane_horizontal="center",
    )
    packet = commands.ata_general(settings, commands.ATA_POWER | commands.ATA_MODE_FLAG)
    assert packet.hex() == "fc410130100103020103070601000000000003b04172"


def test_atw_command_matches_pymitsubishi():
    # pymitsubishi's packet verified on an FTC6 (flags Z1+Z2 setpoint).
    settings = commands.AtwSettings(
        power=True, dhw_mode="normal", z1_mode="cool_flow", z2_mode="cool_flow",
        dhw_temp_target=55.0, z1_target=16.0, z2_target=20.0,
    )
    packet = commands.atw_basic(settings, commands.ATW_ZONE1_TEMP | commands.ATW_ZONE2_TEMP)
    assert packet.hex() == "fc41027a103280020100000404157c064007d00000c8"


def test_atw_settings_from_real_data():
    d = decode.decode_atw(_state("atw").frames)
    settings = commands.AtwSettings.from_data(d)
    assert settings.z1_mode == "cool_flow"
    assert settings.z1_target == d["z1_flow_temp_target"]
    packet = commands.atw_basic(settings, commands.ATW_DHW_TEMP)
    assert api.checksum_ok(packet) and packet[5] == 0x32 and packet[6] == 0x20


def test_atw_controller_packets():
    assert commands.atw_controller(commands.ATW_FORCED_DHW, True)[5:9].hex() == "34010001"
    assert commands.atw_controller(commands.ATW_HOLIDAY, True)[5:10].hex() == "3402000001"


def test_power_estimator_smooths_irregular_steps():
    # ~4 kW seen at 30 s polling: steps arrive alternately after 60 s and 120 s.
    est = _load("estimator").EnergyRateEstimator()
    t, v = 0, 2772.4
    est.update(v, t)
    readings = []
    for gap in [60, 120] * 8:
        t += gap
        v = round(v + 0.1, 1)
        readings.append(est.update(v, t))
    settled = [p for p in readings[4:] if p is not None]
    assert settled and all(3500 <= p <= 4500 for p in settled), settled


def test_ata_auto_mode_byte():
    # CN105 AUTO is 0x08; 0 is ignored by the unit, which keeps its previous mode.
    settings = commands.AtaSettings(
        power=True, mode="auto", target_temp=23.0, fan_speed="auto",
        vane_vertical="auto", vane_horizontal="auto",
    )
    assert commands.ata_general(settings, commands.ATA_MODE_FLAG)[9] == 0x08
    frame = bytearray(22)
    frame[16] = 0x80 + 46
    for raw, mode, i_see in ((0x08, "auto", False), (0x03, "cool", False), (0x09, "heat", True)):
        frame[9] = raw
        d = decode.decode_ata({0x02: bytes(frame)})
        assert (d["mode"], d["i_see_sensor"]) == (mode, i_see)
