"""Base class for DoneTick entities."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import DonetickDataUpdateCoordinator


class DonetickEntity(CoordinatorEntity):
    """Base class for DoneTick entities."""

    def __init__(self, coordinator: DonetickDataUpdateCoordinator):
        """Initialize the entity."""
        super().__init__(coordinator)
