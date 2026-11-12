"""Donetick number platform."""
from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import DonetickApiClient
from .const import CONF_TOKEN, CONF_URL, DOMAIN
from .model import DonetickMember
from .thing import async_setup_entry as thing_async_setup_entry

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Donetick number entities."""
    await thing_async_setup_entry(hass, config_entry, async_add_entities, "number")

    config = hass.data[DOMAIN][config_entry.entry_id]
    client = DonetickApiClient(
        config[CONF_URL], config[CONF_TOKEN], async_get_clientsession(hass)
    )
    members = config.get("circle_members", [])
    async_add_entities(
        DonetickMemberPointsNumber(
            client, member, config, config_entry.entry_id, config["coordinator"]
        )
        for member in members if member.is_active
    )


class DonetickMemberPointsNumber(CoordinatorEntity, NumberEntity):
    """Writable points balance for a Donetick circle member."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:star-circle"
    _attr_native_min_value = 0
    _attr_native_max_value = 1_000_000_000
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "points"

    def __init__(self, client: DonetickApiClient, member: DonetickMember,
                 config: dict[str, Any], entry_id: str,
                 coordinator: DataUpdateCoordinator) -> None:
        self._client = client
        self._config = config
        self._entry_id = entry_id
        self._user_id = member.user_id
        self._circle_id = member.circle_id
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_member_{member.user_id}_points"
        self._attr_name = "Points"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_member_{member.user_id}")},
            "name": member.display_name or member.username,
            "manufacturer": "Donetick",
            "model": "Circle member",
        }

    @property
    def native_value(self) -> float:
        """Return the member's available points balance."""
        member = self._current_member
        if member is None:
            return 0
        return max(0, member.points - member.points_redeemed)

    @property
    def available(self) -> bool:
        """Return whether Donetick currently provides this member."""
        return super().available and self._current_member is not None

    @property
    def _current_member(self) -> DonetickMember | None:
        return next(
            (member for member in self._config.get("circle_members", [])
             if member.user_id == self._user_id),
            None,
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the balance by adding or removing the difference."""
        if not float(value).is_integer() or value < 0:
            raise HomeAssistantError("Donetick points must be a non-negative whole number")
        member = self._current_member
        if member is None:
            raise HomeAssistantError("This Donetick member is no longer available")
        delta = int(value) - max(0, member.points - member.points_redeemed)
        if delta:
            await self._client.async_adjust_member_points(
                self._circle_id, self._user_id,
                "add" if delta > 0 else "remove", abs(delta),
            )
        coordinator = self.hass.data[DOMAIN][self._entry_id]["coordinator"]
        await coordinator.async_request_refresh()
        self.async_write_ha_state()
