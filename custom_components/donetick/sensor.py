"""Donetick sensor platform."""
from __future__ import annotations
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .thing import async_setup_entry as thing_async_setup_entry
from .chore_sensor import async_setup_chore_sensors

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Donetick sensor entities."""
    try:
        await thing_async_setup_entry(hass, config_entry, async_add_entities, "sensor")
    except Exception as err:
        _LOGGER.debug("Thing sensor setup skipped: %s", err)

    await async_setup_chore_sensors(hass, config_entry, async_add_entities)
