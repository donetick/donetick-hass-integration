import assert from 'node:assert/strict';
const {Window} = await import(process.env.DOM_TEST_MODULE || 'happy-dom');
const window = new Window();
Object.assign(globalThis, {window, document: window.document, HTMLElement: window.HTMLElement,
  customElements: window.customElements, CustomEvent: window.CustomEvent});
customElements.define('ha-form',class extends HTMLElement {});
customElements.define('home-assistant',class extends HTMLElement {});
const {performerChoices} = await import('../custom_components/donetick/frontend/donetick-user-todo-card.js');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const calls=[]; let fail=false;
const members=[{user_id:1,display_name:'Casey'},{user_id:2,display_name:'Ivy'},{user_id:3,display_name:'Jamie'},{user_id:4,display_name:'Priya'}];
const hass={locale:{language:'en'},states:{'todo.all':{state:'3',attributes:{config_entry_id:'entry',circle_members:members,tasks:[
  {task_id:1,assigned_to:null,assignee_ids:[],name:'Shared',can_postpone:false},
  {task_id:2,assigned_to:1,assignee_ids:[1],name:'Mine',can_postpone:false},
  {task_id:3,assigned_to:2,assignee_ids:[1,2,3,4],name:'Rotating',can_postpone:false}
]}}},callService:async(...args)=>{calls.push(args);if(fail)throw new Error('Donetick task action failed: Donetick denied the completion (400): User is not assigned to chore');}};
const card=document.createElement('donetick-user-todo-card');
const base={entity:'todo.all',user_id:'all',complete_control:'button',credit_completion:'choose'};
card.setConfig(base);card.hass=hass;document.body.append(card);
const root=card.shadowRoot;
const controls=()=>[...root.querySelectorAll('.actions [aria-label^="Complete: "]')];
const choices=()=>[...root.querySelectorAll('.panel-members button')];

// Only the task's own people are offered, the assignee first: Donetick refuses anyone
// else. A task with nobody assigned offers the whole circle.
const state=hass.states['todo.all'];
assert.deepEqual(performerChoices(state,state.attributes.tasks[0]).map(m=>m.user_id),[1,2,3,4]);
assert.deepEqual(performerChoices(state,state.attributes.tasks[1]).map(m=>m.user_id),[1]);
assert.deepEqual(performerChoices(state,state.attributes.tasks[2]).map(m=>m.user_id),[2,1,3,4]);
// An assignee who has left the circle cannot be offered, and nobody stands in for them.
assert.deepEqual(performerChoices(state,{task_id:9,assigned_to:7,assignee_ids:[]}).map(m=>m.user_id),[]);
assert.deepEqual(performerChoices({attributes:{circle_members:[]}},{task_id:9}),[]);
assert.deepEqual(performerChoices(undefined,{task_id:9}),[]);
console.log('The task\'s own people are offered, the whole circle only when nobody is assigned');

// Tapping asks instead of completing.
assert.equal(root.querySelector('.action-panel'),null);
controls()[0].click();
assert.equal(calls.length,0);
const form=root.querySelector('.action-panel');
assert.ok(form);
assert.equal(form.getAttribute('aria-label'),'Complete as: Shared');
assert.equal(root.querySelector('.action-panel .skip-prompt').textContent,'Complete as…');
assert.equal(root.querySelector('.action-panel .save-action'),null);
assert.equal(controls()[0].getAttribute('aria-expanded'),'true');
assert.equal(controls()[1].getAttribute('aria-expanded'),'false');
assert.deepEqual(choices().map(button=>button.textContent),['Casey','Ivy','Jamie','Priya']);
assert.deepEqual(choices().map(button=>button.title),['Complete as Casey','Complete as Ivy','Complete as Jamie','Complete as Priya']);
assert.equal(choices()[1].title,'Complete as Ivy');
console.log('The completion control opens a member row instead of booking the assignee');

// Picking a member books the completion for that member.
choices()[1].click();
assert.deepEqual(calls.pop(),['donetick','complete_assigned_task',{task_id:1,config_entry_id:'entry',completed_by:2}]);
await tick();
assert.equal(root.querySelector('.action-panel'),null);
assert.equal(root.querySelectorAll('.completed .actions [aria-label^="Complete: "]').length,1);
await new Promise(resolve=>setTimeout(resolve,1050));
console.log('Picking a member credits the completion to them and closes the panel');

