
# Donetick Home Assistant Integration



A Home Assistant integration for Donetick that provides support for managing todo lists and controlling "things" as Home Assistant entities.

## Features

### 📋 Todo Lists
- **Multiple Todo Lists**: "All Tasks" view, individual assignee lists, and optional project lists
- **Task Management**: Create, update, delete, and complete tasks
- **Task attributes**: Task descriptions, due dates can be managed in Home Assistant


### Task sensors

Each task sensor exposes `points` and `interval_type` alongside its existing attributes.
For interval tasks, `interval_type` is `hours`, `days`, `weeks`, `months`, or `years`:
`frequency: 6` and `interval_type: weeks` means every six weeks.
The interval type is `null` for other schedules or missing interval metadata.
Points preserve an explicit zero; tasks without a point value expose `null`.

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
- `donetick.complete_assigned_task` - Complete a task as its current assignee, or as the API token owner for tasks assigned to Anyone
- `donetick.postpone_task` - Move a task to its next scheduled occurrence without recording a completion

The bundled task card uses the last two for its completion control and its **Skip
occurrence** action; both resolve the task on the server before acting.

To reactivate an archived task with `donetick.update_task`, set `force_unarchive: true`. This requires a Donetick server that supports `forceUnarchive`.

When calling `donetick.create_task`, set `created_by` to a Donetick circle member's user ID to create and assign the task to that member. Omitting it uses the API token owner. Tasks created from a member's todo list also belong to that member. The optional `due_date` is sent in RFC3339 format.

To assign a task, call `donetick.update_task` with `task_id` and `assigned_to` set to a Donetick circle member's user ID, or `null` for Anyone. Selecting a member outside the task's assignee list adds them to that list while preserving the existing members and assignment strategy. This and switching to or from Anyone use Donetick's task editor and require permission to edit the task. Donetick remains authoritative on membership and private-project restrictions.

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

The existing card includes a **Completed today** section by default, showing the
completion time and performer. **Task view** can show pending tasks, completed
tasks only, or both (`task_view: pending`, `completed`, or `both`). History survives
a browser refresh and includes completions made outside Home Assistant.

Expand **Completed tasks** in the editor to adjust:

| Setting | Default | Options |
| --- | --- | --- |
| History period | Today | 1–7 calendar days, including today (`completed_days`) |
| Completed tasks to include | All completions in the period | Match task date filter uses the completed occurrence's original due date (`completed_filter: matching`); `all` ignores due-date filters |
| Maximum completed entries | All | 0 for all, or 1–500 entries, newest first (`completed_limit`) |

These settings disappear in pending-only mode and are preserved when switching
views or appearance presets. Completed entries are always filtered by the selected
performer and list/project. For tasks due today with their completed occurrences:

```yaml
type: custom:donetick-user-todo-card
entity: todo.all_tasks
user_id: all
display_filters: [today]
task_view: both
completed_filter: matching
completed_days: 1
```

Change `completed_filter` to `all` to also include tasks completed today that were
due earlier or had no due date. Increase `completed_days` for a longer history,
or use `task_view: completed` for a separate history card with the same component.

The editor starts with **Basics** (list, user, title, task view), followed by
**Task filters**, **Completed tasks**, **Task details**, **Available actions**, and **Appearance**.
Shared label filters always stay in Task filters, with choices from pending,
Anyone, and completed tasks as well as saved selections. Basics and task filters
start open; detailed settings stay collapsed. Completed-only
mode hides pending actions, sorting, and button appearance. If completion filtering
uses original due dates, its date controls remain available. Action icon, label, and
color settings sit together in a separate **Customize action icons, labels and colors**
section, without nested expandable sections. Task details contains points, recurrence,
labels and date display; Available actions controls completion, skipping, date changes
and reassignment. Appearance contains the preset and button layout controls.
Editable fields can be cleared before typing a replacement without restoring defaults.
Collapsed editor sections load their controls only when opened and retain their
values when closed. Unrelated HA state updates leave the editor and preview intact.

