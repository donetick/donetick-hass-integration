"""API client for Donetick."""
import logging
from datetime import datetime
import json
from typing import List, Optional
import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_TIMEOUT
from .model import DonetickTask, DonetickThing
_LOGGER = logging.getLogger(__name__)

class DonetickApiClient:
    """API client for Donetick."""

    def __init__(self, base_url: str, token: str, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self._base_url = base_url.rstrip('/')
        self._token = token
        self._session = session

    async def async_get_tasks(self) -> List[DonetickTask]:
        """Get tasks from Donetick."""
        headers = {
            "secretkey": f"{self._token}",
            "Content-Type": "application/json",
        }
        
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

    async def async_get_things(self) -> List[DonetickThing]:
        """Get things from Donetick."""
        headers = {
            "secretkey": f"{self._token}",
            "Content-Type": "application/json",
        }
        
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
        headers = {
            "secretkey": f"{self._token}",
            "Content-Type": "application/json",
        }
        
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
        headers = {
            "secretkey": f"{self._token}",
            "Content-Type": "application/json",
        }
        
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
        headers = {
            "secretkey": f"{self._token}",
            "Content-Type": "application/json",
        }
        
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


    async def async_complete_task(self, choreId: int) -> DonetickTask:
        """Complete a task"""
        headers = {
            "secretkey": f"{self._token}",
            "Content-Type": "application/json",
        }

        try:
            async with self._session.post(
                f"{self._base_url}/eapi/v1/chore/{choreId}/complete",
                headers=headers,
                timeout=API_TIMEOUT
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return DonetickTask.from_json(data)

        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching tasks from Donetick: %s", err)
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.error("Error parsing Donetick response: %s", err)
            return []