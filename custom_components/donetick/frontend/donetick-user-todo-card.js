// HA starts extra modules alongside its app bundle, which replaces both the
// custom-element registry and HTMLElement with its scoped-registry polyfill.
// Wait before defining classes so they use the final registry and base class.
await customElements.whenDefined('home-assistant');

function compareTasks(a, b, sortBy, language) {
  const timestamp = value => Number.isFinite(Date.parse(value)) ? Date.parse(value) : Infinity;
  const primary = sortBy === 'priority' ? (Number(b.priority) || 0) - (Number(a.priority) || 0)
    : sortBy === 'name' ? (a.name || '').localeCompare(b.name || '', language, {sensitivity:'base',numeric:true}) : 0;
  return primary || timestamp(a.next_due_date) - timestamp(b.next_due_date) || a.task_id - b.task_id;
}
export function upcomingDayLimit(value) {
  return value === undefined ? 7 : value === null || value === '' ? 0 : Number(value);
}
export function completedTasks(state, userId, now = new Date(), config = {}) {
  const owner = state?.attributes?.donetick_user_id ?? userId;
  const days = Number(config.completed_days ?? 1);
  const since = new Date(now.getFullYear(), now.getMonth(), now.getDate() - days + 1);
  const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const tasks = (state?.attributes?.completed_tasks || []).filter(task => {
    const completed = new Date(task.completed_at);
    const matchesDate = userTasks({attributes:{tasks:[task]}}, 'all',
      config.completed_filter === 'matching' ? config.display_filters ?? config.display_filter : 'all',
      now, config.upcoming_days, 'due_date', undefined, config.include_overdue, config.labels, config.label_match).length > 0;
    return completed >= since && completed <= now && completed < tomorrow && matchesDate
      && (owner === 'all' || task.completed_by === Number(owner));
  }).sort((a,b) => Date.parse(b.completed_at) - Date.parse(a.completed_at));
  const limit = Number(config.completed_limit ?? 0);
  return limit > 0 ? tasks.slice(0, limit) : tasks;
}
export function recurrenceText(task) {
  const fixed = {daily:'Daily', weekly:'Weekly', monthly:'Monthly', yearly:'Yearly',
    adaptive:'Adaptive', trigger:'Event-based', always:'Always available',
    days_of_the_week:'Selected weekdays', day_of_the_month:'Monthly schedule'};
  if (task.frequency_type !== 'interval') return Object.hasOwn(fixed, task.frequency_type) ? fixed[task.frequency_type] : '';
  const units = {hours:'hour', days:'day', weeks:'week', months:'month', years:'year'};
  const unit = Object.hasOwn(units, task.interval_type) ? units[task.interval_type] : null;
  const count = task.frequency;
  if (!unit || !Number.isInteger(count) || count < 1) return '';
  return `Every ${count} ${count === 1 ? unit : task.interval_type}`;
}
export function taskLabels(value) {
  const labels = typeof value === 'string' ? value.split(',') : Array.isArray(value) ? value : [];
  return [...new Set(labels.map(label => typeof label === 'string' ? label : label?.name)
    .filter(name => typeof name === 'string' && name.trim()).map(name => name.trim()))];
}
export function labelColors(value, name) {
  const label = Array.isArray(value) ? value.find(label => typeof label?.name === 'string' && label.name.trim() === name
    && typeof label.color === 'string' && /^#[\da-f]{3}(?:[\da-f]{3})?$/i.test(label.color)) : null;
  if (!label) return null;
  const hex = label.color.slice(1);
  const full = hex.length === 3 ? [...hex].map(char => char + char).join('') : hex;
  const [r, g, b] = [0, 2, 4].map(offset => parseInt(full.slice(offset, offset + 2), 16));
  // Match Donetick's choice of black or white text for label backgrounds.
  return {backgroundColor: label.color, color: r * 0.299 + g * 0.587 + b * 0.114 > 186 ? '#000000' : '#ffffff'};
}
export function dateFilters(config) {
  if (config.display_filters !== undefined) return config.display_filters;
  switch (config.display_filter) {
    case 'overdue': return ['overdue'];
    case 'today': return ['today'];
    case 'upcoming': return [...(config.include_overdue !== false ? ['overdue'] : []), 'today', 'future'];
    default: return [];
  }
}
function selectedUser(state, userId) {
  return state?.attributes.donetick_user_id ?? userId ?? 'all';
}
export function userTasks(state, userId, displayFilter = 'all', now = new Date(), upcomingDays = 7, sortBy = 'due_date', language, includeOverdue = false, labels = [], labelMatch = 'any', includeAnyone = false) {
  if (typeof labels === 'boolean') { includeAnyone = labels; labels = []; }
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const limit = upcomingDayLimit(upcomingDays);
  const upcomingEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate() + limit + 1);
  userId = selectedUser(state, userId);
  const tasks = [...(state?.attributes?.tasks || []), ...(includeAnyone ? state?.attributes?.anyone_tasks || [] : [])];
  return tasks.filter(task => userId === 'all' || task.assigned_to === Number(userId) || (includeAnyone && task.assigned_to == null))
    .filter(task => {
      if (!labels.length) return true;
      const names = taskLabels(task.labels);
      return labelMatch === 'all' ? labels.every(label => names.includes(label)) : labels.some(label => names.includes(label));
    })
    .filter(task => {
      if (Array.isArray(displayFilter)) {
        if (!displayFilter.length) return true;
        if (!task.next_due_date) return displayFilter.includes('undated');
        const value = task.next_due_date;
        const due = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value);
        return (displayFilter.includes('overdue') && isOverdue(value, now))
          || (displayFilter.includes('today') && due >= today && due < tomorrow)
          || (displayFilter.includes('future') && due >= tomorrow && (limit === 0 || due < upcomingEnd));
      }
      if (displayFilter === 'all') return true;
      if (displayFilter === 'overdue') return isOverdue(task.next_due_date, now);
      if (!task.next_due_date) return false;
      const value = task.next_due_date;
      const due = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value);
      if (displayFilter === 'today') return due >= today && due < tomorrow;
      if (displayFilter !== 'upcoming' || isNaN(due)) return false;
      if (isOverdue(value, now)) return includeOverdue;
      return due >= today && (limit === 0 || due < upcomingEnd);
    })
    .sort((a, b) => compareTasks(a, b, sortBy, language));
}
export function dueText(value, language, now = new Date(), timeFormat, display = 'date') {
  const dateOnly = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
  const date = value ? new Date(dateOnly ? `${value}T12:00:00` : value) : null;
  if (!date || isNaN(date)) return 'No due date';
  const day = value => Date.UTC(value.getFullYear(), value.getMonth(), value.getDate());
  const days = Math.round((day(date) - day(now)) / 86400000);
  let label = days < 0 ? `Overdue · ${-days} day${days === -1 ? '' : 's'}` : days === 0 ? 'Today' : days === 1 ? 'Tomorrow'
    : date.toLocaleDateString(language, {weekday: 'short', month: 'short', day: 'numeric'});
  if (display !== 'date') {
    const relative = new Intl.RelativeTimeFormat(language, {numeric:'auto'});
    let oriented;
    if (days === 0 && hasDueTime(value)) {
      const hours = Math.round((date - now) / 3600000);
      const minutes = Math.round((date - now) / 60000);
      oriented = relative.format(hours || minutes === 0 ? hours : minutes, hours || minutes === 0 ? 'hour' : 'minute');
    } else oriented = relative.format(days === 7 ? 1 : days === -7 ? -1 : days, Math.abs(days) === 7 ? 'week' : 'day');
    oriented = oriented.charAt(0).toLocaleUpperCase(language) + oriented.slice(1);
    if (display === 'relative') return oriented;
    label = `${oriented} · ${date.toLocaleDateString(language, {weekday:'short',month:'short',day:'numeric'})}`;
  }
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
  const filters = dateFilters(config);
  let filter = config.display_filters !== undefined
    ? filters.length ? filters.map(value=>({overdue:'Overdue',today:'Today',future:'Future',undated:'Without a due date'}[value])).join(', ') : 'All tasks'
    : {all:'All tasks',overdue:'Overdue',today:'Today',upcoming:'Upcoming'}[config.display_filter || 'all'];
  if ((config.display_filter === 'upcoming' && config.display_filters === undefined) || filters.includes('future')) {
    const days = upcomingDayLimit(config.upcoming_days);
    filter += days === 0 ? ' (no day limit)' : ` (${days} day${days === 1 ? '' : 's'} ahead)`;
  }
  return `${config.user_id === 'all' ? 'No tasks for all users' : `No tasks for ${userName}${config.include_anyone ? ' or Anyone' : ''}`} · Filter: ${filter}${config.labels?.length ? ` · Labels: ${config.labels.join(config.label_match === 'all' ? ' AND ' : ', ')}` : ''}`;
}
export function actionData(state, task) {
  const data = {task_id: task.task_id, config_entry_id: state.attributes.config_entry_id};
  return data;
}
export function assignableMembers(state, task, allowAnyAssignee = false) {
  return (state?.attributes.circle_members || []).filter(member => member.is_active !== false && (allowAnyAssignee === true || !task.assignee_ids?.length || task.assignee_ids.includes(member.user_id)));
}
// Only the task's own people: Donetick refuses to credit anyone else ("User is not
// assigned to chore"). It would also take a circle admin or manager on a public chore,
// but the entity exposes no roles, so they are not offered. A task with nobody assigned
// offers the active circle, which Donetick accepts on a public unassigned chore. Not
// assignableMembers: that drops an inactive assignee, whom the plain control credits
// anyway. The assignee comes first, being the likeliest answer, unless this device last
// credited someone else: on a shared tablet that is the likeliest next person.
export function performerChoices(state, task, lastChosen) {
  const own = [task.assigned_to, ...(task.assignee_ids || [])].filter(id => id != null);
  const members = (state?.attributes.circle_members || [])
    .filter(member => (member.is_active !== false || member.user_id === task.assigned_to)
      && (!own.length || own.includes(member.user_id)));
  const rank = member => member.user_id === lastChosen ? -1 : member.user_id === task.assigned_to ? 0 : 1;
  return members.map((member, index) => ({member, index})).sort((a, b) =>
    rank(a.member) - rank(b.member) || a.index - b.index).map(entry => entry.member);
}
export function localDateTime(value) {
  const date = value ? new Date(value) : new Date();
  if (isNaN(date)) return '';
  const pad = value => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}
