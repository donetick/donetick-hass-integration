"""API client for Donetick."""
import logging
from datetime import datetime
import json
from typing import List, Optional
import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_TIMEOUT
from .model import DonetickTask
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

    async def async_get_things(self) -> List[dict]:
        """Get things from Donetick."""
        headers = {
            "secretkey": f"{self._token}",
            "Content-Type": "application/json",
        }
        
        try:
            async with self._session.get(
                f"{self._base_url}/eapi/v1/thing",
                headers=headers,
                timeout=API_TIMEOUT
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                if not isinstance(data, list) :
                    _LOGGER.error("Unexpected response format from Donetick API")
                    return []
                
                return data
                
        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching things from Donetick: %s", err)
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.error("Error parsing Donetick response: %s", err)
            return []
