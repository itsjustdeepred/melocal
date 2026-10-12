<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="custom_components/melocal/brand/dark_logo.png">
  <img src="custom_components/melocal/brand/logo.png" alt="MELocal" width="420">
</picture>

# MELocal for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]][license]
[![hacs][hacs-shield]][hacs]
[![Maintainer][maintainer-shield]][maintainer]

[![Open your Home Assistant instance and show the integrations page.][my-ha-badge]][my-ha]
[![Open your Home Assistant instance and show the add integration page.][add-integration-badge]][add-integration]

</div>

Local, cloud-free control of Mitsubishi Electric heat pumps and air conditioners through their MELCloud Wi-Fi adapter (MAC-5xxIF-E family). No MELCloud account, no internet connection: Home Assistant talks to the adapter directly on your LAN.

> **Note**: This is an independent interoperability project, not affiliated with or endorsed by Mitsubishi Electric. The adapter's local API is undocumented; see [Credits](#credits) for the open-source work it builds on.

## Features

- **Network Scan**: Finds MELCloud adapters on one or more networks (CIDR); every unit found becomes its own device, the others show up under *Discovered*
- **Manual Setup**: Add an adapter by IP address
- **Automatic Unit Detection**: Recognises Ecodan air-to-water heat pumps and air-to-air air conditioners
- **IP Changes Handled**: Devices are identified by MAC address; re-scanning updates the stored IP
- **Local Control**: Climate, hot water, switches and selects work entirely over the LAN
- **Cloud Friendly**: The adapter keeps working with the MELCloud app; MELocal never changes its cloud setting
- **Energy Dashboard Ready**: Cumulative energy counters are `total_increasing`
- **Clock Watchdog**: Raises a Repairs warning when the Ecodan controller clock drifts from Home Assistant's time (e.g. a missed daylight-saving change) and clears it once fixed
- **Translations**: English and Italian

## Supported Units

