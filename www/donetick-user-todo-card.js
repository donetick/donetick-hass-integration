export function userTasks(state, userId, displayFilter = 'all', now = new Date(), upcomingDays = 7) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const upcomingEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate() + Number(upcomingDays) + 1);
  return (state?.attributes?.tasks || []).filter(task => userId === 'all' || task.assigned_to === Number(userId))
    .filter(task => {
      if (displayFilter === 'all') return true;
      if (displayFilter === 'overdue') return isOverdue(task.next_due_date, now);
      if (!task.next_due_date) return false;
      const value = task.next_due_date;
      const due = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value);
      return displayFilter === 'today' ? due >= today && due < tomorrow : displayFilter === 'upcoming' && due >= today && (Number(upcomingDays) === 0 || due < upcomingEnd);
    })
    .sort((a, b) => (Date.parse(a.next_due_date) || Infinity) - (Date.parse(b.next_due_date) || Infinity) || a.task_id - b.task_id);
}
export function dueText(value, language, now = new Date(), timeFormat) {
  const dateOnly = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
  const date = value ? new Date(dateOnly ? `${value}T12:00:00` : value) : null;
  if (!date || isNaN(date)) return 'No due date';
  const day = value => Date.UTC(value.getFullYear(), value.getMonth(), value.getDate());
  const days = Math.round((day(date) - day(now)) / 86400000);
  const label = days < 0 ? `Overdue · ${-days} day${days === -1 ? '' : 's'}` : days === 0 ? 'Today' : days === 1 ? 'Tomorrow'
    : date.toLocaleDateString(language, {weekday: 'short', month: 'short', day: 'numeric'});
  if (!hasDueTime(value)) return label;
  const time = date.toLocaleTimeString(language, {hour:'2-digit', minute:'2-digit', hour12:timeFormat === '12' ? true : timeFormat === '24' ? false : undefined});
  return `${label} · ${time}`;
}
export function hasDueTime(value) {
  if (!value || /^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(value);
  // Donetick date-only deadlines can arrive as a local end-of-day timestamp.
  return !isNaN(date) && !(date.getHours() === 23 && date.getMinutes() === 59);
}
export function isOverdue(value, now = new Date()) {
  if (!value) return false;
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  const due = new Date(dateOnly ? `${value}T00:00:00` : value);
  const cutoff = dateOnly ? new Date(now.getFullYear(), now.getMonth(), now.getDate()) : now;
  return !isNaN(due) && due < cutoff;
}
export function emptyMessage(config, userName) {
  let filter = {all:'All tasks',overdue:'Overdue',today:'Today',upcoming:'Upcoming'}[config.display_filter || 'all'];
  if (config.display_filter === 'upcoming') {
    const days = Number(config.upcoming_days ?? 7);
    filter += days === 0 ? ' (no day limit)' : ` (${days} day${days === 1 ? '' : 's'} ahead)`;
  }
  return `${config.user_id === 'all' ? 'No tasks for all users' : `No tasks for ${userName}`} · Filter: ${filter}`;
}
export function actionData(state, task) {
  const data = {task_id: task.task_id, config_entry_id: state.attributes.config_entry_id};
  return data;
}
export function assignableMembers(state, task) {
  return (state?.attributes.circle_members || []).filter(member => task.assignee_ids?.includes(member.user_id));
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
    if (config.user_id !== 'all' && (!Number.isInteger(Number(config.user_id)) || Number(config.user_id) < 1)) throw new Error('Choose a Donetick user');
    if (config.display_filter && !['all','overdue','today','upcoming'].includes(config.display_filter)) throw new Error('Choose a valid display filter');
    if (config.upcoming_days !== undefined && (!Number.isInteger(Number(config.upcoming_days)) || Number(config.upcoming_days) < 0 || Number(config.upcoming_days) > 365)) throw new Error('Days ahead must be a whole number from 0 to 365');
    this._config = {display_filter:'all', button_style: 'text', button_size: 'compact', button_shape: 'rounded',
      button_content: 'icon', complete_control: 'checkbox', show_assignee:true, show_reassign:true, ...config, user_id: config.user_id === 'all' ? 'all' : Number(config.user_id), upcoming_days:Number(config.upcoming_days ?? 7)};
    this.render();
  }
  set hass(hass) { this._hass = hass; this.render(); }
  getCardSize() { return 2 + userTasks(this._hass?.states[this._config?.entity], this._config?.user_id, this._config?.display_filter, new Date(), this._config?.upcoming_days).length; }
  async act(task, complete, dueDate, assignedTo) {
    if (this._pending.has(task.task_id)) return;
    const state = this._hass.states[this._config.entity];
    this._pending.set(task.task_id, complete); this._error = ''; this.render();
    try {
      const data = actionData(state, task);
      if (dueDate) data.due_date = dueDate;
      if (assignedTo !== undefined) data.assigned_to = assignedTo;
      await this._hass.callService('donetick', dueDate || assignedTo !== undefined ? 'update_task' : complete ? 'complete_assigned_task' : 'postpone_task', data);
      this._panel = null;
      if (complete) {
        this._completed.set(task.task_id, task);
        setTimeout(() => { this._completed.delete(task.task_id); this.render(); }, 1000);
      }
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
    this._panel = {taskId: task.task_id, kind, date: value.slice(0, 10), time: task.next_due_date ? value.slice(11) : '09:00:00', showTime:false, assignedTo:task.assigned_to};
    this._error = '';
    this.render();
    this.shadowRoot.querySelector('.action-panel input, .action-panel select, .action-panel button')?.focus();
  }
  render() {
    if (!this._config || !this._hass) return;
    const state = this._hass.states[this._config.entity];
    const member = state?.attributes.circle_members?.find(m => m.user_id === this._config.user_id);
    const focusedField = this.shadowRoot.activeElement?.dataset.field;
    this.shadowRoot.activeElement?.blur();
    this.shadowRoot.innerHTML = `<style>
      ha-card { padding: 12px; } h2 { margin: 0 0 8px; font-size: 20px; font-weight: 500; }
      .row { position:relative; display: flex; align-items: center; gap: 8px; padding: 2px 0; }
      .completed .name { text-decoration:line-through; color:var(--secondary-text-color); }
      .actions { display:flex; align-items:center; gap:4px; flex-shrink:0; }
      .task { flex: 1; min-width: 0; } .name { overflow-wrap: anywhere; } .due { color: var(--secondary-text-color); font-size: 12px; margin-top: 2px; }
      .due.overdue { color:var(--warning-color); }
      .due { display:flex; align-items:center; gap:4px; }
      .due .recurring { --mdc-icon-size:14px; flex-shrink:0; }
      .due .assignee { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
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
      .action-panel { display:flex; flex-wrap:wrap; align-items:center; gap:4px; margin:2px 0 6px; }
      .action-panel input, .action-panel select { flex:1; min-width:125px; width:0; box-sizing:border-box; height:44px; padding:8px; color-scheme:var(--ha-color-scheme,light); background:var(--secondary-background-color); color:var(--primary-text-color); border:0; border-bottom:1px solid var(--secondary-text-color); border-radius:4px 4px 0 0; font:inherit; font-size:14px; }
      .action-panel button { flex-shrink:0; border-color:transparent; background:transparent; color:var(--primary-color); }
      .action-panel .error { flex-basis:100%; margin:0; font-size:12px; } .skip-prompt { flex:1; font-size:13px; color:var(--secondary-text-color); }
      button[aria-pressed="true"], button[aria-expanded="true"] { background:var(--secondary-background-color); }
    </style><ha-card></ha-card>`;
    const card = this.shadowRoot.querySelector('ha-card');
    card.dataset.style = this._config.button_style;
    card.dataset.size = this._config.button_size;
    card.dataset.shape = this._config.button_shape;
    const addText = (parent, tag, text, cls) => { const el = document.createElement(tag); el.textContent = text; if(cls) el.className = cls; parent.append(el); return el; };
    addText(card, 'h2', this._config.title || (this._config.user_id === 'all' ? 'All users — Tasks' : `${member?.display_name || 'User ' + this._config.user_id} — Tasks`));
    if (this._error && !this._panel) addText(card, 'p', this._error, 'error');
    if (!state || ['unavailable', 'unknown'].includes(state.state)) { addText(card, 'p', 'Donetick list unavailable', 'empty'); return; }
    const tasks = userTasks(state, this._config.user_id, this._config.display_filter, new Date(), this._config.upcoming_days);
    for (const task of this._completed.values()) if (!tasks.some(item => item.task_id === task.task_id) && userTasks({attributes:{tasks:[task]}}, this._config.user_id, this._config.display_filter, new Date(), this._config.upcoming_days).length) tasks.push(task);
    if (!tasks.length) addText(card, 'p', emptyMessage(this._config, member?.display_name || member?.username || `User ${this._config.user_id}`), 'empty');
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
      const dueLabel = addText(text, 'div', dueText(task.next_due_date, this._hass.locale?.language, new Date(), this._hass.locale?.time_format), 'due');
      if (!completed && isOverdue(task.next_due_date)) dueLabel.classList.add('overdue');
      if (due && !isNaN(due)) dueLabel.title = due.toLocaleString(this._hass.locale?.language, {dateStyle:'full',timeStyle:hasDueTime(task.next_due_date) ? 'short' : undefined});
      if (task.is_recurring ?? task.can_postpone) {
        const recurring = document.createElement('ha-icon'); recurring.className = 'recurring';
        recurring.setAttribute('icon', 'mdi:autorenew'); recurring.title = 'Recurring task';
        recurring.setAttribute('role', 'img'); recurring.setAttribute('aria-label', 'Recurring task');
        dueLabel.prepend(recurring);
      }
      if (this._config.show_assignee && this._config.user_id === 'all' && !state.attributes.donetick_user_id && state.attributes.circle_members?.length > 1) {
        const assignee = state.attributes.circle_members.find(member => member.user_id === task.assigned_to);
        const name = assignee?.display_name || assignee?.username || (task.assigned_to ? `User ${task.assigned_to}` : 'Unassigned');
        const label = addText(dueLabel, 'span', `· ${name}`, 'assignee'); label.title = `Assigned to: ${name}`;
      }
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
        const color = actionColor(this._config[complete ? 'complete_color' : 'postpone_color']);
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
      const dueColor = actionColor(this._config.due_date_color);
      if (dueColor) changeDate.style.setProperty(this._config.button_style === 'filled' ? 'background-color' : 'color', dueColor);
      changeDate.disabled = this._pending.has(task.task_id) || completed;
      changeDate.title = `${dateLabel}: ${task.name}`; changeDate.setAttribute('aria-label', changeDate.title);
      changeDate.dataset.action = 'date'; changeDate.dataset.taskId = task.task_id;
      changeDate.setAttribute('aria-expanded', String(this._panel?.taskId === task.task_id && this._panel.kind === 'date'));
      changeDate.addEventListener('click', () => this.togglePanel(task, 'date')); actions.append(changeDate);
      if (this._config.show_reassign && assignableMembers(state, task).some(member => member.user_id !== task.assigned_to)) {
        const reassign = document.createElement('button'); reassign.type = 'button';
        const label = this._config.reassign_label || 'Reassign';
        if (this._config.button_content !== 'label') {
          const icon = document.createElement('ha-icon'); icon.setAttribute('icon', this._config.reassign_icon || 'mdi:account-switch-outline'); reassign.append(icon);
        }
        if (this._config.button_content !== 'icon') reassign.append(document.createTextNode(label));
        const color = actionColor(this._config.reassign_color);
        if (color) reassign.style.setProperty(this._config.button_style === 'filled' ? 'background-color' : 'color', color);
        reassign.disabled = this._pending.has(task.task_id) || completed;
        reassign.title = `${label}: ${task.name}`; reassign.setAttribute('aria-label', reassign.title);
        reassign.dataset.action = 'assign'; reassign.dataset.taskId = task.task_id;
        reassign.setAttribute('aria-expanded', String(this._panel?.taskId === task.task_id && this._panel.kind === 'assign'));
        reassign.addEventListener('click', () => this.togglePanel(task, 'assign')); actions.append(reassign);
      }
      if (this._panel?.taskId === task.task_id) this.renderPanel(row, task, addText);
    }
    if (focusedField) this.shadowRoot.querySelector(`[data-field="${focusedField}"]`)?.focus();
  }
  renderPanel(row, task, addText) {
    const panel = this._panel;
    const busy = this._pending.has(task.task_id);
    const form = document.createElement('form'); form.className = 'action-panel'; row.after(form);
    form.setAttribute('aria-label', `${panel.kind === 'date' ? 'Change due date' : panel.kind === 'assign' ? 'Reassign' : 'Skip occurrence'}: ${task.name}`);
    const iconButton = (label, icon, handler) => {
      const node=document.createElement('button'); node.type='button'; node.disabled=busy;
      node.title=label; node.setAttribute('aria-label',label); node.dataset.field=`control-${label}`;
      const glyph=document.createElement('ha-icon'); glyph.setAttribute('icon',icon); node.append(glyph);
      if (handler) node.addEventListener('click',handler); form.append(node); return node;
    };
    const field = (type, label, value, handler) => {
      const input=document.createElement('input'); input.type=type; input.required=true;
      input.value=value; input.disabled=busy; input.dataset.field=type;
      input.style.colorScheme=this._hass.themes?.darkMode ? 'dark' : 'light';
      input.setAttribute('aria-label',label); input.title=label;
      input.addEventListener('input',handler); form.append(input); return input;
    };
    if (panel.kind === 'date') {
      field('date','Due date',panel.date,event => { panel.date=event.target.value; });
      if (panel.showTime) {
        const input=field('time',`Time (${Intl.DateTimeFormat().resolvedOptions().timeZone})`,panel.time,event => { panel.time=event.target.value; }); input.step='1';
      }
      const time=iconButton(panel.showTime ? 'Hide time' : 'Set time','mdi:clock-outline', () => { panel.showTime=!panel.showTime; this.render(); });
      time.setAttribute('aria-expanded',String(panel.showTime));
    } else if (panel.kind === 'assign') {
      const select = document.createElement('select'); select.required = true; select.disabled = busy;
      select.dataset.field = 'assignee'; select.setAttribute('aria-label', 'Assigned user');
      const placeholder = document.createElement('option'); placeholder.value = ''; placeholder.textContent = 'Choose a user'; placeholder.disabled = true; select.append(placeholder);
      for (const member of assignableMembers(this._hass.states[this._config.entity], task)) {
        const option = document.createElement('option'); option.value = String(member.user_id); option.textContent = member.display_name || member.username || `User ${member.user_id}`; select.append(option);
      }
      select.value = panel.assignedTo ? String(panel.assignedTo) : '';
      select.addEventListener('change', event => { panel.assignedTo = Number(event.target.value); }); form.append(select);
    } else addText(form,'span','Skip to the next occurrence?', 'skip-prompt');
    const save=iconButton(panel.kind === 'date' ? 'Save due date' : panel.kind === 'assign' ? 'Save assignee' : 'Confirm skip','mdi:check'); save.type='submit';
    iconButton('Cancel','mdi:close', () => this.closePanel());
    if (this._error) { const error=addText(form,'p',this._error,'error'); error.setAttribute('role','alert'); }
    form.addEventListener('keydown',event => { if (event.key === 'Escape' && !busy) { event.stopPropagation(); this.closePanel(); } });
    form.addEventListener('submit',event => {
      event.preventDefault(); if (busy || !form.reportValidity()) return;
      if (panel.kind === 'skip') { this.act(task,false); return; }
      if (panel.kind === 'assign') {
        if (!assignableMembers(this._hass.states[this._config.entity], task).some(member => member.user_id === panel.assignedTo)) { this._error = 'Choose an eligible assignee'; this.render(); return; }
        if (panel.assignedTo === task.assigned_to) { this.closePanel(); return; }
        this.act(task, false, undefined, panel.assignedTo); return;
      }
      const value=`${panel.date}T${panel.time}`; const date=new Date(value);
      if (isNaN(date) || localDateTime(date) !== (value.length === 16 ? value+':00' : value)) { this._error='Choose a valid date and time'; this.render(); return; }
      this.act(task,false,date.toISOString());
    });
  }
}
const EDITOR_DEFAULTS = {
  display_filter:'all', upcoming_days:7, show_assignee:true, show_reassign:true, complete_control:'checkbox', button_style:'text', button_size:'compact',
  button_shape:'rounded', button_content:'icon', complete_label:'Complete', postpone_label:'Skip occurrence',
  due_date_label:'Change due date', complete_icon:'mdi:check', postpone_icon:'mdi:calendar-arrow-right',
  due_date_icon:'mdi:calendar-edit', reassign_label:'Reassign', reassign_icon:'mdi:account-switch-outline', complete_color:'primary', postpone_color:'primary', due_date_color:'primary', reassign_color:'primary'
};
const STYLE_PRESETS = {
  todo:{complete_control:'checkbox',button_style:'text',button_size:'compact',button_shape:'rounded',button_content:'icon'},
  labeled:{complete_control:'checkbox',button_style:'text',button_size:'compact',button_shape:'rounded',button_content:'icon_and_label'},
  outlined:{complete_control:'checkbox',button_style:'outlined',button_size:'normal',button_shape:'rounded',button_content:'icon'},
  filled:{complete_control:'checkbox',button_style:'filled',button_size:'normal',button_shape:'rounded',button_content:'icon'}
};
const ACTION_OVERRIDES = ['complete','postpone','due_date','reassign'].flatMap(action=>['label','icon','color'].map(part=>`${action}_${part}`));
const EDITOR_LABELS = {entity:'Donetick task list',user_id:'Assigned user',display_filter:'Tasks to show',upcoming_days:'Days ahead',title:'Card title (optional)',appearance_preset:'Starting style',appearance:'Appearance',actions:'Action icons and colors',complete_control:'Complete tasks with',button_style:'Action button style',button_size:'Tap target size',button_shape:'Button corners',button_content:'Show on action buttons'};
const EDITOR_HELP = {
  entity:'Choose All Tasks to make tasks for every circle user available.',
  user_id:'Show one user’s tasks or all users. Completion is credited to each task’s current assignee.',
  show_assignee:'Show the assigned name beside the due date. Available when the list can contain multiple users.',
  show_reassign:'Show a user-switch action on each row. Changes are saved only after confirmation.',
  display_filter:'Today and Upcoming include tasks due earlier today. Undated tasks appear only in All tasks.',
  upcoming_days:'Maximum days ahead; 0 removes the limit. The integration’s task window must also include those days.',
  title:'Leave empty to use the selected user’s name.',
  appearance_preset:'Choose a ready-made style. Applying a preset resets custom action icons, labels and colors.',
  complete_control:'Checkbox stays on the left; Button places completion beside the other actions on the right.',
  button_style:'Flat follows HA todo styling. Filled uses the action color as its background.',
  button_size:'Compact: 44 px. Standard: 48 px. Large: 52 px. All remain easy to tap.',
  button_content:'Icons save space. Labels explain actions, but may make narrow cards wider.',
  button_shape:'Changes action buttons; the completion checkbox stays the same.'
};
export function actionColor(value) {
  if (!value || value === 'none') return null;
  if (value === 'primary' || value === 'accent') return `var(--${value}-color)`;
  if (/^[a-z]+(?:-[a-z]+)?$/.test(value)) return `var(--${value}-color, ${value})`;
  return value;
}
class DonetickUserTodoEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:'open'}); }
  connectedCallback() { this.ensureForm(); }
  async ensureForm() {
    if (customElements.get('ha-form') || this._loading) return;
    this._loading=true;
    try {
      const helpers=await window.loadCardHelpers();
      const card=await helpers.createCardElement({type:'entities',entities:[]});
      await card.constructor.getConfigElement();
      if (!customElements.get('ha-form')) throw new Error('HA form controls are unavailable');
      this._loadError='';
    } catch { this._loadError='Could not load Home Assistant editor controls. Reload the dashboard and reopen this editor.'; }
    finally { this._loading=false; this.render(); }
  }
  setConfig(config) { this._config={...config}; this.render(); }
  set hass(hass) { this._hass=hass; this.render(); }
  preset() {
    if (ACTION_OVERRIDES.some(key=>this._config[key] && this._config[key] !== EDITOR_DEFAULTS[key])) return 'custom';
    return Object.keys(STYLE_PRESETS).find(name=>Object.entries(STYLE_PRESETS[name]).every(([key,value])=>(this._config[key] ?? EDITOR_DEFAULTS[key])===value)) || 'custom';
  }
  formChanged(event) {
    event.stopPropagation();
    const values=event.detail.value;
    const config={...this._config};
    for (const [key,value] of Object.entries(values)) {
      if (key==='appearance_preset' || JSON.stringify(value)===JSON.stringify(this._formData[key])) continue;
      if (value==='' || value===undefined || value===null) delete config[key];
      else config[key]=key==='user_id' && value !== 'all' ? Number(value) : value;
    }
    if (values.appearance_preset !== this._formData.appearance_preset && STYLE_PRESETS[values.appearance_preset]) {
      Object.assign(config,STYLE_PRESETS[values.appearance_preset]);
      for (const key of ACTION_OVERRIDES) delete config[key];
    }
    if (config.entity !== this._config.entity) {
      const members=this._hass.states[config.entity]?.attributes.circle_members || [];
      if (config.user_id !== 'all' && !members.some(member=>member.user_id===config.user_id)) {
        if (members.length) config.user_id=members[0].user_id;
        else delete config.user_id;
      }
    }
    this._config=config;
    this.dispatchEvent(new CustomEvent('config-changed',{detail:{config},bubbles:true,composed:true}));
    this.render();
  }
  render() {
    if (!this._hass || !this._config) return;
    if (!customElements.get('ha-form')) {
      this.shadowRoot.textContent=this._loadError || 'Loading Home Assistant editor controls…';
      if (!this._loadError) this.ensureForm();
      return;
    }
    if (!this._form) {
      this.shadowRoot.innerHTML='<style>:host{display:block}ha-form{display:block}ha-alert{display:block;margin-bottom:16px}ha-alert[hidden]{display:none}</style>';
      this._warning=document.createElement('ha-alert');this._warning.setAttribute('alert-type','info');this.shadowRoot.append(this._warning);
      this._form=document.createElement('ha-form');this.shadowRoot.append(this._form);
      this._form.computeLabel=schema=>schema.title || {show_assignee:'Show assigned user',show_reassign:'Allow reassignment'}[schema.name] || EDITOR_LABELS[schema.name] || schema.name;
      this._form.computeHelper=schema=>EDITOR_HELP[schema.name] || (schema.name.endsWith('_color') ? 'Theme color. Used for the icon/text, or the background of filled buttons.' : schema.name.endsWith('_icon') ? 'Choose an icon using HA’s searchable icon picker.' : schema.name.endsWith('_label') ? 'Also used in tooltips and accessibility labels, even with icons only.' : undefined);
      this._form.addEventListener('value-changed',event=>this.formChanged(event));
    }
    const entities=Object.keys(this._hass.states).filter(id=>id.startsWith('todo.') && this._hass.states[id].attributes.circle_members);
    const members=this._hass.states[this._config.entity]?.attributes.circle_members || [];
    this._warning.hidden=!!members.length;
    this._warning.textContent='Select a Donetick list with circle members to choose its users. The integration must be loaded.';
    const select=(name,options)=>({name,selector:{select:{mode:'dropdown',options:options.map(([value,label])=>({value,label}))}}});
    const group=(name,title,schema)=>({name,title,type:'expandable',flatten:true,expanded:false,schema});
    const actionGroup=(action,title)=>{
      const fields=[{name:`${action}_icon`,selector:{icon:{}}},{name:`${action}_label`,selector:{text:{}}},{name:`${action}_color`,selector:{ui_color:{default_color:'primary'}}}];
      fields.forEach((field,index)=>{EDITOR_LABELS[field.name]=['Icon','Label','Color'][index];});
      return group(action,title,fields);
    };
    const schema=[
      {name:'entity',required:true,selector:{entity:{include_entities:entities,filter:{domain:'todo'}}}},
      {...select('user_id',[...(!this._hass.states[this._config.entity]?.attributes.donetick_user_id && members.length > 1 ? [['all','All users']] : []), ...members.map(member=>[String(member.user_id),member.display_name || member.username || `User ${member.user_id}`])]),required:true,disabled:!members.length},
      ...(this._config.user_id === 'all' && !this._hass.states[this._config.entity]?.attributes.donetick_user_id && members.length > 1 ? [{name:'show_assignee',selector:{boolean:{}}}] : []),
      {name:'show_reassign',selector:{boolean:{}}},
      select('display_filter',[['all','All tasks'],['overdue','Overdue'],['today','Today'],['upcoming','Upcoming']]),
      ...(this._config.display_filter==='upcoming' ? [{name:'upcoming_days',selector:{number:{min:0,max:365,step:1,mode:'box',unit_of_measurement:'days'}}}] : []),
      {name:'title',selector:{text:{}}},
      select('appearance_preset',[['todo','HA todo — compact icons'],['labeled','Icons with labels'],['outlined','Outlined buttons'],['filled','Filled buttons'],['custom','Custom style']]),
      group('appearance','Fine-tune appearance',[
        select('complete_control',[['checkbox','Checkbox on the left'],['button','Button on the right']]),
        select('button_content',[['icon','Icons only'],['icon_and_label','Icons and labels'],['label','Labels only']]),
        select('button_style',[['text','Flat — HA style'],['outlined','Outlined'],['filled','Filled']]),
        select('button_size',[['compact','Compact — 44 px'],['normal','Standard — 48 px'],['large','Large — 52 px']]),
        select('button_shape',[['rounded','Rounded'],['pill','Pill'],['square','Square']])
      ]),
      group('actions','Customize individual actions',[
        ...(this._config.complete_control==='button' ? [actionGroup('complete','Complete task')] : []),
        actionGroup('postpone','Skip occurrence — Donetick’s next scheduled date'),
        actionGroup('due_date','Change due date — choose a date manually'),
        ...(this._config.show_reassign !== false ? [actionGroup('reassign','Reassign task')] : [])
      ])
    ];
    const signature=JSON.stringify(schema);
    if (signature!==this._schemaSignature) {this._schemaSignature=signature;this._form.schema=schema;}
    this._formData={...EDITOR_DEFAULTS,...this._config,user_id:this._config.user_id ? String(this._config.user_id) : undefined,appearance_preset:this.preset()};
    this._form.hass=this._hass;this._form.data=this._formData;
  }
}
customElements.define('donetick-user-todo-card', DonetickUserTodoCard);
customElements.define('donetick-user-todo-editor', DonetickUserTodoEditor);
window.customCards = window.customCards || [];
window.customCards.push({type: 'donetick-user-todo-card', name: 'Donetick User Tasks', description: 'Tasks for one user with Complete and Postpone controls'});