Native Home Assistant to-do lists also expose today's completed occurrences.
Recurring tasks keep their next pending occurrence separately. Completed records
have distinct history IDs and are read-only; edit or remove history in Donetick.
Per-user lists attribute completions to the performer, even if the next occurrence
is assigned to someone else. The integration retrieves seven days of history and
the native list selects today in the Home Assistant timezone. The card uses the
browser's local calendar days for its configured history period.
History requires access to Donetick's `/api/v1/chores/history` endpoint; unavailable
history leaves pending-task functionality intact.

Under **Task details**, enable **Show task points** or **Show recurrence** to display
points as a small badge beside the task name and recurrence on a separate muted line.
The due date and assignee keep their existing layout. Both options are off by default and also work in YAML:
`show_points: true` and `show_recurrence: true`. For example, an interval task can show
`10 points · Every 6 weeks`. Explicit zero points are shown; unset points and incomplete
interval metadata are omitted. The task sensors expose these values independently
of the card options.

Choose one or more **Labels** in the card editor. With two or more selected, **Match labels** offers **Any selected label (OR)** (the default) or **All selected labels (AND)**. Leave the selection empty to show all labels, including unlabelled tasks. Label names are matched exactly and combine with the assigned-user, date and sorting settings. Choices come from tasks in the selected Donetick list; saved selections remain available even when no current task has those labels. YAML supports `label_match: any` or `label_match: all`.

**Show labels** is off by default. Enable it to display small label chips below each task's due date; long names and multiple labels wrap within the task column. Tasks without labels keep their existing layout. YAML supports `show_labels: true`.

Enable **Use Donetick label colors** under **Task details** after enabling **Show labels**
to match each label's Donetick background and black or white text. This is off by
default; labels without color metadata or a valid hex color keep the neutral style.
YAML supports `use_label_colors: true` alongside `show_labels: true`.

**Task spacing** under **Appearance** controls row padding. YAML supports
`row_spacing: auto` (default; extra space for visible labels), `compact`, or `comfortable`
(extra space for every task). Appearance presets preserve this setting.

For a maintenance dashboard with tasks due months ahead, set the integration's upcoming-task window to **0** (unlimited). Then leave **Pending task dates** empty for all tasks, or select **Overdue**, **Today** and **Future** with **Days ahead** empty or **0**. A card cannot show tasks excluded by the integration's window. YAML supports the same selections:

```yaml
type: custom:donetick-user-todo-card
entity: todo.all_tasks
user_id: all
labels:
  - maintenance
  - technical
display_filters: [overdue, today, future]
upcoming_days: 0
```


