// Complete as: a row action that books a completion for someone other than the
// assignee. The plain completion controls keep crediting the assignee.
import assert from 'node:assert/strict';
const {Window} = await import(process.env.DOM_TEST_MODULE || 'happy-dom');
const window = new Window();
Object.assign(globalThis, {window, document: window.document, HTMLElement: window.HTMLElement,
  customElements: window.customElements, CustomEvent: window.CustomEvent});
customElements.define('ha-form',class extends HTMLElement {});
customElements.define('home-assistant',class extends HTMLElement {});
const {performerChoices} = await import('../custom_components/donetick/frontend/donetick-user-todo-card.js');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
// A failed assertion here can leave happy-dom spinning rather than exiting, so the CI
// step carries a timeout: a stall turns the job red instead of idling.

const members=[{user_id:1,display_name:'Casey'},{user_id:2,display_name:'Ivy'},
  {user_id:3,display_name:'Jamie'},{user_id:4,display_name:'Priya',is_active:false}];
const tasks=[
  {task_id:1,assigned_to:null,assignee_ids:[],name:'Shared',can_postpone:false},
  {task_id:2,assigned_to:1,assignee_ids:[1],name:'Mine',can_postpone:false},
  {task_id:3,assigned_to:2,assignee_ids:[2,3],name:'Rotating',can_postpone:false}
];
// One card per section: a completion leaves a one-second redraw timer behind, and
// happy-dom cannot read activeElement across two live shadow roots. Opening a panel
// focuses its first control, so park the focus in the light DOM before a card goes.
const park=document.createElement('button');document.body.append(park);
let previous;
const mount=(config={},{circle=members,list=tasks,refuse=false}={})=>{
  if (previous) { park.focus(); previous.remove(); }
  const calls=[];
  const hass={locale:{language:'en'},states:{'todo.all':{state:String(list.length),attributes:{
    config_entry_id:'entry',circle_members:circle,tasks:list}}},
    callService:async(...args)=>{calls.push(args);if(refuse)throw new Error(
      'Donetick task action failed: Donetick denied the completion (400): User is not assigned to chore');}};
  const card=document.createElement('donetick-user-todo-card');
  card.setConfig({entity:'todo.all',user_id:'all',show_complete_as:true,...config});
  card.hass=hass;document.body.append(card);previous=card;
  const root=card.shadowRoot;
  return {card,root,calls,
    action:name=>root.querySelector(`[aria-label="Complete as: ${name}"]`),
    panel:()=>root.querySelector('.action-panel')?.getAttribute('aria-label') ?? null,
    select:()=>root.querySelector('.action-panel select[data-field="performer"]'),
    save:()=>root.querySelector('.action-panel .save-action'),
    error:()=>root.querySelector('.action-panel .error')?.textContent ?? null,
    choose:value=>{const field=root.querySelector('.action-panel select[data-field="performer"]');
      field.value=String(value);field.dispatchEvent(new window.Event('change'));},
    submit:()=>root.querySelector('.action-panel').dispatchEvent(new window.Event('submit',{cancelable:true}))};
};

// Who is offered: the active circle, the task's own people first, and no Anyone entry.
const state={attributes:{circle_members:members}};
assert.deepEqual(performerChoices(state,tasks[0]).map(member=>member.user_id),[1,2,3]);
assert.deepEqual(performerChoices(state,tasks[1]).map(member=>member.user_id),[1,2,3]);
assert.deepEqual(performerChoices(state,tasks[2]).map(member=>member.user_id),[2,3,1]);
// An assignee who is no longer active stays offered: the plain control credits them anyway.
assert.deepEqual(performerChoices(state,{task_id:9,assigned_to:4,assignee_ids:[]}).map(member=>member.user_id),[4,1,2,3]);
assert.deepEqual(performerChoices({attributes:{circle_members:[]}},{task_id:9}),[]);
assert.deepEqual(performerChoices(undefined,{task_id:9}),[]);
console.log('The active circle is offered, the task\'s own people first');

// Without a circle list there is nobody to offer, so the action stays away.
{
  const page=mount({},{circle:[],list:[{task_id:9,assigned_to:null,assignee_ids:[],name:'Alone',can_postpone:false}]});
  assert.equal(page.action('Alone'),null);
  assert.ok(page.root.querySelector('input[type=checkbox]'));
  console.log('Without a circle list the action is hidden rather than empty');
}

