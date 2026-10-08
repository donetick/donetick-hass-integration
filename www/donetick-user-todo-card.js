export function userTasks(state, userId) {
  return (state?.attributes?.tasks || []).filter(task => task.assigned_to === Number(userId))
    .sort((a, b) => (Date.parse(a.next_due_date) || Infinity) - (Date.parse(b.next_due_date) || Infinity) || a.task_id - b.task_id);
}
export function quickDate(choice, now = new Date()) {
  const date = new Date(now);
  date.setHours(12, 0, 0, 0);
  date.setDate(date.getDate() + (choice === 'tomorrow' ? 1 : choice === 'weekend' ? (6 - date.getDay() + 7) % 7 || 7 : (8 - date.getDay()) % 7 || 7));
  return localDateTime(date).slice(0, 10);
}
export function dueText(value, language, now = new Date()) {
  const date = value ? new Date(value) : null;
  if (!date || isNaN(date)) return 'No due date';
  const day = value => Date.UTC(value.getFullYear(), value.getMonth(), value.getDate());
  const days = Math.round((day(date) - day(now)) / 86400000);
  if (days < 0) return `Overdue · ${-days} day${days === -1 ? '' : 's'}`;
  if (days === 0) return 'Today';
  if (days === 1) return 'Tomorrow';
  return date.toLocaleDateString(language, {weekday: 'short', month: 'short', day: 'numeric'});
}
export function actionData(state, task) {
  const data = {task_id: task.task_id, config_entry_id: state.attributes.config_entry_id};
  return data;
}
export function localDateTime(value) {
  const date = value ? new Date(value) : new Date();
  if (isNaN(date)) return '';
  const pad = value => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}
