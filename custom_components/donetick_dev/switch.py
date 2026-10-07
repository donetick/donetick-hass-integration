"""Donetick switch platform."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .thing import async_setup_entry as thing_async_setup_entry

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Donetick switch entities."""
    await thing_async_setup_entry(hass, config_entry, async_add_entities, "switch")