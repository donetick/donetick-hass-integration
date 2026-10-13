"""Build completed occurrences independently of the next scheduled task."""

async def async_completed_occurrences(client, tasks):
    """Read a week of history, resolving archived tasks when necessary."""
    history = await client.async_get_task_history(days=7)
    by_id = {task.id: task for task in tasks}
    completed = []
    seen = set()
    for occurrence in history:
        if occurrence.status != 1 or occurrence.performed_at is None or occurrence.id in seen:
            continue
        seen.add(occurrence.id)
        if occurrence.chore_id not in by_id:
            by_id[occurrence.chore_id] = await client.async_get_task_detail(occurrence.chore_id)
        task = by_id[occurrence.chore_id]
        # Do not invent names or expose tasks no longer accessible to this token.
        if task is None:
            continue
        completed.append({
            "uid": f"history--{occurrence.id}",
            "task_id": task.id,
            "name": task.name,
            "description": task.description,
            "project_id": task.project_id,
            "assigned_to": occurrence.assigned_to,
            "completed_by": occurrence.completed_by,
            "completed_at": occurrence.performed_at.isoformat(),
            "next_due_date": occurrence.due_date.isoformat() if occurrence.due_date else None,
        })
    return sorted(completed, key=lambda item: item["completed_at"], reverse=True)