class DonetickUserTodoCard extends HTMLElement {
  static getConfigElement() { return document.createElement('donetick-user-todo-editor'); }
  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find(id => id.startsWith('todo.') && hass.states[id].attributes.circle_members);
    return {entity, user_id: hass.states[entity]?.attributes.circle_members?.[0]?.user_id};
  }
  constructor() {
    super(); this.attachShadow({mode: 'open'}); this._pending = new Map(); this._completed = new Map();
    this._outside = event => { if (this._panel && !event.composedPath().includes(this) && !this._pending.has(this._panel.taskId)) this.closePanel(); };
  }
  connectedCallback() { document.addEventListener('pointerdown', this._outside); }
  disconnectedCallback() { document.removeEventListener('pointerdown', this._outside); }
  setConfig(config) {
    if (!config.entity?.startsWith('todo.')) throw new Error('Choose a Donetick todo list');
    if (!Number.isInteger(Number(config.user_id)) || Number(config.user_id) < 1) throw new Error('Choose a Donetick user');
    this._config = {button_style: 'text', button_size: 'compact', button_shape: 'rounded',
      button_content: 'icon', complete_control: 'checkbox', ...config, user_id: Number(config.user_id)};
    this.render();
  }
  set hass(hass) { this._hass = hass; this.render(); }
  getCardSize() { return 2 + userTasks(this._hass?.states[this._config?.entity], this._config?.user_id).length; }
  async act(task, complete, dueDate) {
    if (this._pending.has(task.task_id)) return;
    const state = this._hass.states[this._config.entity];
    this._pending.set(task.task_id, complete); this._error = ''; this._message = ''; this.render();
    try {
      const data = actionData(state, task);
      if (dueDate) data.due_date = dueDate;
      await this._hass.callService('donetick', dueDate ? 'update_task' : complete ? 'complete_assigned_task' : 'postpone_task', data);
      this._panel = null;
      if (complete) {
        this._completed.set(task.task_id, task);
        setTimeout(() => { this._completed.delete(task.task_id); this.render(); }, 1000);
      }
      this._message = complete ? `${task.name} completed` : dueDate ? `Moved to ${new Date(dueDate).toLocaleDateString(this._hass.locale?.language, {weekday:'short', month:'short', day:'numeric'})}` : 'Occurrence skipped; schedule refreshed';
      clearTimeout(this._messageTimer);
      this._messageTimer = setTimeout(() => { this._message = ''; this.render(); }, 4000);
    } catch (err) { this._error = err.message || String(err); }
    finally { this._pending.delete(task.task_id); this.render(); }
  }
  closePanel() {
    const taskId = this._panel?.taskId;
    const kind = this._panel?.kind;
    this._panel = null; this._error = ''; this.render();
    this.shadowRoot.querySelector(`[data-action="${kind}"][data-task-id="${taskId}"]`)?.focus();
  }
  togglePanel(task, kind) {
    if (this._panel?.taskId === task.task_id && this._panel.kind === kind) { this.closePanel(); return; }
    const value = localDateTime(task.next_due_date);
    this._panel = {taskId: task.task_id, kind, date: value.slice(0, 10), time: task.next_due_date ? value.slice(11) : '09:00:00', showDate:false, showTime:false};
    this._error = '';
    this.render();
    this.shadowRoot.querySelector('.action-panel button')?.focus();
  }
  render() {
    if (!this._config || !this._hass) return;
    const state = this._hass.states[this._config.entity];
    const member = state?.attributes.circle_members?.find(m => m.user_id === this._config.user_id);
    const focusedField = this.shadowRoot.activeElement?.dataset.field;
    this.shadowRoot.innerHTML = `<style>
      ha-card { padding: 12px; } h2 { margin: 0 0 8px; font-size: 20px; font-weight: 500; }
      .row { position:relative; display: flex; align-items: center; gap: 8px; padding: 2px 0; }
      .completed .name { text-decoration:line-through; color:var(--secondary-text-color); }
      .actions { display:flex; align-items:center; gap:4px; flex-shrink:0; }
      .task { flex: 1; min-width: 0; } .name { overflow-wrap: anywhere; } .due { color: var(--secondary-text-color); font-size: 12px; margin-top: 2px; }
      button { cursor: pointer; border: 1px solid var(--divider-color); border-radius: 8px; padding: 9px 11px; background: var(--card-background-color); color: var(--primary-color); font: inherit; font-size: 13px; }
      button:disabled, input:disabled { opacity: .5; cursor: default; }
      .complete-checkbox { width:44px; height:44px; display:flex; align-items:center; justify-content:center; flex-shrink:0; cursor:pointer; }
      input[type="checkbox"] { width:18px; height:18px; margin:0; accent-color:var(--primary-color); cursor:pointer; } button:focus-visible { outline: 2px solid var(--primary-color); }
      button { display:inline-flex; justify-content:center; align-items:center; gap:6px; box-sizing:border-box; min-width:44px; min-height:44px; } ha-icon { --mdc-icon-size:20px; }
      [data-style="text"] button { border-color:transparent; background:transparent; }
      [data-style="filled"] button { color:var(--text-primary-color); background:var(--primary-color); border-color:transparent; }
      [data-size="compact"] button { padding:5px 8px; font-size:12px; } [data-size="normal"] button { min-width:48px; min-height:48px; } [data-size="large"] button { min-width:52px; min-height:52px; padding:12px 16px; font-size:15px; }
      [data-shape="pill"] button { border-radius:24px; } [data-shape="square"] button { border-radius:0; }
      .error { color: var(--error-color); } .empty { color: var(--secondary-text-color); }
      .action-panel { position:absolute; right:0; top:100%; width:min(320px,calc(100vw - 48px)); max-height:calc(100dvh - 24px); overflow:auto; box-sizing:border-box; z-index:10; padding:16px; background:var(--card-background-color); color:var(--primary-text-color); border:1px solid var(--divider-color); border-radius:12px; box-shadow:0 4px 16px #0004; }
      .action-panel h3 { margin:0 0 4px; font-size:16px; } .action-panel p { margin:4px 0 12px; font-size:13px; }
      .quick-dates, .dialog-footer { display:flex; flex-wrap:wrap; gap:4px; } .dialog-footer { justify-content:flex-end; margin-top:12px; }
      .action-panel label { display:block; font-size:13px; margin-top:8px; } .action-panel input { box-sizing:border-box; width:100%; min-height:44px; margin-top:4px; padding:8px; background:var(--card-background-color); color:var(--primary-text-color); border:1px solid var(--divider-color); border-radius:6px; font:inherit; }
      button[aria-pressed="true"], button[aria-expanded="true"] { background:var(--secondary-background-color); }
    </style><ha-card></ha-card>`;
    const card = this.shadowRoot.querySelector('ha-card');
    card.dataset.style = this._config.button_style;
    card.dataset.size = this._config.button_size;
    card.dataset.shape = this._config.button_shape;
    const addText = (parent, tag, text, cls) => { const el = document.createElement(tag); el.textContent = text; if(cls) el.className = cls; parent.append(el); return el; };
    addText(card, 'h2', this._config.title || `${member?.display_name || 'User ' + this._config.user_id} — Tasks`);
    if (this._error && !this._panel) addText(card, 'p', this._error, 'error');
    if (this._message) { const status = addText(card, 'div', this._message, 'due'); status.setAttribute('role','status'); }
    if (!state || ['unavailable', 'unknown'].includes(state.state)) { addText(card, 'p', 'Donetick list unavailable', 'empty'); return; }
    const tasks = userTasks(state, this._config.user_id);
    for (const task of this._completed.values()) if (!tasks.some(item => item.task_id === task.task_id)) tasks.push(task);
    if (!tasks.length) addText(card, 'p', 'No tasks for this user', 'empty');
    for (const task of tasks) {
      const row = document.createElement('div'); row.className = 'row'; card.append(row);
      const completed = this._completed.has(task.task_id);
      if (completed) row.classList.add('completed');
      if (this._config.complete_control === 'checkbox') {
        const target = document.createElement('label'); target.className = 'complete-checkbox'; row.append(target);
        const checkbox = document.createElement('input'); checkbox.type = 'checkbox';
        checkbox.disabled = this._pending.has(task.task_id) || completed; checkbox.checked = this._pending.get(task.task_id) === true || completed;
        checkbox.setAttribute('aria-label', `Complete: ${task.name}`);
        checkbox.title = `Complete: ${task.name}`;
        checkbox.addEventListener('change', () => this.act(task, true)); target.append(checkbox);
      }
      const text = document.createElement('div'); text.className = 'task'; row.append(text);
      addText(text, 'div', task.name, 'name');
      const due = task.next_due_date ? new Date(task.next_due_date) : null;
      const dueLabel = addText(text, 'div', dueText(task.next_due_date, this._hass.locale?.language), 'due');
      if (due && !isNaN(due)) dueLabel.title = due.toLocaleString(this._hass.locale?.language, {dateStyle:'full',timeStyle:'short'});
      const actions = document.createElement('div'); actions.className = 'actions'; row.append(actions);
      for (const [label, complete] of [[this._config.complete_label || 'Complete', true], [this._config.postpone_label || 'Skip occurrence', false]]) {
        if (complete && this._config.complete_control === 'checkbox') continue;
        if (!complete && !task.can_postpone) continue;
        const button = document.createElement('button'); actions.append(button); button.type = 'button';
        button.disabled = this._pending.has(task.task_id) || completed;
        if (this._config.button_content !== 'label') {
          const icon = document.createElement('ha-icon'); icon.setAttribute('icon', this._config[complete ? 'complete_icon' : 'postpone_icon'] || (complete ? 'mdi:check' : 'mdi:calendar-arrow-right'));
          button.append(icon);
        }
        if (this._config.button_content !== 'icon') button.append(document.createTextNode(label));
        const color = this._config[complete ? 'complete_color' : 'postpone_color'];
        if (color) button.style.setProperty(this._config.button_style === 'filled' ? 'background-color' : 'color', color);
        button.title = `${label}: ${task.name}`;
        button.setAttribute('aria-label', button.title);
        if (!complete) { button.dataset.action = 'skip'; button.dataset.taskId = task.task_id; button.setAttribute('aria-expanded', String(this._panel?.taskId === task.task_id && this._panel.kind === 'skip')); }
        button.addEventListener('click', () => complete ? this.act(task, true) : this.togglePanel(task, 'skip'));
      }
      const changeDate = document.createElement('button'); changeDate.type = 'button';
      changeDate.className = 'date-action';
      const dateLabel = this._config.due_date_label || 'Change due date';
      if (this._config.button_content !== 'label') {
        const icon = document.createElement('ha-icon'); icon.setAttribute('icon', this._config.due_date_icon || 'mdi:calendar-edit'); changeDate.append(icon);
      }
      if (this._config.button_content !== 'icon') changeDate.append(document.createTextNode(dateLabel));
      if (this._config.due_date_color) changeDate.style.setProperty(this._config.button_style === 'filled' ? 'background-color' : 'color', this._config.due_date_color);
      changeDate.disabled = this._pending.has(task.task_id) || completed;
      changeDate.title = `${dateLabel}: ${task.name}`; changeDate.setAttribute('aria-label', changeDate.title);
      changeDate.dataset.action = 'date'; changeDate.dataset.taskId = task.task_id;
      changeDate.setAttribute('aria-expanded', String(this._panel?.taskId === task.task_id && this._panel.kind === 'date'));
      changeDate.addEventListener('click', () => this.togglePanel(task, 'date')); actions.append(changeDate);
      if (this._panel?.taskId === task.task_id) this.renderPanel(row, task, addText);
    }
    const dialog = this.shadowRoot.querySelector('.action-panel');
    if (dialog && this.isConnected && typeof dialog.showPopover === 'function') {
      // The browser's top layer prevents cards and dashboard containers from clipping the panel.
      dialog.setAttribute('popover','manual'); dialog.style.position='fixed'; dialog.style.margin='0';
      dialog.style.right='auto'; dialog.style.bottom='auto'; dialog.showPopover();
      const row = dialog.parentElement.getBoundingClientRect();
      const bounds = dialog.getBoundingClientRect();
      dialog.style.left = `${Math.max(12, Math.min(row.right - bounds.width, window.innerWidth - bounds.width - 12))}px`;
      dialog.style.top = `${Math.max(12, row.bottom + bounds.height <= window.innerHeight - 12 ? row.bottom : Math.min(row.top - bounds.height, window.innerHeight - bounds.height - 12))}px`;
    }
    if (focusedField) this.shadowRoot.querySelector(`[data-field="${focusedField}"]`)?.focus();
  }
  renderPanel(row, task, addText) {
    const panel = this._panel;
    const busy = this._pending.has(task.task_id);
    const form = document.createElement('form'); form.className = 'action-panel'; row.append(form);
    form.setAttribute('role','dialog'); form.setAttribute('aria-label', `${panel.kind === 'date' ? 'Change due date' : 'Skip occurrence'}: ${task.name}`);
    addText(form, 'h3', panel.kind === 'date' ? 'Change due date' : 'Skip occurrence');
    addText(form, 'p', task.name);
    if (this._error) { const error=addText(form,'p',this._error,'error'); error.setAttribute('role','alert'); }
    const button = (parent, label, handler) => { const node = addText(parent,'button',label); node.type='button'; node.dataset.field=`control-${label}`; node.disabled=busy; node.addEventListener('click',handler); return node; };
    if (panel.kind === 'date') {
      addText(form,'p', `Current: ${task.next_due_date ? new Date(task.next_due_date).toLocaleDateString(this._hass.locale?.language,{dateStyle:'medium'}) : 'No due date'}`, 'due');
      const quick = document.createElement('div'); quick.className='quick-dates'; form.append(quick);
      for (const [label, choice] of [['Tomorrow','tomorrow'],['This weekend','weekend'],['Next week','week']]) {
        const node = button(quick,label, () => { panel.date=quickDate(choice); panel.choice=choice; this.render(); });
        node.setAttribute('aria-pressed',String(panel.choice === choice));
      }
      const choose = button(form,'Choose a date…', () => { panel.showDate=!panel.showDate; this.render(); this.shadowRoot.querySelector('input[type=date]')?.focus(); });
      choose.setAttribute('aria-expanded',String(panel.showDate));
      if (panel.showDate) {
        const label=addText(form,'label','Date'); const input=document.createElement('input'); input.type='date'; input.required=true; input.value=panel.date; input.disabled=busy; input.dataset.field='date'; label.append(input);
        input.addEventListener('input', () => { panel.date=input.value; panel.choice=null; });
      }
      const selected = panel.date ? new Date(`${panel.date}T12:00:00`) : null;
      addText(form,'p', selected && !isNaN(selected) ? `Selected: ${selected.toLocaleDateString(this._hass.locale?.language,{weekday:'short',month:'short',day:'numeric'})}` : 'Choose a date', 'due');
      const time = button(form,panel.showTime ? 'Hide time' : 'Set time', () => { panel.showTime=!panel.showTime; this.render(); });
      time.setAttribute('aria-expanded',String(panel.showTime));
      if (panel.showTime) {
        const label=addText(form,'label',`Time (${Intl.DateTimeFormat().resolvedOptions().timeZone})`); const input=document.createElement('input'); input.type='time'; input.required=true; input.step='1'; input.value=panel.time; input.disabled=busy; input.dataset.field='time'; label.append(input);
        input.addEventListener('input', () => { panel.time=input.value; });
      }
    } else addText(form,'p','Skip this occurrence and let Donetick calculate the next date.');
    const footer=document.createElement('div'); footer.className='dialog-footer'; form.append(footer);
    button(footer,'Cancel', () => this.closePanel());
    const save=addText(footer,'button',panel.kind === 'date' ? 'Save' : 'Skip'); save.type='submit'; save.disabled=busy;
    form.addEventListener('keydown',event => { if (event.key === 'Escape' && !busy) { event.stopPropagation(); this.closePanel(); } });
    form.addEventListener('submit',event => {
      event.preventDefault(); if (busy || !form.reportValidity()) return;
      if (panel.kind === 'skip') { this.act(task,false); return; }
      const value=`${panel.date}T${panel.time}`; const date=new Date(value);
      if (isNaN(date) || localDateTime(date) !== (value.length === 16 ? value+':00' : value)) { this._error='Choose a valid date and time'; this.render(); return; }
      this.act(task,false,date.toISOString());
    });
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
    for (const [label,key] of [['Complete label','complete_label'],['Postpone label','postpone_label'],['Due date label','due_date_label'],['Complete icon (mdi:...)','complete_icon'],['Postpone icon (mdi:...)','postpone_icon'],['Due date icon (mdi:...)','due_date_icon'],['Complete color (optional)','complete_color'],['Postpone color (optional)','postpone_color'],['Due date color (optional)','due_date_color']]) field(label,key);
  }
}
customElements.define('donetick-user-todo-card', DonetickUserTodoCard);
customElements.define('donetick-user-todo-editor', DonetickUserTodoEditor);
window.customCards = window.customCards || [];
window.customCards.push({type: 'donetick-user-todo-card', name: 'Donetick User Tasks', description: 'Tasks for one user with Complete and Postpone controls'});