The **Donetick User Tasks** card is bundled with the integration and loaded
automatically when Donetick is set up, for both UI and YAML dashboards. No separate
card installation or dashboard resource registration is required. Reload your browser
after updating the integration, then add **Donetick User Tasks** to any dashboard.
Existing cards and their settings continue to work. Remove any old manually registered
`/local/donetick/donetick-user-todo-card.js` resource to avoid loading an outdated copy.
Its visual editor lets you choose
a Donetick todo entity, the assigned user, a title and button appearance.
Use the All Tasks entity to display any user's tasks; individual assignee entities also work.
Enable **Include tasks assigned to Anyone** to show Anyone tasks alongside the selected
user's tasks. This is off by default and works with both All Tasks and individual
assignee entities. YAML supports `include_anyone: true`. Date filters and sorting
apply to both groups, and Anyone completions are credited to the API token owner.
Select **All users** to combine their tasks. **Show assigned user** adds the assignee's
name beside the due date in this view, or when Anyone tasks are included beside a selected user.
Views containing only one user's tasks omit the name. The setting depends on the view's scope, so it stays
useful even when the current filter happens to match only one user's tasks.
**Allow reassignment** enables a user-switch icon on each row.
Tap it to choose **Anyone** or a user, then confirm with the save icon; tap again to close.
The picker includes Anyone even in a single-user circle. By default, user choices
are active members already in the task's eligible assignee list. Tasks without an
eligible list, including Anyone tasks, offer all active circle members.
Enable **Allow assigning any circle member** under **Available actions**
(`allow_any_assignee: true`) to also offer members outside an existing eligible list.
This option is off by default. Selecting a new member adds them to the eligible list,
so they may receive future assignments. Existing members and the assignment strategy
are retained. Selecting Anyone disables automatic user assignment;
selecting a user for an Anyone task keeps that user assigned on future occurrences.
Switching to or from Anyone requires permission to edit the task. This uses `donetick.update_task`
with `assigned_to`, preserves recurrence, and refreshes all lists. A reassigned task
leaves its previous user's card. Future completion uses the new current assignee.
YAML supports `user_id: all`, `show_assignee: false`, and `show_reassign: false`.
For a per-user task list such as **admin's Tasks**, the editor hides **Assigned user** and the card uses the list's owner automatically. YAML can omit `user_id` for these lists; any older user selection is overridden by the list's owner.
The editor's **Toggles** section groups label display, assigned names, completion, Skip
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
display_filters: []
button_style: text
button_size: compact
button_shape: pill
button_content: icon
```

Choose one or more groups in **Pending task dates**: **Overdue** (due date/time has passed),
**Today** (due on the current local date), **Future** (from tomorrow onward), and
**Without a due date**. A task appears if it matches any selected group, without duplicates.
Leave the selection empty for all tasks. Today includes tasks overdue earlier today.
Overdue due text uses your theme's warning color, with a clock icon beside the due text.
YAML supports `display_filters: [overdue, today, future, undated]` or `display_filters: []`.
The editor replaces **Include overdue tasks** with the **Overdue** selection. Existing
`display_filter: all/overdue/today/upcoming` and `include_overdue` YAML settings keep
their original behavior until you change **Pending task dates**. New `display_filters`
selections take precedence over those legacy settings.
Each card stores its own filter. Empty cards show the selected user, active filter and
Future day limit so you can see which settings to adjust.
**Sort tasks by** offers earliest due date (the default, with undated tasks last),
highest priority (Urgent through Low, then unspecified), or alphabetical name using
your HA language. Priority ties use due date. YAML supports `sort_by: due_date`,
`sort_by: priority`, and `sort_by: name`. Card visibility remains controlled by HA.
When Future is selected, **Days ahead** limits that group (default 7; empty or 0 means unlimited).
Clearing the field keeps it empty and saves `upcoming_days: null`, without restoring 7.
For example, 3 includes tomorrow through the third day from today, including the whole
last day. The other selected groups remain visible regardless of this limit.
Set `upcoming_days: 3` in YAML or use the card editor's number field.
Filters use the tasks supplied by the integration. Set its upcoming-task window to 0
if you want every future task available to the card.

**Due date display** offers **Date and time** (the existing default), **Relative**
(for example, In 3 days, Tomorrow, Next week, or 13 hours ago), and **Relative and
date/time**. Relative labels follow your HA language and count calendar days across
daylight-saving changes. Date-only deadlines remain due for their whole day.
The full date is available in the tooltip in every mode. YAML supports
`due_display: date`, `due_display: relative`, or `due_display: both`.

Complete fetches the current task from Donetick and attributes completion to its actual
assigned user, even if someone else clicks the button. Tasks assigned to **Anyone** are
completed as the Donetick user who owns the integration's API token. This also applies
to completion from native Home Assistant to-do lists. `donetick.complete_assigned_task`
additionally takes an optional `completed_by` to credit the completion to another circle
member. Donetick alone decides whether it accepts that person — its rules depend on the
task's privacy, its assignment and its project — and rejects anyone else. The action then
fails, carrying Donetick's own reason where it gives one, so the integration never
second-guesses the server. **Skip occurrence** (the `donetick.postpone_task` action) uses Donetick's internal skip/rescheduling endpoint to advance
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
