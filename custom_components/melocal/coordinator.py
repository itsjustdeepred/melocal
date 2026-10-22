"""Polling coordinator for one adapter."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import KIND_ATW, AdapterState, MelocalClient, MelocalError
from .const import CONF_KIND, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .decode import decode_ata, decode_atw
from .estimator import EnergyRateEstimator

_LOGGER = logging.getLogger(__name__)

WATER_HEAT_CAPACITY = 4.18  # kJ/(kg*K)
COMMAND_REFRESH_DELAY = 5
CLOCK_TOLERANCE_MIN = 10
# Fresh readings in a row before raising a repair issue.
CLOCK_ISSUE_AFTER = 3
# Failed polls in a row before the entities go unavailable. The adapter drops
# off the network for 15-30 s every half hour or so (it restarts its Wi-Fi when
# it cannot reach MELCloud), which would otherwise blank everything each time.
MAX_MISSED_POLLS = 3


class MelocalCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and decode one adapter."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.data[CONF_HOST]}",
            update_interval=timedelta(seconds=interval),
        )
        self.kind: str = entry.data[CONF_KIND]
        self.client = MelocalClient(async_get_clientsession(hass), entry.data[CONF_HOST])
        self.adapter: AdapterState | None = None
        self._frames: dict[int, bytes] = {}
        self._estimator = EnergyRateEstimator()
        self._clock_offset: int | None = None
        self._clock_bad_readings = 0
        self._missed_polls = 0

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            state = await self.client.async_get_state()
        except MelocalError as err:
            self._missed_polls += 1
            if self.data is not None and self._missed_polls < MAX_MISSED_POLLS:
                _LOGGER.debug(
                    "%s: poll failed (%d/%d), keeping last data: %s",
                    self.client.host,
                    self._missed_polls,
                    MAX_MISSED_POLLS,
                    err,
                )
                return self.data
            raise UpdateFailed(str(err)) from err
        if self._missed_polls:
            _LOGGER.debug("%s: back after %d missed polls", self.client.host, self._missed_polls)
            self._missed_polls = 0
        return self._process(state)

    async def async_send_command(self, *packets: bytes, optimistic: dict[str, Any] | None = None) -> None:
        """Send SET packets, show the expected state at once, re-read shortly after."""
        _LOGGER.debug("%s: sending %s", self.client.host, [p.hex() for p in packets])
        try:
            state = await self.client.async_send(*packets)
        except MelocalError as err:
            raise HomeAssistantError(f"Command failed: {err}") from err
        self._apply(state, optimistic)

    def _apply(self, state: AdapterState, optimistic: dict[str, Any] | None) -> None:
        data = self._process(state)
        data.update(optimistic or {})
        self.async_set_updated_data(data)
        # The unit needs a moment before its status frames reflect the change.
        async_call_later(self.hass, COMMAND_REFRESH_DELAY, self._delayed_refresh)

    async def _delayed_refresh(self, _now: Any) -> None:
        await self.async_request_refresh()

    def _process(self, state: AdapterState) -> dict[str, Any]:
        self.adapter = state
        # The adapter does not always send every group; keep the last seen.
        self._frames.update(state.frames)
        if self.kind == KIND_ATW:
            data = decode_atw(self._frames)
            self._add_atw_derived(data)
            self._add_clock_offset(state, data)
        else:
            data = decode_ata(self._frames)
        data["rssi"] = state.rssi
        data["adapter_firmware"] = state.app_version
        data["adapter_timestamp"] = state.timestamp
        return data

    def _add_clock_offset(self, state: AdapterState, data: dict[str, Any]) -> None:
        """Minutes the FTC clock is ahead (+) or behind (-) Home Assistant's local time."""
        # Only a frame from this answer is fresh; a cached one would drift.
        if 0x01 in state.frames and data.get("controller_time"):
            try:
                controller = datetime.strptime(data["controller_time"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                controller = None
            if controller:
                now = dt_util.now().replace(tzinfo=None)
                self._clock_offset = round((controller - now).total_seconds() / 60)
                self._update_clock_issue()
        data["controller_clock_offset"] = self._clock_offset
        data["controller_clock_out_of_sync"] = (
            abs(self._clock_offset) >= CLOCK_TOLERANCE_MIN if self._clock_offset is not None else None
        )

    def _update_clock_issue(self) -> None:
        """Raise a repair when the FTC clock is off, e.g. after a daylight-saving change."""
        issue_id = f"controller_clock_{self.config_entry.entry_id}"
        if self._clock_offset is not None and abs(self._clock_offset) >= CLOCK_TOLERANCE_MIN:
            self._clock_bad_readings += 1
            if self._clock_bad_readings >= CLOCK_ISSUE_AFTER:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="controller_clock",
                    translation_placeholders={
                        "name": self.config_entry.title,
                        "offset": f"{self._clock_offset:+d}",
                    },
                )
        else:
            self._clock_bad_readings = 0
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def _add_atw_derived(self, data: dict[str, Any]) -> None:
        total = data.get("energy_consumed_total")
        if total is not None:
            data["power_consumption_estimated"] = self._estimator.update(total, time.monotonic())
        flow_rate = data.get("flow_rate")
        flow, ret = data.get("flow_temp"), data.get("return_temp")
        if flow_rate is None or flow is None or ret is None:
            return
        delta = ret - flow if data.get("operation") == "cooling" else flow - ret
        running = data.get("compressor") and flow_rate > 0
        data["thermal_power"] = (
            round(flow_rate / 60 * max(delta, 0) * WATER_HEAT_CAPACITY, 2) if running else 0.0
        )
