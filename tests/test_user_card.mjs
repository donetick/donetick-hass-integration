import assert from 'node:assert/strict';
globalThis.HTMLElement = class {};
globalThis.customElements = {define() {}, get() {}, whenDefined() { return Promise.resolve(); }};
globalThis.window = {};
const {userTasks, actionData, emptyMessage, dueText, upcomingDayLimit, taskLabels, dateFilters, recurrenceText, memberInitials} = await import('../custom_components/donetick/frontend/donetick-user-todo-card.js');
for (const unit of ['hours','days','weeks','months','years']) {
  assert.equal(recurrenceText({frequency_type:'interval',frequency:6,interval_type:unit}),`Every 6 ${unit}`);
  assert.equal(recurrenceText({frequency_type:'interval',frequency:1,interval_type:unit}),`Every 1 ${unit.slice(0,-1)}`);
}
assert.equal(recurrenceText({frequency_type:'weekly'}),'Weekly');
assert.equal(recurrenceText({frequency_type:'once'}),'');
assert.equal(recurrenceText({frequency_type:'interval',frequency:6}),'');
assert.equal(recurrenceText({frequency_type:'interval',frequency:0,interval_type:'weeks'}),'');
const state = {attributes: {config_entry_id: 'entry', tasks: [
  {task_id: 1, assigned_to: 2}, {task_id: 2, assigned_to: 1}, {task_id: 3, assigned_to: null}
]}};
assert.deepEqual(userTasks(state, '2').map(t => t.task_id), [1]);
assert.deepEqual(userTasks(state, 'all').map(t => t.task_id), [1,2,3]);
assert.deepEqual(userTasks(state, '2', 'all', new Date(), 7, 'due_date', 'en', false, true).map(t => t.task_id), [1,3]);
const memberState = {attributes:{tasks:[{task_id:1,assigned_to:2}], anyone_tasks:[{task_id:3,assigned_to:null}]}};
assert.deepEqual(userTasks(memberState, 2).map(t=>t.task_id),[1]);
assert.deepEqual(userTasks(memberState, 2, 'all', new Date(), 7, 'due_date', 'en', false, true).map(t=>t.task_id),[1,3]);
assert.equal(emptyMessage({user_id:2,include_anyone:true},'Melissa'),'No tasks for Melissa or Anyone · Filter: All tasks');
const mixedState = {attributes:{tasks:[
  {task_id:1,assigned_to:2,next_due_date:'2026-10-20',name:'Zebra'},
  {task_id:2,assigned_to:null,next_due_date:'2026-10-20',name:'Apple'},
  {task_id:3,assigned_to:null,next_due_date:'2026-10-19',name:'Overdue'},
  {task_id:4,assigned_to:1,next_due_date:'2026-10-20',name:'Other user'},
  {task_id:5,assigned_to:null,name:'Undated'}
]}};
const mixedNow = new Date(2026,9,20,12);
assert.deepEqual(userTasks(mixedState,2,'today',mixedNow,7,'name','en',false,true).map(t=>t.task_id),[2,1]);
assert.deepEqual(userTasks(mixedState,2,'overdue',mixedNow,7,'name','en',false,true).map(t=>t.task_id),[3]);
assert.deepEqual(userTasks(mixedState,2,'upcoming',mixedNow,7,'name','en',true,true).map(t=>t.task_id),[2,3,1]);
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
const labelState={attributes:{tasks:[
  {task_id:1,assigned_to:1,name:'HVAC',labels:[{id:7,name:'maintenance'},{id:8,name:'technical'}],next_due_date:'2026-10-25'},
  {task_id:2,assigned_to:1,name:'Cleaning',labels:'household, daily',next_due_date:'2026-10-24'},
  {task_id:3,assigned_to:2,name:'Inspection',labels:[{id:7,name:'maintenance'}],next_due_date:'2026-10-25'},
  {task_id:4,assigned_to:1,name:'Filter',labels:['technical'],next_due_date:'2027-10-25'},
  {task_id:5,assigned_to:1,name:'Unlabelled'}
]}};
const labelIds=(labels,user='all',filter='all',days=0,sort='due_date')=>userTasks(labelState,user,filter,now,days,sort,'en',false,labels).map(task=>task.task_id);
assert.deepEqual(labelIds(['maintenance']),[1,3]);
assert.deepEqual(labelIds(['maintenance','technical']),[1,3,4]);
assert.deepEqual(labelIds(['maintenance'],1),[1]);
assert.deepEqual(labelIds(['maintenance','technical'],1,'upcoming',1),[1]);
assert.deepEqual(labelIds(['technical'],1,'upcoming',0),[1,4]);
assert.deepEqual(labelIds(['daily'],1,'today'),[2]);
assert.deepEqual(labelIds(['maintenance','technical'],'all','all',0,'name'),[4,1,3]);
assert.deepEqual(labelIds(['missing']),[]);
assert.equal(labelIds([]).length,5);
assert.deepEqual(taskLabels(' daily, household, daily, '),['daily','household']);
assert.deepEqual(taskLabels([null,{}, {name:'maintenance'},' technical ',{name:5}]),['maintenance','technical']);
assert.deepEqual(taskLabels(null),[]);
assert.equal(emptyMessage({user_id:'all',labels:['maintenance','technical']}),'No tasks for all users · Filter: All tasks · Labels: maintenance, technical');
assert.deepEqual(actionData(labelState,labelState.attributes.tasks[0]),{task_id:1,config_entry_id:undefined});
console.log('Label selection combines with user, date and sort filters without changing action payloads');
const groupIds=(filters,days=7)=>userTasks(filterState,1,filters,now,days).map(task=>task.task_id);
assert.deepEqual(groupIds(['overdue']),[1,2]);
assert.deepEqual(groupIds(['today']),[2,3]);
assert.deepEqual(groupIds(['overdue','today']),[1,2,3]); // Overlap never duplicates tasks.
assert.deepEqual(groupIds(['future']),[4]);
assert.deepEqual(groupIds(['undated']),[5]);
assert.deepEqual(groupIds(['today','future','undated']),[2,3,4,5]);
assert.deepEqual(groupIds([]),[1,2,3,4,5,7]);
assert.deepEqual(userTasks(windowState,1,['future'],now,1).map(task=>task.task_id),[2]);
assert.deepEqual(userTasks(windowState,1,['future'],now,0).map(task=>task.task_id),[2,3,4]);
assert.deepEqual(userTasks(labelState,1,['future'],now,0,'due_date','en',false,['technical']).map(task=>task.task_id),[1,4]);
assert.deepEqual(dateFilters({display_filter:'upcoming'}),['overdue','today','future']);
assert.deepEqual(dateFilters({display_filter:'upcoming',include_overdue:false}),['today','future']);
assert.deepEqual(dateFilters({display_filters:[],display_filter:'overdue'}),[]);
assert.deepEqual(dateFilters({display_filter:'today'}),['today']);
assert.equal(emptyMessage({user_id:'all',display_filters:['overdue','undated']}),'No tasks for all users · Filter: Overdue, Without a due date');
assert.match(emptyMessage({display_filters:['future'],upcoming_days:0},'Admin'),/Future \(no day limit\)/);
const ownerState={attributes:{...state.attributes,donetick_user_id:2}};
assert.deepEqual(userTasks(ownerState,1).map(task=>task.task_id),[1]);
assert.deepEqual(userTasks(ownerState,undefined).map(task=>task.task_id),[1]);
console.log('Date groups combine without duplicates and per-user lists override stale assignment');
const matchIds=(labels,mode)=>userTasks(labelState,'all',['future'],now,0,'due_date','en',false,labels,mode).map(task=>task.task_id);
assert.deepEqual(matchIds(['maintenance','technical'],'any'),[1,3,4]);
assert.deepEqual(matchIds(['maintenance','technical'],'all'),[1]);
assert.deepEqual(matchIds(['maintenance','missing'],'all'),[]);
assert.deepEqual(matchIds(['maintenance'],'all'),matchIds(['maintenance'],'any'));
assert.deepEqual(matchIds([],'all'),[1,3,4]);
assert.deepEqual(userTasks(labelState,2,['future'],now,0,'due_date','en',false,['maintenance','technical'],'all'),[]);
assert.match(emptyMessage({user_id:'all',labels:['maintenance','technical'],label_match:'all'}),/maintenance AND technical/);
console.log('AND and OR label matching compose with user and date groups');

