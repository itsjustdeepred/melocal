"""Base entity for MELocal."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import KIND_ATW
from .const import DOMAIN
from .coordinator import MelocalCoordinator


@dataclass(frozen=True, kw_only=True)
class MelocalEntityDescription(EntityDescription):
    """Entity bound to a key of the decoded data."""

    kinds: tuple[str, ...]
    # Default: created when the first decoded data has a value for ``key``.
    exists_fn: Callable[[dict[str, Any]], bool] | None = None


class MelocalEntity(CoordinatorEntity[MelocalCoordinator]):
    _attr_has_entity_name = True
    entity_description: MelocalEntityDescription

    def __init__(self, coordinator: MelocalCoordinator, description: MelocalEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        mac = entry.unique_id
        self._attr_unique_id = f"{mac}_{description.key}"
        adapter = coordinator.adapter
        data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer="Mitsubishi Electric",
            model="Ecodan air-to-water heat pump" if coordinator.kind == KIND_ATW else "Air conditioner",
            name=entry.title,
            serial_number=adapter.serial if adapter else None,
            sw_version=data.get("controller_firmware"),
            hw_version=f"Wi-Fi adapter {adapter.app_version}" if adapter else None,
        )

    @property
    def native_data(self) -> Any:
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        return super().available and self.native_data is not None


def descriptions_for(
    coordinator: MelocalCoordinator, descriptions: tuple[MelocalEntityDescription, ...]
) -> list[MelocalEntityDescription]:
    data = coordinator.data
    return [
        d
        for d in descriptions
        if coordinator.kind in d.kinds
        and (d.exists_fn(data) if d.exists_fn else data.get(d.key) is not None)
    ]
