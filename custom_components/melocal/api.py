"""Local HTTP API of Mitsubishi Electric MELCloud Wi-Fi adapters (MAC-5xxIF-E).

The adapter answers ``POST /smart`` with an XML envelope whose body is
AES-128-CBC encrypted with a static key. The decrypted payload carries the raw
CN105 frames the adapter exchanged with the indoor unit / FTC controller.
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
import os
import re

import aiohttp
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEY = b"unregistered".ljust(16, b"\0")
# No <CONNECT> element: the adapter's MELCloud setting is left untouched.
STATUS_REQUEST = "<CSV></CSV>"

KIND_ATW = "atw"  # Ecodan air-to-water heat pump
KIND_ATA = "ata"  # air-to-air air conditioner

_KIND_BY_HEADER = {b"\x02\x7a": KIND_ATW, b"\x01\x30": KIND_ATA}
_ENVELOPE = re.compile(r"<(?:ESV|LSV)>(.*?)</(?:ESV|LSV)>", re.S)
_VALUE = re.compile(r"<VALUE>([0-9a-fA-F]+)</VALUE>")


class MelocalError(Exception):
    """Communication with the adapter failed."""


class MelocalUnsupported(MelocalError):
    """The host answered but is not a supported adapter."""


def encrypt(text: str) -> str:
    iv = os.urandom(16)
    data = text.encode()
    data += b"\0" * (-len(data) % 16)
    enc = Cipher(algorithms.AES(KEY), modes.CBC(iv)).encryptor()
    return base64.b64encode(iv + enc.update(data) + enc.finalize()).decode()


def decrypt(b64: str) -> str:
    raw = base64.b64decode(b64)
    dec = Cipher(algorithms.AES(KEY), modes.CBC(raw[:16])).decryptor()
    text = (dec.update(raw[16:]) + dec.finalize()).decode(errors="replace")
    # Strip block padding after the closing tag.
    return text[: text.rfind(">") + 1]


def checksum_ok(frame: bytes) -> bool:
    return (0xFC - sum(frame[:-1])) & 0xFF == frame[-1]


def _tag(xml: str, name: str) -> str | None:
    match = re.search(rf"<{name}>(.*?)</{name}>", xml, re.S)
    return match.group(1) if match else None


@dataclass
class AdapterState:
    """One decoded answer of the adapter."""

    mac: str
    serial: str | None
    kind: str | None
    app_version: str | None
    rssi: int | None
    timestamp: str | None
    frames: dict[int, bytes] = field(default_factory=dict)

    @classmethod
    def from_xml(cls, xml: str) -> AdapterState:
        mac = _tag(xml, "MAC")
        if not mac:
            raise MelocalUnsupported("no MAC in response")
        frames: dict[int, bytes] = {}
        kind = None
        code = _tag(xml, "CODE") or ""
        for hexs in _VALUE.findall(code):
            frame = bytes.fromhex(hexs)
            if len(frame) < 22 or frame[0] != 0xFC or not checksum_ok(frame):
                continue
            kind = kind or _KIND_BY_HEADER.get(frame[2:4])
            # 0x62 = get response, 0x7B = profile/capabilities
            if frame[1] in (0x62, 0x7B):
                frames[frame[5]] = frame
        rssi = _tag(xml, "RSSI")
        return cls(
            mac=mac.lower(),
            serial=_tag(xml, "SERIAL"),
            kind=kind,
            app_version=_tag(xml, "APP_VER"),
            rssi=int(rssi) if rssi and rssi.lstrip("-").isdigit() else None,
            timestamp=_tag(xml, "DATDATE"),
            frames=frames,
        )


class MelocalClient:
    """Talks to a single adapter. Requests are serialised, the adapter is slow."""

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self._session = session
        self.host = host
        self._lock = asyncio.Lock()

    async def _post(self, payload: str, timeout: float) -> str:
        body = f'<?xml version="1.0" encoding="UTF-8"?><ESV>{encrypt(payload)}</ESV>'
        try:
            async with self._lock, self._session.post(
                f"http://{self.host}/smart",
                data=body,
                headers={"Content-Type": "text/plain;charset=UTF-8"},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    raise MelocalUnsupported(f"HTTP {resp.status}")
                text = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise MelocalError(f"{self.host}: {err!r}") from err
        match = _ENVELOPE.search(text)
        if not match:
            raise MelocalUnsupported("unexpected response")
        try:
            return decrypt(match.group(1))
        except ValueError as err:
            raise MelocalUnsupported("cannot decrypt response") from err

    async def async_get_state(self, timeout: float = 10) -> AdapterState:
        return AdapterState.from_xml(await self._post(STATUS_REQUEST, timeout))

    async def async_send(self, *packets: bytes) -> AdapterState:
        """Send CN105 SET packets; the adapter answers with its state."""
        values = "".join(f"<VALUE>{p.hex()}</VALUE>" for p in packets)
        return AdapterState.from_xml(await self._post(f"<CSV><CODE>{values}</CODE></CSV>", 15))

