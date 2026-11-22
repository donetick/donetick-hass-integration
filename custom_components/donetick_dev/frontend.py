"""Serve and automatically load the bundled Donetick frontend modules."""
import asyncio
from hashlib import sha256
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

<<<<<<< HEAD:custom_components/donetick_dev/frontend.py
CARD_URL = "/donetick_dev/donetick-user-todo-card.js"
CARD_FILE = Path(__file__).parent / "frontend" / "donetick-user-todo-card.js"
ACTION_URL = "/donetick_dev/donetick-action-editor.js"
ACTION_FILE = Path(__file__).parent / "frontend" / "donetick-action-editor.js"
DATA_FRONTEND = "donetick_dev_frontend"
=======
FRONTEND_DIR = Path(__file__).parent / "frontend"
CARD_URL = "/donetick/donetick-user-todo-card.js"
CARD_FILE = FRONTEND_DIR / "donetick-user-todo-card.js"
ACTION_URL = "/donetick/donetick-action-editor.js"
ACTION_FILE = FRONTEND_DIR / "donetick-action-editor.js"
REWARDS_URL = "/donetick/donetick-rewards-card.js"
REWARDS_FILE = FRONTEND_DIR / "donetick-rewards-card.js"
CREATE_CARD_URL = "/donetick/donetick-create-task-card.js"
CREATE_CARD_FILE = FRONTEND_DIR / "donetick-create-task-card.js"
CREATE_EDITOR_URL = "/donetick/donetick-create-task-editor.js"
CREATE_EDITOR_FILE = FRONTEND_DIR / "donetick-create-task-editor.js"
DATA_FRONTEND = "donetick_frontend"
>>>>>>> 08829ddcaac572a30a45bb190e16b0d3a24516f9:custom_components/donetick/frontend.py


def _module_version(*files: Path) -> str:
    checksum = sha256()
    for file in files:
        checksum.update(file.read_bytes())
    return checksum.hexdigest()[:12]


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Register once per HA process, including concurrent entries and reloads."""
    state = hass.data.setdefault(DATA_FRONTEND, {"lock": asyncio.Lock()})
    async with state["lock"]:
        if state.get("registered"):
            return
        # Hash file contents outside the event loop to invalidate browser caches.
        card_version = await hass.async_add_executor_job(_module_version, CARD_FILE)
        action_version = await hass.async_add_executor_job(_module_version, ACTION_FILE)
        rewards_version = await hass.async_add_executor_job(_module_version, REWARDS_FILE)
        # The create card forwards its version to the editor's lazy import.
        create_version = await hass.async_add_executor_job(
            _module_version, CREATE_CARD_FILE, CREATE_EDITOR_FILE
        )
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(CARD_URL, str(CARD_FILE), False),
                StaticPathConfig(ACTION_URL, str(ACTION_FILE), False),
                StaticPathConfig(REWARDS_URL, str(REWARDS_FILE), False),
                StaticPathConfig(CREATE_CARD_URL, str(CREATE_CARD_FILE), False),
                StaticPathConfig(CREATE_EDITOR_URL, str(CREATE_EDITOR_FILE), False),
            ]
        )
        add_extra_js_url(hass, f"{CARD_URL}?v={card_version}")
        add_extra_js_url(hass, f"{ACTION_URL}?v={action_version}")
        add_extra_js_url(hass, f"{REWARDS_URL}?v={rewards_version}")
        add_extra_js_url(hass, f"{CREATE_CARD_URL}?v={create_version}")
        state["registered"] = True