// Off by default, and the completion control is untouched by it.
{
  const page=mount({show_complete_as:false});
  assert.equal(page.action('Shared'),null);
  // And a config that never mentions the action must not show it either: the default is off.
  page.card.setConfig({entity:'todo.all',user_id:'all'});
  assert.equal(page.action('Shared'),null);
  page.root.querySelectorAll('input[type=checkbox]')[0].dispatchEvent(new window.Event('change'));
  await tick();
  assert.deepEqual(page.calls.pop(),['donetick','complete_assigned_task',{task_id:1,config_entry_id:'entry'}]);
  console.log('Off by default, and the completion control still credits the assignee');
}

// Enabled, it opens a dropdown beside the other row actions and confirms like they do.
{
  const page=mount();
  assert.ok(page.action('Shared'));
  assert.equal(page.action('Shared').getAttribute('aria-expanded'),'false');
  page.action('Shared').click();
  assert.equal(page.calls.length,0);
  assert.equal(page.panel(),'Complete as: Shared');
  assert.equal(page.action('Shared').getAttribute('aria-expanded'),'true');
  assert.deepEqual([...page.select().options].map(option=>option.textContent),['Casey','Ivy','Jamie']);
  assert.equal(page.select().value,'1');
  assert.equal(page.save().getAttribute('aria-label'),'Confirm completion');
  assert.equal(page.save().disabled,false);
  console.log('The action opens a performer dropdown with a confirm button');

  page.choose(2);
  assert.equal(page.save().disabled,false);
  page.submit();
  assert.deepEqual(page.calls.pop(),['donetick','complete_assigned_task',{task_id:1,config_entry_id:'entry',completed_by:2}]);
  await tick();
  assert.equal(page.panel(),null);
  console.log('Confirming credits the chosen member and closes the panel');
}

// The assignee leads the list, so an unchanged confirm books what the control would.
{
  const page=mount();
  page.action('Rotating').click();
  assert.deepEqual([...page.select().options].map(option=>option.textContent),['Ivy','Jamie','Casey']);
  assert.equal(page.select().value,'2');
  page.submit();
  assert.deepEqual(page.calls.pop(),['donetick','complete_assigned_task',{task_id:3,config_entry_id:'entry',completed_by:2}]);
  console.log('The assignee is preselected, so an unchanged confirm books the same credit');
}

// A refusal keeps the panel open with the server's own sentence and the pick intact.
{
  const page=mount({},{refuse:true});
  page.action('Mine').click();
  page.choose(3);
  page.submit();
  await tick();await tick();
  assert.equal(page.panel(),'Complete as: Mine');
  assert.match(page.error(),/denied the completion \(400\): User is not assigned to chore/);
  assert.equal(page.select().value,'3');
  console.log('A refusal keeps the panel open with the server error');
}

// Somebody the card never offered cannot be confirmed, however the option got there.
{
  const page=mount();
  page.action('Shared').click();
  const field=page.select();
  const outsider=document.createElement('option');outsider.value='99';outsider.textContent='Nobody';
  field.append(outsider);field.value='99';field.dispatchEvent(new window.Event('change'));
  assert.equal(page.save().disabled,true);
  page.submit();
  assert.equal(page.calls.length,0);
  assert.match(page.error(),/Choose someone from the circle/);
  console.log('Someone outside the offered circle cannot be confirmed');
}

// Escape closes it, and so does turning the action off underneath it.
{
  const page=mount();
  page.action('Shared').click();
  page.root.querySelector('.action-panel').dispatchEvent(new window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  assert.equal(page.panel(),null);
  page.action('Shared').click();
  assert.equal(page.panel(),'Complete as: Shared');
  // A config change that leaves the action on keeps its panel, as the other panels do.
  page.card.setConfig({entity:'todo.all',user_id:'all',show_complete_as:true,title:'Chores'});
  assert.equal(page.panel(),'Complete as: Shared');
  page.card.setConfig({entity:'todo.all',user_id:'all',show_complete_as:false});
  assert.equal(page.panel(),null);
  assert.equal(page.action('Shared'),null);
  console.log('Escape closes it, and so does turning the action off');
}
