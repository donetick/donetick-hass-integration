import assert from 'node:assert/strict';
import {recurrenceFields, cleanPatternChange, installRecurrenceEditor} from '../custom_components/donetick/frontend/donetick-action-editor.js';

assert.deepEqual([...recurrenceFields({})], []);
assert.deepEqual([...recurrenceFields({frequency_type:'once'})], []);
const interval = recurrenceFields({frequency_type:'interval'});
assert.ok(interval.has('frequency') && interval.has('interval_unit') && interval.has('schedule_time'));
assert.equal(interval.has('weekdays'), false);
const weekly = recurrenceFields({frequency_type:'days_of_the_week'});
assert.ok(weekly.has('weekdays') && weekly.has('week_pattern'));
assert.equal(weekly.has('frequency'), false);
assert.equal(weekly.has('occurrences'), false);
assert.ok(recurrenceFields({frequency_type:'days_of_the_week',week_pattern:'week_of_month'}).has('occurrences'));
assert.ok(recurrenceFields({frequency_type:'day_of_the_month'}).has('months'));
assert.deepEqual([...recurrenceFields({frequency_type:'daily'})], ['schedule_from']);
assert.ok(recurrenceFields({frequency:3}).has('interval_unit'));
assert.ok(recurrenceFields({frequency_type:'{{ pattern }}'}).has('frequency'));
assert.ok(recurrenceFields({frequency_type:'{{ pattern }}'}).has('months'));
assert.deepEqual(cleanPatternChange({frequency_type:'interval'}, {
  task_id:71,frequency_type:'days_of_the_week',frequency:3,interval_unit:'days',schedule_time:'18:00:00',
}), {task_id:71,frequency_type:'days_of_the_week',schedule_time:'18:00:00'});
assert.deepEqual(cleanPatternChange({frequency_type:'days_of_the_week',week_pattern:'week_of_month'}, {
  frequency_type:'days_of_the_week',week_pattern:'every_week',weekdays:['monday'],occurrences:[1,-1],
}), {frequency_type:'days_of_the_week',week_pattern:'every_week',weekdays:['monday']});
const template = {frequency_type:'{{ pattern }}',frequency:3,months:['january']};
assert.equal(cleanPatternChange({frequency_type:'interval'}, template), template);

const {Window} = await import(process.env.DOM_TEST_MODULE || 'happy-dom');
const window = new Window();
Object.assign(globalThis, {window,document:window.document,HTMLElement:window.HTMLElement,
  customElements:window.customElements,CustomEvent:window.CustomEvent});
const fields = ['frequency','interval_unit','weekdays','week_pattern','occurrences','months','day_of_month',
  'schedule_time','schedule_from','name'];
class Control extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:'open'});
    this._checkedKeys = new Set(['frequency','interval_unit','schedule_time']);
    this.originalCalls = 0;
    for (const key of fields) {
      const row = document.createElement('ha-settings-row');
      const selector = document.createElement('ha-selector');
      selector.key = key;
      if (key === 'occurrences') selector.selector = {select:{multiple:true}};
      row.append(selector);
      this.shadowRoot.append(row);
    }
  }
  updated() { this.originalCalls++; }
}
customElements.define('ha-service-control',Control);
installRecurrenceEditor(Control);
const wrapper = Control.prototype.updated;
installRecurrenceEditor(Control);
assert.equal(Control.prototype.updated,wrapper);
const control = document.createElement('ha-service-control');
document.body.append(control);
control.value = {action:'donetick.update_task',data:{frequency_type:'interval',frequency:3,interval_unit:'days'}};
control.updated();
const row = key => [...control.shadowRoot.querySelectorAll('ha-selector')].find(item => item.key === key).parentElement;
assert.equal(row('frequency').hidden,false);
assert.equal(row('weekdays').style.display,'none');
assert.equal(row('name').hidden,false);
let received;
document.body.addEventListener('value-changed',event => { received = event.detail.value; });
control.dispatchEvent(new CustomEvent('value-changed',{bubbles:true,composed:true,detail:{value:{
  ...control.value,data:{...control.value.data,frequency_type:'days_of_the_week'},
}}}));
assert.equal(received.data.frequency,undefined);
assert.equal(received.data.interval_unit,undefined);
assert.equal(control._checkedKeys.has('frequency'),false);
control.value = received;
control.updated();
assert.equal(row('frequency').hidden,true);
assert.equal(row('weekdays').hidden,false);
assert.equal(row('occurrences').hidden,true);
control.value = {...received,data:{...received.data,week_pattern:'week_of_month'}};
control.updated();
assert.equal(row('occurrences').hidden,false);
// Opening existing YAML never silently drops or conceals enabled fields.
control.value = {action:'donetick.update_task',data:{frequency_type:'days_of_the_week',frequency:3}};
control.updated();
assert.equal(row('frequency').hidden,false);
assert.equal(control.value.data.frequency,3);
// Nested action-selector values are not changes to the containing action.
const nestedData = {frequency_type:'once',frequency:3};
row('name').querySelector('ha-selector').dispatchEvent(new CustomEvent('value-changed',{
  bubbles:true,composed:true,detail:{value:{action:'donetick.update_task',data:nestedData}},
}));
assert.equal(received.data,nestedData);
// Numeric YAML occurrences display using HA's string-valued select options,
// while the saved YAML retains its original numeric values.
const numericOccurrences = [1,-1];
control.value = {action:'donetick.update_task',data:{
  frequency_type:'days_of_the_week',week_pattern:'week_of_month',occurrences:numericOccurrences,
}};
control.updated();
assert.deepEqual(row('occurrences').querySelector('ha-selector').value,['1','-1']);
assert.equal(control.value.data.occurrences,numericOccurrences);
// Temporarily detaching and reattaching an editor cannot strand hidden rows.
control.value = {action:'donetick.update_task',data:{frequency_type:'once'}};
control.updated();
control.remove();
control.updated();
document.body.append(control);
control.value = {action:'donetick.update_task',data:{frequency_type:'interval'}};
control.updated();
assert.equal(row('frequency').hidden,false);
assert.notEqual(row('frequency').style.display,'none');
// Other integrations always regain their complete native controls.
control.value = {action:'another.update_task',data:{frequency_type:'once'}};
control.updated();
for (const key of fields) assert.equal(row(key).hidden,false);
// The YAML data editor itself is untouched.
control.shadowRoot.append(document.createElement('ha-yaml-editor'));
control.value = {action:'donetick.update_task',data:{frequency_type:'interval',frequency:3}};
control.updated();
const yamlData = {frequency_type:'once',frequency:3};
control.dispatchEvent(new CustomEvent('value-changed',{bubbles:true,detail:{value:{action:'donetick.update_task',data:yamlData}}}));
assert.equal(received.data,yamlData);
assert.ok(control.originalCalls>=6);
// Loading the automatic startup adapter remains safe and idempotent.
customElements.define('home-assistant',class extends HTMLElement {});
await import('../custom_components/donetick/frontend/donetick-action-editor.js?startup');
assert.equal(Control.prototype.updated,wrapper);
control.shadowRoot.querySelector('ha-yaml-editor').remove();
control.value = {action:'donetick.update_task',data:{frequency_type:'once'}};
control.dispatchEvent(new window.MouseEvent('click',{bubbles:true,composed:true}));
assert.equal(row('frequency').hidden,true);
console.log('Recurrence controls follow pattern selection, clear incompatible UI fields, and preserve YAML, templates, and other actions');