const circle=[{user_id:1,display_name:'Casey'},{user_id:2,display_name:'Ivy'},{user_id:3,display_name:'Jamie'},{user_id:4,display_name:'Jasmin'},{user_id:5,username:'avery'},{user_id:6}];
assert.equal(memberInitials(circle[0],circle,'en'),'C');
assert.equal(memberInitials(circle[1],circle,'en'),'I');
assert.equal(memberInitials(circle[2],circle,'en'),'Ja');
assert.equal(memberInitials(circle[3],circle,'en'),'Ja');
assert.equal(memberInitials(circle[4],circle,'en'),'A');
assert.equal(memberInitials(circle[5],circle,'en'),'U');
assert.equal(memberInitials(undefined,circle,'en'),'');
assert.equal(memberInitials({user_id:7,display_name:'   '},circle,'en'),'');
assert.equal(memberInitials({user_id:8,display_name:'ida'},[{user_id:8,display_name:'ida'},{user_id:9,display_name:'Ingo'}],'en'),'Id');
assert.equal(memberInitials({user_id:1,display_name:'Casey'},[],'en'),'C');
assert.equal(memberInitials({user_id:1,display_name:'\u{1f600}ngo'},circle,'en'),'\u{1f600}');
assert.equal(memberInitials({user_id:1,display_name:'ilker'},[{user_id:1,display_name:'ilker'}],'tr'),'\u0130');
assert.equal(memberInitials({user_id:10,display_name:'J Smith'},[{user_id:10,display_name:'J Smith'},{user_id:11,display_name:'Jasmin'}],'en'),'Js');
assert.equal(memberInitials({user_id:10,display_name:'J. Smith'},[{user_id:10,display_name:'J. Smith'},{user_id:11,display_name:'Jasmin'}],'en'),'Js');
assert.equal(memberInitials({user_id:10,display_name:'J'},[{user_id:10,display_name:'J'},{user_id:11,display_name:'Jasmin'}],'en'),'J');
console.log('Member initials disambiguate shared first letters and follow the HA language');
