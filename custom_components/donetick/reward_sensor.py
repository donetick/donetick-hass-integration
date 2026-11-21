"""Reward catalog entities used by the dashboard card and action picker."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_reward_sensors(hass: HomeAssistant, entry: ConfigEntry,
                                    async_add_entities: AddEntitiesCallback) -> None:
    config = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(DonetickRewardSensor(config["reward_coordinator"], entry, reward)
                       for reward in config.get("rewards", []))
    known = {reward.id for reward in config.get("rewards", [])}

    def updated():
        nonlocal known
        current = {reward.id for reward in config.get("rewards", [])}
        added = current - known
        if added:
            async_add_entities(DonetickRewardSensor(config["reward_coordinator"], entry, reward)
                               for reward in config["rewards"] if reward.id in added)
        known = current

    config["reward_coordinator"].async_add_listener(updated)


class DonetickRewardSensor(CoordinatorEntity, SensorEntity):
    """One active catalog reward, with its point price as the state."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:gift-outline"
    _attr_native_unit_of_measurement = "points"

    def __init__(self, coordinator, entry: ConfigEntry, reward):
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        self._reward_id = reward.id
        self._attr_unique_id = f"{entry.entry_id}_reward_{reward.id}"

    @property
    def _reward(self):
        return next((item for item in (self.coordinator.data or [])
                     if item.id == self._reward_id), None)

    @property
    def name(self):
        reward = self._reward
        return reward.name if reward else None

    @property
    def native_value(self):
        reward = self._reward
        return reward.points_cost if reward else None

    @property
    def extra_state_attributes(self):
        reward = self._reward
        return {
            "reward_id": self._reward_id,
            "description": reward.description if reward else "",
            "points_cost": reward.points_cost if reward else None,
            "config_entry_id": self._entry_id,
        }

    @property
    def available(self):
        return super().available and self.native_value is not None
