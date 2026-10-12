# Changelog

## 1.0.0

First public release.

### Features
- **Local API**: reads and controls Mitsubishi Electric units through the MELCloud Wi-Fi adapter's local `/smart` endpoint, without the cloud.
- **Setup**: network scan (CIDR) or manual IP; units are detected automatically (Ecodan air-to-water or air-to-air) and identified by MAC, so IP changes are picked up on re-scan. Extra units found by a scan appear under *Discovered*.
- **Ecodan**: hot water `water_heater`, zone 1 `climate` and control-type `select`, forced hot water and system power switches, and sensors for temperatures, modes, pumps, valves, heaters, energy, COP / EER, estimated electrical power and calculated thermal power.
- **Air conditioner**: `climate` entity (mode, target, fan, vanes) and sensors including instantaneous power in W.
- **Cloud friendly**: polling never changes the adapter's MELCloud setting, so the MELCloud app keeps working alongside.
- **Clock watchdog**: controller clock offset sensor, a problem sensor and a Repairs warning when the Ecodan clock differs from Home Assistant's time by 10 minutes or more (e.g. a manual summer-time setting after a daylight-saving change). The warning clears itself once the clock is right.
- **Estimated electrical power** for the Ecodan averaged over the counter steps of the last 10 minutes, so it stays steady with 30 s polling.
- English and Italian translations.
