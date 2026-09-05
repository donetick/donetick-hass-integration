"""Test bootstrap that loads the API client without Home Assistant Core."""

import sys
import types
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "donetick"

custom_components = types.ModuleType("custom_components")
custom_components.__path__ = [str(ROOT / "custom_components")]
sys.modules.setdefault("custom_components", custom_components)

donetick = types.ModuleType("custom_components.donetick")
donetick.__path__ = [str(COMPONENT)]
sys.modules.setdefault("custom_components.donetick", donetick)

model = types.ModuleType("custom_components.donetick.model")
for name in (
    "DonetickTask",
    "DonetickThing",
    "DonetickMember",
    "DonetickChoreHistory",
):
    setattr(model, name, type(name, (), {}))
sys.modules.setdefault("custom_components.donetick.model", model)

homeassistant = cast(Any, types.ModuleType("homeassistant"))
helpers = cast(Any, types.ModuleType("homeassistant.helpers"))
aiohttp_client = cast(Any, types.ModuleType("homeassistant.helpers.aiohttp_client"))
aiohttp_client.async_get_clientsession = lambda hass: None
helpers.aiohttp_client = aiohttp_client
homeassistant.helpers = helpers
sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.helpers", helpers)
sys.modules.setdefault("homeassistant.helpers.aiohttp_client", aiohttp_client)
