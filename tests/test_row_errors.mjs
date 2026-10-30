// A failed action's message belongs to the task it was refused for. A service call
// takes several Donetick round trips, during which every other row stays live, so the
// message must survive whatever the user taps meanwhile.
import assert from 'node:assert/strict';
const {Window} = await import(process.env.DOM_TEST_MODULE || 'happy-dom');
const window = new Window();
Object.assign(globalThis, {window, document: window.document, HTMLElement: window.HTMLElement,
  customElements: window.customElements, CustomEvent: window.CustomEvent});
customElements.define('ha-form',class extends HTMLElement {});
customElements.define('home-assistant',class extends HTMLElement {});
await import('../custom_components/donetick/frontend/donetick-user-todo-card.js');
const settle=async()=>{await new Promise(resolve=>setTimeout(resolve,0));await new Promise(resolve=>setTimeout(resolve,0));};

const members=[{user_id:1,display_name:'Casey'},{user_id:2,display_name:'Ivy'}];
let refuse;
const hass={locale:{language:'en'},states:{'todo.all':{state:'2',attributes:{config_entry_id:'entry',circle_members:members,tasks:[
  {task_id:1,assigned_to:1,assignee_ids:[1],name:'Dishes',can_postpone:true,next_due_date:'2026-10-24T16:00:00Z',description:'Rinse first'},
  {task_id:2,assigned_to:2,assignee_ids:[2],name:'Laundry',can_postpone:true,next_due_date:'2026-10-25T16:00:00Z'}
]}}},callService:()=>new Promise((_,reject)=>{refuse=()=>reject(new Error('Donetick task action failed: no permission'));})};
const card=document.createElement('donetick-user-todo-card');
card.setConfig({entity:'todo.all',user_id:'all'});
card.hass=hass;document.body.append(card);
const root=card.shadowRoot;
const click=label=>root.querySelector(`[aria-label="${label}"]`).click();
const panelFor=()=>root.querySelector('.action-panel')?.getAttribute('aria-label') ?? null;
const cardError=()=>[...root.querySelectorAll('ha-card > .error')].map(error=>error.textContent);
const submit=()=>root.querySelector('form').dispatchEvent(new window.Event('submit',{cancelable:true}));
const escape=()=>root.querySelector('.action-panel')?.dispatchEvent(new window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));

// A completion is refused with no panel anywhere: the message names its own task.
root.querySelectorAll('input[type=checkbox]')[0].dispatchEvent(new window.Event('change'));
refuse();await settle();
assert.equal(panelFor(),null);
assert.deepEqual(cardError(),['Dishes: Donetick task action failed: no permission']);
assert.equal(root.querySelector('ha-card > .error').getAttribute('role'),'alert');
console.log('A failure with no open panel names the task it belongs to');

// Refused with its own panel open, it reads best inside that panel, as the server wrote it.
click('Skip occurrence: Dishes');
assert.deepEqual(cardError(),[]);
submit();
refuse();await settle();
assert.equal(panelFor(),'Skip occurrence: Dishes');
assert.equal(root.querySelector('.action-panel .error').textContent,'Donetick task action failed: no permission');
assert.deepEqual(cardError(),[]);
console.log('The refused task\'s own panel shows the message as the server wrote it');
escape();

// Another row's panel opened meanwhile must not wear it.
click('Skip occurrence: Dishes');
submit();
click('Skip occurrence: Laundry');
assert.equal(panelFor(),'Skip occurrence: Laundry');
refuse();await settle();
assert.equal(panelFor(),'Skip occurrence: Laundry');
assert.equal(root.querySelector('.action-panel .error'),null);
assert.match(cardError()[0],/^Dishes: /);
assert.equal(root.querySelectorAll('[role=alert]').length,1);
console.log('A refusal never lands in another row\'s panel');
escape();

// Nor may it be swallowed when the refused row opens its description instead.
click('Skip occurrence: Dishes');
submit();
click('Show description: Dishes');
assert.ok(root.querySelector('.description'));
refuse();await settle();
assert.match(cardError()[0],/^Dishes: /);
console.log('A refusal survives the row opening its description instead');
click('Show description: Dishes');

// The same holds when the call succeeds: it closes its own panel, not whichever is open.
let accept;
hass.callService=(...args)=>new Promise(resolve=>{accept=()=>resolve();});
click('Skip occurrence: Dishes');
submit();
click('Skip occurrence: Laundry');
assert.equal(panelFor(),'Skip occurrence: Laundry');
accept();await settle();
assert.equal(panelFor(),'Skip occurrence: Laundry');
assert.deepEqual(cardError(),[]);
console.log('A successful action closes its own panel and leaves another row\'s open');

// A panel's own validation message is owned by that panel's task too, so it stays put:
// tests/test_user_card_dom.mjs asserts it inside .action-panel for the date and assign
// panels, which is the guard for that half.
