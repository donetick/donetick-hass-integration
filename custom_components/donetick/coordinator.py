"""Data update coordinator for the DoneTick integration."""
from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DonetickApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DonetickDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the DoneTick integration."""

    def __init__(self, hass, api_client: DonetickApiClient):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.api_client = api_client

    async def _async_update_data(self):
        """Fetch data from the API."""
        try:
            tasks = await self.api_client.async_get_tasks()
            things = await self.api_client.async_get_things()
            return {"tasks": tasks, "things": things}
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
