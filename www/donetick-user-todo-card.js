export function userTasks(state, userId) {
  return (state?.attributes?.tasks || []).filter(task => task.assigned_to === Number(userId));
}
export function actionData(state, task, days) {
  const data = {task_id: task.task_id, config_entry_id: state.attributes.config_entry_id};
  if (days !== undefined) data.days = days;
  return data;
}
class DonetickUserTodoCard extends HTMLElement {
  static getConfigElement() { return document.createElement('donetick-user-todo-editor'); }
  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find(id => id.startsWith('todo.') && hass.states[id].attributes.circle_members);
    return {entity, user_id: hass.states[entity]?.attributes.circle_members?.[0]?.user_id, postpone_days: 1};
  }
  constructor() { super(); this.attachShadow({mode: 'open'}); this._pending = new Set(); }
  setConfig(config) {
    if (!config.entity?.startsWith('todo.')) throw new Error('Choose a Donetick todo list');
    if (!Number.isInteger(Number(config.user_id)) || Number(config.user_id) < 1) throw new Error('Choose a Donetick user');
    const days = Number(config.postpone_days ?? 1);
    if (!Number.isInteger(days) || days < 1 || days > 365) throw new Error('Postpone days must be between 1 and 365');
    this._config = {...config, user_id: Number(config.user_id), postpone_days: days}; this.render();
  }
  set hass(hass) { this._hass = hass; this.render(); }
  getCardSize() { return 2 + userTasks(this._hass?.states[this._config?.entity], this._config?.user_id).length; }
  async act(task, complete) {
    if (this._pending.has(task.task_id)) return;
    const state = this._hass.states[this._config.entity];
    this._pending.add(task.task_id); this._error = ''; this.render();
    try {
      await this._hass.callService('donetick', complete ? 'complete_assigned_task' : 'postpone_task',
        actionData(state, task, complete ? undefined : this._config.postpone_days));
    } catch (err) { this._error = err.message || String(err); }
    finally { this._pending.delete(task.task_id); this.render(); }
  }
  render() {
    if (!this._config || !this._hass) return;
    const state = this._hass.states[this._config.entity];
    const member = state?.attributes.circle_members?.find(m => m.user_id === this._config.user_id);
    this.shadowRoot.innerHTML = `<style>
      ha-card { padding: 18px; } h2 { margin: 0 0 14px; font-size: 20px; font-weight: 500; }
      .row { display: flex; align-items: center; gap: 10px; padding: 12px 0; border-top: 1px solid var(--divider-color); }
      .task { flex: 1; min-width: 0; } .name { overflow-wrap: anywhere; } .due { color: var(--secondary-text-color); font-size: 12px; margin-top: 4px; }
      button { cursor: pointer; border: 1px solid var(--divider-color); border-radius: 8px; padding: 9px 11px; background: var(--card-background-color); color: var(--primary-color); font: inherit; font-size: 13px; }
      button:disabled { opacity: .5; cursor: wait; } button:focus-visible { outline: 2px solid var(--primary-color); }
      .error { color: var(--error-color); } .empty { color: var(--secondary-text-color); }
      @media(max-width: 420px) { .row { flex-wrap: wrap; } .task { flex-basis: 100%; } }
    </style><ha-card></ha-card>`;
    const card = this.shadowRoot.querySelector('ha-card');
    const addText = (parent, tag, text, cls) => { const el = document.createElement(tag); el.textContent = text; if(cls) el.className = cls; parent.append(el); return el; };
    addText(card, 'h2', this._config.title || `${member?.display_name || 'User ' + this._config.user_id} — Tasks`);
    if (this._error) addText(card, 'p', this._error, 'error');
    if (!state || ['unavailable', 'unknown'].includes(state.state)) { addText(card, 'p', 'Donetick list unavailable', 'empty'); return; }
    const tasks = userTasks(state, this._config.user_id);
    if (!tasks.length) addText(card, 'p', 'No tasks for this user', 'empty');
    for (const task of tasks) {
      const row = document.createElement('div'); row.className = 'row'; card.append(row);
      const text = document.createElement('div'); text.className = 'task'; row.append(text);
      addText(text, 'div', task.name, 'name');
      const due = task.next_due_date ? new Date(task.next_due_date) : null;
      addText(text, 'div', due && !isNaN(due) ? due.toLocaleString(this._hass.locale?.language || undefined, {dateStyle: 'medium', timeStyle: 'short'}) : 'No due date', 'due');
      for (const [label, complete] of [['Complete', true], [`Postpone ${this._config.postpone_days}d`, false]]) {
        const button = addText(row, 'button', label); button.type = 'button'; button.disabled = this._pending.has(task.task_id);
        button.setAttribute('aria-label', `${label}: ${task.name}`); button.addEventListener('click', () => this.act(task, complete));
      }
    }
  }
}
class DonetickUserTodoEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({mode: 'open'}); }
  setConfig(config) { this._config = {...config}; this.render(); }
  set hass(hass) { this._hass = hass; this.render(); }
  change(key, value) {
    this._config = {...this._config, [key]: value};
    if (key === 'entity') this._config.user_id = this._hass.states[value]?.attributes.circle_members?.[0]?.user_id;
    this.dispatchEvent(new CustomEvent('config-changed', {detail: {config: this._config}, bubbles: true, composed: true})); this.render();
  }
  render() {
    if (!this._hass || !this._config) return;
    this.shadowRoot.innerHTML = '<style>label{display:block;margin:14px 0;color:var(--primary-text-color)}select,input{display:block;box-sizing:border-box;width:100%;margin-top:6px;padding:10px;background:var(--card-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color);border-radius:6px;font:inherit}</style>';
    const field = (label, key, options, numeric=false) => {
      const wrapper = document.createElement('label'); wrapper.append(document.createTextNode(label));
      const input = document.createElement(options ? 'select' : 'input');
      if (options) { for (const [value, text] of options) { const option = document.createElement('option'); option.value = value; option.textContent = text; input.append(option); } }
      else input.type = numeric ? 'number' : 'text';
      if (numeric) { input.min = '1'; input.max = '365'; }
      input.value = this._config[key] ?? (key === 'postpone_days' ? 1 : '');
      input.addEventListener('change', () => this.change(key, numeric ? Number(input.value) : input.value));
      wrapper.append(input); this.shadowRoot.append(wrapper);
    };
    field('Donetick list', 'entity', [['', 'Select a list'], ...Object.entries(this._hass.states).filter(([id,s]) => id.startsWith('todo.') && s.attributes.circle_members).map(([id,s]) => [id,s.attributes.friendly_name || id])]);
    const members = this._hass.states[this._config.entity]?.attributes.circle_members || [];
    field('Assigned user', 'user_id', [['', 'Select a user'], ...members.map(m => [m.user_id, m.display_name || m.username])], true);
    field('Title (optional)', 'title'); field('Days to postpone', 'postpone_days', null, true);
  }
}
customElements.define('donetick-user-todo-card', DonetickUserTodoCard);
customElements.define('donetick-user-todo-editor', DonetickUserTodoEditor);
window.customCards = window.customCards || [];
window.customCards.push({type: 'donetick-user-todo-card', name: 'Donetick User Tasks', description: 'Tasks for one user with Complete and Postpone controls'});
