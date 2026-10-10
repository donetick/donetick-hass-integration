import assert from 'node:assert/strict';
globalThis.HTMLElement = class {};
globalThis.customElements = {define() {}, get() {}};
globalThis.window = {};
const {userTasks, actionData, emptyMessage, dueText, upcomingDayLimit} = await import('../custom_components/donetick/frontend/donetick-user-todo-card.js');
const state = {attributes: {config_entry_id: 'entry', tasks: [
  {task_id: 1, assigned_to: 2}, {task_id: 2, assigned_to: 1}, {task_id: 3, assigned_to: null}
]}};
assert.deepEqual(userTasks(state, '2').map(t => t.task_id), [1]);
assert.deepEqual(userTasks(state, 'all').map(t => t.task_id), [1,2,3]);
assert.equal(emptyMessage({user_id:'all',display_filter:'today'}),'No tasks for all users · Filter: Today');
assert.deepEqual(userTasks(undefined, 2), []);
const sortingState={attributes:{tasks:[
  {task_id:1,assigned_to:1,name:'Zeta',priority:1,next_due_date:'2026-10-20'},
  {task_id:2,assigned_to:1,name:'Alpha 10',priority:4,next_due_date:'2026-10-23'},
  {task_id:3,assigned_to:1,name:'alpha 2',priority:4,next_due_date:'2026-10-22'},
  {task_id:4,assigned_to:1,name:'Beta'},
  {task_id:5,assigned_to:1,name:'Éclair',priority:2,next_due_date:'2026-10-21'},
  {task_id:6,assigned_to:1,name:'Bravo',priority:4}
]}};
const sortedIds=sort=>userTasks(sortingState,1,'all',new Date(),7,sort,'en').map(task=>task.task_id);
assert.deepEqual(sortedIds('due_date'),[1,5,3,2,4,6]);
assert.deepEqual(sortedIds('priority'),[3,2,6,5,1,4]);
assert.deepEqual(sortedIds('name'),[3,2,4,6,5,1]);
assert.deepEqual(sortingState.attributes.tasks.map(task=>task.task_id),[1,2,3,4,5,6]);
assert.deepEqual(actionData(state, state.attributes.tasks[0]), {task_id: 1, config_entry_id: 'entry'});
assert.equal('days' in actionData(state, state.attributes.tasks[0]), false);
const now = new Date('2026-10-24T12:00:00+02:00');
const filterState = {attributes:{tasks:[
  {task_id:1,assigned_to:1,next_due_date:'2026-10-23'},
  {task_id:2,assigned_to:1,next_due_date:'2026-10-24T09:00:00+02:00'},
  {task_id:3,assigned_to:1,next_due_date:'2026-10-24T18:00:00+02:00'},
  {task_id:4,assigned_to:1,next_due_date:'2026-10-25'},
  {task_id:5,assigned_to:1},
  {task_id:6,assigned_to:2,next_due_date:'2026-10-23'},
  {task_id:7,assigned_to:1,next_due_date:'invalid'}
]}};
const ids = filter => userTasks(filterState,1,filter,now).map(task=>task.task_id);
assert.deepEqual(ids('all'),[1,2,3,4,5,7]);
assert.deepEqual(ids('overdue'),[1,2]);
assert.deepEqual(ids('today'),[2,3]);
assert.deepEqual(ids('upcoming'),[3,4]);
assert.deepEqual(userTasks(filterState,1,'upcoming',now,7,'due_date','en',true).map(task=>task.task_id),[1,2,3,4]);
assert.deepEqual(userTasks(filterState,1,'today',new Date('2026-10-25T12:00:00+01:00')).map(task=>task.task_id),[4]);
const windowState={attributes:{tasks:[
  {task_id:1,assigned_to:1,next_due_date:'2026-10-24'},
  {task_id:2,assigned_to:1,next_due_date:'2026-10-25'},
  {task_id:3,assigned_to:1,next_due_date:'2026-10-31T23:59:00+01:00'},
  {task_id:4,assigned_to:1,next_due_date:'2026-11-01T00:00:00+01:00'},
  {task_id:5,assigned_to:1}
]}};
assert.deepEqual(userTasks(windowState,1,'upcoming',now,1).map(task=>task.task_id),[1,2]);
assert.deepEqual(userTasks(windowState,1,'upcoming',now,7).map(task=>task.task_id),[1,2,3]);
assert.deepEqual(userTasks(windowState,1,'upcoming',now,0).map(task=>task.task_id),[1,2,3,4]);
assert.deepEqual(userTasks(windowState,1,'all',now,1).map(task=>task.task_id),[1,2,3,4,5]);
console.log('Card user filtering and entry routing passed');
assert.equal(emptyMessage({display_filter:'all'},'Torben'),'No tasks for Torben · Filter: All tasks');
assert.equal(emptyMessage({display_filter:'today'},'Torben'),'No tasks for Torben · Filter: Today');
assert.match(emptyMessage({display_filter:'upcoming',upcoming_days:1},'Torben'),/1 day ahead/);
assert.match(emptyMessage({display_filter:'upcoming',upcoming_days:0},'Torben'),/no day limit/);
assert.match(emptyMessage({display_filter:'upcoming'},'Torben'),/7 days ahead/);
assert.match(emptyMessage({display_filter:'upcoming',upcoming_days:null},'Torben'),/no day limit/);
assert.equal(upcomingDayLimit(undefined),7);
assert.equal(upcomingDayLimit(null),0);
assert.equal(upcomingDayLimit(''),0);
assert.deepEqual(userTasks(windowState,1,'upcoming',now,null).map(task=>task.task_id),[1,2,3,4]);
const relativeNow = new Date(2026,9,24,12);
assert.equal(dueText('2026-10-25','en',relativeNow,'24','relative'),'Tomorrow');
assert.equal(dueText('2026-10-27','en',relativeNow,'24','relative'),'In 3 days');
assert.equal(dueText('2026-10-31','en',relativeNow,'24','relative'),'Next week');
assert.equal(dueText('2026-10-23','en',relativeNow,'24','relative'),'Yesterday');
assert.equal(dueText(new Date(2026,9,24,9).toISOString(),'en',relativeNow,'24','relative'),'3 hours ago');
assert.match(dueText('2026-10-27','en',relativeNow,'24','both'),/^In 3 days · .*Oct.*27/);
assert.equal(dueText('2026-10-25','fr',relativeNow,'24','relative'),'Demain');
assert.equal(dueText(null,'en',relativeNow,'24','relative'),'No due date');
assert.equal(dueText('invalid','en',relativeNow,'24','both'),'No due date');
console.log('Unlimited windows, optional overdue tasks and relative date modes passed');
