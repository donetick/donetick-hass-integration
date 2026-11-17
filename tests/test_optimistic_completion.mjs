import assert from 'node:assert/strict';
const {Window} = await import(process.env.DOM_TEST_MODULE || 'happy-dom');
const window = new Window();
Object.assign(globalThis, {window, document:window.document, HTMLElement:window.HTMLElement,
  customElements:window.customElements, CustomEvent:window.CustomEvent});
customElements.define('ha-form',class extends HTMLElement {});
customElements.define('home-assistant',class extends HTMLElement {});
await import('../custom_components/donetick/frontend/donetick-user-todo-card.js');
const tasks = [1,2].map(task_id=>({task_id,assigned_to:1,name:`Task ${task_id}`,can_postpone:true}));
const calls=[];
const hass={states:{'todo.all':{attributes:{config_entry_id:'entry',
  circle_members:[{user_id:1,display_name:'Casey'}],tasks}}},
  callService:(...args)=>new Promise((resolve,reject)=>calls.push({args,resolve,reject}))};
const makeCard=config=>{
  const card=document.createElement('donetick-user-todo-card');
  card.setConfig({entity:'todo.all',task_view:'pending',...config});card.hass=hass;return card;
};
// Control the success timers without sleeping through a slow server request.
const timers=[];
const originalTimeout=globalThis.setTimeout;
globalThis.setTimeout=(callback,delay)=>{timers.push({callback,delay});return timers.length;};
try {
  for (const complete_control of ['checkbox','initials','button']) {
    const card=makeCard({optimistic_completion:true,complete_control});
    const root=card.shadowRoot;
    const action=card.act(tasks[0],true);
    assert.ok(root.querySelector('.row').classList.contains('completed'));
    assert.equal(root.querySelector('[aria-label="Complete: Task 1"]').disabled,true);
    if (complete_control==='checkbox') assert.equal(root.querySelector('input').checked,true);
    assert.equal(root.querySelector('[aria-label="Complete: Task 2"]').disabled,false);
    const count=calls.length;
    await card.act(tasks[0],true);
    assert.equal(calls.length,count,'Repeated activation must not send another request');
    assert.equal(timers.length,0,'No removal timer may run before server acceptance');
    // An unrelated update must preserve immediate completion feedback.
    card.hass={...hass};
    assert.ok(root.querySelector('.row').classList.contains('completed'));
    calls.at(-1).reject(new Error('Permission denied'));
    await action;
    assert.equal(root.querySelector('.completed'),null);
    assert.equal(root.querySelector('[aria-label="Complete: Task 1"]').disabled,false);
    if (complete_control==='checkbox') assert.equal(root.querySelector('input').checked,false);
    assert.match(root.querySelector('[role=alert]').textContent,/Task 1: Permission denied/);
  }
  const card=makeCard({optimistic_completion:true});
  const first=card.act(tasks[0],true,undefined,undefined,1);
  const second=card.act(tasks[1],true);
  assert.equal(card.shadowRoot.querySelectorAll('.completed').length,2);
  assert.equal(calls.at(-2).args[2].completed_by,1);
  // A coordinator update removes the completed one-off; retain its feedback row.
  card.hass={...hass,states:{'todo.all':{attributes:{...hass.states['todo.all'].attributes,tasks:[tasks[1]]}}}};
  assert.equal(card.shadowRoot.querySelectorAll('.completed').length,2);
  calls.at(-2).resolve();await first;
  assert.equal(timers.length,1);
  calls.at(-1).reject(new Error('Offline'));await second;
  assert.match(card.shadowRoot.querySelector('[role=alert]').textContent,/Task 2: Offline/);
  timers.shift().callback();
  assert.equal(card.shadowRoot.querySelector('.completed'),null);
  assert.equal(card.shadowRoot.querySelectorAll('.row').length,1);
  // Service success can arrive before HA publishes the new entity state. Expiring
  // feedback must not resurrect the old occurrence, even across unrelated updates.
  for (const optimistic_completion of [true,false]) {
    const delayed=makeCard({optimistic_completion});
    const completion=delayed.act(tasks[0],true);
    calls.at(-1).resolve();await completion;
    timers.shift().callback();
    assert.equal(delayed.shadowRoot.querySelectorAll('.row').length,1);
    delayed.hass={...hass};
    assert.equal(delayed.shadowRoot.querySelectorAll('.row').length,1);
    const count=calls.length;
    await delayed.act(tasks[0],true);
    assert.equal(calls.length,count,'Accepted stale occurrence cannot be completed twice');
    delayed.hass={...hass,states:{'todo.all':{attributes:{...hass.states['todo.all'].attributes,tasks:[tasks[1]]}}}};
    assert.equal(delayed.shadowRoot.querySelectorAll('.row').length,1);
    assert.equal(delayed._awaitingCompletions.size,0,'Release reconciliation state when HA catches up');
  }
  // A recurring task's refreshed next occurrence becomes usable after feedback ends.
  const recurring=makeCard({optimistic_completion:true});
  const recurrence=recurring.act(tasks[0],true);
  const nextOccurrence={...tasks[0],next_due_date:'2026-11-18T09:00:00Z'};
  recurring.hass={...hass,states:{'todo.all':{attributes:{...hass.states['todo.all'].attributes,tasks:[nextOccurrence]}}}};
  assert.ok(recurring.shadowRoot.querySelector('.row').classList.contains('completed'));
  calls.at(-1).resolve();await recurrence;
  assert.equal(recurring.shadowRoot.querySelector('input').disabled,true);
  timers.shift().callback();
  assert.equal(recurring.shadowRoot.querySelector('.completed'),null);
  assert.equal(recurring.shadowRoot.querySelector('input').checked,false);
  assert.equal(recurring.shadowRoot.querySelector('input').disabled,false);
  assert.deepEqual(recurring.filteredTasks(recurring._hass.states['todo.all']),[nextOccurrence]);
  const nextCompletion=recurring.act(nextOccurrence,true);
  assert.equal(calls.at(-1).args[2].task_id,nextOccurrence.task_id);
  calls.at(-1).reject(new Error('Offline'));await nextCompletion;
  assert.equal(recurring.shadowRoot.querySelector('input').disabled,false);
  // The option is off by default and non-completion actions never get strikethrough.
  for (const config of [{},{optimistic_completion:false},{optimistic_completion:true}]) {
    const card=makeCard(config);
    const complete=config.optimistic_completion!==true;
    const action=card.act(tasks[0],complete);
    assert.equal(card.shadowRoot.querySelector('.completed'),null);
    calls.at(-1).reject(new Error('Offline'));await action;
  }
  assert.throws(()=>makeCard({optimistic_completion:'true'}),/must be true or false/);
  assert.throws(()=>makeCard({completion_strikethrough:'false'}),/must be true or false/);

  for (const complete_control of ['checkbox','initials','button']) {
    const plain=makeCard({optimistic_completion:true,completion_strikethrough:false,complete_control});
    const action=plain.act(tasks[0],true);
    assert.ok(plain.shadowRoot.querySelector('.completed.no-strikethrough'));
    if (complete_control==='checkbox') assert.equal(plain.shadowRoot.querySelector('input').checked,true);
    calls.at(-1).reject(new Error('Denied'));await action;
    assert.equal(plain.shadowRoot.querySelector('.completed'),null);
  }

  // A burst of different tasks can settle in any order, without losing errors or
  // restoring accepted occurrences when another row fails or begins a retry.
  const burstTasks=Array.from({length:8},(_,index)=>({...tasks[0],task_id:index+10,name:`Burst ${index}`}));
  const burst=makeCard({optimistic_completion:true});
  burst.hass={...hass,states:{'todo.all':{attributes:{...hass.states['todo.all'].attributes,tasks:burstTasks}}}};
  const actions=burstTasks.map(task=>burst.act(task,true));
  const requests=calls.slice(-8);
  assert.equal(burst.shadowRoot.querySelectorAll('.completed').length,8);
  for (const index of [5,0,7,1]) { requests[index].resolve();await actions[index]; }
  for (const index of [3,6,2,4]) { requests[index].reject(new Error(`Refused ${index}`));await actions[index]; }
  assert.equal(burst.shadowRoot.querySelectorAll('[role=alert]').length,4);
  while(timers.length) timers.shift().callback();
  assert.equal(burst.shadowRoot.querySelectorAll('.row').length,4);
  const retry=burst.act(burstTasks[2],true);
  assert.equal(burst.shadowRoot.querySelectorAll('[role=alert]').length,3);
  calls.at(-1).reject(new Error('Retry refused'));await retry;
  assert.equal(burst.shadowRoot.querySelectorAll('[role=alert]').length,4);

  // A response from an old list must not touch a new list with the same task ID.
  for (const rejectOld of [false,true]) {
    const switched=makeCard({optimistic_completion:true});
    const old=switched.act(tasks[0],true);
    const oldRequest=calls.at(-1);
    switched.setConfig({entity:'todo.other',optimistic_completion:true,task_view:'pending'});
    switched.hass={...hass,states:{'todo.other':{attributes:{...hass.states['todo.all'].attributes,config_entry_id:'other'}}}};
    const current=switched.act(tasks[0],true);
    if (rejectOld) oldRequest.reject(new Error('Old account error'));else oldRequest.resolve();
    await old;
    assert.equal(switched._pending.get(tasks[0].task_id),true);
    assert.equal(switched.shadowRoot.querySelector('[role=alert]'),null);
    calls.at(-1).reject(new Error('Current error'));await current;
    assert.match(switched.shadowRoot.querySelector('[role=alert]').textContent,/Current error/);
  }

  // A timer from a previous account cannot remove a new account's feedback.
  const switched=makeCard({optimistic_completion:true});
  let action=switched.act(tasks[0],true);calls.at(-1).resolve();await action;
  const oldTimer=timers.shift();
  switched.hass={...hass,states:{'todo.all':{attributes:{...hass.states['todo.all'].attributes,config_entry_id:'other'}}}};
  action=switched.act(tasks[0],true);calls.at(-1).resolve();await action;
  oldTimer.callback();
  assert.ok(switched.shadowRoot.querySelector('.completed'));
  timers.shift().callback();
  assert.equal(switched.shadowRoot.querySelector('.completed'),null);

  // A newly reopened panel for the same row belongs to the new interaction.
  const reopened=makeCard({optimistic_completion:true});
  reopened.togglePanel(tasks[0],'skip');
  action=reopened.act(tasks[0],true);
  reopened.closePanel();reopened.togglePanel(tasks[0],'date');
  const newPanel=reopened._panel;
  calls.at(-1).resolve();await action;
  assert.equal(reopened._panel,newPanel);
  timers.shift().callback();

  // Snapshot the occurrence at click time, even if a mock/state object is mutated.
  const mutable={...tasks[0],next_due_date:'2026-11-17T09:00:00Z'};
  const snapshot=makeCard({optimistic_completion:true});
  snapshot.hass={...hass,states:{'todo.all':{attributes:{...hass.states['todo.all'].attributes,tasks:[mutable]}}}};
  action=snapshot.act(mutable,true);
  assert.equal(calls.at(-1).args[2].expected_due_date,'2026-11-17T09:00:00Z');
  mutable.next_due_date='2026-11-18T09:00:00Z';
  snapshot.hass={...snapshot._hass};
  assert.equal(snapshot._completed.get(mutable.task_id).next_due_date,'2026-11-17T09:00:00Z');
  calls.at(-1).resolve();await action;
  timers.shift().callback();
  assert.equal(snapshot.shadowRoot.querySelector('input').disabled,false);

  // Always-available tasks may retain their due date. New history acknowledges
  // completion so these tasks do not remain hidden indefinitely.
  const always=makeCard({optimistic_completion:true});
  const initial={...hass.states['todo.all'].attributes,completed_tasks:[{task_id:1,uid:'old'}]};
  always.hass={...hass,states:{'todo.all':{attributes:initial}}};
  action=always.act(tasks[0],true);calls.at(-1).resolve();await action;
  always.hass={...hass,states:{'todo.all':{attributes:{...initial,completed_tasks:[...initial.completed_tasks,{task_id:1,uid:'new'}]}}}};
  timers.shift().callback();
  assert.equal(always.shadowRoot.querySelector('input').disabled,false);
  assert.equal(always._awaitingCompletions.size,0);

  // A refresh may remove the refused row while its old panel is still selected.
  // Its error must then move above the list rather than disappear with the row.
  const removed=makeCard({optimistic_completion:true});
  removed.togglePanel(tasks[0],'performer');
  action=removed.act(tasks[0],true);
  removed.hass={...hass,states:{'todo.all':{attributes:{...hass.states['todo.all'].attributes,tasks:[tasks[1]]}}}};
  calls.at(-1).reject(new Error('Task is no longer active'));await action;
  assert.match(removed.shadowRoot.querySelector('ha-card > [role=alert]').textContent,/Task 1: Task is no longer active/);

  // Known one-time tasks disappear at click time, without a feedback timer. A
  // refusal restores only its own row; an accepted sibling stays hidden.
  for (const metadata of [{is_recurring:false},{frequency_type:'once'},{frequency_type:'no_repeat'}]) {
    const oneTimeTasks=tasks.map(task=>({...task,...metadata}));
    const immediate=makeCard({optimistic_completion:true});
    const list={attributes:{...hass.states['todo.all'].attributes,tasks:oneTimeTasks}};
    immediate.hass={...hass,states:{'todo.all':list}};
    const first=immediate.act(oneTimeTasks[0],true);
    const request=calls.at(-1);
    assert.equal(immediate.shadowRoot.querySelectorAll('.row').length,1);
    const second=immediate.act(oneTimeTasks[1],true);
    assert.equal(immediate.shadowRoot.querySelectorAll('.row').length,0);
    calls.at(-1).resolve();await second;
    assert.equal(timers.length,0);
    // History can be newer than the pending-task snapshot during a refresh.
    immediate.hass={...hass,states:{'todo.all':{attributes:{...list.attributes,completed_tasks:[{task_id:2,uid:'just-completed'}]}}}};
    assert.equal(immediate.shadowRoot.querySelectorAll('.row').length,0);
    immediate.hass={...immediate._hass};
    assert.equal(immediate.shadowRoot.querySelectorAll('.row').length,0);
    request.reject(new Error('Denied'));await first;
    assert.equal(immediate.shadowRoot.querySelectorAll('.row').length,1);
    assert.equal(immediate.shadowRoot.querySelector('input').checked,false);
    assert.equal(immediate.shadowRoot.querySelector('input').disabled,false);
    assert.match(immediate.shadowRoot.querySelector('[role=alert]').textContent,/Task 1: Denied/);
    assert.equal(immediate.shadowRoot.querySelector('.completed'),null);
  }
  // With optimism disabled, a one-time row disappears only after acceptance.
  const confirmed=makeCard({optimistic_completion:false});
  const oneTime={...tasks[0],is_recurring:false};
  confirmed.hass={...hass,states:{'todo.all':{attributes:{...hass.states['todo.all'].attributes,tasks:[oneTime]}}}};
  action=confirmed.act(oneTime,true);
  assert.equal(confirmed.shadowRoot.querySelectorAll('.row').length,1);
  calls.at(-1).resolve();await action;
  assert.equal(confirmed.shadowRoot.querySelectorAll('.row').length,0);
  assert.equal(timers.length,0);
} finally {globalThis.setTimeout=originalTimeout;}
console.log('Completion races: out-of-order bursts, failures, retries, account switches, timers, panels, snapshots and recurrence passed');
