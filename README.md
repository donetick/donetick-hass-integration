
# Donetick Home Assistant Integration

A Home Assistant integration for Donetick that provides support for managing todo lists and controlling "things" as Home Assistant entities.

## Contents

- [Features](#features)
- [Services](#services)
- [Installation](#installation)
- [Configuration](#configuration)
- [Task card and advanced actions](#task-card-and-advanced-actions)

## Features

### Todo lists
- **Multiple Todo Lists**: "All Tasks" view, individual assignee lists, and optional project lists
- **Task Management**: Create, update, delete, and complete tasks
- **Task attributes**: Task descriptions, due dates can be managed in Home Assistant


### Task sensors

Each task sensor exposes `points` and `interval_type` alongside its existing attributes.
For interval tasks, `interval_type` is `hours`, `days`, `weeks`, `months`, or `years`:
`frequency: 6` and `interval_type: weeks` means every six weeks.
The interval type is `null` for other schedules or missing interval metadata.
Points preserve an explicit zero; tasks without a point value expose `null`.

### Member points controls

The number platform creates a writable **Points** number entity for each active
circle member. Its value is the member's available balance (`points` minus
`pointsRedeemed`). Set it to a higher or lower whole number to add or remove that
many points; the step is 1, and the balance cannot be reduced below zero. Changes
are recorded in Donetick's points history. The connected Donetick account must be
a circle admin, and the server must support the member points adjustment API.

### Things integration
- **Sync things**: Control Donetick "things" as Home Assistant entities
- **Multiple Entity Types**: 
  - **Switch**: Boolean things (true/false)
  - **Number**: Numeric things with increment/decrement
  - **Text**: Text input things

### Services
- `donetick.create_task` - Create new tasks
- `donetick.update_task` - Update existing tasks
- `donetick.delete_task` - Delete tasks
- `donetick.complete_task` - Mark tasks complete with user attribution
- `donetick.delete_history` - Delete one history entry of a task, e.g. to undo a completion
- `donetick.complete_assigned_task` - Complete a task as its current assignee, or as the API token owner for tasks assigned to Anyone
- `donetick.postpone_task` - Move a task to its next scheduled occurrence without recording a completion
- `donetick.complete_chore` - Complete a chore through Donetick's full API and credit any active circle member, not only its assignees; the assignees stay unchanged. Choose the task from the searchable picker or by task ID, as with `update_task`. Needs an API token of a circle admin or manager, so everyone who can call this action can record completions for any member

See the [services and automation guide](docs/actions.md) for completion behavior, undoing completions, task creation, points, reminders, and assignment.

## Installation

### Install from Marketplace
1. Open Marketplace in Home Assistant
2. Navigate to Integrations  
3. Click "⋮" → "Custom repositories"
4. Add repository: `https://github.com/donetick/donetick-hass-integration/`
5. Category: Integration
6. Search for "Donetick" and install
7. Restart Home Assistant

## Configuration

Configure via **Settings** → **Devices & Services** → **Add Integration** → **Donetick**

**Required:**
- **Server URL**: 
  - Cloud: `https://api.donetick.com`
  - Self-hosted: `http://your-host:2021` (or your port)
- **API Token**: Generate from Donetick user settings

### Connecting to the Home Assistant app

For the [Donetick Home Assistant app](https://github.com/donetick/hassio-addons),
use `http://<HA-host-IP>:2021`, for example `http://192.168.1.50:2021`.
When Home Assistant and the app run on the same host, `http://localhost:2021`
can also work. If you changed the app's exposed port under its **Network**
settings, use that port instead of `2021`.

The URL must reach Donetick from Home Assistant, rather than from your browser.
Your Home Assistant dashboard URL, ingress URL, or DuckDNS address does not
automatically route to Donetick. A hostname such as `homeassistant.local` only
works if Home Assistant can resolve it and reach Donetick on the specified port.

### Changing the server URL or API token

Go to **Settings > Devices & services > Donetick**, open the integration entry's
three-dot menu, and choose **Reconfigure**. Update the server URL and optionally
enter a replacement API token; leave the token blank to keep the existing one.
The connection is checked before saving, then the integration reloads. Existing
entity IDs, task settings, and user mappings are retained. A failed connection
leaves the saved configuration unchanged.

Use this for an address change or token replacement on the same Donetick server
and circle. To connect to a different server or circle, add a separate integration:
user, task, and project IDs and existing mappings may refer to different records.

### Task list settings

**Optional:**
- **Show Due In**: Days ahead to display upcoming tasks (default: 7)
- **Create Unified List**: Enable "All Tasks" todo list (default: true)  
- **Create Assignee Lists**: Individual todo lists per user (default: false) 

## Task card and advanced actions

The integration bundles the **Donetick User Tasks** card. It works in UI and YAML dashboards and needs no separate installation or resource registration. The full guide covers task filters, completed history, appearance, reassignment, due-date editing, completion attribution, HA user mapping, action pickers, and repeat schedules.

- [Task card guide](docs/task-card.md)
