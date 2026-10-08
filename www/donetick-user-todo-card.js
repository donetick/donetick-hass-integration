export function userTasks(state, userId) {
  return (state?.attributes?.tasks || []).filter(task => task.assigned_to === Number(userId));
}
export function actionData(state, task) {
  const data = {task_id: task.task_id, config_entry_id: state.attributes.config_entry_id};
  return data;
}
class DonetickUserTodoCard extends HTMLElement {
  static getConfigElement() { return document.createElement('donetick-user-todo-editor'); }
  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find(id => id.startsWith('todo.') && hass.states[id].attributes.circle_members);
    return {entity, user_id: hass.states[entity]?.attributes.circle_members?.[0]?.user_id};
  }
  constructor() { super(); this.attachShadow({mode: 'open'}); this._pending = new Map(); }
  setConfig(config) {
    if (!config.entity?.startsWith('todo.')) throw new Error('Choose a Donetick todo list');
    if (!Number.isInteger(Number(config.user_id)) || Number(config.user_id) < 1) throw new Error('Choose a Donetick user');
    this._config = {button_style: 'text', button_size: 'compact', button_shape: 'rounded',
      button_content: 'icon', complete_control: 'checkbox', ...config, user_id: Number(config.user_id)};
    this.render();
  }
  set hass(hass) { this._hass = hass; this.render(); }
  getCardSize() { return 2 + userTasks(this._hass?.states[this._config?.entity], this._config?.user_id).length; }
  async act(task, complete) {
    if (this._pending.has(task.task_id)) return;
    const state = this._hass.states[this._config.entity];
    this._pending.set(task.task_id, complete); this._error = ''; this.render();
    try {
      await this._hass.callService('donetick', complete ? 'complete_assigned_task' : 'postpone_task',
        actionData(state, task));
    } catch (err) { this._error = err.message || String(err); }
    finally { this._pending.delete(task.task_id); this.render(); }
  }
  render() {
    if (!this._config || !this._hass) return;
    const state = this._hass.states[this._config.entity];
    const member = state?.attributes.circle_members?.find(m => m.user_id === this._config.user_id);
    this.shadowRoot.innerHTML = `<style>
      ha-card { padding: 16px; } h2 { margin: 0 0 12px; font-size: 20px; font-weight: 500; }
      .row { display: flex; align-items: center; gap: 16px; padding: 10px 0; }
      .task { flex: 1; min-width: 0; } .name { overflow-wrap: anywhere; } .due { color: var(--secondary-text-color); font-size: 12px; margin-top: 4px; }
      button { cursor: pointer; border: 1px solid var(--divider-color); border-radius: 8px; padding: 9px 11px; background: var(--card-background-color); color: var(--primary-color); font: inherit; font-size: 13px; }
      button:disabled, input:disabled { opacity: .5; cursor: default; }
      input[type="checkbox"] { flex-shrink:0; width:18px; height:18px; margin:0 4px 0 0; accent-color:var(--primary-color); cursor:pointer; } button:focus-visible { outline: 2px solid var(--primary-color); }
      button { display:inline-flex; align-items:center; gap:6px; } ha-icon { --mdc-icon-size:20px; }
      [data-style="text"] button { border-color:transparent; background:transparent; }
      [data-style="filled"] button { color:var(--text-primary-color); background:var(--primary-color); border-color:transparent; }
      [data-size="compact"] button { padding:5px 8px; font-size:12px; } [data-size="large"] button { padding:12px 16px; font-size:15px; }
      [data-shape="pill"] button { border-radius:24px; } [data-shape="square"] button { border-radius:0; }
      .error { color: var(--error-color); } .empty { color: var(--secondary-text-color); }
      @media(max-width: 420px) { ha-card { padding: 12px; } .row { gap: 12px; } }
    </style><ha-card></ha-card>`;
    const card = this.shadowRoot.querySelector('ha-card');
    card.dataset.style = this._config.button_style;
    card.dataset.size = this._config.button_size;
    card.dataset.shape = this._config.button_shape;
    const addText = (parent, tag, text, cls) => { const el = document.createElement(tag); el.textContent = text; if(cls) el.className = cls; parent.append(el); return el; };
    addText(card, 'h2', this._config.title || `${member?.display_name || 'User ' + this._config.user_id} — Tasks`);
    if (this._error) addText(card, 'p', this._error, 'error');
    if (!state || ['unavailable', 'unknown'].includes(state.state)) { addText(card, 'p', 'Donetick list unavailable', 'empty'); return; }
    const tasks = userTasks(state, this._config.user_id);
    if (!tasks.length) addText(card, 'p', 'No tasks for this user', 'empty');
    for (const task of tasks) {
      const row = document.createElement('div'); row.className = 'row'; card.append(row);
      if (this._config.complete_control === 'checkbox') {
        const checkbox = document.createElement('input'); checkbox.type = 'checkbox';
        checkbox.disabled = this._pending.has(task.task_id); checkbox.checked = this._pending.get(task.task_id) === true;
        checkbox.setAttribute('aria-label', `Complete: ${task.name}`);
        checkbox.addEventListener('change', () => this.act(task, true)); row.append(checkbox);
      }
      const text = document.createElement('div'); text.className = 'task'; row.append(text);
      addText(text, 'div', task.name, 'name');
      const due = task.next_due_date ? new Date(task.next_due_date) : null;
      addText(text, 'div', due && !isNaN(due) ? due.toLocaleString(this._hass.locale?.language || undefined, {dateStyle: 'medium', timeStyle: 'short'}) : 'No due date', 'due');
      for (const [label, complete] of [[this._config.complete_label || 'Complete', true], [this._config.postpone_label || 'Postpone', false]]) {
        if (complete && this._config.complete_control === 'checkbox') continue;
        const button = document.createElement('button'); row.append(button); button.type = 'button';
        button.disabled = this._pending.has(task.task_id) || (!complete && !task.can_postpone);
        if (!complete && !task.can_postpone) button.title = 'This task has no next scheduled occurrence';
        if (this._config.button_content !== 'label') {
          const icon = document.createElement('ha-icon'); icon.setAttribute('icon', this._config[complete ? 'complete_icon' : 'postpone_icon'] || (complete ? 'mdi:check' : 'mdi:calendar-arrow-right'));
          button.append(icon);
        }
        if (this._config.button_content !== 'icon') button.append(document.createTextNode(label));
        const color = this._config[complete ? 'complete_color' : 'postpone_color'];
        if (color) button.style.setProperty(this._config.button_style === 'filled' ? 'background-color' : 'color', color);
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
      input.value = this._config[key] ?? ({complete_control:'checkbox',button_style:'text',button_size:'compact',button_shape:'rounded',button_content:'icon'}[key] || '');
      input.addEventListener('change', () => this.change(key, numeric ? Number(input.value) : input.value));
      wrapper.append(input); this.shadowRoot.append(wrapper);
    };
    field('Donetick list', 'entity', [['', 'Select a list'], ...Object.entries(this._hass.states).filter(([id,s]) => id.startsWith('todo.') && s.attributes.circle_members).map(([id,s]) => [id,s.attributes.friendly_name || id])]);
    const members = this._hass.states[this._config.entity]?.attributes.circle_members || [];
    field('Assigned user', 'user_id', [['', 'Select a user'], ...members.map(m => [m.user_id, m.display_name || m.username])], true);
    field('Title (optional)', 'title');
    field('Complete control', 'complete_control', [['checkbox','Checkbox (todo style)'],['button','Button']]);
    field('Button style', 'button_style', [['outlined','Outlined'],['text','Text'],['filled','Filled']]);
    field('Button size', 'button_size', [['normal','Normal'],['compact','Compact'],['large','Large']]);
    field('Button shape', 'button_shape', [['rounded','Rounded'],['pill','Pill'],['square','Square']]);
    field('Button content', 'button_content', [['icon_and_label','Icon and label'],['label','Label only'],['icon','Icon only']]);
    for (const [label,key] of [['Complete label','complete_label'],['Postpone label','postpone_label'],['Complete icon (mdi:...)','complete_icon'],['Postpone icon (mdi:...)','postpone_icon'],['Complete color (optional)','complete_color'],['Postpone color (optional)','postpone_color']]) field(label,key);
  }
}
customElements.define('donetick-user-todo-card', DonetickUserTodoCard);
customElements.define('donetick-user-todo-editor', DonetickUserTodoEditor);
window.customCards = window.customCards || [];
window.customCards.push({type: 'donetick-user-todo-card', name: 'Donetick User Tasks', description: 'Tasks for one user with Complete and Postpone controls'});
