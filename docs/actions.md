# Services and automations

## On this page

- [Completion, undo, and task creation](#completion-undo-and-task-creation)
- [Assignment, points, priority, and repeats in automations](#assignment-points-priority-and-repeats-in-automations)

[Back to the integration README](../README.md)

## Completion, undo, and task creation

The bundled card uses `donetick.complete_assigned_task` for completion and
`donetick.postpone_task` to skip an occurrence. Both resolve the task on the server
before acting.

To undo a completion, call `donetick.complete_task` with `response_variable`. The response holds `history_id` (the history entry the completion created), `due_date` (the due date before the completion) and `next_due_date`. Pass `task_id` and `history_id` to `donetick.delete_history`, then restore `due_date` with `donetick.update_task` (with `force_unarchive: true` for a one-off task). A failed completion now raises an error instead of only logging it.

To reactivate an archived task with `donetick.update_task`, set `force_unarchive: true`. This requires a Donetick server that supports `forceUnarchive`.

When calling `donetick.create_task`, set `created_by` to a Donetick circle member's user ID to create and assign the task to that member. Omitting it uses the API token owner. Tasks created from a member's todo list also belong to that member. The optional `due_date` is sent in RFC3339 format.

## Assignment, points, priority, and repeats in automations

`create_task` also accepts `assigned_to` (a Donetick user ID, or `null` for Anyone)
or `assigned_to_username`, independently of `created_by`. Omit both assignee fields
to keep the existing creator-as-assignee behavior. Username choices are scoped to
their integration, as in Update Task. Do not supply both assignee fields.

Both `create_task` and `update_task` accept `points`: a non-negative whole number.
Set `0` for no reward; omit to retain the current value when updating. They also accept
`priority`, Donetick's levels from `1` (urgent) to `4` (low); `0` means none. The repeatable
Reminders selector supports up to five offsets. Add each with **When** (Before, On due
date, or After), **Amount**, and **Unit** (Minutes, Hours, or Days). Reminder choices
are summarized on one line. On update, leave Reminders unset to
keep existing reminders, or remove all entries to disable them.

`create_task` takes the same repeat-schedule fields as `update_task`
(`frequency_type`, `interval_unit`, `weekdays`, `schedule_from`, ...), so a repeating
task can be created in one action. A repeating task needs a first `due_date`.

For example, an automation triggered when the dishwasher finishes can create:

```yaml
action: donetick.create_task
data:
  name: Empty the dishwasher
  assigned_to_username: son
  due_date: "{{ (now() + timedelta(minutes=30)).isoformat() }}"
  points: 3
  reminders:
    - when: "Before due date"
      amount: 30
      unit: minutes
```

A weekly task that is due again one week after it was completed:

```yaml
action: donetick.create_task
data:
  name: Water the plants
  due_date: "2026-11-15"
  frequency_type: weekly
  schedule_from: completion
  priority: 3
```

Extra creation settings are saved through Donetick's task editor after the task is
created, retaining the existing `created_by` behavior. The token needs permission
to edit that task (for another creator, use an authorized circle admin/manager).
If this second step fails, the action reports the created task ID and refreshes
the list. Recover with `update_task` on that ID rather than repeating creation.
Updates preserve unrelated task settings and use the current concurrency timestamp;
points and reminders can be combined with the existing repeat-schedule fields.
Thing trigger configuration remains managed in Donetick.

To assign a task, call `donetick.update_task` with `task_id` and `assigned_to` set to a Donetick circle member's user ID, or `null` for Anyone. Selecting a member outside the task's assignee list adds them to that list while preserving the existing members and assignment strategy; a list with a single person is replaced by the new member instead, keeping its strategy. This and switching to or from Anyone use Donetick's task editor and require permission to edit the task. Donetick remains authoritative on membership and private-project restrictions.
