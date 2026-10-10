
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

## Per-user task card

The **Donetick User Tasks** card is bundled with the integration and loaded
automatically when Donetick is set up, for both UI and YAML dashboards. No separate
card installation or dashboard resource registration is required. Reload your browser
after updating the integration, then add **Donetick User Tasks** to any dashboard.
Existing cards and their settings continue to work. Remove any old manually registered
`/local/donetick/donetick-user-todo-card.js` resource to avoid loading an outdated copy.
Its visual editor lets you choose
a Donetick todo entity, the assigned user, a title and button appearance.
Use the All Tasks entity to display any user's tasks; individual assignee entities also work.
Select **All users** to combine their tasks. **Show assigned user** adds the assignee's
name beside the due date in this view when the entity can contain multiple users.
Single-user views omit the name. The setting depends on the view's scope, so it stays
useful even when the current filter happens to match only one user's tasks.
**Allow reassignment** enables a user-switch icon on each row.
Tap it to choose a user, then confirm with the save icon; tap again to close.
When no alternative assignee is available, it explains what to configure in Donetick.
The picker includes only current circle members in that task's Donetick assignee list.
Add eligible assignees in Donetick first if needed. This uses `donetick.update_task`
with `assigned_to`, preserves recurrence, and refreshes all lists. A reassigned task
leaves its previous user's card. Future completion uses the new current assignee.
YAML supports `user_id: all`, `show_assignee: false`, and `show_reassign: false`.
The editor's **Actions to show** switches independently control completion, Skip
occurrence, Change due date, and reassignment. Completion visibility applies to both
the checkbox and button styles. Turn all four off for a display-only card with no
unused action space. Appearance presets preserve these visibility choices.
YAML also supports `show_complete: false`, `show_postpone: false`, and
`show_due_date: false`. All actions remain enabled by default.
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
(from today onward). **Include overdue tasks** is enabled by default for Upcoming,
and includes all past deadlines alongside future tasks. Turn it off to show only tasks
that are still due, including date-only tasks due today. Today includes tasks overdue earlier today.
Overdue due text uses your theme's warning color, with a clock icon beside the due text.
YAML supports `include_overdue: false`.
Each card stores its own filter. Empty cards show the selected user, active filter and
Upcoming day limit so you can see which settings to adjust.
**Sort tasks by** offers earliest due date (the default, with undated tasks last),
highest priority (Urgent through Low, then unspecified), or alphabetical name using
your HA language. Priority ties use due date. YAML supports `sort_by: due_date`,
`sort_by: priority`, and `sort_by: name`. Card visibility remains controlled by HA.
When Upcoming is selected, **Days ahead** limits the window (default 7; empty or 0 means unlimited).
Clearing the field keeps it empty and saves `upcoming_days: null`, without restoring 7.
For example, 3 includes today through the third day from today, including the whole
last day. Set `upcoming_days: 3` in YAML or use the card editor's number field.
Filters use the tasks supplied by the integration. Set its upcoming-task window to 0
if you want every future task available to the card.

**Due date display** offers **Date and time** (the existing default), **Relative**
(for example, In 3 days, Tomorrow, Next week, or 13 hours ago), and **Relative and
date/time**. Relative labels follow your HA language and count calendar days across
daylight-saving changes. Date-only deadlines remain due for their whole day.
The full date is available in the tooltip in every mode. YAML supports
`due_display: date`, `due_display: relative`, or `due_display: both`.

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
Choose a date, then tap the save icon. Save is enabled only for a valid changed date or time.
The clock icon toggles the optional time
field. Tap the original action again to close without saving. The editor stays inline
without an extra task heading.
The inline editor uses HA's native date and time selectors, including its standard
calendar dialog and locale-aware time fields. Browser inputs provide a fallback if
HA's controls cannot be loaded. Tap the task name or due text to expand its description
below the row; tap again to collapse it. Descriptions preserve line breaks and display
as readable plain text, with HTML tags and embedded scripts removed while paragraphs,
line breaks, lists, and decoded entities are preserved. A subtle chevron beside the name indicates an available description
and points upward while expanded. Tasks without a description are plain text and
do not open a panel.
The current time is preserved unless edited with Set time; undated tasks default to 09:00.
Only Save changes the task. Tapping the original action, Escape or tapping outside dismisses the editor.
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
