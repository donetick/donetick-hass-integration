
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
a Donetick todo entity, the assigned user, a title and the days to postpone.
Use the All Tasks entity to display any user's tasks; individual assignee entities also work.
The card respects the integration's upcoming-task window. Set it to 0 to show all tasks.

```yaml
type: custom:donetick-user-todo-card
entity: todo.all_tasks
user_id: 1
postpone_days: 1
```

Complete fetches the current task from Donetick and attributes completion to its actual
assigned user, even if someone else clicks the button. Unassigned tasks cannot be completed
with this action. Postpone keeps the assignment and moves the due date forward by the
configured number of days, using Home Assistant's local timezone. For overdue or undated
tasks it starts from now. Recurring task schedules are preserved; postponing does not
complete or skip the task. Actions refresh the list and show errors in the card.