| Unit | Reading | Control |
| ---- | ------- | ------- |
| Ecodan air-to-water heat pump (FTC controller) | ✅ | ✅ |
| Air-to-air air conditioner | ✅ | ✅ |

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to Integrations
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/itsjustdeepred/melocal`
6. Select category: "Integration"
7. Click "Add"
8. Find "MELocal" in the HACS integrations list
9. Click "Download"
10. Restart Home Assistant
11. Go to Settings → Devices & Services → Add Integration
12. Search for "MELocal" and follow the setup wizard

### Manual Installation

1. Download or clone this repository
2. Copy the `custom_components/melocal` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration
5. Search for "MELocal" and follow the setup wizard

## Configuration

### Network Requirements

Home Assistant must reach the adapters on **TCP port 80**. If the adapters live on a separate IoT VLAN, allow traffic from Home Assistant to the adapters on port 80 in your firewall.

### Setup Steps

1. **Add Integration**:
   - Go to Settings → Devices & Services → Add Integration
   - Search for "MELocal"
   - Choose **Scan the network** or **Enter an IP address**

2. **Scan the Network**:
   - The networks Home Assistant is on are pre-filled
   - Add other networks as CIDR, comma separated (e.g. `10.0.20.0/24`); up to 4096 addresses in total
   - Pick the unit to add now; the remaining ones appear under *Discovered* and can be added with one click

3. **Enter an IP Address**:
   - Type the adapter's IP address
   - If the unit is already configured, its stored IP is updated instead

### Options

To change the polling interval (default 30 s, minimum 10 s):

1. Go to Settings → Devices & Services
2. Find your MELocal device
3. Click on it, then click "Configure"

## Entities

### Ecodan Heat Pump

| Platform | Entities |
| -------- | -------- |
| `water_heater` | Hot water: target temperature, Normal / Eco mode, holiday mode as away mode |
| `climate` | Zone 1: heat / cool, room or flow target temperature |
| `select` | Zone 1 control: room temperature, flow temperature, compensation curve |
| `switch` | Forced hot water, system power |
| `sensor` | Outside, flow, return, zone, hot water tank, boiler, mixing tank and refrigerant temperatures; targets; operation and zone modes; compressor frequency; flow rate; energy consumed (total); last-day consumed / delivered energy and COP / EER; **estimated electrical power**; **calculated thermal power**; fault code; controller clock and clock offset |
| `binary_sensor` | Power, compressor, defrost, booster and immersion heaters, water pumps, 3-way valves, thermostat inputs, forced hot water, holiday, prohibit flags, clock out of sync |

Zone 2 entities are created only when the controller's DIP switches report two zones.

**Estimated electrical power**: the Ecodan only reports a cumulative counter in 0.1 kWh steps, so electrical power is the average between steps (a moving average, not an instantaneous reading). **Thermal power** is calculated from flow rate × ΔT.

### Air Conditioner

| Platform | Entities |
| -------- | -------- |
| `climate` | Power, mode (auto / heat / cool / dry / fan), target temperature, fan speed, vertical and horizontal vanes |
| `sensor` | Room and target temperature, **instantaneous power (W)**, energy consumed (total), compressor frequency, operating hours, mode, fan, vanes, error code |
| `binary_sensor` | Power, operating, power saving, i-See sensor |

### How Commands Work

Every Ecodan command repeats the unit's current values and flags only the field being changed, so nothing else moves. After a command the entity updates immediately and the state is re-read a few seconds later.

Verified on real units: air conditioner power / mode / target temperature, Ecodan hot water target, Normal / Eco, forced hot water and zone 1 flow target. The remaining Ecodan commands (holiday, zone mode change, system power) follow the published protocol notes but have been tested less.

## Troubleshooting

### No Adapter Found

- Check that Home Assistant can reach the adapter on TCP port 80 (firewall / VLAN rules)
- Scan the network the adapter is on, not only the one Home Assistant is on
- Try adding the adapter by IP address

### Entities Unavailable

- The adapter's Wi-Fi signal may be weak; check the *Wi-Fi signal* diagnostic sensor
- Increase the polling interval in the options if the adapter is slow to answer

### Controller Clock Out of Sync

The Ecodan controller clock cannot be set through the local API (no documented command exists). Set the date and time from the unit's main remote controller: Menu → Initial settings → Date/Time.

## Requirements

- Home Assistant 2025.2.0 or later
- A Mitsubishi Electric unit with a MELCloud Wi-Fi adapter reachable on the LAN
- No extra Python packages

## Credits

MELocal stands on the reverse-engineering work of the open-source community. Thank you to:

- **[gekkekoe/esphome-ecodan-hp](https://github.com/gekkekoe/esphome-ecodan-hp)** (GPL-3.0): Ecodan CN105 decoding and set commands; the Ecodan decoder is a Python port of its logic
- **[F1p/Mitsubishi-CN105-Protocol-Decode](https://github.com/F1p/Mitsubishi-CN105-Protocol-Decode)** and **[F1p/Mitsubishi-Ecodan-Bridge-CN105](https://github.com/F1p/Mitsubishi-Ecodan-Bridge-CN105)** (GPL-3.0): the CN105 protocol documentation for Ecodan and MELCloud traffic
- **[pymitsubishi/pymitsubishi](https://github.com/pymitsubishi/pymitsubishi)** (MIT): the MELCloud adapter's local `/smart` API, its encryption, air conditioner decoding and command packets, and the verified Ecodan setpoint packet
- **[SwiCago/HeatPump](https://github.com/SwiCago/HeatPump)** (GPL-3.0): the original CN105 air conditioner protocol reverse engineering

Reverse engineering for interoperability is permitted by Art. 6 of Directive 2009/24/EC. MELCloud and Ecodan are trademarks of Mitsubishi Electric Corporation.

## Support

For issues, feature requests, or contributions, please visit the [GitHub repository](https://github.com/itsjustdeepred/melocal).

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.

---

<div align="center">

**If you find this integration useful, please consider giving it a ⭐ on GitHub!**

Made with ❤️ for the Home Assistant community

</div>

[releases-shield]: https://img.shields.io/github/release/itsjustdeepred/melocal.svg
[releases]: https://github.com/itsjustdeepred/melocal/releases
[license-shield]: https://img.shields.io/github/license/itsjustdeepred/melocal.svg?cacheSeconds=3600
[license]: https://github.com/itsjustdeepred/melocal/blob/main/LICENSE
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-orange.svg
[hacs]: https://hacs.xyz
[maintainer-shield]: https://img.shields.io/badge/maintainer-@itsjustdeepred-blue.svg
[maintainer]: https://github.com/itsjustdeepred
[my-ha-badge]: https://my.home-assistant.io/badges/integrations.svg
[my-ha]: https://my.home-assistant.io/redirect/integrations/
[add-integration-badge]: https://my.home-assistant.io/badges/config_flow_start.svg
[add-integration]: https://my.home-assistant.io/redirect/config_flow_start/?domain=melocal
