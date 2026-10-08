import assert from 'node:assert/strict';
const {Window} = await import(process.env.DOM_TEST_MODULE || 'happy-dom');
const window = new Window();
Object.assign(globalThis, {window, document: window.document, HTMLElement: window.HTMLElement,
  customElements: window.customElements, CustomEvent: window.CustomEvent});
const {localDateTime, dueText, userTasks} = await import('../www/donetick-user-todo-card.js');
const calls=[]; let fail=false;
const hass={locale:{language:'en'},states:{'todo.all':{state:'2',attributes:{config_entry_id:'entry',circle_members:[{user_id:1,display_name:'Torben'}],tasks:[
  {task_id:1,assigned_to:1,name:'Weekly',can_postpone:true,next_due_date:'2026-10-20T16:00:00Z'},
  {task_id:2,assigned_to:1,name:'One-off',can_postpone:false},
  {task_id:3,assigned_to:2,name:'Other user',can_postpone:true}
]}}},callService:async(...args)=>{calls.push(args);if(fail)throw new Error('Permission denied');}};
const card=document.createElement('donetick-user-todo-card');card.setConfig({entity:'todo.all',user_id:1});card.hass=hass;document.body.append(card);
const root=card.shadowRoot;
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const click=label=>root.querySelector(`[aria-label="${label}"]`).click();
const submit=()=>root.querySelector('form').dispatchEvent(new window.Event('submit',{cancelable:true}));
assert.equal(root.querySelectorAll('.row').length,2);
assert.equal(root.querySelectorAll('input[type=checkbox]').length,2);
assert.equal(root.querySelectorAll('.actions > button').length,3);
assert.equal(root.querySelector('.row').firstElementChild.className,'complete-checkbox');
assert.equal(root.querySelector('.row').lastElementChild.className,'actions');
click('Skip occurrence: Weekly');assert.ok(root.querySelector('form'));assert.equal(calls.length,0);
click('Skip occurrence: Weekly');assert.equal(root.querySelector('form'),null);
click('Skip occurrence: Weekly');submit();await tick();
assert.deepEqual(calls.pop(),['donetick','postpone_task',{task_id:1,config_entry_id:'entry'}]);
click('Change due date: Weekly');
assert.equal(root.querySelectorAll('[role=dialog], [popover]').length,0);
assert.equal(root.querySelectorAll('.action-panel button').length,3);
assert.equal(root.querySelector('.action-panel').previousElementSibling.className,'row');
assert.equal(root.querySelector('input[type=date]').value,'2026-10-20');
assert.equal(root.querySelector('input[type=time]'),null);
click('Change due date: Weekly');assert.equal(root.querySelector('form'),null);
click('Change due date: Weekly');
let input=root.querySelector('input[type=date]');input.value='2026-10-24';input.dispatchEvent(new window.Event('input'));
card.hass=hass;assert.equal(root.querySelector('input[type=date]').value,'2026-10-24');
click('Set time');assert.equal(root.querySelector('input[type=time]').value,'18:00');
click('Hide time');assert.equal(root.querySelector('input[type=time]'),null);
submit();await tick();
assert.deepEqual(calls.pop(),['donetick','update_task',{task_id:1,config_entry_id:'entry',due_date:'2026-10-24T16:00:00.000Z'}]);
assert.equal(root.querySelector('form'),null);
assert.equal(localDateTime('2026-10-24T16:00:00Z'),'2026-10-24T18:00:00');
assert.equal(localDateTime('2026-10-27T16:00:00Z'),'2026-10-27T17:00:00');
assert.equal(dueText('2026-10-24T16:00:00Z','en',new Date('2026-10-26T12:00:00+01:00')),'Overdue · 2 days');
assert.equal(dueText('2026-10-24T16:00:00Z','en',new Date('2026-10-24T12:00:00+02:00')),'Today');
assert.equal(dueText('2026-10-25T16:00:00Z','en',new Date('2026-10-24T12:00:00+02:00')),'Tomorrow');
assert.deepEqual(userTasks({attributes:{tasks:[{task_id:1,assigned_to:1},{task_id:2,assigned_to:1,next_due_date:'2026-10-12T10:00:00Z'},{task_id:3,assigned_to:1,next_due_date:'2026-10-10T10:00:00Z'}]}},1).map(task=>task.task_id),[3,2,1]);
click('Change due date: Weekly');fail=true;submit();await tick();
assert.match(root.querySelector('.action-panel .error').textContent,/Permission denied/);
root.querySelector('form').dispatchEvent(new window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));assert.equal(root.querySelector('form'),null);
fail=false;click('Change due date: One-off');click('Skip occurrence: Weekly');
assert.equal(root.querySelectorAll('form').length,1);assert.equal(root.querySelector('form').getAttribute('aria-label'),'Skip occurrence: Weekly');
document.body.dispatchEvent(new window.PointerEvent('pointerdown',{bubbles:true}));assert.equal(root.querySelector('form'),null);
root.querySelector('[aria-label="Complete: Weekly"]').dispatchEvent(new window.Event('change'));await tick();
assert.deepEqual(calls.pop(),['donetick','complete_assigned_task',{task_id:1,config_entry_id:'entry'}]);assert.ok(root.querySelector('.completed input').checked);
await new Promise(resolve=>setTimeout(resolve,1050));
card.setConfig({entity:'todo.all',user_id:1,complete_control:'button',button_content:'icon_and_label'});
assert.equal(root.querySelectorAll('input[type=checkbox]').length,0);
console.log('Compact inline editing, repeated-tap toggles, preserved time, confirmed actions and feedback passed');