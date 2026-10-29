"""Searchable action choices, resolved within a single Donetick integration."""
from copy import copy, deepcopy

from homeassistant.auth import EVENT_USER_ADDED, EVENT_USER_REMOVED, EVENT_USER_UPDATED
from homeassistant.const import EVENT_SERVICE_REGISTERED
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_get_all_descriptions, async_set_service_schema

from .const import DOMAIN


async def async_refresh_action_selectors(hass):
    """Use scoped values because HA shares action descriptions across entries."""
    users = [user for user in await hass.auth.async_get_users()
             if user.is_active and not user.system_generated]
    names = [user.name or user.id for user in users]
    ha_options = [
        {"value": user.id, "label": (user.name or user.id)
         if names.count(user.name or user.id) == 1 else f"{user.name or user.id} ({user.id})"}
        for user in sorted(users, key=lambda user: (user.name or user.id).casefold())
    ]
    tasks, members, integrations = [], [], []
    for entry_id, config in hass.data.get(DOMAIN, {}).items():
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            continue
        reference = entry_id[-6:]
        if sum(key.endswith(reference) for key in hass.data[DOMAIN]) != 1:
            reference = entry_id
        label = f"{entry.title} ({reference})"
        integrations.append({"value": entry_id, "label": label})
        active_members = [member for member in config.get("circle_members", []) if member.is_active]
        usernames = {member.user_id: member.username for member in active_members}
        members.extend({"value": f"{entry_id}/{member.username}",
                        "label": f"{member.username} · {label}"} for member in active_members)
        for task in config["coordinator"].data or []:
            if not task.is_active:
                continue
            assignee = usernames.get(task.assigned_to, "Anyone" if task.assigned_to is None else f"User #{task.assigned_to}")
            project = f" · Project #{task.project_id}" if task.project_id is not None else ""
            task_label = f"#{task.id} · {assignee} · {task.name}{project} · {label}"
            # The searchable HA picker displays its stored value. Resolve the
            # number and integration suffix so renamed tasks still work.
            tasks.append({"value": task_label, "label": task_label})
    options = {"task": tasks, "completed_by_ha_user": ha_options,
               "completed_by_username": members, "assigned_to_username": members,
               "config_entry_id": integrations}
    descriptions = await async_get_all_descriptions(hass)
    for service, original in descriptions.get(DOMAIN, {}).items():
        description = deepcopy(original)
        for field, choices in options.items():
            if field in description["fields"]:
                selector = {"options": sorted(choices, key=lambda choice: choice["label"].casefold()),
                            "mode": "dropdown"}
                if field in ("task", "config_entry_id"):
                    selector["custom_value"] = True
                description["fields"][field]["selector"] = {"select": selector}
        if description != original:
            async_set_service_schema(hass, DOMAIN, service, description)
            # Connected editors refresh cached action descriptions on this event.
            hass.bus.async_fire(EVENT_SERVICE_REGISTERED, {"domain": DOMAIN, "service": service})


async def async_setup_action_selectors(hass, entry):
    """Keep task choices current after coordinator updates and entry reloads."""
    async def refresh(_event=None):
        await async_refresh_action_selectors(hass)

    def schedule_refresh():
        hass.async_create_task(refresh())

    await refresh()
    entry.async_on_unload(hass.data[DOMAIN][entry.entry_id]["coordinator"].async_add_listener(schedule_refresh))
    for event in (EVENT_USER_ADDED, EVENT_USER_REMOVED, EVENT_USER_UPDATED):
        entry.async_on_unload(hass.bus.async_listen(event, refresh))


async def async_prepare_action_call(hass, call, resolve_entry):
    """Resolve selectors to legacy IDs before any action changes a task."""
    data = dict(call.data)
    if call.service != "create_task":
        if ("task" in data) == ("task_id" in data):
            raise HomeAssistantError("Choose either Task or Task ID, not both; one is required")
    performer_fields = ("completed_by", "completed_by_ha_user", "completed_by_username")
    if sum(field in data for field in performer_fields) > 1:
        raise HomeAssistantError("Choose only one completion performer: ID, HA user, or Donetick username")
    if "assigned_to" in data and "assigned_to_username" in data:
        raise HomeAssistantError("Choose either Assignee User ID or Assignee username, not both")

    scoped_entry = None
    for field in ("task", "completed_by_username", "assigned_to_username"):
        if field not in data:
            continue
        value = data[field]
        if field == "task" and value.startswith("#") and " · " in value and value.endswith(")") and " (" in value:
            task_id = value.split(" · ", 1)[0][1:]
            reference = value.rsplit(" (", 1)[1][:-1]
            entries = [key for key in hass.data.get(DOMAIN, {}) if key.endswith(reference)]
            if len(entries) != 1:
                raise HomeAssistantError("The task's integration is unavailable or ambiguous; choose the task again or use Task ID")
            value = f"{entries[0]}/{task_id}"
        if "/" in value:
            entry_id, value = value.split("/", 1)
            if scoped_entry is not None and entry_id != scoped_entry:
                raise HomeAssistantError("Task and username selections must use the same Donetick integration")
            scoped_entry = entry_id
        elif field == "task":
            raise HomeAssistantError("Choose a task from the picker or provide task_id")
        data[field] = value

    selector = data.get("config_entry_id")
    entry = await resolve_entry(hass, selector if selector is not None else scoped_entry)
    if entry is None:
        raise HomeAssistantError("No matching Donetick integration found")
    if scoped_entry is not None and scoped_entry != entry.entry_id:
        raise HomeAssistantError("The selected task or username belongs to a different Donetick integration")
    data["config_entry_id"] = entry.entry_id
    if "task" in data:
        try:
            task_id = int(data.pop("task"))
            if task_id < 1:
                raise ValueError
        except ValueError as err:
            raise HomeAssistantError("Invalid task selection; choose a task again") from err
        data["task_id"] = task_id

    username_fields = {"completed_by_username": "completed_by", "assigned_to_username": "assigned_to"}
    if any(field in data for field in username_fields):
        # Check current membership rather than trusting a cached dropdown.
        try:
            members = await hass.data[DOMAIN][entry.entry_id]["client"].async_get_circle_members()
        except Exception as err:
            raise HomeAssistantError("Unable to load current Donetick users; check the integration connection") from err
        for field, target in username_fields.items():
            if field not in data:
                continue
            username = data.pop(field)
            matches = [member for member in members if member.is_active and member.username == username]
            if len(matches) != 1:
                raise HomeAssistantError(f"Donetick username '{username}' is unavailable or ambiguous in this integration")
            data[target] = matches[0].user_id
    prepared = copy(call)
    prepared.data = data
    return prepared
