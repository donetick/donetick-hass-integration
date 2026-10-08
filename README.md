
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
display_filter: all
button_style: text
button_size: compact
button_shape: pill
button_content: icon
```

Choose **Display filter** in the card editor: **All tasks** (including undated), **Overdue**
(due date/time has passed), **Today** (due on the current local date), or **Upcoming**
(from tomorrow onward). Today can include tasks already overdue earlier today.
Each card stores its own filter. Empty cards show the selected user, active filter and
Upcoming day limit so you can see which settings to adjust.
When Upcoming is selected, **Days ahead** limits the window (default 7; 0 means unlimited).
For example, 3 includes tomorrow through the third day from today, including the whole
last day. Set `upcoming_days: 3` in YAML or use the card editor's number field.
Filters use the tasks supplied by the integration. Set its upcoming-task window to 0
if you want every future task available to the card.

Complete fetches the current task from Donetick and attributes completion to its actual
assigned user, even if someone else clicks the button. Unassigned tasks cannot be completed
with this action. **Skip occurrence** (the `donetick.postpone_task` action) uses Donetick's internal skip/rescheduling endpoint to advance
to the next occurrence. Donetick records a skipped occurrence, keeps the assignee and
calculates the next date from the task's schedule. Tasks without a recurring schedule
have Skip occurrence hidden. Tap the icon to open a confirmation; tap it again to close
without changing the task. Confirming Skip advances the schedule. Actions refresh the list
and show errors in the card.

Each row shows a **Change due date** calendar-edit icon beside the other actions, including
for one-off tasks. Tap to open a slim inline editor below that row, or tap again to close.
Choose a date, then tap the check icon to save. The clock icon toggles the optional time
field; the close icon cancels. There is no floating popup or extra task heading.
The current time is preserved unless edited with Set time; undated tasks default to 09:00.
Only Save changes the task. Cancel, Escape or tapping outside dismisses the editor.
This uses `donetick.update_task` without skipping an occurrence or changing recurrence.
Dates use your browser's time zone; its name appears only when editing the time. Requests
send explicit UTC timestamps. The editor stays open after a service failure for retry.

By default each compact row has a completion checkbox on the left, the task and date in
the middle, and horizontal action icons on the right: calendar-arrow-right to skip to
the next occurrence, and calendar-edit to choose a date. The checkbox and buttons have
at least 44 × 44 pixel tap targets, with spacing between buttons,
accessible action names and hover tooltips. Due text shows Today, Tomorrow or Overdue,
including the local due time when available (following HA's 12/24-hour preference).
Overdue labels use the theme's warning color. Local 23:59 end-of-day placeholders are
hidden from the label and tooltip. The full date is available in a tooltip.
Tasks sort by due date, with undated tasks last. Completion
briefly shows a checked, struck-through row. Successful actions update the list without
extra confirmation text; failures remain visible.
The card editor uses native Home Assistant form controls: entity and user selectors,
searchable icon pickers, theme color choices, and helper text explaining each setting.
Choose a **Starting style** (HA todo, icons with labels, outlined or filled buttons), then
expand **Fine-tune appearance** or **Customize individual actions** when needed. Presets
reset action icon, label and color overrides while preserving the list, user, filter and
title. Completion-specific action customization appears when completion uses a button.
The HA dashboard editor's live preview reflects each change. Existing YAML options remain
supported, including custom CSS colors and variables such as `var(--success-color)`.
