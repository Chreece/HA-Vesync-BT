"""Base entity for HA-VeSync-BT."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, SUPPORTED_MODEL
from .coordinator import HaVesyncCoordinator


class HaVesyncEntity(CoordinatorEntity[HaVesyncCoordinator]):
    """Base HA-VeSync-BT entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HaVesyncCoordinator,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, self.coordinator.address)},
            manufacturer=MANUFACTURER,
            model=SUPPORTED_MODEL,
            name="COSORI Nutrition Scale",
        )

    @property
    def available(self) -> bool:
        """Return device availability."""
        return self.coordinator.data.connected
