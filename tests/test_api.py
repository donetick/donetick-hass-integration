"""Tests for the Donetick HTTP API client."""

from typing import Any, cast

import pytest

from custom_components.donetick.api import DonetickApiClient


class FakeResponse:
    def __init__(
        self,
        payload: object,
        status: int = 200,
        *,
        status_error: Exception | None = None,
        json_error: Exception | None = None,
    ) -> None:
        self.payload = payload
        self.status = status
        self.status_error = status_error
        self.json_error = json_error
        self.raise_for_status_called = False
        self.json_called = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True
        if self.status_error:
            raise self.status_error

    async def json(self) -> object:
        self.json_called = True
        if self.json_error:
            raise self.json_error
        return self.payload


class RecordingSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict] = []

    def post(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.response


async def test_create_chore_posts_full_api_payload_and_returns_id() -> None:
    response = FakeResponse({"res": 42})
    session = RecordingSession(response)
    client = DonetickApiClient(
        "https://donetick.example/", "test-token", cast(Any, session)
    )
    payload = {
        "name": "Clean kitchen",
        "description": "Including the worktop",
        "frequencyType": "weekly",
        "frequency": 1,
        "frequencyMetadata": {"days": [1, 4]},
        "assignees": [2, 3],
        "assignStrategy": "least_completed",
        "priority": 2,
    }

    chore_id = await client.async_create_chore(payload)

    assert chore_id == 42
    assert session.calls == [
        {
            "method": "POST",
            "url": "https://donetick.example/api/v1/chores",
            "headers": {
                "secretkey": "test-token",
                "Content-Type": "application/json",
            },
            "json": payload,
            "timeout": 10,
        }
    ]
    assert response.raise_for_status_called


async def test_complete_chore_posts_actual_performer_to_full_api() -> None:
    response = FakeResponse({"res": {"id": 42}})
    session = RecordingSession(response)
    client = DonetickApiClient(
        "https://donetick.example/", "test-token", cast(Any, session)
    )

    await client.async_complete_chore(42, completed_by=7)

    assert session.calls == [
        {
            "method": "POST",
            "url": "https://donetick.example/api/v1/chores/42/do",
            "headers": {
                "secretkey": "test-token",
                "Content-Type": "application/json",
            },
            "json": {"completedBy": 7},
            "timeout": 10,
        }
    ]
    assert response.raise_for_status_called


@pytest.mark.parametrize("response_payload", [{}, {"res": "42"}, {"res": True}])
async def test_create_chore_rejects_response_without_integer_id(
    response_payload: object,
) -> None:
    session = RecordingSession(FakeResponse(response_payload))
    client = DonetickApiClient(
        "https://donetick.example", "test-token", cast(Any, session)
    )

    with pytest.raises(ValueError, match="Unexpected Donetick create chore response"):
        await client.async_create_chore({"name": "Clean kitchen"})


async def test_create_chore_propagates_http_errors_before_reading_json() -> None:
    response = FakeResponse({}, status_error=RuntimeError("HTTP 500"))
    session = RecordingSession(response)
    client = DonetickApiClient(
        "https://donetick.example", "test-token", cast(Any, session)
    )

    with pytest.raises(RuntimeError, match="HTTP 500"):
        await client.async_create_chore({"name": "Clean kitchen"})

    assert response.raise_for_status_called
    assert not response.json_called


async def test_create_chore_propagates_json_decode_errors() -> None:
    response = FakeResponse({}, json_error=RuntimeError("invalid JSON"))
    session = RecordingSession(response)
    client = DonetickApiClient(
        "https://donetick.example", "test-token", cast(Any, session)
    )

    with pytest.raises(RuntimeError, match="invalid JSON"):
        await client.async_create_chore({"name": "Clean kitchen"})

    assert response.raise_for_status_called
    assert response.json_called
