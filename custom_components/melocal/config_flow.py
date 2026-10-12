"""Config flow for MELocal."""

from __future__ import annotations

import ipaddress
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import network
from homeassistant.config_entries import (
    SOURCE_INTEGRATION_DISCOVERY,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import KIND_ATW
from .const import (
    CONF_KIND,
    CONF_MAC,
    CONF_NETWORKS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .discovery import FoundAdapter, async_probe, async_scan, parse_networks

_LOGGER = logging.getLogger(__name__)

KIND_NAMES = {KIND_ATW: "Ecodan", "ata": "Air conditioner"}


def _title(found: FoundAdapter) -> str:
    return f"{KIND_NAMES.get(found.kind, found.kind)} {found.mac[-5:].replace(':', '')}"


def _entry_data(found: FoundAdapter) -> dict[str, Any]:
    return {CONF_HOST: found.host, CONF_MAC: found.mac, CONF_KIND: found.kind}


class MelocalConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._found: dict[str, FoundAdapter] = {}
        self._discovered: FoundAdapter | None = None

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return MelocalOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["scan", "manual"])

    async def _default_networks(self) -> str:
        nets = []
        for adapter in await network.async_get_adapters(self.hass):
            if not adapter["enabled"]:
                continue
            for ip in adapter["ipv4"]:
                # Large networks: only suggest the /24 around our own address.
                prefix = 24 if ip["network_prefix"] < 22 else ip["network_prefix"]
                net = ipaddress.IPv4Network(f"{ip['address']}/{prefix}", strict=False)
                if not net.is_loopback:
                    nets.append(str(net))
        return ", ".join(dict.fromkeys(nets))

    async def async_step_scan(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                networks = parse_networks(user_input[CONF_NETWORKS])
            except ValueError:
                errors[CONF_NETWORKS] = "invalid_networks"
            else:
                found = await async_scan(async_get_clientsession(self.hass), networks)
                configured = self._async_current_ids(include_ignore=True)
                for adapter in found:
                    if adapter.mac in configured:
                        self._update_host(adapter)
                self._found = {a.mac: a for a in found if a.mac not in configured}
                if self._found:
                    return await self.async_step_pick()
                errors["base"] = "no_new_devices" if found else "no_devices_found"
        default = (user_input or {}).get(CONF_NETWORKS) or await self._default_networks()
        return self.async_show_form(
            step_id="scan",
            data_schema=vol.Schema({vol.Required(CONF_NETWORKS, default=default): str}),
            errors=errors,
        )

    async def async_step_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            chosen = self._found.pop(user_input[CONF_MAC])
            # Offer the remaining units as discovered devices.
            for other in self._found.values():
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": SOURCE_INTEGRATION_DISCOVERY},
                        data=_entry_data(other),
                    )
                )
            await self.async_set_unique_id(chosen.mac)
            self._abort_if_unique_id_configured(updates={CONF_HOST: chosen.host})
            return self.async_create_entry(title=_title(chosen), data=_entry_data(chosen))

        options = [
            SelectOptionDict(value=a.mac, label=f"{_title(a)} — {a.host} ({a.mac})")
            for a in self._found.values()
        ]
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAC): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
            description_placeholders={"count": str(len(options))},
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            found = await async_probe(async_get_clientsession(self.hass), host)
            if found is None:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(found.mac)
                self._abort_if_unique_id_configured(updates={CONF_HOST: found.host})
                return self.async_create_entry(title=_title(found), data=_entry_data(found))
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        found = FoundAdapter(
            discovery_info[CONF_HOST], discovery_info[CONF_MAC], discovery_info[CONF_KIND]
        )
        await self.async_set_unique_id(found.mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: found.host})
        self._discovered = found
        self.context["title_placeholders"] = {"name": _title(found), "host": found.host}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovered
        if user_input is not None:
            return self.async_create_entry(
                title=_title(self._discovered), data=_entry_data(self._discovered)
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": _title(self._discovered),
                "host": self._discovered.host,
            },
        )

    def _update_host(self, found: FoundAdapter) -> None:
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, found.mac)
        if entry and entry.data.get(CONF_HOST) != found.host:
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_HOST: found.host}
            )
            self.hass.config_entries.async_schedule_reload(entry.entry_id)


class MelocalOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)
                    )
                }
            ),
        )
