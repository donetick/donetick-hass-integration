
# Donetick Home Assistant Integration



A Home Assistant integration for Donetick that provides support for managing todo lists and controlling "things" as Home Assistant entities.

> [!WARNING]  
> This version of the integration requires Donetick server version **0.1.53** or greater.

## Features

### 📋 Todo Lists
- **Multiple Todo Lists**: "All Tasks" view, individual assignee lists, and optional project lists
- **Task Management**: Create, update, delete, and complete tasks
- **Task attributes**: Task descriptions, due dates can be managed in Home Assistant


### 🔧 Things Integration  
- **Sync things**: Control Donetick "things" as Home Assistant entities
- **Multiple Entity Types**: 
  - **Switch**: Boolean things (true/false)
  - **Number**: Numeric things with increment/decrement
  - **Text**: Text input things

### 🔧 Services
- `donetick.create_task` - Create new tasks
- `donetick.update_task` - Update existing tasks
- `donetick.delete_task` - Delete tasks
- `donetick.complete_task` - Mark tasks complete with user attribution

To reactivate an archived task with `donetick.update_task`, set `force_unarchive: true`. This requires a Donetick server that supports `forceUnarchive`.

To assign a task, call `donetick.update_task` with `task_id` and `assigned_to` set to a Donetick user ID. The user must already be in that task's assignee list, and the API token must have permission to edit the task.

## Installation

### Via HACS
1. Open HACS in Home Assistant
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

**Optional:**
- **Show Due In**: Days ahead to display upcoming tasks (default: 7)
- **Create Unified List**: Enable "All Tasks" todo list (default: true)  
- **Create Assignee Lists**: Individual todo lists per user (default: false) 

## Per-user task card (feature branch)

Copy `www/donetick-user-todo-card.js` to `/config/www/donetick/` and register
`/local/donetick/donetick-user-todo-card.js` as a JavaScript module in dashboard resources.
Then add **Donetick User Tasks** to any dashboard. Its visual editor lets you choose
a Donetick todo entity, the assigned user, a title and button appearance.
Use the All Tasks entity to display any user's tasks; individual assignee entities also work.
The card respects the integration's upcoming-task window. Set it to 0 to show all tasks.

```yaml
type: custom:donetick-user-todo-card
entity: todo.all_tasks
user_id: 1
button_style: text
button_size: compact
button_shape: pill
button_content: icon
```

Complete fetches the current task from Donetick and attributes completion to its actual
assigned user, even if someone else clicks the button. Unassigned tasks cannot be completed
with this action. Postpone uses Donetick's internal skip/rescheduling endpoint to advance
to the next occurrence. Donetick records a skipped occurrence, keeps the assignee and
calculates the next date from the task's schedule. Tasks without a recurring schedule
have Postpone hidden. Actions refresh the list and show errors in the card.

Each row shows **Change due date** beneath its date, including for one-off tasks. Choose a date
and time, then Save. This uses the existing `donetick.update_task` action; it does not skip
an occurrence or change the task's recurrence pattern. The picker shows your browser's
time zone and sends an explicit UTC timestamp. Cancel leaves the task unchanged.

By default each row resembles HA todo items: a completion checkbox and a small reschedule icon.
The card editor supports a completion checkbox or button; outlined, text or filled buttons; compact, normal or large sizes;
rounded, pill or square shapes; labels, icons or both; and separate labels, MDI icons and
colors for each action. Defaults follow the HA theme. Colors accept CSS colors or HA
variables, for example `var(--success-color)`.
