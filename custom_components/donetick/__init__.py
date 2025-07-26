"""The Donetick integration."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_URL, CONF_TOKEN, CONF_SHOW_DUE_IN
from .coordinator import DonetickDataUpdateCoordinator
from .api import DonetickApiClient

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.TODO, Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Donetick from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    session = async_get_clientsession(hass)
    api_client = DonetickApiClient(entry.data[CONF_URL], entry.data[CONF_TOKEN], session)
    
    coordinator = DonetickDataUpdateCoordinator(hass, api_client)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
