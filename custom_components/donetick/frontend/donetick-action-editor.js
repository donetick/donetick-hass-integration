// HA action descriptions cannot filter fields by another field's value.
// Keep this optional adapter confined to Donetick's native Update Task form.
const CUSTOM = ['interval', 'days_of_the_week', 'day_of_the_month'];
const REPEATING = [...CUSTOM, 'daily', 'weekly', 'monthly', 'yearly', 'adaptive'];
const NON_REPEATING = ['once', 'no_repeat', 'always', 'trigger'];
const FIELDS = new Set(['frequency', 'interval_unit', 'weekdays', 'week_pattern',
  'occurrences', 'months', 'day_of_month', 'schedule_time', 'schedule_from']);
const INSTALLED = Symbol.for('donetick.action-editor.installed');
const states = new WeakMap();

export function recurrenceFields(data = {}) {
  let kind = data.frequency_type;
  if (kind != null && ![...REPEATING, ...NON_REPEATING].includes(kind)) return new Set(FIELDS);
  if (!kind) {
    if ('frequency' in data || 'interval_unit' in data) kind = 'interval';
    else if (['weekdays', 'week_pattern', 'occurrences'].some(key => key in data)) kind = 'days_of_the_week';
    else if ('months' in data || 'day_of_month' in data) kind = 'day_of_the_month';
  }
  if (!kind) return new Set(Object.keys(data).filter(key => FIELDS.has(key)));
  const visible = new Set();
  if (!kind || REPEATING.includes(kind)) visible.add('schedule_from');
  if (!kind || CUSTOM.includes(kind)) {
    visible.add('schedule_time');
  }
  if (kind === 'interval') ['frequency', 'interval_unit'].forEach(key => visible.add(key));
  if (kind === 'days_of_the_week') {
    visible.add('weekdays');
    visible.add('week_pattern');
    if (['week_of_month', 'week_of_quarter'].includes(data.week_pattern)) visible.add('occurrences');
  }
  if (kind === 'day_of_the_month') ['months', 'day_of_month'].forEach(key => visible.add(key));
  return visible;
}

export function cleanPatternChange(previous = {}, next = {}) {
  const kind = next.frequency_type;
  const known = [...REPEATING, ...NON_REPEATING].includes(kind);
  const changed = known && kind !== previous.frequency_type;
  const everyWeek = kind === 'days_of_the_week' && next.week_pattern === 'every_week'
    && previous.week_pattern !== next.week_pattern;
  if (!changed && !everyWeek) return next;
  const allowed = recurrenceFields(next);
  const cleaned = {...next};
  for (const key of FIELDS) {
    if ((changed && !allowed.has(key)) || (everyWeek && key === 'occurrences')) delete cleaned[key];
  }
  return cleaned;
}

function restoreRows(state) {
  for (const [row, original] of state.rows) {
    row.style.display = original.display;
    row.hidden = original.hidden;
  }
  state.rows.clear();
}

export function syncRecurrenceEditor(control) {
  let state = states.get(control);
  if (!state) {
    state = {rows: new Map()};
    states.set(control, state);
    control.addEventListener('value-changed', event => {
      if (event.composedPath()[0] !== control) return;
      const next = event.detail?.value;
      if (next?.action !== 'donetick.update_task' || control.shadowRoot?.querySelector('ha-yaml-editor')) return;
      const previous = control.value?.data || {};
      const cleaned = cleanPatternChange(previous, next.data || {});
      if (cleaned === next.data) return;
      event.detail.value = {...next, data: cleaned};
      // Optional checkboxes have local state in HA. Release removed fields so
      // switching back starts with an unchecked field, rather than a blank value.
      if (control._checkedKeys instanceof Set) {
        for (const key of FIELDS) if (key in (next.data || {}) && !(key in cleaned)) control._checkedKeys.delete(key);
      }
    }, {capture: true});
  }
  const value = control.value;
  if (value?.action !== 'donetick.update_task' || !control.shadowRoot
      || control.shadowRoot.querySelector('ha-yaml-editor')) {
    restoreRows(state);
    return;
  }
  const data = value.data || {};
  const visible = recurrenceFields(data);
  for (const selector of control.shadowRoot.querySelectorAll('ha-selector')) {
    if (!FIELDS.has(selector.key)) continue;
    if (selector.key === 'occurrences' && selector.selector?.select && Array.isArray(data.occurrences)
        && data.occurrences.some(value => typeof value === 'number')) {
      const strings = data.occurrences.map(String);
      if (!Array.isArray(selector.value) || strings.length !== selector.value.length
          || strings.some((value,index) => value !== selector.value[index])) selector.value = strings;
    }
    const row = selector.closest('ha-settings-row');
    if (!row) continue;
    if (!state.rows.has(row)) state.rows.set(row, {display: row.style.display, hidden: row.hidden});
    const original = state.rows.get(row);
    // Never hide an enabled value loaded from YAML; let the user inspect or
    // remove it. Only an explicit UI pattern change clears incompatible data.
    const show = visible.has(selector.key) || data[selector.key] !== undefined;
    row.style.display = show ? original.display : 'none';
    row.hidden = show ? original.hidden : true;
  }
  for (const [row, original] of state.rows) {
    if (!control.shadowRoot.contains(row)) {
      row.style.display = original.display;
      row.hidden = original.hidden;
      state.rows.delete(row);
    }
  }
}

export function installRecurrenceEditor(Control) {
  if (!Control || Control.prototype[INSTALLED]) return;
  const original = Control.prototype.updated;
  Control.prototype.updated = function(changed) {
    original?.call(this, changed);
    // HA internals can change independently of this integration. Fail open to
    // the complete native form if the optional enhancement is incompatible.
    try { syncRecurrenceEditor(this); } catch {
      const state = states.get(this);
      if (state) restoreRows(state);
    }
  };
  Object.defineProperty(Control.prototype, INSTALLED, {value: true});
}

async function startup() {
  // Some HA versions register this component in a scoped registry. Discover
  // the actual instance from composed UI events instead of assuming the global
  // registry owns it. This avoids polling or observing the whole HA document.
  const discovery = Symbol.for('donetick.action-editor.discovery');
  if (typeof document !== 'undefined' && !document[discovery]) {
    document[discovery] = true;
    const discover = event => {
      const control = event.composedPath().find(node => node.localName === 'ha-service-control');
      if (!control) return;
      try {
        installRecurrenceEditor(control.constructor);
        syncRecurrenceEditor(control);
      } catch {
        const state = states.get(control);
        if (state) restoreRows(state);
      }
    };
    document.addEventListener('click', discover, {capture: true});
    document.addEventListener('focusin', discover, {capture: true});
    document.addEventListener('value-changed', discover, {capture: true});
  }
  // HA replaces its registry during startup; wait before claiming the final one.
  if (!customElements.get('home-assistant')) await customElements.whenDefined('home-assistant');
  await customElements.whenDefined('ha-service-control');
  installRecurrenceEditor(customElements.get('ha-service-control'));
}
if (typeof customElements !== 'undefined') void startup();
