"""Sensor platform for DoneTick."""
from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .coordinator import DonetickDataUpdateCoordinator
from .entity import DonetickEntity
from .model import DonetickThing


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DonetickSensor(coordinator, thing) for thing in coordinator.data["things"]
    )


class DonetickSensor(DonetickEntity, SensorEntity):
    """Donetick sensor."""

    def __init__(
        self,
        coordinator: DonetickDataUpdateCoordinator,
        thing: DonetickThing,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._thing = thing
        self._attr_unique_id = f"sensor.dt_{thing.id}"
        self._attr_name = thing.name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._thing.state