"""Find MELCloud adapters on the LAN by probing their local API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import ipaddress
import logging

import aiohttp

from .api import MelocalClient, MelocalError
from .const import MAX_SCAN_HOSTS

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FoundAdapter:
    host: str
    mac: str
    kind: str


def parse_networks(text: str) -> list[ipaddress.IPv4Network]:
    """Parse comma/space separated CIDRs or single IPs. Raises ValueError."""
    networks = []
    for item in text.replace(",", " ").split():
        networks.append(ipaddress.IPv4Network(item, strict=False))
    if not networks:
        raise ValueError("empty")
    if sum(n.num_addresses for n in networks) > MAX_SCAN_HOSTS:
        raise ValueError("too many hosts")
    return networks


async def _port_open(host: str, timeout: float) -> bool:
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, 80), timeout)
    except (OSError, TimeoutError):
        return False
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    return True


async def async_probe(session: aiohttp.ClientSession, host: str) -> FoundAdapter | None:
    """Return adapter info if ``host`` is a supported adapter."""
    try:
        state = await MelocalClient(session, host).async_get_state(timeout=8)
    except MelocalError:
        return None
    if state.kind is None:
        _LOGGER.debug("%s answered but reported no known unit type", host)
        return None
    return FoundAdapter(host, state.mac, state.kind)


async def async_scan(
    session: aiohttp.ClientSession,
    networks: list[ipaddress.IPv4Network],
    concurrency: int = 64,
) -> list[FoundAdapter]:
    """Probe every host of ``networks`` that has port 80 open."""
    hosts = {str(ip) for net in networks for ip in (net.hosts() if net.num_addresses > 2 else net)}
    sem = asyncio.Semaphore(concurrency)

    async def check(host: str) -> FoundAdapter | None:
        async with sem:
            if not await _port_open(host, 1.5):
                return None
        return await async_probe(session, host)

    results = await asyncio.gather(*(check(h) for h in sorted(hosts)))
    found = {r.mac: r for r in results if r}
    return sorted(found.values(), key=lambda r: ipaddress.IPv4Address(r.host))
