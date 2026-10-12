# MELocal for Home Assistant

Local, cloud-free control of Mitsubishi Electric heat pumps and air conditioners through their MELCloud Wi-Fi adapter.

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]][license]
[![hacs][hacsbadge]][hacs]
[![Maintainer][maintainer-shield]][maintainer]

> **Note**: Independent interoperability project, not affiliated with Mitsubishi Electric. Built on the work of gekkekoe/esphome-ecodan-hp, F1p, pymitsubishi and SwiCago/HeatPump.

Home Assistant talks to the adapter directly on your LAN (TCP port 80). No MELCloud account and no internet connection are needed.

## Features

- **Network Scan** or **Manual IP** setup, with automatic unit detection
- **Ecodan air-to-water heat pumps**: hot water, zone 1 climate, forced hot water, system power and many sensors, including estimated electrical power and calculated thermal power
- **Air-to-air air conditioners**: full climate control and instantaneous power in W
- Works alongside the MELCloud app: the adapter's cloud setting is never changed
- **Clock watchdog** for the Ecodan controller clock
- English and Italian translations

## Configuration

- Go to Settings → Devices & Services
- Click the + ADD INTEGRATION button in the lower right corner
- Search for **MELocal** and click the integration
- Choose **Scan the network** (enter the networks to scan, e.g. `10.0.20.0/24`) or **Enter an IP address**

[releases-shield]: https://img.shields.io/github/release/itsjustdeepred/melocal.svg
[releases]: https://github.com/itsjustdeepred/melocal/releases
[license-shield]: https://img.shields.io/github/license/itsjustdeepred/melocal.svg?cacheSeconds=3600
[license]: https://github.com/itsjustdeepred/melocal/blob/main/LICENSE
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg
[hacs]: https://hacs.xyz
[maintainer-shield]: https://img.shields.io/badge/maintainer-@itsjustdeepred-blue.svg
[maintainer]: https://github.com/itsjustdeepred
