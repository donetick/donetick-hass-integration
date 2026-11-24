# Donetick User Tasks card

The **Donetick User Tasks** card is bundled with the integration. It appears in the dashboard card picker after Donetick is set up. No separate download or resource registration is needed. After an integration update, reload the browser; remove any old manually added `/local/donetick/donetick-user-todo-card.js` resource.

[Back to the integration README](../README.md)

## Find a topic

- [Create tasks from a dashboard](#create-tasks-from-a-dashboard)
- [Choose whose tasks to show](#choose-whose-tasks-to-show)
- [Filter and sort tasks](#filter-and-sort-tasks)
- [Show completed tasks](#show-completed-tasks)
- [Customize task details and rows](#customize-task-details-and-rows)
- [Complete, skip, change dates, and reassign](#complete-skip-change-dates-and-reassign)
- [Credit completion to someone else](#credit-completion-to-someone-else)
- [Map Home Assistant users](#map-home-assistant-users)
- [Use performer and task pickers in automations](#use-performer-and-task-pickers-in-automations)
- [Edit a repeat schedule](#edit-a-repeat-schedule)

## Create tasks from a dashboard

After setting up the Donetick integration, edit your dashboard and choose **Add card > By card > Donetick Create Task**. Home Assistant loads the card and its visual editor automatically. The form runs the [Create Task action](actions.md), with native date and time pickers and the fields supported by the installed integration.

On a dashboard you can edit in Home Assistant, open the card's visual editor to change its title, reorder or hide fields, and set defaults. A hidden field keeps its position so it returns to the same place when shown again. A default can also supply a value for a hidden field.

For a YAML dashboard, start with the card type and add any overrides you need. For example, this shows three fields and assigns five points to each new task.

```yaml
type: custom:donetick-create-task-card
fields:
  - name
  - due_date
  - assignee
sections: {}
defaults:
  points: 5
```

Use `sections` to define named groups of fields and `hidden_fields` to keep fields in those groups while hiding them from the task form.

## Quick start

1. Add **Donetick User Tasks** to a dashboard.
2. Choose a Donetick todo entity and a user.
3. Pick which tasks to show under **Pending task dates**. Leave it empty to show all available tasks.
4. Adjust **Task details**, **Available actions**, or **Appearance** as needed.

The editor groups options into **Basics**, **Task filters**, **Completed tasks**, **Task details**, **Available actions**, and **Appearance**. Basics and filters start open; other groups expand when needed. The live preview updates as you edit. Appearance presets preserve your list, user, filters, title, task visibility, and row spacing.

## Choose whose tasks to show

| Setting | What it shows | YAML |
| --- | --- | --- |
| All Tasks entity | Tasks across assignees; individual assignee entities also work | Set `entity` to the todo list |
| Assigned user | One person's tasks; per-user entities use their owner automatically | `user_id: 1`; omit `user_id` for an individual assignee entity |
| All users | Tasks for everyone | `user_id: all` |
| Anyone tasks only | Only unassigned tasks, independent of the selected user | `user_id: anyone` |
| Include tasks assigned to Anyone | Adds Anyone tasks to the selected user's tasks; they credit the API token owner by default | `include_anyone: true` |
| Show assigned user | Shows the assignee beside the due date in multi-user or Anyone views | `show_assignee: true` |

For compatibility with older YAML, `anyone_only: true` is also accepted and is equivalent to `user_id: anyone`.

Each card stores its own filters. A card cannot show tasks excluded by the integration's upcoming-task window. Set that integration setting to `0` (unlimited) to make all future tasks available.

## Filter and sort tasks

### Pending task dates

Select any combination of these groups. A task appears once if it matches any selected group; leave the selection empty to show all tasks.

| Group | Includes |
| --- | --- |
| Overdue | Tasks whose due date or time has passed |
| Today | Tasks due today, including those that became overdue earlier today |
| Future | Tasks due tomorrow or later |
| Without a due date | Tasks with no due date |

YAML: `display_filters: [overdue, today, future, undated]`. Use `display_filters: []` to show all tasks.

When **Future** is selected, **Days ahead** limits future tasks (default 7). Empty or `0` means no limit; `3` includes tomorrow through the third day. The other selected groups are not affected. YAML: `upcoming_days: 3` or `upcoming_days: 0`.

The editor replaces the older **Include overdue tasks** setting. Existing `display_filter` and `include_overdue` YAML options retain their behavior until you change **Pending task dates**; then `display_filters` takes precedence. Empty cards show the current user, filter, and future limit.

### Labels and priority

Choose labels to include only matching tasks. Names match exactly and combine with user and date filters. No selection shows every task, including unlabelled ones. With multiple labels, **Match labels** chooses **Any (OR)** or **All (AND)**; default is Any. Choices come from tasks in the selected list, and saved choices remain available if those labels temporarily disappear. YAML: `labels: [maintenance, technical]` and `label_match: any` or `all`.

**Sort tasks by** supports earliest due date (default; undated last), priority (Urgent to Low, then unspecified), or name (in your HA language). Priority ties use due date. YAML: `sort_by: due_date`, `priority`, or `name`.

## Show completed tasks

The card shows **Completed today** by default. **Task view** can show pending tasks, completed tasks, or both: `task_view: pending`, `completed`, or `both`. History includes completions made outside Home Assistant and survives browser refreshes.

Under **Completed tasks**, configure:

| Setting | Default | YAML | Notes |
| --- | --- | --- | --- |
| History period | Today | `completed_days` | 1–7 calendar days, including today |
| Which completions | All in period | `completed_filter` | `matching` applies pending date filters to the occurrence's original due date; `all` ignores them |
| Maximum entries | All | `completed_limit` | 0 means all; 1–500 shows newest first |

Completed items also follow the selected user and list/project. These controls are hidden in pending-only mode and retained when changing views or presets.

```yaml
type: custom:donetick-user-todo-card
entity: todo.all_tasks
user_id: all
display_filters: [today]
task_view: both
completed_filter: matching
completed_days: 1
```

Use `completed_filter: all` to include tasks completed today that were due earlier or had no due date. Set `task_view: completed` for a history-only card.

Native Home Assistant to-do lists also show today's completed occurrences. Recurring tasks keep their next pending occurrence separately; completed records have distinct history IDs and are read-only. Manage history in Donetick. The integration fetches seven days of history; the native list uses the HA timezone, while the card's period follows the browser's local calendar. History requires `/api/v1/chores/history`; if unavailable, pending tasks still work.

## Customize task details and rows

| Setting | Default | YAML | Effect |
| --- | --- | --- | --- |
| Show task points | Off | `show_points: true` | Shows points by the task name. Explicit zero appears; unset values are omitted. |
| Show recurrence | Off | `show_recurrence: true` | Shows recurrence on a separate line; incomplete interval metadata is omitted. |
| Show labels | Off | `show_labels: true` | Shows wrapping label chips under the due date. |
| Use Donetick label colors | Off | `use_label_colors: true` | Applies valid label colors; missing or invalid colors use the neutral style. Requires labels to be shown. |
| Task spacing | Auto | `row_spacing: auto`, `compact`, or `comfortable` | Auto adds room for visible labels; presets preserve this choice. |
| Due date display | Date and time | `due_display: date`, `relative`, or `both` | Relative dates follow HA language and local calendar days. Date-only deadlines remain due all day; the full date is always in a tooltip. |

Task sensors expose points and recurrence independently of the card options.
- Tap a task name or due date to expand its description. Text keeps line breaks, lists, and paragraphs; HTML tags and scripts are removed.

Rows have a completion control on the left, task and due date in the middle, and action icons on the right. Due text uses Today, Tomorrow, or Overdue and follows HA's 12/24-hour preference. Overdue uses the theme warning color; local 23:59 end-of-day placeholders are hidden. Controls have 44 × 44 pixel tap targets and accessible names. Successful actions refresh the list; errors remain visible on the affected row or above the list.

## Complete, skip, change dates, and reassign

### Completion and skipping

Completion fetches the current task from Donetick and credits its assignee, even if another person clicks. Anyone tasks credit the API token owner. `donetick.complete_assigned_task` can accept `completed_by` to credit another circle member; Donetick decides whether that person is allowed based on assignment, privacy, and project access.

Under **Available actions → Credit completion to**, choose a specific Donetick member or a mapped Home Assistant user to always credit them for completions from that card, without asking at completion time. The YAML value is `donetick:<user_id>` for a Donetick member or `ha:<home_assistant_user_id>` for a mapped HA user. For example, `credit_completion: 'donetick:2'`. HA user choices appear only when mapped to an active Donetick member. Donetick still validates whether the selected person may complete each task; a fixed user who is not eligible for a task will receive the server's error.

Enable **Mark completed immediately** under **Available actions** (YAML:
`optimistic_completion: true`) to check and strike through the row immediately
while Donetick completes it in the background. This is off by default. Other tasks
remain usable, and duplicate completion clicks are blocked while waiting. On failure,
the row returns to pending and the card shows the error. This also applies to
**Complete as**, after choosing the performer.
**Strike through tasks when completing** is a separate toggle, on by default.
Set `completion_strikethrough: false` to keep task names unchanged while still
checking the checkbox immediately with `optimistic_completion: true`.
With optimistic completion enabled, known one-time tasks disappear immediately
instead of keeping a feedback row. A rejected completion restores the row and
shows the error. Recurring tasks retain the brief completion feedback.
Accepted completions stay hidden while Home Assistant refreshes its task list.
Recurring tasks return as a new occurrence with their next due date, if it matches
the card's date filters.
Rejected completions restore the task and refresh its data without reloading the
dashboard or interrupting other completions. Errors for different tasks remain
visible independently. Duplicate in-flight actions on the same task are rejected;
scheduled completions also check that the occurrence's due date has not changed.

**Complete tasks with** offers a checkbox (default), an initials circle, or a button: `complete_control: checkbox`, `initials`, or `button`. The initials circle completes for the assignee; Anyone shows an empty circle. Initials use one letter, or two when needed to distinguish circle members.

**Skip occurrence** advances a recurring task using Donetick's schedule, keeps its assignee, and records the skip. It is hidden for tasks without a recurring schedule and asks for confirmation before advancing. YAML actions: `donetick.postpone_task` to skip and `donetick.complete_assigned_task` to complete.

### Change a due date

The calendar-edit action opens an inline date editor, including for one-off tasks. Choose a date and optionally a time, then save. The current time is kept unless changed; undated tasks default to 09:00. Escape, tapping outside, or tapping the action again closes without saving. The editor uses HA date/time controls with browser inputs as a fallback. Dates use the browser's timezone and requests send UTC timestamps. This calls `donetick.update_task` without changing recurrence or skipping an occurrence; the editor stays open if the action fails.

### Reassign a task

**Allow reassignment** adds a user-switch action. Choose Anyone or a user, then save. By default, choices are active members already eligible for the task; tasks without an eligible list offer all active members. The current assignee remains available if deactivated. **Allow assigning any circle member** (`allow_any_assignee: true`) adds other members to the eligible list. Existing eligible members and assignment strategy are preserved, except a single-person list is replaced by the new member.

Assigning Anyone disables automatic user assignment; assigning a user to an Anyone task keeps that user on future occurrences. Switching to or from Anyone requires permission to edit the task. Reassignment uses `donetick.update_task`, preserves recurrence, refreshes lists, and changes which user's card contains the task. YAML: `show_reassign: false` hides the control. Per-user list cards use the list owner rather than `user_id`.

Use **Available actions** to hide controls. All are enabled by default.

| Control | YAML to hide it |
| --- | --- |
| Completion | `show_complete: false` |
| Skip occurrence | `show_postpone: false` |
| Due-date editing | `show_due_date: false` |
| Reassignment | `show_reassign: false` |

Turn them all off for a display-only card.

## Credit completion to someone else

**Complete as** is off by default. Enable **Credit completion to > Ask who completed it** (`credit_completion: choose`) to ask from the checkbox or button, or enable **Show complete as** (`show_complete_as: true`) to add a separate row action. The default `credit_completion: assignee` keeps one-tap completion.

The inline picker offers eligible people, not Anyone. The current assignee appears first, followed by other assignees. If nobody is assigned, it offers active circle members. A browser remembers the last selected performer per Donetick account and puts them first; every completion still requires selection. Donetick may reject a person based on task privacy or project rules. If no performer is available, the separate row action is hidden and the normal completion control remains available.

The picker uses chips by default (`complete_as_picker: chips`); each chip completes immediately. Choose `dropdown` for a long list; select a person and confirm. Escape, tapping outside, or tapping the control again closes without changes. Choosing a performer does not reassign the task. The row action supports `complete_as_icon`, `complete_as_label`, and `complete_as_color`.

## Map Home Assistant users

Open **Settings > Devices & services > Donetick > Configure > User mapping and completion credit**. Mapping is per Donetick integration and disabled by default. Each HA user can map to a Donetick user; choose **Not mapped** to remove a link. Save changes together.

On first setup, unique matches between local HA login usernames and Donetick usernames are suggested (case and surrounding spaces ignored). Review them and check **Apply suggested username matches shown above** to accept. Display names and external authentication identities are not matched. Existing links are preserved; initialization happens once, so removed links stay removed.

When enabled, completions from the card, native to-do lists, and `donetick.complete_task` use the authenticated HA caller's mapping. An explicit `completed_by` overrides it, including for `complete_assigned_task`. Donetick still enforces permissions. For unmapped users or actions without a logged-in caller, choose the assignee/API-token-owner fallback (default) or require a mapping or explicit performer. Automations without caller context can provide `completed_by`.

A shared tablet with one HA login cannot tell who tapped the screen. Use explicit performer selection for that case. Mapping does not provide SSO or change completion in Donetick's web interface.

## Use performer and task pickers in automations

In **Developer tools > Actions**, scripts, or automations, **Donetick: Complete Task** and **Complete as assigned user** can show a **Completed by HA user** dropdown. It resolves through the selected integration's mapping even if automatic caller mapping is disabled. Configure the mapping first; unmapped selections fail without completing the task.

Set one performer field: `completed_by_ha_user`, `completed_by_username`, or numeric `completed_by`. Combining them is an error. Omitting them retains caller mapping and fallback behavior. Existing numeric IDs and templates work. With multiple integrations, use `config_entry_id`.

```yaml
action: donetick.complete_assigned_task
data:
  task_id: 42
  completed_by_ha_user: "HA_USER_ID"
  config_entry_id: "DONETICK_CONFIG_ENTRY_ID"
```

The **Task** dropdown searches active tasks by name, ID, assignee, or project ID. Labels identify the integration when names repeat. Choose either **Task** or **Task ID**; direct IDs still work for archived tasks and history. Completion actions also offer **Completed by Donetick username**; **Update Task** offers **Assignee username**. Usernames resolve active circle members; missing, inactive, or ambiguous names fail without changing the task. Use either `assigned_to_username` or numeric `assigned_to` (`null` means Anyone).

Picker values include the integration. If you set `config_entry_id`, every picker selection must belong to it. For YAML, use plain values with `config_entry_id`, or integration-qualified values:

```yaml
action: donetick.update_task
data:
  task: "DONETICK_CONFIG_ENTRY_ID/42"
  assigned_to_username: "DONETICK_CONFIG_ENTRY_ID/alice"
```

Task choices refresh when integration data updates; usernames refresh with circle membership. Username-based actions follow the login, so update them if it is renamed. Numeric IDs remain stable.

## Edit a repeat schedule

In **Update Task**, open **Repeat schedule**. Patterns include one-time, daily, weekly, monthly, yearly, adaptive, custom interval, selected weekdays, and a day of selected months. **Reschedule from** chooses the previous due date or completion date as the basis for the next occurrence.

The editor shows fields for the selected pattern. Custom intervals use **Repeat every** and **Interval unit**; weekday and month patterns show their own controls. For selected weekdays, choose **Every week** or **Nth weekday of the month**, then choose occurrences. For selected months, choose the month and day. Templated patterns show all controls because HA cannot know the value before execution. Switching patterns clears incompatible fields; YAML values remain visible for review.

Repeating tasks need a first **Due Date**; adding recurrence does not move it. New intervals default to every day. **Custom repeat time** applies to custom patterns and uses Donetick's default timezone (currently UTC). HA does not set a schedule timezone. Partial edits preserve stored timezone metadata; changing repeat time resets it to the server default. Date-only recurrence edits mean local end of day. Use **Due Date** to move the current occurrence or change the time of a standard daily/weekly/monthly/yearly schedule.

```yaml
action: donetick.update_task
data:
  task_id: 42
  frequency_type: days_of_the_week
  weekdays: [monday, friday]
  week_pattern: week_of_month
  occurrences: ["1", "-1"]
  schedule_time: "09:00:00"
  schedule_from: due_date
  due_date: "2026-11-02T09:00:00+01:00"
```

Repeat edits use Donetick's task editor permissions and preserve assignment, labels, subtasks, reminders, projects, points, approval rules, and completion actions. Donetick controls scheduling and plan restrictions. Configure new Thing triggers in Donetick. Always-available and existing Thing-trigger schedules are supported; switching to either disables reminders, and switching away from a Thing trigger removes its association.
