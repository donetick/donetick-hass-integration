"""Tests for Donetick Home Assistant service integration."""

from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
from homeassistant.exceptions import HomeAssistantError

import custom_components.donetick as integration


class FakeConfigEntry:
    entry_id = "entry-1"
    data: ClassVar[dict[str, str]] = {
        "url": "https://donetick.example",
        "token": "test-token",
    }

    def add_update_listener(self, listener: Any) -> None:
        self.listener = listener


class FakeConfigEntries:
    def __init__(self, entry: FakeConfigEntry) -> None:
        self.entry = entry

    def async_get_entry(self, entry_id: str) -> FakeConfigEntry | None:
        return self.entry if entry_id == self.entry.entry_id else None

    def async_entries(self, domain: str) -> list[FakeConfigEntry]:
        return [self.entry]

    async def async_forward_entry_setups(self, entry: Any, platforms: Any) -> None:
        return None

    async def async_unload_platforms(self, entry: Any, platforms: Any) -> bool:
        return True


class FakeServices:
    def __init__(self) -> None:
        self.registered: dict[tuple[str, str], tuple[Any, Any]] = {}

    def async_register(
        self, domain: str, service: str, handler: Any, *, schema: Any
    ) -> None:
        self.registered[(domain, service)] = (handler, schema)

    def has_service(self, domain: str, service: str) -> bool:
        return (domain, service) in self.registered

    def async_remove(self, domain: str, service: str) -> None:
        self.registered.pop((domain, service))


class FakeHass:
    def __init__(self, entry: FakeConfigEntry) -> None:
        self.data: dict[str, Any] = {}
        self.config_entries = FakeConfigEntries(entry)
        self.services = FakeServices()


class RecordingClient:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    async def async_create_chore(self, payload: dict[str, Any]) -> int:
        self.payloads.append(payload)
        return 42


class CompletionClient:
    def __init__(self) -> None:
        self.completions: list[tuple[int, int]] = []

    async def async_complete_chore(self, chore_id: int, completed_by: int) -> None:
        self.completions.append((chore_id, completed_by))


class FailingClient:
    async def async_create_chore(self, payload: dict[str, Any]) -> int:
        raise RuntimeError("Donetick unavailable")


class FailingCoordinator:
    async def async_request_refresh(self) -> None:
        raise RuntimeError("refresh unavailable")


async def test_complete_chore_service_records_actual_performer_and_refreshes() -> None:
    entry = FakeConfigEntry()
    hass = FakeHass(entry)
    await integration.async_setup_entry(hass, entry)
    client = CompletionClient()
    hass.data[integration.DOMAIN][entry.entry_id]["client"] = client

    handler, schema = hass.services.registered[(integration.DOMAIN, "complete_chore")]
    await handler(
        SimpleNamespace(
            data=schema(
                {
                    "chore_id": 42,
                    "completed_by": 7,
                    "config_entry_id": entry.entry_id,
                }
            )
        )
    )

    assert client.completions == [(42, 7)]
    coordinator = hass.data[integration.DOMAIN][entry.entry_id]["coordinator"]
    assert coordinator.refresh_count == 1


async def test_create_chore_service_calls_full_api_and_refreshes_coordinator() -> None:
    entry = FakeConfigEntry()
    hass = FakeHass(entry)
    await integration.async_setup_entry(hass, entry)
    client = RecordingClient()
    hass.data[integration.DOMAIN][entry.entry_id]["client"] = client

    handler, schema = hass.services.registered[(integration.DOMAIN, "create_chore")]
    call_data = schema(
        {
            "name": "Clean kitchen",
            "next_due_date": "2026-09-07T18:00:00+02:00",
            "frequency_type": "weekly",
            "frequency": 2,
            "assignee_ids": [2, 3],
            "assigned_to": 2,
            "assign_strategy": "round_robin",
            "priority": 1,
            "config_entry_id": entry.entry_id,
        }
    )

    await handler(SimpleNamespace(data=call_data))

    assert client.payloads == [
        {
            "name": "Clean kitchen",
            "nextDueDate": "2026-09-07T18:00:00+02:00",
            "frequencyType": "weekly",
            "frequency": 2,
            "assignees": [{"userId": 2}, {"userId": 3}],
            "assignedTo": 2,
            "assignStrategy": "round_robin",
            "priority": 1,
        }
    ]
    coordinator = hass.data[integration.DOMAIN][entry.entry_id]["coordinator"]
    assert coordinator.refresh_count == 1


async def test_create_chore_service_surfaces_api_failure_without_refresh() -> None:
    entry = FakeConfigEntry()
    hass = FakeHass(entry)
    await integration.async_setup_entry(hass, entry)
    hass.data[integration.DOMAIN][entry.entry_id]["client"] = FailingClient()
    handler, schema = hass.services.registered[(integration.DOMAIN, "create_chore")]

    with pytest.raises(HomeAssistantError, match="Donetick unavailable") as error:
        await handler(SimpleNamespace(data=schema({"name": "Clean kitchen"})))

    assert isinstance(error.value.__cause__, RuntimeError)
    coordinator = hass.data[integration.DOMAIN][entry.entry_id]["coordinator"]
    assert coordinator.refresh_count == 0


async def test_create_chore_service_rejects_unloaded_config_entry() -> None:
    entry = FakeConfigEntry()
    hass = FakeHass(entry)

    with pytest.raises(HomeAssistantError, match="is not loaded") as error:
        await integration.async_create_chore_service(
            hass,
            SimpleNamespace(
                data={
                    "name": "Clean kitchen",
                    "config_entry_id": entry.entry_id,
                }
            ),
        )

    assert isinstance(error.value.__cause__, KeyError)


async def test_create_chore_service_reports_create_success_when_refresh_fails() -> None:
    entry = FakeConfigEntry()
    hass = FakeHass(entry)
    await integration.async_setup_entry(hass, entry)
    client = RecordingClient()
    hass.data[integration.DOMAIN][entry.entry_id]["client"] = client
    hass.data[integration.DOMAIN][entry.entry_id]["coordinator"] = FailingCoordinator()
    handler, schema = hass.services.registered[
        (integration.DOMAIN, integration.SERVICE_CREATE_CHORE)
    ]

    with pytest.raises(
        HomeAssistantError,
        match="created with ID 42, but Home Assistant refresh failed",
    ) as error:
        await handler(SimpleNamespace(data=schema({"name": "Partial success"})))

    assert isinstance(error.value.__cause__, RuntimeError)
    assert client.payloads == [
        {
            "name": "Partial success",
            "frequencyType": "once",
            "frequency": 1,
            "assignStrategy": "no_assignee",
            "priority": 0,
        }
    ]


async def test_unloading_final_entry_removes_create_chore_service() -> None:
    entry = FakeConfigEntry()
    hass = FakeHass(entry)
    await integration.async_setup_entry(hass, entry)
    service_key = (integration.DOMAIN, integration.SERVICE_CREATE_CHORE)
    assert service_key in hass.services.registered

    assert await integration.async_unload_entry(hass, entry)

    assert service_key not in hass.services.registered
