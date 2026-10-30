"""Resolve completion credit from an explicit performer or HA action context."""
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_MAP_COMPLETION_USER, CONF_USER_MAPPING, CONF_UNMAPPED_USER


def completion_user(entry, context, default=None, explicit=None, ha_user=None):
    """Keep legacy defaults unless mapping is enabled; never infer from names."""
    if explicit is not None and ha_user is not None:
        raise HomeAssistantError("Choose either completed_by or completed_by_ha_user, not both")
    data = getattr(entry, "data", {})
    if ha_user is not None:
        member_id = data.get(CONF_USER_MAPPING, {}).get(ha_user)
        if type(member_id) is not int or member_id <= 0:
            raise HomeAssistantError(
                "The selected HA user has no Donetick mapping for this integration. "
                "Configure User mapping or provide completed_by instead.")
        return member_id
    if explicit is not None:
        return explicit
    if not data.get(CONF_MAP_COMPLETION_USER, False):
        return default
    user_id = getattr(context, "user_id", None)
    member_id = data.get(CONF_USER_MAPPING, {}).get(user_id)
    if type(member_id) is int and member_id > 0:
        return member_id
    if data.get(CONF_UNMAPPED_USER, "existing") == "require_mapping":
        raise HomeAssistantError(
            "No Donetick user is mapped to the HA user for this action. "
            "Configure User mapping or explicitly choose who completed the task. "
            "Automations without a user must provide completed_by or use the existing-behavior fallback.")
    return default


def username_mappings(users, members, existing=None):
    """Suggest only unique local login username matches, preserving explicit links."""
    mappings = dict(existing or {})
    ha_names = {}
    member_names = {}
    for user in users:
        if not user.is_active or user.system_generated:
            continue
        names = {credential.data.get("username", "").strip().casefold()
                 for credential in getattr(user, "credentials", [])
                 if credential.auth_provider_type == "homeassistant"
                 and isinstance(credential.data.get("username"), str)}
        # Multiple different login identities must be mapped manually.
        names.discard("")
        if len(names) == 1:
            ha_names.setdefault(names.pop(), []).append(user.id)
    for member in members:
        if member.is_active and isinstance(member.username, str) and member.username.strip():
            member_names.setdefault(member.username.strip().casefold(), []).append(member.user_id)
    for name, ids in ha_names.items():
        candidates = member_names.get(name, [])
        if len(ids) == 1 and len(candidates) == 1 and ids[0] not in mappings:
            mappings[ids[0]] = candidates[0]
    return mappings
