import assert from 'node:assert/strict';
const {Window} = await import(process.env.DOM_TEST_MODULE || 'happy-dom');
const window = new Window();
Object.assign(globalThis, {window, document: window.document, HTMLElement: window.HTMLElement,
  customElements: window.customElements, CustomEvent: window.CustomEvent});
customElements.define('ha-form',class extends HTMLElement {});
customElements.define('home-assistant',class extends HTMLElement {});
await import('../custom_components/donetick/frontend/donetick-user-todo-card.js');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const calls=[]; let fail=false;
const hass={locale:{language:'en'},states:{'todo.all':{state:'3',attributes:{config_entry_id:'entry',
  circle_members:[{user_id:1,display_name:'Casey'},{user_id:2,display_name:'Jamie'},{user_id:3,display_name:'Jasmin'}],
  tasks:[
    {task_id:1,assigned_to:1,name:'Weekly',can_postpone:true,next_due_date:'2026-10-20T16:00:00Z'},
    {task_id:2,assigned_to:null,name:'Shared',can_postpone:false},
    {task_id:3,assigned_to:3,name:'Rotating',can_postpone:false}
  ]}}},callService:async(...args)=>{calls.push(args);if(fail)throw new Error('Permission denied');}};
const card=document.createElement('donetick-user-todo-card');
const base={entity:'todo.all',user_id:'all',complete_control:'initials'};
card.setConfig(base);card.hass=hass;document.body.append(card);
const root=card.shadowRoot;
const circles=()=>[...root.querySelectorAll('.complete-initials')];

// The circle replaces the checkbox without adding a second completion control.
assert.equal(circles().length,3);
assert.equal(root.querySelectorAll('input[type=checkbox]').length,0);
assert.equal(root.querySelectorAll('[aria-label^="Complete: "]').length,3);
// Skip occurrence, Change due date and Reassign stay on the right; Complete does not join them.
assert.equal(root.querySelectorAll('.actions > button').length,7);
assert.equal(root.querySelectorAll('.actions [aria-label^="Complete: "]').length,0);
assert.equal(circles()[0].previousElementSibling,null);
assert.equal(circles()[0].nextElementSibling.className,'task');
console.log('Initials mode renders one circle per row instead of the checkbox');

// Jamie and Jasmin share a first letter, so both get two characters; Casey stays short.
assert.deepEqual(circles().map(circle=>circle.textContent),['C','','Ja']);
assert.equal(circles()[1].getAttribute('aria-label'),'Complete: Shared');
assert.equal(circles()[1].title,'Complete: Shared · Anyone');
assert.equal(circles()[0].title,'Complete: Weekly · Casey');
assert.equal(circles()[2].title,'Complete: Rotating · Jasmin');
assert.equal(circles()[0].querySelector('span').textContent,'C');
assert.match(root.querySelector('style').textContent,/button\.complete-initials\s*\{[^}]*min-width:44px/);
console.log('Circles carry the assignee initials, stay empty for Anyone and keep the full name in the title');

// An assignee missing from circle_members must not look like an Anyone task.
hass.states['todo.all'].attributes.tasks.push({task_id:4,assigned_to:12,name:'New member',can_postpone:false});
card.hass=hass;
assert.equal(circles().length,4);
assert.equal(circles()[3].textContent,'U');
assert.equal(circles()[3].title,'Complete: New member · User 12');
assert.notEqual(circles()[3].textContent,circles()[1].textContent);
hass.states['todo.all'].attributes.tasks.pop();
card.hass=hass;
console.log('An unresolved assignee falls back to the name the title shows');

// A completion from the circle behaves like the checkbox, including the pending state.
circles()[0].click();
assert.deepEqual(calls.pop(),['donetick','complete_assigned_task',{task_id:1,config_entry_id:'entry'}]);
assert.ok(circles()[0].disabled);
await tick();
assert.equal(root.querySelectorAll('.completed .complete-initials').length,1);
await new Promise(resolve=>setTimeout(resolve,1050));
fail=true;circles()[2].click();await tick();
assert.match(root.querySelector('.error').textContent,/Permission denied/);
assert.equal(circles()[2].disabled,false);
fail=false;
console.log('Completing from a circle calls the service, disables the control and reports failures');

// Unknown values are rejected; the other controls keep working unchanged.
assert.throws(()=>card.setConfig({...base,complete_control:'circle'}),/valid completion control/);
card.setConfig({...base,show_complete:false});
assert.equal(circles().length,0);
card.setConfig({...base,complete_control:'button',button_content:'label'});
assert.equal(circles().length,0);
assert.equal(root.querySelectorAll('[aria-label^="Complete: "]').length,3);
card.setConfig({...base,complete_control:'checkbox'});
assert.equal(root.querySelectorAll('input[type=checkbox]').length,3);
assert.equal(circles().length,0);
console.log('The circle is opt-in and leaves the checkbox and button styles untouched');

// With credit_completion: choose the circle asks who did the work, like the checkbox.
const asking=document.createElement('donetick-user-todo-card');
asking.setConfig({...base,credit_completion:'choose'});asking.hass=hass;document.body.append(asking);
const askRoot=asking.shadowRoot;
const askCircles=()=>[...askRoot.querySelectorAll('.complete-initials')];
const before=calls.length;
assert.equal(askCircles()[2].getAttribute('aria-expanded'),'false');
askCircles()[2].click();
assert.equal(calls.length,before);
assert.ok(askRoot.querySelector('.action-panel'));
assert.equal(askCircles()[2].getAttribute('aria-expanded'),'true');
assert.deepEqual([...askRoot.querySelectorAll('.panel-members button')].map(button=>button.textContent.trim()),['Jasmin']);
askRoot.querySelector('.panel-members button').click();
assert.deepEqual(calls.pop()[2],{task_id:3,config_entry_id:'entry',completed_by:3});
console.log('Asking who did the work also starts from the circle');
