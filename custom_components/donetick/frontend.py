"""Serve and automatically load the bundled Donetick dashboard card."""
import asyncio
from hashlib import sha256
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

CARD_URL = "/donetick/donetick-user-todo-card.js"
CARD_FILE = Path(__file__).parent / "frontend" / "donetick-user-todo-card.js"
DATA_FRONTEND = "donetick_frontend"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Register once per HA process, including concurrent entries and reloads."""
    state = hass.data.setdefault(DATA_FRONTEND, {"lock": asyncio.Lock()})
    async with state["lock"]:
        if state.get("registered"):
            return
        # File IO runs outside the event loop. A content hash invalidates browser
        # caches whenever HACS installs a changed card, without a second version.
        content = await hass.async_add_executor_job(CARD_FILE.read_bytes)
        version = sha256(content).hexdigest()[:12]
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(CARD_FILE), False)]
        )
        add_extra_js_url(hass, f"{CARD_URL}?v={version}")
        state["registered"] = True
