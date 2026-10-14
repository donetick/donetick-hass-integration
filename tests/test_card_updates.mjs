import assert from 'node:assert/strict';
const {Window}=await import(process.env.DOM_TEST_MODULE || 'happy-dom');
const window=new Window();
Object.assign(globalThis,{window,document:window.document,HTMLElement:window.HTMLElement,customElements:window.customElements,CustomEvent:window.CustomEvent});
customElements.define('home-assistant',class extends HTMLElement {});
let dataWrites=0;
customElements.define('ha-form',class extends HTMLElement {
  set data(value){this._data=value;dataWrites++;}
  get data(){return this._data;}
});
await import('../custom_components/donetick/frontend/donetick-user-todo-card.js');
const task={task_id:1,assigned_to:1,name:'Daily task',labels:['original']};
const state={state:'1',attributes:{circle_members:[{user_id:1,display_name:'Demo'}],tasks:[task]}};
let hass={states:{'todo.demo':state},locale:{language:'en'},themes:{darkMode:false},callService:async()=>{}};
const config={entity:'todo.demo',user_id:1};
const card=document.createElement('donetick-user-todo-card');card.setConfig(config);card.hass=hass;
const editor=document.createElement('donetick-user-todo-editor');editor.setConfig(config);editor.hass=hass;
let editorRenders=0;
const originalRender=editor.render.bind(editor);
editor.render=()=>{editorRenders++;originalRender();};
const row=card.shadowRoot.querySelector('.row');
const initialWrites=dataWrites;
for(let i=0;i<20;i++) {
  hass={...hass,states:{...hass.states,'sensor.unrelated':{state:String(i),attributes:{}}}};
  card.hass=hass;editor.hass=hass;
}
assert.equal(card.shadowRoot.querySelector('.row'),row);
assert.equal(editorRenders,0);assert.equal(dataWrites,initialWrites);
card.setConfig({...config});editor.setConfig({...config});
assert.equal(card.shadowRoot.querySelector('.row'),row);assert.equal(editorRenders,0);
console.log('20 unrelated HA updates: 0 editor renders, 0 form data writes, 0 preview row replacements');

// New list data must update the preview and label choices, but not rewrite values.
hass={...hass,states:{...hass.states,'todo.demo':{...state,attributes:{...state.attributes,tasks:[{...task,name:'Updated task',labels:['new-label']}]}}}};
card.hass=hass;editor.hass=hass;
assert.equal(card.shadowRoot.querySelector('.name').textContent,'Updated task');
assert.equal(editorRenders,1);assert.equal(dataWrites,initialWrites);
const flatten=fields=>fields.flatMap(field=>[field,...flatten(field.schema || [])]);
const form=editor.shadowRoot.querySelector('ha-form');
assert.deepEqual(flatten(form.schema).find(field=>field.name==='labels').selector.select.options.map(option=>option.value),['new-label']);

// A new list must become selectable; a presentation change must reach both views.
hass={...hass,states:{...hass.states,'todo.second':{...state}}};editor.hass=hass;
assert.ok(flatten(form.schema).find(field=>field.name==='entity').selector.entity.include_entities.includes('todo.second'));
const beforeLocale=card.shadowRoot.querySelector('.row');
hass={...hass,locale:{language:'nl'}};card.hass=hass;editor.hass=hass;
assert.notEqual(card.shadowRoot.querySelector('.row'),beforeLocale);assert.equal(form.hass.locale.language,'nl');
const beforeTheme=card.shadowRoot.querySelector('.row');
hass={...hass,themes:{darkMode:true}};card.hass=hass;editor.hass=hass;
assert.notEqual(card.shadowRoot.querySelector('.row'),beforeTheme);assert.equal(form.hass.themes.darkMode,true);

// Relative dates and today's history still refresh at minute/day boundaries.
const originalNow=Date.now;const beforeMinute=card.shadowRoot.querySelector('.row');
try {Date.now=()=>originalNow()+60000;card.hass={...hass};assert.notEqual(card.shadowRoot.querySelector('.row'),beforeMinute);}
finally {Date.now=originalNow;}

// Config feedback from HA must not duplicate a render or break blank fields.
let configEvents=0;
editor.addEventListener('config-changed',event=>{configEvents++;editor.setConfig({...event.detail.config});});
const beforeChange=editorRenders;
form.dispatchEvent(new CustomEvent('value-changed',{detail:{value:{...form.data,completed_days:null}}}));
assert.equal(editorRenders,beforeChange+1);assert.equal(form.data.completed_days,null);assert.equal(configEvents,1);
form.dispatchEvent(new CustomEvent('value-changed',{detail:{value:{...form.data}}}));
assert.equal(configEvents,1);
form.dispatchEvent(new CustomEvent('value-changed',{detail:{value:{...form.data,completed_days:3}}}));
assert.equal(form.data.completed_days,3);assert.equal(configEvents,2);
console.log('List, selector choices, locale, theme, time boundaries, and config feedback remain correct');
// Collapsed sections must not mount their native selectors. Expanding changes
// presentation only, never config; closing must retain values for reopening.
const historyGroup=()=>form.schema.find(field=>field.name==='completed_options');
assert.equal(historyGroup().expanded,false);assert.deepEqual(historyGroup().schema,[]);
assert.deepEqual(form.schema.find(field=>field.name==='customization_options').schema,[]);
const expandable=document.createElement('ha-form-expandable');
form.append(expandable);
const toggle=expanded=>{
  expandable.schema=historyGroup();
  expandable.dispatchEvent(new CustomEvent('expanded-will-change',{detail:{expanded},bubbles:true,composed:true}));
};
const beforeExpansionWrites=dataWrites;const beforeExpansionEvents=configEvents;
toggle(true);
assert.equal(historyGroup().expanded,true);
assert.ok(historyGroup().schema.find(field=>field.name==='completed_days'));
assert.equal(form.data.completed_days,3);
hass={...hass,states:{...hass.states,'todo.demo':{...hass.states['todo.demo']}}};
editor.hass=hass;assert.equal(historyGroup().expanded,true);
toggle(false);assert.deepEqual(historyGroup().schema,[]);
toggle(true);assert.equal(form.data.completed_days,3);
assert.equal(configEvents,beforeExpansionEvents);assert.equal(dataWrites,beforeExpansionWrites);
expandable.remove();
console.log('Collapsed controls unmount; opening and closing preserves values and expansion across HA updates');
