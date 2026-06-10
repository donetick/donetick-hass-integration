"""API client for Donetick."""
import logging
from datetime import datetime
import json
from typing import List, Optional
import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_TIMEOUT
from .model import DonetickTask, DonetickThing, DonetickMember, DonetickChoreHistory
_LOGGER = logging.getLogger(__name__)

class DonetickApiClient:
    """API client for Donetick."""

    def __init__(self, base_url: str, token: str, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self._base_url = base_url.rstrip('/')
        self._token = token
        self._session = session

    def _headers(self) -> dict:
        """Return headers for Donetick API requests."""
        return {
            "secretkey": f"{self._token}",
            "Content-Type": "application/json",
        }

    async def async_get_tasks(self) -> List[DonetickTask]:
        """Get tasks from Donetick."""
        headers = self._headers()
        
        try:
            async with self._session.get(
                f"{self._base_url}/eapi/v1/chore",
                headers=headers,
                timeout=API_TIMEOUT
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                if not isinstance(data, list) :
                    _LOGGER.error("Unexpected response format from Donetick API")
                    return []
                
                return [DonetickTask.from_json(task) for task in data]
                
        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching tasks from Donetick: %s", err)
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.error("Error parsing Donetick response: %s", err)
            return []

    async def async_get_circle_members(self) -> List[DonetickMember]:
        """Get circle members from Donetick."""
        headers = self._headers()
        
        try:
            async with self._session.get(
                f"{self._base_url}/eapi/v1/circle/members",
                headers=headers,
                timeout=API_TIMEOUT
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                if not isinstance(data, list):
                    _LOGGER.error("Unexpected response format from Donetick circle members API")
                    return []
                
                return [DonetickMember.from_json(member) for member in data]
                
        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching circle members from Donetick: %s", err)
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.error("Error parsing Donetick circle members response: %s", err)
            return []

    async def async_get_things(self) -> List[DonetickThing]:
        """Get things from Donetick."""
        headers = self._headers()
        
        try:
            async with self._session.get(
                f"{self._base_url}/eapi/v1/things",
                headers=headers,
                timeout=API_TIMEOUT
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                if not isinstance(data, list):
                    _LOGGER.error("Unexpected response format from Donetick things API")
                    return []
                
                return [DonetickThing.from_json(thing) for thing in data]
                
        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching things from Donetick: %s", err)
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.error("Error parsing Donetick things response: %s", err)
            return []

    async def async_get_thing_state(self, thing_id: int) -> Optional[str]:
        """Get the current state of a thing."""
        headers = self._headers()
        
        try:
            async with self._session.get(
                f"{self._base_url}/eapi/v1/things/{thing_id}/state",
                headers=headers,
                timeout=API_TIMEOUT
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("state")
                
        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching thing state from Donetick: %s", err)
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.error("Error parsing Donetick thing state response: %s", err)
            return None

    async def async_set_thing_state(self, thing_id: int, state: str) -> bool:
        """Set the state of a thing directly."""
        headers = self._headers()
        
        params = {"state": state}
        
        try:
            async with self._session.get(
                f"{self._base_url}/eapi/v1/things/{thing_id}/state",
                headers=headers,
                params=params,
                timeout=API_TIMEOUT
            ) as response:
                response.raise_for_status()
                return True
                
        except aiohttp.ClientError as err:
            _LOGGER.error("Error setting thing state in Donetick: %s", err)
            raise
        except Exception as err:
            _LOGGER.error("Error setting thing state: %s", err)
            return False

    async def async_change_thing_state(self, thing_id: int, new_state: str = None, increment: int = None) -> Optional[str]:
        """Change the state of a thing using the change endpoint."""
        headers = self._headers()
        
        params = {}
        if new_state is not None:
            params["set"] = new_state
        if increment is not None:
            params["op"] = increment
        
        try:
            async with self._session.get(
                f"{self._base_url}/eapi/v1/things/{thing_id}/state/change",
                headers=headers,
                params=params,
                timeout=API_TIMEOUT
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("state")
                
        except aiohttp.ClientError as err:
            _LOGGER.error("Error changing thing state in Donetick: %s", err)
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.error("Error parsing Donetick change state response: %s", err)
            return None

    async def async_complete_task(self, choreId: int, completed_by: int = None) -> DonetickTask:
        """Complete a task"""
        headers = self._headers()

        # Add completed_by parameter if provided
        params = {}
        if completed_by:
            params["completedBy"] = completed_by
            _LOGGER.debug("Adding completedBy parameter: %d", completed_by)
        else:
            _LOGGER.debug("No completedBy parameter - using default")

        try:
            async with self._session.post(
                f"{self._base_url}/eapi/v1/chore/{choreId}/complete",
                headers=headers,
                params=params,
                timeout=API_TIMEOUT
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return DonetickTask.from_json(data)

        except aiohttp.ClientError as err:
            _LOGGER.error("Error completing task in Donetick: %s", err)
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.error("Error parsing Donetick complete task response: %s", err)
            raise

    async def async_create_task(self, name: str, description: str = None, due_date: str = None, created_by: int = None) -> DonetickTask:
        """Create a new task"""
        headers = self._headers()

        payload = {"name": name}
        if description:
            payload["description"] = description
        if due_date:
            payload["dueDate"] = due_date
        if created_by:
            payload["createdBy"] = created_by

        try:
            async with self._session.post(
                f"{self._base_url}/eapi/v1/chore",
                headers=headers,
                json=payload,
                timeout=API_TIMEOUT
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return DonetickTask.from_json(data)

        except aiohttp.ClientError as err:
            _LOGGER.error("Error creating task in Donetick: %s", err)
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.error("Error parsing Donetick create task response: %s", err)
            raise

    async def async_update_task(self, task_id: int, name: str = None, description: str = None, due_date: str = None) -> DonetickTask:
        """Update an existing task"""
        headers = self._headers()

        payload = {}
        if name:
            payload["name"] = name
        if description is not None:  # Allow empty string to clear description
            payload["description"] = description
        if due_date:
            payload["dueDate"] = due_date

        if not payload:
            raise ValueError("At least one field must be provided for update")

        try:
            async with self._session.put(
                f"{self._base_url}/eapi/v1/chore/{task_id}",
                headers=headers,
                json=payload,
                timeout=API_TIMEOUT
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return DonetickTask.from_json(data)

        except aiohttp.ClientError as err:
            _LOGGER.error("Error updating task in Donetick: %s", err)
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.error("Error parsing Donetick update task response: %s", err)
            raise

    async def async_skip_task(self, choreId: int, completed_by: int = None) -> DonetickTask:
        """Skip a task, advancing to the next scheduled occurrence without recording a completion."""
        headers = self._headers()

        params = {}
        if completed_by:
            params["completedBy"] = completed_by

        try:
            async with self._session.post(
                f"{self._base_url}/eapi/v1/chore/{choreId}/skip",
                headers=headers,
                params=params,
                timeout=API_TIMEOUT
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return DonetickTask.from_json(data)

        except aiohttp.ClientError as err:
            _LOGGER.error("Error skipping task in Donetick: %s", err)
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.error("Error parsing Donetick skip task response: %s", err)
            raise

    async def async_delete_task(self, task_id: int) -> bool:
        """Delete a task"""
        headers = self._headers()

        try:
            async with self._session.delete(
                f"{self._base_url}/eapi/v1/chore/{task_id}",
                headers=headers,
                timeout=API_TIMEOUT
            ) as response:
                response.raise_for_status()
                return True

        except aiohttp.ClientError as err:
            _LOGGER.error("Error deleting task in Donetick: %s", err)
            raise
        except Exception as err:
            _LOGGER.error("Error deleting task: %s", err)
            return False

    async def async_get_task_detail(self, task_id: int) -> Optional[DonetickTask]:
        """Get detailed task timing data when the full API endpoint is available."""
        try:
            async with self._session.get(
                f"{self._base_url}/api/v1/chores/{task_id}/details",
                headers=self._headers(),
                timeout=API_TIMEOUT
            ) as response:
                if response.status in (401, 403, 404):
                    _LOGGER.debug("Donetick task detail endpoint unavailable: HTTP %s", response.status)
                    return None

                response.raise_for_status()
                data = await response.json()
                detail = data.get("res", data) if isinstance(data, dict) else data

                if not isinstance(detail, dict):
                    _LOGGER.debug("Unexpected Donetick task detail response format")
                    return None

                return DonetickTask.from_json(detail)

        except aiohttp.ClientError as err:
            _LOGGER.debug("Unable to fetch Donetick task detail %d: %s", task_id, err)
            return None
        except (KeyError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.debug("Unable to parse Donetick task detail %d: %s", task_id, err)
            return None

    async def async_get_task_history(self, days: int = 30, include_members: bool = True) -> List[DonetickChoreHistory]:
        """Get recent chore history when the full API endpoint is available."""
        params = {
            "limit": max(days, 1),
            "members": "true" if include_members else "false",
        }

        try:
            async with self._session.get(
                f"{self._base_url}/api/v1/chores/history",
                headers=self._headers(),
                params=params,
                timeout=API_TIMEOUT
            ) as response:
                if response.status in (401, 403, 404):
                    _LOGGER.debug("Donetick task history endpoint unavailable: HTTP %s", response.status)
                    return []

                response.raise_for_status()
                data = await response.json()
                history = data.get("res", data) if isinstance(data, dict) else data

                if not isinstance(history, list):
                    _LOGGER.debug("Unexpected Donetick task history response format")
                    return []

                return DonetickChoreHistory.from_json_list(history)

        except aiohttp.ClientError as err:
            _LOGGER.debug("Unable to fetch Donetick task history: %s", err)
            return []
        except (KeyError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.debug("Unable to parse Donetick task history: %s", err)
            return []