// An assigned task offers only its own people; a refusal still stays visible.
controls()[1].click();
assert.deepEqual(choices().map(button=>button.textContent),['Casey']);
// The ranking reaches the panel: the assignee comes before the circle's order.
controls()[1].click();controls()[2].click();
assert.deepEqual(choices().map(button=>button.textContent),['Ivy','Casey','Jamie','Priya']);
assert.equal(choices()[0].getAttribute('aria-label'),'Complete as Ivy');
controls()[2].click();controls()[1].click();
fail=true;choices()[0].click();await tick();
assert.match(root.querySelector('.error').textContent,/denied the completion \(400\): User is not assigned to chore/);
assert.ok(root.querySelector('.action-panel'));
fail=false;
root.querySelector('.action-panel').dispatchEvent(new window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
assert.equal(root.querySelector('.action-panel'),null);
console.log('A rejected completion keeps the panel open with the server error');

// The option is off by default and works with every completion control.
card.setConfig({entity:'todo.all',user_id:'all',complete_control:'button'});
controls()[0].click();
assert.deepEqual(calls.pop(),['donetick','complete_assigned_task',{task_id:1,config_entry_id:'entry'}]);
assert.equal(root.querySelector('.action-panel'),null);
await new Promise(resolve=>setTimeout(resolve,1050));
assert.throws(()=>card.setConfig({...base,credit_completion:'ask'}),/valid completion credit/);
card.setConfig({...base,complete_control:'checkbox'});
const checkbox=root.querySelector('input[type=checkbox]');
calls.length=0;
checkbox.checked=true;checkbox.dispatchEvent(new window.Event('change'));
assert.equal(calls.length,0);
assert.ok(root.querySelector('.panel-members'));
// Tapping the control again closes the panel, as the other row panels do.
root.querySelector('input[type=checkbox]').dispatchEvent(new window.Event('change'));
assert.equal(root.querySelector('.action-panel'),null);
card.setConfig({...base,complete_control:'button',button_content:'icon_and_label'});
root.querySelector('[aria-label="Complete: Shared"]').click();
assert.ok(root.querySelector('.panel-members'));
assert.equal(root.querySelector('[aria-label="Complete: Shared"]').getAttribute('aria-expanded'),'true');
card.setConfig({...base,credit_completion:'choose',show_complete:false});
assert.equal(root.querySelector('.action-panel'),null);
console.log('Credit selection is opt-in and available for every completion control');

// An empty circle list must not make a task uncompletable.
const bare=document.createElement('donetick-user-todo-card');
const bareHass={...hass,states:{'todo.all':{state:'1',attributes:{config_entry_id:'entry',circle_members:[],
  tasks:[{task_id:9,assigned_to:null,assignee_ids:[],name:'Alone',can_postpone:false}]}}}};
bare.setConfig({entity:'todo.all',user_id:'all',complete_control:'button',credit_completion:'choose'});
bare.hass=bareHass;document.body.append(bare);
calls.length=0;
bare.shadowRoot.querySelector('.actions [aria-label^="Complete: "]').click();
assert.equal(bare.shadowRoot.querySelector('.action-panel'),null);
assert.deepEqual(calls.pop(),['donetick','complete_assigned_task',{task_id:9,config_entry_id:'entry'}]);
console.log('Without a circle list the control completes instead of opening an empty panel');
await new Promise(resolve=>setTimeout(resolve,1050));

// Switching the option off closes an open panel.
card.setConfig({...base});
controls()[0].click();
assert.ok(root.querySelector('.panel-members'));
card.setConfig({...base,credit_completion:'assignee'});
assert.equal(root.querySelector('.action-panel'),null);
console.log('Turning the option off closes a panel that is still open');

// Only switching completion off closes the member row; any other change leaves it open, and it stays closed.
card.setConfig({...base});
controls()[0].click();
assert.ok(root.querySelector('.panel-members'));
card.setConfig({...base,show_points:true});
assert.ok(root.querySelector('.panel-members'));
card.setConfig({...base,show_complete:false});
assert.equal(root.querySelector('.action-panel'),null);
card.setConfig({...base});
assert.equal(root.querySelector('.action-panel'),null);
console.log('Switching completion off closes an open member row, other changes keep it');

// A slow call must leave the rest of the card alone, and its refusal must stay its own.
let accept, refuse;
const slowHass={locale:{language:'en'},states:{'todo.all':{state:'2',attributes:{config_entry_id:'entry',circle_members:members,tasks:[
  {task_id:1,assigned_to:1,assignee_ids:[1],name:'Dishes',can_postpone:false},
  {task_id:2,assigned_to:2,assignee_ids:[2],name:'Laundry',can_postpone:false}
]}}},callService:(...args)=>new Promise((resolve,reject)=>{calls.push(args);accept=resolve;refuse=()=>reject(new Error(
  'Donetick task action failed: Donetick denied the completion (400): User is not assigned to chore'));})};
const slow=document.createElement('donetick-user-todo-card');
slow.setConfig(base);slow.hass=slowHass;document.body.append(slow);
const slowRoot=slow.shadowRoot;
const slowControls=()=>[...slowRoot.querySelectorAll('.actions [aria-label^="Complete: "]')];
const cardError=()=>[...slowRoot.querySelectorAll('ha-card > .error')].map(error=>error.textContent);
slowControls()[0].click();
slowRoot.querySelector('.panel-members button').click();
// Everyone stays put while the booking is in flight, so a mistap cannot double-book.
assert.deepEqual([...slowRoot.querySelectorAll('.panel-members button')].map(button=>button.disabled),[true]);
slowControls()[1].click();
assert.equal(slowRoot.querySelector('.action-panel').getAttribute('aria-label'),'Complete as: Laundry');
refuse();await tick();await tick();
// The second row's panel survives the first row's answer, and wears none of it.
assert.equal(slowRoot.querySelector('.action-panel').getAttribute('aria-label'),'Complete as: Laundry');
assert.equal(slowRoot.querySelector('.action-panel .error'),null);
assert.match(cardError()[0],/^Dishes: .*User is not assigned to chore$/);
assert.equal(slowRoot.querySelectorAll('[role=alert]').length,1);
console.log('A refusal names its own task and never lands on another row\'s panel');

// The same holds when the first row's booking succeeds: it closes its own panel only.
slow.setConfig(base);
calls.length=0;
slowControls()[0].click();
slowRoot.querySelector('.panel-members button').click();
slowControls()[1].click();
assert.equal(slowRoot.querySelector('.action-panel').getAttribute('aria-label'),'Complete as: Laundry');
accept();await tick();await tick();
assert.deepEqual(calls.pop(),['donetick','complete_assigned_task',{task_id:1,config_entry_id:'entry',completed_by:1}]);
assert.equal(slowRoot.querySelector('.action-panel').getAttribute('aria-label'),'Complete as: Laundry');
assert.equal(cardError().length,0);
console.log('A booking that succeeds closes its own panel and leaves another row\'s open');
await new Promise(resolve=>setTimeout(resolve,1050));

// The panel closes rather than standing empty if the circle list empties under it.
slow.setConfig(base);
slowControls()[0].click();
assert.ok(slowRoot.querySelector('.panel-members'));
slowHass.states['todo.all']={...slowHass.states['todo.all'],attributes:{...slowHass.states['todo.all'].attributes,circle_members:[]}};
slow.hass=slowHass;
assert.equal(slowRoot.querySelector('.action-panel'),null);
assert.equal(slowRoot.querySelector('.panel-members'),null);
console.log('A circle list that empties under an open panel closes it instead of showing nothing');
await new Promise(resolve=>setTimeout(resolve,1050));

// Chips book on a tap only: submitting the panel some other way (Enter) books nobody.
{
  const page=document.createElement('donetick-user-todo-card');
  const pageCalls=[];
  page.setConfig(base);page.hass={...hass,callService:async(...args)=>{pageCalls.push(args);}};document.body.append(page);
  const pageRoot=page.shadowRoot;
  pageRoot.querySelector('.actions [aria-label="Complete: Mine"]').click();
  assert.ok(pageRoot.querySelector('.panel-members'));
  assert.equal(pageRoot.querySelector('.action-panel select'),null);
  assert.equal(pageRoot.querySelector('.action-panel .save-action'),null);
  pageRoot.querySelector('.action-panel').dispatchEvent(new window.Event('submit',{cancelable:true}));
  await tick();
  assert.equal(pageCalls.length,0);
  assert.ok(pageRoot.querySelector('.panel-members'));
  console.log('Chips book only on a tap on a person, never on a bare submit');

  // The dropdown picker asks the same question with a choice and a confirmation.
  assert.throws(()=>page.setConfig({...base,complete_as_picker:'list'}),/valid Complete as picker/);
  page.setConfig({...base,complete_as_picker:'dropdown'});
  pageRoot.querySelector('.action-panel').dispatchEvent(new window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  pageRoot.querySelector('.actions [aria-label="Complete: Rotating"]').click();
  assert.equal(pageCalls.length,0);
  assert.equal(pageRoot.querySelector('.panel-members'),null);
  const select=pageRoot.querySelector('.action-panel select[data-field="performer"]');
  assert.deepEqual([...select.options].map(option=>option.textContent),['Ivy','Casey','Jamie','Priya']);
  assert.equal(select.value,'2');
  assert.equal(pageRoot.querySelector('.action-panel .save-action').getAttribute('aria-label'),'Confirm completion');
  select.value='3';select.dispatchEvent(new window.Event('change'));
  assert.equal(pageCalls.length,0);
  pageRoot.querySelector('.action-panel').dispatchEvent(new window.Event('submit',{cancelable:true}));
  assert.deepEqual(pageCalls.pop(),['donetick','complete_assigned_task',{task_id:3,config_entry_id:'entry',completed_by:3}]);
  await tick();
  assert.equal(pageRoot.querySelector('.action-panel'),null);
  console.log('The dropdown picker books the chosen person only after confirming');
  await new Promise(resolve=>setTimeout(resolve,1050));

  // Both ways in open the same panel, and it stays while either of them is still on.
  page.setConfig({...base,show_complete_as:true});
  const rowAction=()=>pageRoot.querySelector('[aria-label="Complete as: Shared"]');
  rowAction().click();
  assert.equal(pageRoot.querySelector('.action-panel').getAttribute('aria-label'),'Complete as: Shared');
  assert.ok(pageRoot.querySelector('.panel-members'));
  assert.equal(pageRoot.querySelector('.actions [aria-label="Complete: Shared"]').getAttribute('aria-expanded'),'true');
  page.setConfig({...base,show_complete_as:true,credit_completion:'assignee'});
  assert.equal(pageRoot.querySelector('.action-panel').getAttribute('aria-label'),'Complete as: Shared');
  page.setConfig({...base,show_complete_as:false,credit_completion:'assignee'});
  assert.equal(pageRoot.querySelector('.action-panel'),null);
  // With asking off, the control books the assignee straight away, even beside the row action.
  page.setConfig({...base,show_complete_as:true,credit_completion:'assignee'});
  pageRoot.querySelector('.actions [aria-label="Complete: Mine"]').click();
  assert.deepEqual(pageCalls.pop(),['donetick','complete_assigned_task',{task_id:2,config_entry_id:'entry'}]);
  assert.equal(pageRoot.querySelector('.action-panel'),null);
  console.log('The row action and the completion control share one panel');
  await new Promise(resolve=>setTimeout(resolve,1050));
  page.remove();
}

// The person this device last credited is offered first, and every completion still asks.
{
  assert.deepEqual(performerChoices(state,state.attributes.tasks[2],1).map(m=>m.user_id),[1,2,3,4]);
  assert.deepEqual(performerChoices(state,state.attributes.tasks[2],4).map(m=>m.user_id),[4,2,1,3]);
  // Somebody no longer offered is simply not there to lead.
  assert.deepEqual(performerChoices(state,state.attributes.tasks[2],99).map(m=>m.user_id),[2,1,3,4]);
  assert.deepEqual(performerChoices({attributes:{circle_members:[...members,{user_id:5,username:'former',is_active:false}]}},
    state.attributes.tasks[2],5).map(m=>m.user_id),[2,1,3,4]);

  globalThis.localStorage=window.localStorage;localStorage.clear();
  const pageCalls=[];let refuse=false;
  const pageHass={...hass,callService:async(...args)=>{pageCalls.push(args);if(refuse)throw new Error('Donetick denied the completion (400)');}};
  const page=document.createElement('donetick-user-todo-card');
  page.setConfig(base);page.hass=pageHass;document.body.append(page);
  const pageRoot=page.shadowRoot;
  const open=name=>pageRoot.querySelector(`.actions [aria-label="Complete: ${name}"]`).click();
  const offered=()=>[...pageRoot.querySelectorAll('.panel-members button')].map(button=>button.textContent);
  open('Rotating');
  assert.deepEqual(offered(),['Ivy','Casey','Jamie','Priya']);
  pageRoot.querySelector('[aria-label="Complete as Casey"]').click();await tick();
  assert.deepEqual(pageCalls.pop(),['donetick','complete_assigned_task',{task_id:3,config_entry_id:'entry',completed_by:1}]);
  await new Promise(resolve=>setTimeout(resolve,1050));
  open('Rotating');
  // Opening books nothing: the remembered person leads, but has to be tapped again.
  assert.equal(pageCalls.length,0);
  assert.deepEqual(offered(),['Casey','Ivy','Jamie','Priya']);
  open('Rotating');open('Shared');
  assert.deepEqual(offered(),['Casey','Ivy','Jamie','Priya']);
  console.log('The person this device last credited is offered first, and still has to be tapped');

  // A refused completion does not move anyone forward.
  refuse=true;
  pageRoot.querySelector('[aria-label="Complete as Priya"]').click();await tick();await tick();
  assert.equal(pageCalls.pop()[2].completed_by,4);
  refuse=false;
  open('Shared');open('Rotating');
  assert.deepEqual(offered(),['Casey','Ivy','Jamie','Priya']);
  console.log('A refused completion leaves the order alone');

  // The dropdown starts on the same person and books only once confirmed.
  page.setConfig({...base,complete_as_picker:'dropdown'});
  open('Rotating');open('Rotating');
  const select=pageRoot.querySelector('.action-panel select[data-field="performer"]');
  assert.deepEqual([...select.options].map(option=>option.textContent),['Casey','Ivy','Jamie','Priya']);
  assert.equal(select.value,'1');
  assert.equal(pageCalls.length,0);
  pageRoot.querySelector('.action-panel').dispatchEvent(new window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  console.log('The dropdown starts on the remembered person and still needs a confirmation');

  // Remembered per Donetick account: user ids of another server mean other people.
  page.setConfig(base);
  page.hass={...pageHass,states:{'todo.all':{...hass.states['todo.all'],attributes:{...hass.states['todo.all'].attributes,config_entry_id:'other'}}}};
  open('Rotating');
  assert.deepEqual(offered(),['Ivy','Casey','Jamie','Priya']);
  open('Rotating');
  page.hass=pageHass;
  // Without an account to file it under, nothing is remembered.
  page.hass={...pageHass,states:{'todo.all':{...hass.states['todo.all'],attributes:{...hass.states['todo.all'].attributes,config_entry_id:undefined}}}};
  open('Rotating');
  assert.deepEqual(offered(),['Ivy','Casey','Jamie','Priya']);
  pageRoot.querySelector('[aria-label="Complete as Jamie"]').click();await tick();
  assert.equal(pageCalls.pop()[2].completed_by,3);
  await new Promise(resolve=>setTimeout(resolve,1050));
  open('Rotating');
  assert.deepEqual(offered(),['Ivy','Casey','Jamie','Priya']);
  open('Rotating');
  page.hass=pageHass;
  console.log('The remembered person belongs to one Donetick account');

  // Blocked storage costs the ordering, never the completion.
  const blocked={getItem(){throw new Error('blocked');},setItem(){throw new Error('blocked');}};
  globalThis.localStorage=blocked;
  page.setConfig(base);
  open('Rotating');
  assert.deepEqual(offered(),['Ivy','Casey','Jamie','Priya']);
  pageRoot.querySelector('[aria-label="Complete as Jamie"]').click();await tick();
  assert.equal(pageCalls.pop()[2].completed_by,3);
  await tick();
  assert.equal(pageRoot.querySelector('.action-panel'),null);
  console.log('Blocked browser storage keeps the default order and still completes');
  await new Promise(resolve=>setTimeout(resolve,1050));
  page.remove();delete globalThis.localStorage;
}
