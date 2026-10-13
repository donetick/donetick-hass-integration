import assert from 'node:assert/strict';
const {Window} = await import(process.env.DOM_TEST_MODULE || 'happy-dom');
const window = new Window();
Object.assign(globalThis,{window,document:window.document,HTMLElement:window.HTMLElement,customElements:window.customElements,CustomEvent:window.CustomEvent});
customElements.define('home-assistant',class extends HTMLElement {});
const {completedTasks} = await import('../custom_components/donetick/frontend/donetick-user-todo-card.js');
const today = new Date(Date.now()-60000);
const yesterday = new Date(today); yesterday.setDate(yesterday.getDate()-1);
const state = {state:'1',attributes:{circle_members:[{user_id:1,display_name:'Alex'},{user_id:2,display_name:'Sam'}],tasks:[{task_id:10,name:'Daily task',assigned_to:2,next_due_date:new Date(today.getTime()+86400000).toISOString()}],completed_tasks:[
  {uid:'history--1',task_id:10,name:'Daily task',completed_at:today.toISOString(),completed_by:1},
  {uid:'history--2',task_id:10,name:'Yesterday',completed_at:yesterday.toISOString(),completed_by:1}
]}};
assert.equal(completedTasks(state,1).length,1);
assert.equal(completedTasks(state,2).length,0);
assert.equal(completedTasks({...state,attributes:{...state.attributes,donetick_user_id:1}},2).length,1);
const card = document.createElement('donetick-user-todo-card');
card.setConfig({entity:'todo.all',user_id:'all'}); card.hass={states:{'todo.all':state},locale:{language:'en'}};
const root=card.shadowRoot;
assert.equal(root.querySelectorAll('.row').length,2);
assert.equal(root.querySelectorAll('.history-row').length,1);
assert.match(root.querySelector('.history-row .due').textContent,/Alex/);
assert.equal(root.querySelector('.history-row button, .history-row input'),null);
card.setConfig({entity:'todo.all',user_id:'all',task_view:'completed',display_filter:'overdue'});
assert.equal(root.querySelectorAll('.row').length,1);
card.setConfig({entity:'todo.all',user_id:'all',task_view:'pending'});
assert.equal(root.querySelectorAll('.history-row').length,0);
assert.throws(()=>card.setConfig({entity:'todo.all',user_id:'all',task_view:'bad'}),/task view/);
console.log('Persistent completed occurrences, performer attribution and independent pending filters passed');
const now = new Date('2026-10-26T12:00:00+01:00');
const historyState={attributes:{completed_tasks:[
  {uid:'h1',completed_by:1,completed_at:'2026-10-26T09:00:00+01:00',next_due_date:'2026-10-26'},
  {uid:'h2',completed_by:1,completed_at:'2026-10-26T08:00:00+01:00',next_due_date:'2026-10-25'},
  {uid:'h3',completed_by:1,completed_at:'2026-10-25T00:15:00+02:00',next_due_date:null},
  {uid:'h4',completed_by:1,completed_at:'2026-10-24T23:59:00+02:00',next_due_date:'2026-10-26'},
  {uid:'h5',completed_by:2,completed_at:'2026-10-26T10:00:00+01:00',next_due_date:'2026-10-26'},
  {uid:'h6',completed_by:1,completed_at:'invalid',next_due_date:'2026-10-26'},
  {uid:'h7',completed_by:1,completed_at:'2026-10-26T13:00:00+01:00',next_due_date:'2026-10-26'}
]}};
assert.deepEqual(completedTasks(historyState,1,now,{completed_days:2}).map(t=>t.uid),['h1','h2','h3']);
assert.deepEqual(completedTasks(historyState,1,now,{completed_days:2,completed_filter:'matching',display_filter:'today'}).map(t=>t.uid),['h1']);
assert.deepEqual(completedTasks(historyState,1,now,{completed_days:2,completed_limit:1}).map(t=>t.uid),['h1']);
assert.equal(completedTasks(historyState,'all',now,{completed_days:2,completed_limit:0}).length,4);
assert.equal(completedTasks(historyState,1,now,{completed_days:2,completed_filter:'matching',display_filter:'all'}).length,3);
for (const options of [{completed_days:0},{completed_days:8},{completed_days:1.5},{completed_limit:-1},{completed_limit:501},{completed_limit:true},{completed_filter:'bad'}]) {
  assert.throws(()=>card.setConfig({entity:'todo.all',user_id:'all',...options}));
}
state.attributes.completed_tasks[0].next_due_date=yesterday.toISOString();
card.setConfig({entity:'todo.all',user_id:'all',task_view:'completed',display_filter:'today',completed_filter:'matching'});
assert.equal(root.querySelectorAll('.history-row').length,0);
assert.match(root.querySelector('.empty').textContent,/match the task date filter/);
card.setConfig({entity:'todo.all',user_id:'all',task_view:'completed',completed_days:7});
assert.equal(root.querySelectorAll('.history-row').length,2);
assert.match(root.querySelector('.history-heading').textContent,/last 7 days/);
assert.doesNotMatch(root.querySelector('.history-row .due').textContent,/Overdue/);
card.setConfig({entity:'todo.all',user_id:'all',task_view:'completed',completed_days:null,completed_limit:null});
assert.equal(root.querySelectorAll('.history-row').length,1);
assert.match(root.querySelector('.history-heading').textContent,/Completed today/);
console.log('History periods across DST, original due dates, limits and option validation passed');
