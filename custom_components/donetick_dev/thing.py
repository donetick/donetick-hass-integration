"""Donetick thing entities."""
import logging
from typing import Any, Optional
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.number import NumberEntity
from homeassistant.components.text import TextEntity
from homeassistant.const import STATE_ON, STATE_OFF

from .api import DonetickApiClient
from .const import DOMAIN, CONF_URL, CONF_TOKEN
from .model import DonetickThing

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    platform: str = None,
) -> None:
    """Set up Donetick thing entities for specific platform."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = config["coordinator"]
    session = async_get_clientsession(hass)
    client = DonetickApiClient(
        config[CONF_URL],
        config[CONF_TOKEN], 
        session
    )
    
    try:
        things = await client.async_get_things()
        entities = []
        
        for thing in things:
            # Only create entities for the current platform
            if platform == "switch" and thing.type == "boolean":
                entities.append(DonetickThingSwitch(client, thing, coordinator))
            elif platform == "number" and thing.type == "number":
                entities.append(DonetickThingNumber(client, thing, coordinator))
            elif platform == "text" and thing.type == "text":
                entities.append(DonetickThingText(client, thing, coordinator))
            elif platform == "sensor" and thing.type not in ["boolean", "number", "text"]:
                entities.append(DonetickThingSensor(client, thing, coordinator))
        
        if entities:
            async_add_entities(entities, True)
        
    except Exception as err:
        _LOGGER.error("Error setting up Donetick things: %s", err)

class DonetickThingBase(Entity):
    """Base class for Donetick thing entities."""
    
    def __init__(self, client: DonetickApiClient, thing: DonetickThing, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the entity."""
        self._client = client
        self._thing = thing
        self._coordinator = coordinator
        self._attr_unique_id = f"donetick_thing_{thing.id}"
        self._attr_name = thing.name
        self._attr_has_entity_name = True
        
    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, "things")},
            "name": "Donetick Dev Things",
            "manufacturer": "Donetick",
            "model": "Things",
        }

    async def async_update(self) -> None:
        """Update the entity state."""
        try:
            state = await self._client.async_get_thing_state(self._thing.id)
            if state is not None:
                self._thing.state = state
        except Exception as err:
            _LOGGER.error("Error updating thing %s: %s", self._thing.name, err)

class DonetickThingSensor(DonetickThingBase, SensorEntity):
    """Donetick thing sensor entity."""
    
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self._thing.state

class DonetickThingSwitch(DonetickThingBase, SwitchEntity):
    """Donetick thing switch entity for boolean types."""
    
    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._thing.state.lower() in ("on", "true", "1")
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            success = await self._client.async_set_thing_state(
                self._thing.id, "true"
            )
            if success:
                self._thing.state = "true"
                self.async_write_ha_state()
                await self._coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Error turning on thing %s: %s", self._thing.name, err)
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            success = await self._client.async_set_thing_state(
                self._thing.id, "false"
            )
            if success:
                self._thing.state = "false"
                self.async_write_ha_state()
                await self._coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Error turning off thing %s: %s", self._thing.name, err)

class DonetickThingNumber(DonetickThingBase, NumberEntity):
    """Donetick thing number entity."""
    
    @property
    def native_value(self) -> float:
        """Return the numeric value."""
        try:
            return float(self._thing.state)
        except (ValueError, TypeError):
            return 0.0
    
    async def async_set_native_value(self, value: float) -> None:
        """Set the numeric value."""
        try:
            success = await self._client.async_set_thing_state(
                self._thing.id, str(int(value))
            )
            if success:
                self._thing.state = str(value)
                self.async_write_ha_state()
                await self._coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Error setting number thing %s: %s", self._thing.name, err)

class DonetickThingText(DonetickThingBase, TextEntity):
    """Donetick thing text entity."""
    
    @property
    def native_value(self) -> str:
        """Return the text value."""
        return self._thing.state
    
    async def async_set_value(self, value: str) -> None:
        """Set the text value."""
        try:
            success = await self._client.async_set_thing_state(
                self._thing.id, value
            )
            if success:
                self._thing.state = value
                self.async_write_ha_state()
                await self._coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Error setting text thing %s: %s", self._thing.name, err)
