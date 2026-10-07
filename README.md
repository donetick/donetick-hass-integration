
# Donetick Dev Home Assistant Integration



A Home Assistant integration for Donetick that provides support for managing todo lists and controlling "things" as Home Assistant entities.

> [!WARNING]  
> This version of the integration requires Donetick server version **0.1.53** or greater.

## Features

### 📋 Todo Lists
- **Multiple Todo Lists**: "All Tasks" view and individual assignee-specific lists
- **Task Management**: Create, update, delete, and complete tasks
- **Task attributes**: Task descriptions, due dates can be managed in Home Assistant


### 🔧 Things Integration  
- **Sync things**: Control Donetick "things" as Home Assistant entities
- **Multiple Entity Types**: 
  - **Switch**: Boolean things (true/false)
  - **Number**: Numeric things with increment/decrement
  - **Text**: Text input things

### 🔧 Services
- `donetick_dev.create_task` - Create new tasks
- `donetick_dev.update_task` - Update existing tasks
- `donetick_dev.delete_task` - Delete tasks
- `donetick_dev.complete_task` - Mark tasks complete with user attribution

To reactivate an archived task with `donetick_dev.update_task`, set `force_unarchive: true`. This requires a Donetick server that supports `forceUnarchive`.

## Running alongside upstream Donetick

This fork uses the Home Assistant domain `donetick_dev`, while upstream uses
`donetick`. Their config flows, services, runtime data, and device and entity
registry identities are separate, following Home Assistant's
[unique domain requirement](https://developers.home-assistant.io/docs/creating_integration_manifest/).

Install upstream from `donetick/donetick-hass-integration` and this fork from
`torbenvanassche/donetick-hass-integration`. For manual installation, keep both
folders in your Home Assistant configuration directory:

```text
custom_components/
  donetick/      # upstream
  donetick_dev/  # this fork
```

Restart Home Assistant, then add **Donetick** and **Donetick Dev** separately in
**Settings → Devices & Services**. Each has its own server URL and API token,
allowing connections to different servers or to the same server.

Use `donetick.*` actions for upstream and `donetick_dev.*` actions for this fork.
The YAML in `examples/` targets the fork. Select the fork's actual entity IDs in
your dashboards; Home Assistant may add suffixes where entity names overlap.
Service calls specifying `config_entry_id` must use a loaded Donetick Dev entry
(or its todo entity ID).

If you previously installed this fork under `donetick`, existing entries remain
under that domain; there is no automatic migration. Install upstream into
`custom_components/donetick`, install this fork into `custom_components/donetick_dev`,
and add a new **Donetick Dev** entry. Update automations intended for the fork
to use its new actions and entities.

Both integrations affect the same tasks when connected to the same server.

## Installation

### Via HACS
1. Open HACS in Home Assistant
2. Navigate to Integrations  
3. Click "⋮" → "Custom repositories"
4. Add repository: `https://github.com/torbenvanassche/donetick-hass-integration/`
5. Category: Integration
6. Search for "Donetick Dev" and install
7. Restart Home Assistant

## Configuration

Configure via **Settings** → **Devices & Services** → **Add Integration** → **Donetick Dev**

**Required:**
- **Server URL**: 
  - Cloud: `https://api.donetick.com`
  - Self-hosted: `http://your-host:2021` (or your port)
- **API Token**: Generate from Donetick user settings

**Optional:**
- **Show Due In**: Days ahead to display upcoming tasks (default: 7)
- **Create Unified List**: Enable "All Tasks" todo list (default: true)  
- **Create Assignee Lists**: Individual todo lists per user (default: false) 
