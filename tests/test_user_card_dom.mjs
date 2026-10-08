import assert from 'node:assert/strict';
const {Window} = await import(process.env.DOM_TEST_MODULE || 'happy-dom');
const window = new Window();
Object.assign(globalThis, {window, document: window.document, HTMLElement: window.HTMLElement,
  customElements: window.customElements, CustomEvent: window.CustomEvent});
const {localDateTime} = await import('../www/donetick-user-todo-card.js');
const calls = [];
let fail = false;
const hass = {locale: {language: 'en'}, states: {'todo.all': {state: '2', attributes: {
  config_entry_id: 'entry', circle_members: [{user_id: 1, display_name: 'Torben'}], tasks: [
    {task_id: 1, assigned_to: 1, name: 'Weekly', can_postpone: true, next_due_date: '2026-10-20T16:00:00Z'},
    {task_id: 2, assigned_to: 1, name: 'One-off', can_postpone: false},
    {task_id: 3, assigned_to: 2, name: 'Other user', can_postpone: true}
  ]}}}, callService: async (...args) => {calls.push(args); if (fail) throw new Error('Permission denied');}};
const card = document.createElement('donetick-user-todo-card');
card.setConfig({entity: 'todo.all', user_id: 1}); card.hass = hass;
const root = card.shadowRoot;
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
assert.equal(root.querySelectorAll('.row').length, 2);
assert.equal(root.querySelectorAll('input[type=checkbox]').length, 2);
assert.equal(root.querySelectorAll('[aria-label^="Postpone:"]').length, 1);
assert.equal(root.querySelectorAll('details').length, 2);
root.querySelector('[aria-label="Postpone: Weekly"]').click(); await tick();
assert.deepEqual(calls.pop(), ['donetick', 'postpone_task', {task_id: 1, config_entry_id: 'entry'}]);
root.querySelector('[aria-label="Complete: Weekly"]').dispatchEvent(new window.Event('change')); await tick();
assert.deepEqual(calls.pop(), ['donetick', 'complete_assigned_task', {task_id: 1, config_entry_id: 'entry'}]);
root.querySelector('[aria-label="Change due date: One-off"]').click();
let input = root.querySelector('input[type=datetime-local]');
input.value = '2026-10-24T18:00:00'; input.dispatchEvent(new window.Event('input'));
card.hass = hass; // A coordinator refresh must preserve the unfinished edit.
assert.equal(root.querySelector('input[type=datetime-local]').value, '2026-10-24T18:00');
root.querySelector('form').dispatchEvent(new window.Event('submit', {cancelable: true})); await tick();
assert.deepEqual(calls.pop(), ['donetick', 'update_task', {task_id: 2, config_entry_id: 'entry', due_date: '2026-10-24T16:00:00.000Z'}]);
assert.equal(root.querySelector('form'), null);
assert.equal(localDateTime('2026-10-24T16:00:00Z'), '2026-10-24T18:00:00');
assert.equal(localDateTime('2026-10-27T16:00:00Z'), '2026-10-27T17:00:00');
root.querySelector('[aria-label="Change due date: Weekly"]').click();
fail = true;
root.querySelector('form').dispatchEvent(new window.Event('submit', {cancelable: true})); await tick();
assert.match(root.querySelector('.error').textContent, /Permission denied/);
assert.ok(root.querySelector('form')); // Keep the selected date available for retry.
root.querySelector('form').dispatchEvent(new window.KeyboardEvent('keydown', {key: 'Escape'}));
assert.equal(root.querySelector('form'), null);
card.setConfig({entity: 'todo.all', user_id: 1, due_date_control: 'button'});
assert.equal(root.querySelectorAll('details').length, 0);
assert.equal(root.querySelectorAll('[aria-label^="Change due date:"]').length, 2);
console.log('Dynamic rows, next-occurrence action, manual date edits, timezone conversion and failure handling passed');