export function descriptionText(value) {
  if (typeof value !== 'string' || !value.trim()) return '';
  // Template contents are inert and never attached to the page. Only text is rendered.
  const template = document.createElement('template'); template.innerHTML = value;
  const omitted = new Set(['SCRIPT','STYLE','NOSCRIPT','IFRAME','OBJECT','EMBED','SVG','MATH','HEAD','TEMPLATE']);
  const blocks = new Set(['P','DIV','SECTION','ARTICLE','BLOCKQUOTE','PRE','H1','H2','H3','H4','H5','H6']);
  const text = node => {
    if (node.nodeType === 3) return node.nodeValue || '';
    if (node.nodeType !== 1 || omitted.has(node.tagName)) return '';
    if (node.tagName === 'BR') return '\n';
    const content = [...node.childNodes].map(text).join('');
    if (node.tagName === 'LI') return `- ${content.trim()}\n`;
    if (blocks.has(node.tagName) || ['UL','OL','TR'].includes(node.tagName)) return `\n${content}\n`;
    if (['TD','TH'].includes(node.tagName)) return `${content}\t`;
    return content;
  };
  return [...template.content.childNodes].map(text).join('').replace(/\u00a0/g,' ')
    .replace(/[ \t]+\n/g,'\n').replace(/\n{3,}/g,'\n\n').trim();
}
// HA replaces its hass object for unrelated entity updates too. Only the selected
// list and presentation settings affect this card's DOM.
function samePresentation(previous, next) {
  return previous.locale === next.locale && previous.themes === next.themes
    && previous.config === next.config && previous.localize === next.localize;
}
class DonetickUserTodoCard extends HTMLElement {
  static getConfigElement() { return document.createElement('donetick-user-todo-editor'); }
  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find(id => id.startsWith('todo.') && hass.states[id].attributes.circle_members);
    return {entity, user_id: hass.states[entity]?.attributes.donetick_user_id ?? hass.states[entity]?.attributes.circle_members?.[0]?.user_id};
  }
  constructor() {
    super(); this.attachShadow({mode: 'open'}); this._pending = new Map(); this._completed = new Map();
    this._outside = event => {
      const path = event.composedPath();
      if (this._panel && !path.includes(this) && !path.some(node => node.localName === 'ha-dialog-date-picker') && !this._pending.has(this._panel.taskId)) this.closePanel();
    };
  }
  connectedCallback() { document.addEventListener('pointerdown', this._outside); this.ensureForm(); }
  async ensureForm() {
    if (customElements.get('ha-form') || this._loadingForm) return;
    this._loadingForm = true;
    try {
      const helpers = await window.loadCardHelpers();
      const card = await helpers.createCardElement({type:'entities',entities:[]});
      await card.constructor.getConfigElement();
      this.render();
    } catch { /* Native inputs remain available if HA controls cannot be loaded. */ }
    finally { this._loadingForm = false; }
  }
  disconnectedCallback() { document.removeEventListener('pointerdown', this._outside); }
  setConfig(config) {
    const signature = JSON.stringify(config);
    if (signature === this._configInputSignature) return;
    if (!config.entity?.startsWith('todo.')) throw new Error('Choose a Donetick todo list');
    if (config.task_view && !['both','pending','completed'].includes(config.task_view)) throw new Error('Choose a valid task view');
    if (config.completed_filter !== undefined && !['all','matching'].includes(config.completed_filter)) throw new Error('Choose a valid completed task filter');
    for (const [key, min, max] of [['completed_days',1,7],['completed_limit',0,500]]) {
      if (config[key] != null && (config[key] === '' || typeof config[key] === 'boolean' || !Number.isInteger(Number(config[key])) || Number(config[key]) < min || Number(config[key]) > max)) throw new Error(`${key === 'completed_days' ? 'Completed history days' : 'Completed task limit'} must be a whole number from ${min} to ${max}`);
    }
    if (config.user_id !== undefined && config.user_id !== 'all' && (!Number.isInteger(Number(config.user_id)) || Number(config.user_id) < 1)) throw new Error('Choose a Donetick user');
    if (config.display_filter && !['all','overdue','today','upcoming'].includes(config.display_filter)) throw new Error('Choose a valid display filter');
    if (config.display_filters !== undefined && (!Array.isArray(config.display_filters) || config.display_filters.some(filter=>!['overdue','today','future','undated'].includes(filter)))) throw new Error('Choose valid task date groups');
    if (config.labels !== undefined && (!Array.isArray(config.labels) || config.labels.some(label => typeof label !== 'string' || !label.trim()))) throw new Error('Labels must be a list of label names');
    if (config.label_match !== undefined && !['any','all'].includes(config.label_match)) throw new Error('Choose any or all for label matching');
    if (config.sort_by && !['due_date','priority','name'].includes(config.sort_by)) throw new Error('Choose a valid sort order');
    if (config.due_display && !['date','relative','both'].includes(config.due_display)) throw new Error('Choose a valid due date display');
    if (config.row_spacing !== undefined && !['auto','compact','comfortable'].includes(config.row_spacing)) throw new Error('Choose valid task spacing');
    if (config.credit_completion !== undefined && !['assignee','choose'].includes(config.credit_completion)) throw new Error('Choose a valid completion credit');
    if (config.complete_as_picker !== undefined && !['chips','dropdown'].includes(config.complete_as_picker)) throw new Error('Choose a valid Complete as picker');
    if (config.upcoming_days !== undefined && (!Number.isInteger(Number(config.upcoming_days)) || Number(config.upcoming_days) < 0 || Number(config.upcoming_days) > 365)) throw new Error('Days ahead must be a whole number from 0 to 365');
    this._config = {task_view:'both', completed_days:1, completed_filter:'all', completed_limit:0, row_spacing:'auto', display_filter:'all', sort_by:'due_date', button_style: 'text', button_size: 'compact', button_shape: 'rounded',
      button_content: 'icon', complete_control: 'checkbox', credit_completion: 'assignee', complete_as_picker: 'chips', include_overdue:true, include_anyone:false, due_display:'date', show_labels:false, show_points:false, show_recurrence:false, use_label_colors:false, show_assignee:true, show_complete:true, show_complete_as:false, show_postpone:true, show_due_date:true, show_reassign:true, allow_any_assignee:false, ...config, completed_days:config.completed_days ?? 1, completed_limit:config.completed_limit ?? 0, labels:taskLabels(config.labels), user_id: config.user_id === undefined || config.user_id === 'all' ? 'all' : Number(config.user_id), upcoming_days:upcomingDayLimit(config.upcoming_days)};
    if (this._panel && this._panel.kind !== 'details' && !(this._panel.kind === 'performer' ? this.offersCompleteAs()
      : this._config[{skip:'show_postpone',date:'show_due_date',assign:'show_reassign'}[this._panel.kind]])) this._panel = null;
    this._configInputSignature = signature;
    this.render();
  }
  set hass(hass) {
    const previous = this._hass;
    const minute = Math.floor(Date.now() / 60000);
    const unchanged = previous && previous !== hass && this._lastHassMinute === minute
      && previous.states[this._config?.entity] === hass.states[this._config?.entity]
      && samePresentation(previous, hass);
    this._hass = hass; this._lastHassMinute = minute;
    if (!unchanged) this.render();
  }
  getCardSize() {
    const state = this._hass?.states[this._config?.entity];
    return 2 + (this._config?.task_view === 'completed' ? 0 : this.filteredTasks(state).length)
      + (this._config?.task_view === 'pending' ? 0 : completedTasks(state, this._config?.user_id, new Date(), this._config).length);
  }
  filteredTasks(state) {
    return userTasks(state, this._config?.user_id, this._config?.display_filters ?? this._config?.display_filter, new Date(), this._config?.upcoming_days, this._config?.sort_by, this._hass?.locale?.language, this._config?.include_overdue, this._config?.labels, this._config?.label_match, this._config?.include_anyone);
  }
  // The Complete as panel has two ways in: its own row action, and the completion
  // control itself when credit_completion asks who did the work.
  offersCompleteAs() {
    return !!this._config.show_complete_as || (!!this._config.show_complete && this._config.credit_completion === 'choose');
  }
  // Remembered per browser and Donetick account, never across them: user ids belong to
  // one Donetick server. It only orders the offer; every completion still asks.
  // Without an account to file it under, nothing is remembered.
  performerKey() {
    const entry = this._hass?.states[this._config?.entity]?.attributes.config_entry_id;
    return entry ? `donetick-user-todo-card:last-performer:${entry}` : null;
  }
  lastPerformer() {
    const key = this.performerKey(); if (!key) return undefined;
    try { const value = Number(globalThis.localStorage?.getItem(key)); return Number.isInteger(value) && value > 0 ? value : undefined; }
    catch { return undefined; }
  }
  rememberPerformer(userId) {
    const key = this.performerKey(); if (!key) return;
    try { globalThis.localStorage?.setItem(key, String(userId)); } catch { /* Storage may be blocked; the order just stays the default. */ }
  }
  completeAction(task) {
    // No circle member to offer (the integration fetches the list once at setup and
    // leaves it empty when that fails) must not make the task uncompletable.
    const choices = performerChoices(this._hass.states[this._config.entity], task);
    if (this._config.credit_completion === 'choose' && choices.length) this.togglePanel(task, 'performer', 'control');
    else this.act(task, true);
  }
  async act(task, complete, dueDate, assignedTo, completedBy) {
    if (this._pending.has(task.task_id)) return;
    const state = this._hass.states[this._config.entity];
    this._pending.set(task.task_id, complete); this.clearError(); this.render();
    try {
      const data = actionData(state, task);
      if (dueDate) data.due_date = dueDate;
      if (assignedTo !== undefined) data.assigned_to = assignedTo;
      if (completedBy !== undefined) data.completed_by = completedBy;
      await this._hass.callService('donetick', dueDate || assignedTo !== undefined ? 'update_task' : complete ? 'complete_assigned_task' : 'postpone_task', data);
      // Only a completion Donetick accepted moves its person to the front.
      if (completedBy !== undefined) this.rememberPerformer(completedBy);
      // Only this task's panel: a slow call must not close one opened meanwhile for
      // another row.
      if (this._panel?.taskId === task.task_id) this._panel = null;
      if (complete) {
        this._completed.set(task.task_id, task);
        setTimeout(() => { this._completed.delete(task.task_id); this.render(); }, 1000);
      }
    } catch (err) { this._error = err.message || String(err); this._errorTask = task; }
    finally { this._pending.delete(task.task_id); this.render(); }
  }
  clearError() { this._error = ''; this._errorTask = null; }
  // Only the panel of the task the message is about can show it.
  errorIsInPanel() { return !!this._errorTask && this._panel?.taskId === this._errorTask.task_id && this._panel.kind !== 'details'; }
  closePanel() {
    const taskId = this._panel?.taskId;
    const kind = this._panel?.kind;
    const opener = this._panel?.opener;
    this._panel = null; this.clearError(); this.render();
    // Complete as has two ways in; focus goes back to the one that opened it.
    this.shadowRoot.querySelector(`[data-action="${kind}"][data-task-id="${taskId}"]${opener ? `[data-opener="${opener}"]` : ''}`)?.focus();
  }
  togglePanel(task, kind, opener) {
    if (this._panel?.taskId === task.task_id && this._panel.kind === kind) { this.closePanel(); return; }
    const value = localDateTime(task.next_due_date);
    const choices = performerChoices(this._hass.states[this._config.entity], task, this.lastPerformer());
    // The dropdown starts on the first person offered; it still books only on confirm.
    this._panel = {taskId: task.task_id, kind, date: value.slice(0, 10), time: task.next_due_date ? value.slice(11) : '09:00:00', showTime:false, assignedTo:task.assigned_to ?? null,
      performer: choices[0]?.user_id ?? null, opener};
    this.clearError();
    this.render();
    // Chips book on activation, so none of them takes the focus: a second Enter must not
    // complete the task for whoever happens to come first.
    if (kind === 'performer' && this._config.complete_as_picker !== 'dropdown') { this.shadowRoot.querySelector('.action-panel')?.focus(); return; }
    this.shadowRoot.querySelector('.action-panel input, .action-panel select, .action-panel ha-form, .action-panel button')?.focus();
  }
  render() {
    if (!this._config || !this._hass) return;
    const state = this._hass.states[this._config.entity];
    const userId = selectedUser(state, this._config.user_id);
    const member = state?.attributes.circle_members?.find(m => m.user_id === userId);
    const focusedField = this.shadowRoot.activeElement?.dataset.field;
    this.shadowRoot.activeElement?.blur();
    this.shadowRoot.innerHTML = `<style>
      ha-card { padding: 12px; } h2 { margin: 0 0 8px; font-size: 20px; font-weight: 500; }
      .row { position:relative; display: flex; align-items: center; gap: 8px; padding: 2px 0; }
      .row.has-labels { padding:8px 0; }
      ha-card[data-spacing="compact"] .row { padding:2px 0; }
      ha-card[data-spacing="comfortable"] .row { padding:8px 0; }
      ha-card[data-labels="true"] { margin-block:4px; }
      .completed .name { text-decoration:line-through; color:var(--secondary-text-color); }
      .history-heading { font-size:14px; font-weight:500; color:var(--secondary-text-color); margin:16px 0 6px; border-top:1px solid var(--divider-color); padding-top:12px; }
      .history-check { color:var(--success-color, #43a047); width:44px; flex-shrink:0; }
      .history-row { padding:6px 0; }
      .actions { display:flex; align-items:center; gap:4px; flex-shrink:0; }
      .task { flex: 1; min-width: 0; } .name { overflow-wrap: anywhere; } .due { color: var(--secondary-text-color); font-size: 12px; margin-top: 2px; }
      .due.overdue { color:var(--warning-color); }
      .due { display:flex; align-items:center; gap:4px; }
      .task-points { display:inline-flex; align-items:center; gap:3px; flex-shrink:0; padding:0 5px; border-radius:10px; background:var(--secondary-background-color); color:var(--secondary-text-color); font-size:11px; line-height:18px; }
      .task-points ha-icon { --mdc-icon-size:12px; }
      .task-recurrence { display:flex; align-items:center; gap:4px; color:var(--secondary-text-color); font-size:12px; line-height:16px; }
      .task-recurrence ha-icon { --mdc-icon-size:14px; flex-shrink:0; }
      .due .recurring, .due .due-clock { --mdc-icon-size:14px; flex-shrink:0; }
      .due .assignee { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      ha-card button.task, ha-card div.task { display:flex; flex-direction:column; align-items:flex-start; justify-content:center; gap:2px; border:0; border-radius:0; padding:0; min-width:0; min-height:44px; text-align:left; background:transparent; color:var(--primary-text-color); font:inherit; }
      .task .name { display:flex; flex-wrap:wrap; align-items:center; gap:4px; line-height:20px; } .task .due { margin-top:0; line-height:16px; }
      .task-labels { display:flex; flex-wrap:wrap; gap:4px; max-width:100%; margin-top:2px; }
      .task-label { max-width:100%; box-sizing:border-box; padding:1px 6px; border-radius:10px; background:var(--secondary-background-color); color:var(--secondary-text-color); font-size:11px; line-height:16px; overflow-wrap:anywhere; text-align:start; }
      .description-indicator { --mdc-icon-size:16px; flex-shrink:0; color:var(--secondary-text-color); }
      .description { white-space:pre-wrap; overflow-wrap:anywhere; font-size:14px; color:var(--secondary-text-color); margin:2px 0 8px; }
      button { cursor: pointer; border: 1px solid var(--divider-color); border-radius: 8px; padding: 9px 11px; background: var(--card-background-color); color: var(--primary-color); font: inherit; font-size: 13px; }
      button:disabled, input:disabled { opacity: .5; cursor: default; }
      .complete-checkbox { width:44px; height:44px; display:flex; align-items:center; justify-content:center; flex-shrink:0; cursor:pointer; }
      input[type="checkbox"] { width:18px; height:18px; margin:0; accent-color:var(--primary-color); cursor:pointer; } button:focus-visible { outline: 2px solid var(--primary-color); }
      button { display:inline-flex; justify-content:center; align-items:center; gap:6px; box-sizing:border-box; min-width:44px; min-height:44px; } ha-icon { --mdc-icon-size:20px; display:inline-flex; align-items:center; justify-content:center; width:var(--mdc-icon-size); height:var(--mdc-icon-size); line-height:0; vertical-align:middle; }
      [data-style="text"] button { border-color:transparent; background:transparent; }
      [data-style="filled"] button { color:var(--text-primary-color); background:var(--primary-color); border-color:transparent; }
      [data-size="compact"] button { padding:5px 8px; font-size:12px; } [data-size="normal"] button { min-width:48px; min-height:48px; } [data-size="large"] button { min-width:52px; min-height:52px; padding:12px 16px; font-size:15px; }
      [data-shape="pill"] button { border-radius:24px; } [data-shape="square"] button { border-radius:0; }
      .error { color: var(--error-color); } .empty { color: var(--secondary-text-color); }
      .action-panel { display:flex; flex-wrap:wrap; align-items:center; gap:4px; margin:2px 0 6px; }
      .action-panel ha-form { flex:1; min-width:180px; --ha-space-6:8px; --time-input-flex:1; --ha-input-padding-bottom:0; --ha-input-required-marker:""; }
      .action-panel.date-panel { display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:center; }
      .date-panel ha-form { min-width:0; }
      .date-panel .error { grid-column:1 / -1; }
      .panel-actions { display:flex; align-items:center; gap:4px; flex-shrink:0; margin-inline-start:auto; }
      .action-panel input, .action-panel select { flex:1; min-width:125px; width:0; box-sizing:border-box; height:44px; padding:8px; color-scheme:var(--ha-color-scheme,light); background:var(--secondary-background-color); color:var(--primary-text-color); border:0; border-bottom:1px solid var(--secondary-text-color); border-radius:4px 4px 0 0; font:inherit; font-size:14px; }
      .action-panel select option { background:var(--secondary-background-color); color:var(--primary-text-color); }
      .action-panel select option:hover, .action-panel select option:checked { background:Highlight; color:HighlightText; }
      .action-panel button { flex-shrink:0; border-color:transparent; background:transparent; color:var(--primary-color); }
      .action-panel .performer-prompt { flex:0 1 auto; }
      .action-panel:focus { outline:none; }
      .panel-members { display:flex; flex-wrap:wrap; align-items:center; gap:6px; flex-basis:100%; }
      ha-card .action-panel .panel-members button { min-height:36px; padding:4px 12px; border:1px solid var(--primary-color); border-radius:18px; background:transparent; color:var(--primary-color); font-size:13px; overflow-wrap:anywhere; }
      .action-panel .error { flex-basis:100%; margin:0; font-size:12px; } .skip-prompt { flex:1; font-size:13px; color:var(--secondary-text-color); }
      button[aria-pressed="true"], button[aria-expanded="true"] { background:var(--secondary-background-color); }
    </style><ha-card></ha-card>`;
    const card = this.shadowRoot.querySelector('ha-card');
    card.dataset.style = this._config.button_style;
    card.dataset.size = this._config.button_size;
    card.dataset.shape = this._config.button_shape;
    card.dataset.spacing = this._config.row_spacing;
    const addText = (parent, tag, text, cls) => { const el = document.createElement(tag); el.textContent = text; if(cls) el.className = cls; parent.append(el); return el; };
    addText(card, 'h2', this._config.title || (userId === 'all' ? 'All users — Tasks' : `${member?.display_name || 'User ' + userId} — Tasks`));
    // A message shows inside its own task's panel; anywhere else it would be read as
    // belonging to the wrong row, so it moves up here and says which task it is about.
    if (this._error && !this.errorIsInPanel()) addText(card, 'p', this._errorTask
      ? `${this._errorTask.name}: ${this._error}` : this._error, 'error').setAttribute('role', 'alert');
    if (!state || ['unavailable', 'unknown'].includes(state.state)) { addText(card, 'p', 'Donetick list unavailable', 'empty'); return; }
    const tasks = this._config.task_view === 'completed' ? [] : this.filteredTasks(state);
    for (const task of this._completed.values()) if (this._config.task_view !== 'completed' && !tasks.some(item => item.task_id === task.task_id) && this.filteredTasks({attributes:{tasks:[task]}}).length) tasks.push(task);
    tasks.sort((a,b) => compareTasks(a,b,this._config.sort_by,this._hass.locale?.language));
    if (!tasks.length && this._config.task_view !== 'completed') addText(card, 'p', emptyMessage({...this._config,user_id:userId}, member?.display_name || member?.username || `User ${userId}`), 'empty');
    for (const task of tasks) {
      const row = document.createElement('div'); row.className = 'row'; card.append(row);
      const completed = this._completed.has(task.task_id);
      const choosing = this._config.credit_completion === 'choose';
      const performerOpen = this._panel?.taskId === task.task_id && this._panel.kind === 'performer';
      if (completed) row.classList.add('completed');
      if (this._config.show_complete && this._config.complete_control === 'checkbox') {
        const target = document.createElement('label'); target.className = 'complete-checkbox'; row.append(target);
        const checkbox = document.createElement('input'); checkbox.type = 'checkbox';
        checkbox.disabled = this._pending.has(task.task_id) || completed; checkbox.checked = this._pending.get(task.task_id) === true || completed;
        checkbox.setAttribute('aria-label', `Complete: ${task.name}`);
        checkbox.title = `Complete: ${task.name}`;
        // No aria-expanded here: unlike the button, role checkbox does not support it.
        if (choosing) { checkbox.dataset.action = 'performer'; checkbox.dataset.taskId = task.task_id; checkbox.dataset.opener = 'control'; }
        checkbox.addEventListener('change', () => this.completeAction(task));
        target.append(checkbox);
      }
      const hasDescription = !!descriptionText(task.description);
      const text = document.createElement(hasDescription ? 'button' : 'div'); text.className = 'task'; row.append(text);
      if (hasDescription) {
      text.type = 'button';
      text.dataset.action = 'details'; text.dataset.taskId = task.task_id;
      text.title = `Show description: ${task.name}`;
      text.setAttribute('aria-label', text.title);
      text.setAttribute('aria-expanded', String(this._panel?.taskId === task.task_id && this._panel.kind === 'details'));
      text.setAttribute('aria-controls', `description-${task.task_id}`);
      text.addEventListener('click', () => this.togglePanel(task, 'details'));
      text.addEventListener('keydown', event => { if (event.key === 'Escape' && this._panel?.kind === 'details') { event.stopPropagation(); this.closePanel(); } });
      }
      const name = addText(text, 'span', task.name, 'name');
      if (this._config.show_points && Number.isFinite(task.points)) {
        const label = `${task.points} ${task.points === 1 ? 'point' : 'points'}`;
        const badge = addText(name, 'span', String(task.points), 'task-points');
        badge.title = `Task value: ${label}`; badge.setAttribute('aria-label', label);
        const star = document.createElement('ha-icon'); star.setAttribute('icon', 'mdi:star-outline');
        star.setAttribute('aria-hidden', 'true'); badge.prepend(star);
      }
      if (hasDescription) {
        const indicator = document.createElement('ha-icon'); indicator.className = 'description-indicator';
        indicator.setAttribute('icon', this._panel?.taskId === task.task_id && this._panel.kind === 'details' ? 'mdi:chevron-up' : 'mdi:chevron-down');
        indicator.setAttribute('aria-hidden', 'true'); name.append(indicator);
      }
      const dateOnly = typeof task.next_due_date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(task.next_due_date);
      const due = task.next_due_date ? new Date(dateOnly ? `${task.next_due_date}T12:00:00` : task.next_due_date) : null;
      const dueLabel = addText(text, 'span', dueText(task.next_due_date, this._hass.locale?.language, new Date(), this._hass.locale?.time_format, this._config.due_display), 'due');
      if (!completed && isOverdue(task.next_due_date)) dueLabel.classList.add('overdue');
      if (due && !isNaN(due)) {
        const clock = document.createElement('ha-icon'); clock.className = 'due-clock';
        clock.setAttribute('icon', 'mdi:clock'); clock.setAttribute('aria-hidden', 'true'); dueLabel.prepend(clock);
      }
      if (due && !isNaN(due)) dueLabel.title = due.toLocaleString(this._hass.locale?.language, {dateStyle:'full',timeStyle:hasDueTime(task.next_due_date) ? 'short' : undefined});
      const recurrence = this._config.show_recurrence ? recurrenceText(task) : '';
      if (!recurrence && (task.is_recurring ?? task.can_postpone)) {
        const recurring = document.createElement('ha-icon'); recurring.className = 'recurring';
        recurring.setAttribute('icon', 'mdi:autorenew'); recurring.title = 'Recurring task';
        recurring.setAttribute('role', 'img'); recurring.setAttribute('aria-label', 'Recurring task');
        dueLabel.prepend(recurring);
      }
      if (this._config.show_assignee && (userId !== 'all' && this._config.include_anyone || userId === 'all' && state.attributes.circle_members?.length > 1)) {
        const assignee = state.attributes.circle_members.find(member => member.user_id === task.assigned_to);
        const name = assignee?.display_name || assignee?.username || (task.assigned_to ? `User ${task.assigned_to}` : 'Anyone');
        const label = addText(dueLabel, 'span', `· ${name}`, 'assignee'); label.title = `Assigned to: ${name}`;
      }
      if (recurrence) {
        const label = addText(text, 'span', recurrence, 'task-recurrence'); label.title = recurrence;
        const icon = document.createElement('ha-icon'); icon.setAttribute('icon', 'mdi:autorenew');
        icon.setAttribute('aria-hidden', 'true'); label.prepend(icon);
      }
      if (this._config.show_labels) {
        const labels = taskLabels(task.labels);
        if (labels.length) {
          row.classList.add('has-labels'); card.dataset.labels = 'true';
          const chips = document.createElement('span'); chips.className = 'task-labels'; text.append(chips);
          for (const label of labels) {
            const chip = addText(chips, 'span', label, 'task-label');
            const colors = this._config.use_label_colors ? labelColors(task.labels, label) : null;
            if (colors) Object.assign(chip.style, colors);
          }
        }
      }
      const actions = document.createElement('div'); actions.className = 'actions'; row.append(actions);
      for (const [label, complete] of [[this._config.complete_label || 'Complete', true], [this._config.postpone_label || 'Skip occurrence', false]]) {
        if (complete && (!this._config.show_complete || this._config.complete_control === 'checkbox')) continue;
        if (!complete && (!this._config.show_postpone || !task.can_postpone)) continue;
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
        if (complete && choosing) { button.dataset.action = 'performer'; button.dataset.taskId = task.task_id; button.dataset.opener = 'control'; button.setAttribute('aria-expanded', String(performerOpen)); }
        button.addEventListener('click', () => complete ? this.completeAction(task) : this.togglePanel(task, 'skip'));
      }
      if (this._config.show_due_date) {
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
      }
      // With nobody to offer the action would open an empty panel, so it stays away.
      if (this._config.show_complete_as && performerChoices(state, task).length) {
        const completeAs = document.createElement('button'); completeAs.type = 'button';
        const label = this._config.complete_as_label || 'Complete as';
        if (this._config.button_content !== 'label') {
          const icon = document.createElement('ha-icon'); icon.setAttribute('icon', this._config.complete_as_icon || 'mdi:account-check-outline'); completeAs.append(icon);
        }
        if (this._config.button_content !== 'icon') completeAs.append(document.createTextNode(label));
        const color = actionColor(this._config.complete_as_color);
        if (color) completeAs.style.setProperty(this._config.button_style === 'filled' ? 'background-color' : 'color', color);
        completeAs.disabled = this._pending.has(task.task_id) || completed;
        completeAs.title = `${label}: ${task.name}`; completeAs.setAttribute('aria-label', completeAs.title);
        completeAs.dataset.action = 'performer'; completeAs.dataset.taskId = task.task_id; completeAs.dataset.opener = 'row';
        completeAs.setAttribute('aria-expanded', String(performerOpen));
        completeAs.addEventListener('click', () => this.togglePanel(task, 'performer', 'row')); actions.append(completeAs);
      }
      if (this._config.show_reassign) {
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
      if (!actions.childElementCount) actions.remove();
      if (this._panel?.taskId === task.task_id) this.renderPanel(row, task, addText);
    }
    if (this._config.task_view !== 'pending') {
      const history = completedTasks(state, this._config.user_id, new Date(), this._config);
      const period = Number(this._config.completed_days) === 1 ? 'today' : `in the last ${this._config.completed_days} days`;
      addText(card, 'h3', `Completed ${period} · ${history.length}`, 'history-heading');
      if (!history.length) addText(card, 'p', this._config.completed_filter === 'matching' ? `No completed tasks ${period} match the task date filter` : `No tasks completed ${period}`, 'empty');
      for (const task of history) {
        const row = document.createElement('div'); row.className = 'row completed history-row'; row.dataset.uid = task.uid; card.append(row);
        const check = document.createElement('ha-icon'); check.className = 'history-check'; check.setAttribute('icon','mdi:check-circle-outline'); check.setAttribute('aria-label','Completed'); row.append(check);
        const text = document.createElement('div'); text.className = 'task'; row.append(text);
        addText(text, 'span', task.name, 'name');
        const performer = state.attributes.circle_members?.find(member => member.user_id === task.completed_by);
        const name = performer?.display_name || performer?.username || (task.completed_by ? `User ${task.completed_by}` : 'Unknown user');
        const time = Number(this._config.completed_days) > 1
          ? new Date(task.completed_at).toLocaleString(this._hass.locale?.language, {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:this._hass.locale?.time_format === '12' ? true : this._hass.locale?.time_format === '24' ? false : undefined})
          : new Date(task.completed_at).toLocaleTimeString(this._hass.locale?.language, {hour:'2-digit', minute:'2-digit', hour12:this._hass.locale?.time_format === '12' ? true : this._hass.locale?.time_format === '24' ? false : undefined});
        addText(text, 'span', `${time} · ${name}`, 'due');
      }
    }
    if (focusedField) this.shadowRoot.querySelector(`[data-field="${focusedField}"]`)?.focus();
  }
  renderPanel(row, task, addText) {
    const panel = this._panel;
    if (panel.kind === 'details') {
      const content = descriptionText(task.description);
      if (!content) { this._panel = null; return; }
      const description = document.createElement('div'); description.className = 'description';
      description.id = `description-${task.task_id}`;
      description.textContent = content;
      row.after(description); return;
    }
    const busy = this._pending.has(task.task_id);
    const form = document.createElement('form'); form.className = 'action-panel'; row.after(form);
    const controls = document.createElement('div'); controls.className = 'panel-actions';
    const draftDate = () => {
      const value = `${panel.date}T${panel.time}`;
      const date = new Date(value);
      return !isNaN(date) && localDateTime(date) === (value.length === 16 ? value + ':00' : value) ? date : null;
    };
    const changed = () => panel.kind === 'skip' || panel.kind === 'performer' || (panel.kind === 'assign'
      ? panel.assignedTo !== (task.assigned_to ?? null)
      : draftDate() && (!task.next_due_date || localDateTime(draftDate()) !== localDateTime(task.next_due_date)));
    let save;
    const updateSave = () => {
      if (!save) return;
      save.disabled = busy || !changed()
        || (panel.kind === 'assign' && panel.assignedTo !== null && !assignableMembers(this._hass.states[this._config.entity], task, this._config.allow_any_assignee).some(member => member.user_id === panel.assignedTo))
        || (panel.kind === 'performer' && !performerChoices(this._hass.states[this._config.entity], task).some(member => member.user_id === panel.performer));
    };
    form.setAttribute('aria-label', `${panel.kind === 'date' ? 'Change due date' : panel.kind === 'assign' ? 'Reassign' : panel.kind === 'performer' ? 'Complete as' : 'Skip occurrence'}: ${task.name}`);
    const iconButton = (label, icon, handler) => {
      const node=document.createElement('button'); node.type='button'; node.disabled=busy;
      node.title=label; node.setAttribute('aria-label',label); node.dataset.field=`control-${label}`;
      const glyph=document.createElement('ha-icon'); glyph.setAttribute('icon',icon); node.append(glyph);
      if (handler) node.addEventListener('click',handler); controls.append(node); return node;
    };
    const field = (type, label, value, handler) => {
      const input=document.createElement('input'); input.type=type; input.required=true;
      input.value=value; input.disabled=busy; input.dataset.field=type;
      input.style.colorScheme=this._hass.themes?.darkMode ? 'dark' : 'light';
      input.setAttribute('aria-label',label); input.title=label;
      input.addEventListener('input',handler); form.append(input); return input;
    };
    if (panel.kind === 'date') {
      if (customElements.get('ha-form')) {
        form.classList.add('date-panel');
        const fields = document.createElement('ha-form'); fields.dataset.field = 'date-fields';
        fields.dataset.withTime = String(panel.showTime);
        fields.setAttribute('aria-label', 'Due date and time');
        fields.hass = this._hass; fields.disabled = busy;
        fields.computeLabel = schema => schema.name === 'date' ? 'Due date' : '';
        fields.schema = [{name:'',type:'grid',column_min_width:'150px',schema:[
          // Save validates the date below; omitting required avoids HA's empty hint row.
          {name:'date',selector:{date:{}}},
          ...(panel.showTime ? [{name:'time',required:true,selector:{time:{no_second:true}}}] : [])
        ]}];
        fields.data = {date:panel.date,time:panel.time};
        fields.addEventListener('value-changed', event => {
          event.stopPropagation();
          const values = event.detail.value;
          if ('date' in values) panel.date = values.date || '';
          if ('time' in values) panel.time = values.time || '';
          updateSave();
          if (!fields.isConnected) this.render();
        });
        form.append(fields);
      } else {
      field('date','Due date',panel.date,event => { panel.date=event.target.value; updateSave(); });
      if (panel.showTime) {
        const input=field('time',`Time (${Intl.DateTimeFormat().resolvedOptions().timeZone})`,panel.time,event => { panel.time=event.target.value; updateSave(); }); input.step='1';
      }
      }
      const time=iconButton(panel.showTime ? 'Hide time' : 'Set time','mdi:clock-outline', () => { panel.showTime=!panel.showTime; this.render(); });
      time.setAttribute('aria-expanded',String(panel.showTime));
    } else if (panel.kind === 'assign') {
      const state = this._hass.states[this._config.entity];
      const members = assignableMembers(state, task, this._config.allow_any_assignee);
      const select = document.createElement('select'); select.required = true; select.disabled = busy;
      select.style.colorScheme = this._hass.themes?.darkMode ? 'dark' : 'light';
      select.dataset.field = 'assignee'; select.setAttribute('aria-label', 'Assigned user');
      const anyone = document.createElement('option'); anyone.value = 'anyone'; anyone.textContent = 'Anyone'; select.append(anyone);
      for (const member of members) {
        const option = document.createElement('option'); option.value = String(member.user_id); option.textContent = member.display_name || member.username || `User ${member.user_id}`; select.append(option);
      }
      select.value = panel.assignedTo === null ? 'anyone' : String(panel.assignedTo);
      select.addEventListener('change', event => { panel.assignedTo = event.target.value === 'anyone' ? null : Number(event.target.value); updateSave(); }); form.append(select);
    } else if (panel.kind === 'performer') {
      const members = performerChoices(this._hass.states[this._config.entity], task, this.lastPerformer());
      if (!members.length) { this._panel = null; form.remove(); return; }
      addText(form, 'span', 'Complete as…', 'skip-prompt performer-prompt');
      // Anyone is absent on purpose: a completion is credited to a person, and leaving it
      // to the token owner is what the plain completion control already does.
      if (this._config.complete_as_picker !== 'dropdown') {
        form.tabIndex = -1;
        const picker = document.createElement('div'); picker.className = 'panel-members'; form.append(picker);
        for (const member of members) {
          const name = member.display_name || member.username || `User ${member.user_id}`;
          const choice = document.createElement('button'); choice.type = 'button'; choice.disabled = busy;
          // The full name, not initials: two members can share initials, and a tablet
          // never shows a tooltip.
          choice.textContent = name; choice.title = `Complete as ${name}`;
          choice.setAttribute('aria-label', choice.title); choice.dataset.field = `performer-${member.user_id}`;
          // One tap books it: picking the person is the confirmation.
          choice.addEventListener('click', () => this.act(task, true, undefined, undefined, member.user_id));
          picker.append(choice);
        }
      } else {
      const select = document.createElement('select'); select.required = true; select.disabled = busy;
      select.style.colorScheme = this._hass.themes?.darkMode ? 'dark' : 'light';
      select.dataset.field = 'performer'; select.setAttribute('aria-label', 'Completed by');
      for (const member of members) {
        const option = document.createElement('option'); option.value = String(member.user_id);
        option.textContent = member.display_name || member.username || `User ${member.user_id}`;
        select.append(option);
      }
      select.value = String(panel.performer);
      select.addEventListener('change', event => { panel.performer = Number(event.target.value); updateSave(); }); form.append(select);
      }
    } else addText(form,'span','Move to the next scheduled date?', 'skip-prompt');
    if (panel.kind !== 'performer' || this._config.complete_as_picker === 'dropdown') {
    save = document.createElement('button'); save.type = 'submit'; save.className = 'save-action';
    const saveIcon = document.createElement('ha-icon');
    saveIcon.setAttribute('icon', panel.kind === 'skip' ? 'mdi:skip-next-outline' : panel.kind === 'performer' ? 'mdi:check' : 'mdi:content-save-outline');
    save.append(saveIcon);
    save.setAttribute('aria-label', panel.kind === 'date' ? 'Save due date' : panel.kind === 'assign' ? 'Save assignee' : panel.kind === 'performer' ? 'Confirm completion' : 'Confirm skip');
    save.title = save.getAttribute('aria-label');
    controls.append(save); updateSave();
    }
    form.append(controls);
    if (this._error && this._errorTask?.task_id === task.task_id) { const error=addText(form,'p',this._error,'error'); error.setAttribute('role','alert'); }
    form.addEventListener('keydown',event => { if (event.key === 'Escape' && !busy) { event.stopPropagation(); this.closePanel(); } });
    form.addEventListener('submit',event => {
      event.preventDefault(); if (busy || !form.reportValidity() || form.querySelector('ha-form')?.reportValidity?.() === false) return;
      if (panel.kind === 'skip') { this.act(task,false); return; }
      if (panel.kind === 'performer') {
        // Chips have no preselection to confirm: only tapping a person books.
        if (this._config.complete_as_picker !== 'dropdown') return;
        if (!performerChoices(this._hass.states[this._config.entity], task).some(member => member.user_id === panel.performer)) { this._error = 'Choose someone from the circle'; this._errorTask = task; this.render(); return; }
        this.act(task, true, undefined, undefined, panel.performer); return;
      }
      if (panel.kind === 'assign') {
        if (panel.assignedTo !== null && !assignableMembers(this._hass.states[this._config.entity], task, this._config.allow_any_assignee).some(member => member.user_id === panel.assignedTo)) { this._error = 'Choose an eligible assignee'; this._errorTask = task; this.render(); return; }
        if (!changed()) return;
        this.act(task, false, undefined, panel.assignedTo); return;
      }
      const date = draftDate();
      if (!date) { this._error='Choose a valid date and time'; this._errorTask = task; this.render(); return; }
      if (!changed()) return;
      this.act(task,false,date.toISOString());
    });
  }
}
const EDITOR_DEFAULTS = {
  task_view:'both',
  completed_days:1, completed_filter:'all', completed_limit:0,
  row_spacing:'auto',
  credit_completion:'assignee', complete_as_picker:'chips',
  display_filters:[], label_match:'any', sort_by:'due_date', upcoming_days:7, include_anyone:false, due_display:'date', show_labels:false, show_points:false, show_recurrence:false, use_label_colors:false, show_assignee:true, show_complete:true, show_complete_as:false, show_postpone:true, show_due_date:true, show_reassign:true, allow_any_assignee:false, complete_control:'checkbox', button_style:'text', button_size:'compact',
  button_shape:'rounded', button_content:'icon', complete_label:'Complete', postpone_label:'Skip occurrence',
  due_date_label:'Change due date', complete_icon:'mdi:check', postpone_icon:'mdi:calendar-arrow-right',
  due_date_icon:'mdi:calendar-edit', reassign_label:'Reassign', reassign_icon:'mdi:account-switch-outline', complete_as_label:'Complete as', complete_as_icon:'mdi:account-check-outline',
  complete_color:'primary', postpone_color:'primary', due_date_color:'primary', reassign_color:'primary', complete_as_color:'primary'
};
const STYLE_PRESETS = {
  todo:{complete_control:'checkbox',button_style:'text',button_size:'compact',button_shape:'rounded',button_content:'icon'},
  labeled:{complete_control:'checkbox',button_style:'text',button_size:'compact',button_shape:'rounded',button_content:'icon_and_label'},
  outlined:{complete_control:'checkbox',button_style:'outlined',button_size:'normal',button_shape:'rounded',button_content:'icon'},
  filled:{complete_control:'checkbox',button_style:'filled',button_size:'normal',button_shape:'rounded',button_content:'icon'}
};
const ACTION_OVERRIDES = ['complete','postpone','due_date','reassign','complete_as'].flatMap(action=>['label','icon','color'].map(part=>`${action}_${part}`));
const EDITOR_LABELS = {allow_any_assignee:'Allow assigning any circle member',entity:'Donetick task list',user_id:'Assigned user',include_anyone:'Include tasks assigned to Anyone',display_filters:'Pending task dates',show_points:'Show task points',show_recurrence:'Show recurrence',upcoming_days:'Days ahead',include_overdue:'Include overdue tasks',due_display:'Due date display',title:'Card title (optional)',appearance_preset:'Starting style',appearance:'Appearance',complete_control:'Complete tasks with',button_style:'Action button style',button_size:'Tap target size',button_shape:'Button corners',button_content:'Show on action buttons'};
const EDITOR_HELP = {
  task_view:'Show pending tasks, completed occurrences, or both. Completed entries are read-only and attributed to the person who completed them.',
  completed_days:'Today is 1 day. Leave empty for today. Includes today and the previous days, up to 7 days of history. The most recent completions appear first.',
  completed_filter:'All completions includes tasks finished in this period regardless of their due date. Match task date filter uses the occurrence’s original due date, so Tomorrow’s next occurrence does not hide a task completed today.',
  completed_limit:'Maximum completed entries to show, newest first. Use 0 for all matching entries. Does not limit pending tasks.',
  show_points:'Show a small points badge beside the task name. Tasks without points omit the badge.',
  show_recurrence:'Show the recurrence on its own muted line, including the unit for interval schedules.',
  row_spacing:'Auto adds space to tasks with visible labels. Compact keeps all rows tight; Comfortable adds space to every task.',
  labels:'Filter by selected labels. Leave empty for all labels. Choices come from this list’s tasks; set the integration’s task window to 0 to include distant tasks.',
  label_match:'Any (OR) matches at least one selected label. All (AND) requires every selected label. User and date filters still apply.',
  show_labels:'Show small label chips below each task’s due date. Hidden by default; long names wrap within the task column.',
  use_label_colors:'Use each label’s Donetick background color and matching readable text. Labels without a valid color keep the neutral style.',
  entity:'Choose All Tasks to make tasks for every circle user available.',
  user_id:'Show one user’s tasks or all users. Unless Credit completion to asks, completion credits the current assignee by default, or the API token owner for Anyone tasks. Optional HA user mapping in the integration settings can override this.',
  include_anyone:'Show Anyone tasks alongside the selected user’s tasks, using the same date filters and sorting.',
  show_assignee:'Show the assigned name beside the due date. Available when the list can contain multiple users.',
  allow_any_assignee:'Off by default. Selecting someone outside a task’s eligible assignees adds them to that list. They may receive future assignments under the existing rotation strategy. Requires permission to edit the task.',
  show_reassign:'Show a user-switch action on each row. Changes are saved only after confirmation.',
  show_complete_as:'Show an action that completes a task for someone else among its assignees, or anyone in the circle when nobody is assigned. Off by default; the plain completion control keeps crediting as before.',
  show_complete:'Show the completion checkbox or button. Turn off for a display-only task list.',
  show_postpone:'Show Skip occurrence for tasks with a recurring schedule.',
  show_due_date:'Show the action to choose a due date manually, including for one-off tasks.',
  display_filters:'Show tasks in any selected group. Leave empty for all tasks. Today includes deadlines earlier today; Future starts tomorrow. Choose Overdue to include past deadlines and Without a due date for undated tasks.',
  due_display:'Show a date, relative time such as Tomorrow or In 3 days, or both. The full due date is always available in the tooltip.',
  sort_by:'Due date: earliest first, undated last. Priority: urgent first, then due date. Name: A–Z using your HA language.',
  upcoming_days:'Maximum days ahead; leave empty or use 0 for no limit. The integration’s task window must also include those days.',
  title:'Leave empty to use the selected user’s name.',
  appearance_preset:'Choose a ready-made style. Applying a preset resets custom action icons, labels and colors.',
  complete_control:'Checkbox stays on the left; Button places completion beside the other actions on the right.',
  button_style:'Flat follows HA todo styling. Filled uses the action color as its background.',
  button_size:'Compact: 44 px. Standard: 48 px. Large: 52 px. All remain easy to tap.',
  button_content:'Icons save space. Labels explain actions, but may make narrow cards wider.',
  button_shape:'Changes action buttons; the completion checkbox stays the same.'
};
Object.assign(EDITOR_LABELS, {credit_completion:'Credit completion to', complete_as_picker:'Complete as picker'});
Object.assign(EDITOR_HELP, {
  credit_completion:'The task assignee is credited by default. Ask who completed it makes the completion control open Complete as, offering the task’s assignees, or anyone in the circle when nobody is assigned.',
  complete_as_picker:'Chips complete the task with one tap on a person. A dropdown scales better to a large circle and books after a confirmation.'
});
EDITOR_LABELS.task_view = 'Task view';
Object.assign(EDITOR_LABELS, {completed_days:'History period (days)',completed_filter:'Completed tasks to include',completed_limit:'Maximum completed entries'});
export function actionColor(value) {
  if (!value || value === 'none') return null;
  if (value === 'primary' || value === 'accent') return `var(--${value}-color)`;
  if (/^[a-z]+(?:-[a-z]+)?$/.test(value)) return `var(--${value}-color, ${value})`;
  return value;
}
class DonetickUserTodoEditor extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:'open'});
    this._expandedGroups=new Map();this._groupSchemas=new Map();
    this.shadowRoot.addEventListener('expanded-will-change',event=>{
      const group=event.composedPath().find(node=>node.localName==='ha-form-expandable');
      const name=group?.schema?.name;
      if (!this._groupSchemas.has(name) || typeof event.detail?.expanded !== 'boolean') return;
      this._expandedGroups.set(name,event.detail.expanded);
      this.render();
    });
  }
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
  setConfig(config) {
    if (JSON.stringify(config) === JSON.stringify(this._config)) return;
    this._config={...config}; this.render();
  }
  set hass(hass) {
    const previous = this._hass;
    const lists = Object.entries(hass.states).filter(([id,state])=>id.startsWith('todo.') && state.attributes.circle_members);
    const unchanged = previous && previous !== hass && samePresentation(previous,hass)
      && previous.entities === hass.entities && previous.devices === hass.devices && previous.areas === hass.areas
      && this._editorLists?.length === lists.length
      && lists.every(([id,state],index)=>this._editorLists[index][0] === id && this._editorLists[index][1] === state);
    this._hass=hass; this._editorLists=lists;
    if (!unchanged) this.render();
  }
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
      if (key==='display_filters') {
        config.display_filters=value || [];
        delete config.display_filter;
        delete config.include_overdue;
      }
      // Preserve an explicitly cleared editable field across HA's setConfig
      // feedback so displayed defaults do not interrupt typing a replacement.
      else if ((['upcoming_days','completed_days','completed_limit'].includes(key) || ACTION_OVERRIDES.includes(key)) && (value==='' || value===undefined || value===null)) config[key]=null;
      else if (value==='' || value===undefined || value===null) delete config[key];
      else config[key]=key==='user_id' && value !== 'all' ? Number(value) : value;
    }
    if (values.appearance_preset !== this._formData.appearance_preset && STYLE_PRESETS[values.appearance_preset]) {
      Object.assign(config,STYLE_PRESETS[values.appearance_preset]);
      for (const key of ACTION_OVERRIDES) delete config[key];
    }
    const state=this._hass.states[config.entity];
    if (state?.attributes.donetick_user_id !== undefined) config.user_id=state.attributes.donetick_user_id;
    else if (config.entity !== this._config.entity) {
      const members=state?.attributes.circle_members || [];
      if (config.user_id !== 'all' && !members.some(member=>member.user_id===config.user_id)) {
        if (members.length) config.user_id=members[0].user_id;
        else delete config.user_id;
      }
    }
    if (JSON.stringify(config) === JSON.stringify(this._config)) return;
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
      this._form.computeLabel=schema=>schema.title || {row_spacing:'Task spacing',show_labels:'Show labels',use_label_colors:'Use Donetick label colors',label_match:'Match labels',labels:'Labels',sort_by:'Sort tasks by',show_assignee:'Show assigned user',show_complete:'Complete task',show_postpone:'Skip occurrence',show_due_date:'Change due date',show_reassign:'Reassign task',show_complete_as:'Complete as'}[schema.name] || EDITOR_LABELS[schema.name] || schema.name;
      this._form.computeHelper=schema=>EDITOR_HELP[schema.name] || (schema.name.endsWith('_color') ? 'Theme color. Used for the icon/text, or the background of filled buttons.' : schema.name.endsWith('_icon') ? 'Choose an icon using HA’s searchable icon picker.' : schema.name.endsWith('_label') ? 'Also used in tooltips and accessibility labels, even with icons only.' : undefined);
      this._form.addEventListener('value-changed',event=>this.formChanged(event));
    }
    const entities=Object.keys(this._hass.states).filter(id=>id.startsWith('todo.') && this._hass.states[id].attributes.circle_members);
    const members=this._hass.states[this._config.entity]?.attributes.circle_members || [];
    const owner=this._hass.states[this._config.entity]?.attributes.donetick_user_id;
    const filters=dateFilters(this._config);
    // Keep selected names available when no current task has that label.
    const attributes=this._hass.states[this._config.entity]?.attributes || {};
    const labels=[...new Set([...[...(attributes.tasks || []),...(attributes.anyone_tasks || []),...(attributes.completed_tasks || [])].flatMap(task=>taskLabels(task.labels)), ...taskLabels(this._config.labels)])]
      .sort((a,b)=>a.localeCompare(b,this._hass.locale?.language));
    this._warning.hidden=owner !== undefined || !!members.length;
    this._warning.textContent='Select a Donetick list with circle members to choose its users. The integration must be loaded.';
    const select=(name,options)=>({name,selector:{select:{mode:'dropdown',options:options.map(([value,label])=>({value,label}))}}});
    this._groupSchemas.clear();
    const group=(name,title,schema)=>{
      const expanded=this._expandedGroups.get(name) ?? ['basics','filters'].includes(name);
      this._groupSchemas.set(name,schema);
      // HA creates nested forms even in collapsed panels. Keep expensive
      // selectors unmounted until opened, and remove them again when closed.
      return {name,title,type:'expandable',flatten:true,expanded,schema:expanded ? schema : []};
    };
    const hasPending = this._config.task_view !== 'completed';
    const hasCompleted = this._config.task_view !== 'pending';
    const matchesCompleted = hasCompleted && this._config.completed_filter === 'matching';
    const labelFields = [
      {name:'labels',selector:{select:{mode:'dropdown',multiple:true,options:labels.map(label=>({value:label,label}))}}},
      ...(taskLabels(this._config.labels).length > 1 ? [select('label_match',[['any','Any selected label (OR)'],['all','All selected labels (AND)']])] : [])
    ];
    const actionGroup=(action,title)=>{
      const fields=[{name:`${action}_icon`,selector:{icon:{}}},{name:`${action}_label`,selector:{text:{}}},{name:`${action}_color`,selector:{ui_color:{default_color:'primary'}}}];
      fields.forEach((field,index)=>{EDITOR_LABELS[field.name]=`${title} · ${['Icon','Label','Color'][index]}`;});
      return {name:action,type:'grid',flatten:true,column_min_width:'150px',schema:fields};
    };
    const actionFields=[
      ...(this._config.show_complete !== false && this._config.complete_control==='button' ? [actionGroup('complete','Complete task')] : []),
      ...(this._config.show_postpone !== false ? [actionGroup('postpone','Skip occurrence')] : []),
      ...(this._config.show_due_date !== false ? [actionGroup('due_date','Change due date')] : []),
      ...(this._config.show_reassign !== false ? [actionGroup('reassign','Reassign task')] : []),
      ...(this._config.show_complete_as ? [actionGroup('complete_as','Complete as')] : [])
    ];
    const schema=[
      {...group('basics','Basics',[
      {name:'entity',required:true,selector:{entity:{include_entities:entities,filter:{domain:'todo'}}}},
      ...(owner === undefined ? [{...select('user_id',[...(members.length > 1 ? [['all','All users']] : []), ...members.map(member=>[String(member.user_id),member.display_name || member.username || `User ${member.user_id}`])]),required:true,disabled:!members.length}] : []),
      ...(hasPending && selectedUser(this._hass.states[this._config.entity], this._config.user_id) !== 'all' ? [{name:'include_anyone',selector:{boolean:{}}}] : []),
      {name:'title',selector:{text:{}}},
      select('task_view',[['both','Pending and completed'],['pending','Pending tasks only'],['completed','Completed tasks only']])
      ])},
      {...group('filters','Task filters',[
      ...labelFields,
      ...(hasPending || matchesCompleted ? [
      {name:'display_filters',title:hasPending ? 'Pending task dates' : 'Original due dates',selector:{select:{mode:'dropdown',multiple:true,options:[{value:'overdue',label:'Overdue'},{value:'today',label:'Today'},{value:'future',label:'Future'},{value:'undated',label:'Without a due date'}]}}},
      ...(filters.includes('future') ? [{name:'upcoming_days',selector:{number:{min:0,max:365,step:1,mode:'box',unit_of_measurement:'days'}}}] : [])
      ] : []),
      ...(hasPending ? [select('sort_by',[['due_date','Due date — earliest first'],['priority','Priority — highest first'],['name','Name — A–Z']])] : [])
      ])},
      ...(hasCompleted ? [group('completed_options','Completed tasks',[
        {name:'completed_days',selector:{number:{min:1,max:7,step:1,mode:'box',unit_of_measurement:'days'}}},
        select('completed_filter',[['all','All completions in the period'],['matching','Match task date filter']]),
        {name:'completed_limit',selector:{number:{min:0,max:500,step:1,mode:'box'}}}
      ])] : []),
      ...(hasPending ? [group('display_options','Task details',[
      ...(selectedUser(this._hass.states[this._config.entity], this._config.user_id) !== 'all' && this._config.include_anyone || this._config.user_id === 'all' && !this._hass.states[this._config.entity]?.attributes.donetick_user_id && members.length > 1 ? [{name:'show_assignee',selector:{boolean:{}}}] : []),
      select('due_display',[['date','Date and time'],['relative','Relative — Tomorrow, In 3 days, Next week'],['both','Relative and date/time']]),
      ...['show_labels',...(this._config.show_labels ? ['use_label_colors'] : []),'show_points','show_recurrence'].map(name=>({name,selector:{boolean:{}}}))
      ])] : []),
      ...(hasPending ? [group('actions_options','Available actions',[
        ...['show_complete','show_complete_as','show_postpone','show_due_date','show_reassign'].map(name=>({name,selector:{boolean:{}}})),
        ...(this._config.show_reassign !== false ? [{name:'allow_any_assignee',selector:{boolean:{}}}] : [])
      ])] : []),
      ...(hasPending ? [group('appearance','Appearance',[
        select('appearance_preset',[['todo','HA todo — compact icons'],['labeled','Icons with labels'],['outlined','Outlined buttons'],['filled','Filled buttons'],['custom','Custom style']]),
        select('row_spacing',[['auto','Auto — extra space for labels'],['compact','Compact'],['comfortable','Comfortable']]),
        ...(this._config.show_complete !== false ? [select('complete_control',[['checkbox','Checkbox on the left'],['button','Button on the right']])] : []),
        ...(this._config.show_complete !== false ? [select('credit_completion',[['assignee','The task assignee'],['choose','Ask who completed it']])] : []),
        ...(this._config.show_complete_as || (this._config.show_complete !== false && this._config.credit_completion === 'choose')
          ? [select('complete_as_picker',[['chips','Chips — one tap completes'],['dropdown','Dropdown — choose, then confirm']])] : []),
        select('button_content',[['icon','Icons only'],['icon_and_label','Icons and labels'],['label','Labels only']]),
        select('button_style',[['text','Flat — HA style'],['outlined','Outlined'],['filled','Filled']]),
        select('button_size',[['compact','Compact — 44 px'],['normal','Standard — 48 px'],['large','Large — 52 px']]),
        select('button_shape',[['rounded','Rounded'],['pill','Pill'],['square','Square']])
      ])] : []),
      ...(hasPending && actionFields.length ? [group('customization_options','Customize action icons, labels and colors',actionFields)] : [])
    ];
    const signature=JSON.stringify(schema);
    if (signature!==this._schemaSignature) {this._schemaSignature=signature;this._form.schema=schema;}
    const formData={...EDITOR_DEFAULTS,...this._config,display_filters:filters,labels:taskLabels(this._config.labels),user_id:String(owner ?? this._config.user_id ?? 'all'),appearance_preset:this.preset()};
    const dataSignature=JSON.stringify(formData);
    if (this._form.hass !== this._hass) this._form.hass=this._hass;
    if (dataSignature !== this._formDataSignature) {
      this._formDataSignature=dataSignature;this._formData=formData;this._form.data=formData;
    }
  }
}
if (!customElements.get('donetick-user-todo-card')) customElements.define('donetick-user-todo-card', DonetickUserTodoCard);
if (!customElements.get('donetick-user-todo-editor')) customElements.define('donetick-user-todo-editor', DonetickUserTodoEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === 'donetick-user-todo-card')) window.customCards.push({type: 'donetick-user-todo-card', name: 'Donetick User Tasks', description: 'Tasks for one user with Complete and Postpone controls'});
