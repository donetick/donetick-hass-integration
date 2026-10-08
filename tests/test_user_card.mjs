import assert from 'node:assert/strict';
globalThis.HTMLElement = class {};
globalThis.customElements = {define() {}};
globalThis.window = {};
const {userTasks, actionData} = await import('../www/donetick-user-todo-card.js');
const state = {attributes: {config_entry_id: 'entry', tasks: [
  {task_id: 1, assigned_to: 2}, {task_id: 2, assigned_to: 1}, {task_id: 3, assigned_to: null}
]}};
assert.deepEqual(userTasks(state, '2').map(t => t.task_id), [1]);
assert.deepEqual(userTasks(undefined, 2), []);
assert.deepEqual(actionData(state, state.attributes.tasks[0]), {task_id: 1, config_entry_id: 'entry'});
assert.deepEqual(actionData(state, state.attributes.tasks[0], 3), {task_id: 1, config_entry_id: 'entry', days: 3});
console.log('Card user filtering and entry routing passed');
