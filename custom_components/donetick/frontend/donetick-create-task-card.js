await customElements.whenDefined("home-assistant");

const cardType = "donetick-create-task-card";
const ASSIGNEE_ANYONE_OPTION = "anyone";
const ASSIGNEE_USER_PREFIX = "user:";
const ISO_DATE_ONLY_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const defaultFields = ["name", "description", "due_date", "due_time", "assignee"];
const defaultSections = {
  "Priority and points": ["priority", "points"],
  "Repeat schedule": [
    "frequency_type", "frequency", "interval_unit", "weekdays", "week_pattern",
    "occurrences", "months", "day_of_month", "schedule_time", "schedule_from",
  ],
  "Reminders and follow-ups": [
    "reminders", "overdue_follow_ups", "overdue_follow_up_interval_minutes",
    "overdue_follow_up_limit", "overdue_follow_up_until_complete",
  ],
  Advanced: ["assigned_to", "created_by", "config_entry_id"],
};
const repeatTypeFields = {
  interval: ["frequency", "interval_unit", "schedule_time"],
  days_of_the_week: ["weekdays", "week_pattern", "occurrences", "schedule_time"],
  day_of_the_month: ["months", "day_of_month", "schedule_time"],
};
const repeatDetails = new Set([...Object.values(repeatTypeFields).flat(), "schedule_from"]);
const rollingTypes = new Set(["daily", "weekly", "monthly", "yearly", "adaptive",
  "interval", "days_of_the_week", "day_of_the_month"]);

function showField(name, values) {
  if (!repeatDetails.has(name)) return true;
  const { frequency_type: frequency, week_pattern: pattern } = values;
  if (name === "schedule_from") return rollingTypes.has(frequency);
  if (name === "occurrences") return frequency === "days_of_the_week" && pattern === "week_of_month";
  return Object.hasOwn(repeatTypeFields, frequency) && repeatTypeFields[frequency].includes(name);
}

function configure(config) {
  const fields = config.fields ?? defaultFields;
  const sections = config.sections ?? defaultSections;
  const defaults = config.defaults ?? {};
  if (!Array.isArray(fields) || !sections || Array.isArray(sections) ||
      typeof sections !== "object" || !defaults || Array.isArray(defaults) ||
      typeof defaults !== "object") {
    throw new Error("Use a list for fields and mappings for sections and defaults.");
  }
  const lists = [fields, ...Object.values(sections)];
  const hiddenFields = config.hidden_fields ?? [];
  if ([...lists, hiddenFields].some((list) =>
    !Array.isArray(list) || list.some((name) => typeof name !== "string"))) {
    throw new Error("Each field list must contain action field names.");
  }
  const names = lists.flat();
  if (new Set(names).size !== names.length) throw new Error("List each field only once.");
  if ((!names.includes("name") || hiddenFields.includes("name")) && !defaults.name?.trim?.()) {
    throw new Error("Show the name field or set defaults.name.");
  }
  return { fields, sections, defaults, hiddenFields, showHelp: config.show_help ?? false };
}

export function buildActionData(values, serviceFields) {
  const { due_date, due_time, assignee, ...fields } = values;
  const name = fields.name?.trim();
  if (!name) throw new Error("Enter a task name.");
  if (due_time && !due_date) throw new Error("Choose a due date for the due time.");

  const data = Object.fromEntries(Object.entries(fields).filter(([key, value]) =>
    Object.hasOwn(serviceFields, key) && showField(key, values) &&
    value !== undefined && value !== "" && (value !== null || key === "assigned_to"),
  ));
  data.name = name;
  if (due_date) {
    if (due_time && !ISO_DATE_ONLY_PATTERN.test(due_date)) {
      throw new Error("Use YYYY-MM-DD when setting a separate due time.");
    }
    data.due_date = due_time ? `${due_date}T${due_time}` : due_date;
  }

  if (assignee && (Object.hasOwn(data, "assigned_to") || data.assigned_to_username)) {
    throw new Error("Use either Assignee or the advanced assignee ID.");
  }
  if (assignee === ASSIGNEE_ANYONE_OPTION) data.assigned_to = null;
  if (assignee?.startsWith(ASSIGNEE_USER_PREFIX)) data.assigned_to_username = assignee.slice(ASSIGNEE_USER_PREFIX.length);
  return data;
}

function nativeFields(fields) {
  const entries = Object.entries(fields).flatMap(([name, field]) =>
    field.fields ? Object.entries(field.fields) : [[name, field]],
  );
  const available = Object.fromEntries(entries);
  if (available.due_date) {
    available.due_date = {
      name: "Due date",
      selector: { date: {} },
      shortHelp: "Leave the time blank to use the end of the day.",
    };
    available.due_time = {
      name: "Due time",
      selector: { time: {} },
      shortHelp: "Uses Home Assistant’s time zone.",
    };
  }
  if (available.assigned_to) {
    const options = available.assigned_to_username?.selector?.select?.options ?? [];
    available.assignee = {
      name: "Assignee",
      shortHelp: "Leave blank to use the action’s default assignment.",
      selector: { select: { mode: "dropdown", options: [
        { value: ASSIGNEE_ANYONE_OPTION, label: "Anyone" },
        ...options.map((option) => typeof option === "string"
          ? { value: `${ASSIGNEE_USER_PREFIX}${option}`, label: option }
          : { ...option, value: `${ASSIGNEE_USER_PREFIX}${option.value}` }),
      ] } },
    };
  }
  return available;
}

function buildSchema(config, fields, values) {
  const hidden = new Set(config.hiddenFields);
  const select = (names) => names.filter((name) =>
    !hidden.has(name) && Object.hasOwn(fields, name) && showField(name, values)).map((name) => {
    const field = fields[name];
    return {
      name,
      required: field.required,
      selector: field.selector ?? { text: {} },
      title: field.name ?? name,
      helper: field.shortHelp ?? (config.showHelp ? field.description : undefined),
    };
  });

  return [
    ...select(config.fields),
    ...Object.entries(config.sections).flatMap(([title, names], index) => {
      const schema = select(names);
      return schema.length ? [{ name: `section_${index}`, title, type: "expandable",
        expanded: false, flatten: true, schema }] : [];
    }),
  ];
}

let formLoader;
async function loadForm() {
  if (customElements.get("ha-form")) return;
  formLoader ??= (async () => {
    const helpers = await window.loadCardHelpers();
    const button = helpers.createCardElement({ type: "button", name: "Create task" });
    await button.constructor.getConfigElement();
    await customElements.whenDefined("ha-form");
  })().catch((error) => {
    formLoader = undefined;
    throw error;
  });
  await formLoader;
}

class DonetickCreateTaskCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  static async getConfigElement() {
    const editorUrl = new URL("./donetick-create-task-editor.js", import.meta.url);
    editorUrl.search = new URL(import.meta.url).search;
    const [{ registerEditor }] = await Promise.all([import(editorUrl.href), loadForm()]);
    return document.createElement(registerEditor(configure, nativeFields));
  }

  setConfig(config) {
    this.config = configure(config);
    const { defaults, ...layout } = this.config;
    const defaultsKey = JSON.stringify(defaults);
    const layoutKey = JSON.stringify(layout);
    const defaultsChanged = defaultsKey !== this.defaultsKey;
    const layoutChanged = layoutKey !== this.layoutKey;
    this.defaultsKey = defaultsKey;
    this.layoutKey = layoutKey;
    if (!this.card) this.renderCard();
    this.card.header = config.title ?? "Create a Donetick task";
    this.button.textContent = config.submit_label ?? "Create task";
    if (this.form) {
      if (defaultsChanged) this.form.data = structuredClone(defaults);
      if (layoutChanged || defaultsChanged) this.updateSchema();
    }
    this.refreshFields();
  }

  set hass(hass) {
    this.homeAssistant = hass;
    this.refreshFields();
  }

  getGridOptions() {
    return { columns: 12, rows: "auto" };
  }

  getCardSize() {
    return 7;
  }

  renderCard() {
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        .content { display: grid; gap: 20px; padding: 16px; }
        .footer { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
        button {
          min-height: 44px; padding: 8px 18px; font: inherit; font-weight: 600;
          color: var(--text-primary-color, white); background: var(--primary-color);
          border: 0; border-radius: 22px; cursor: pointer;
        }
        button:disabled { opacity: .55; cursor: default; }
        [role=status] { overflow-wrap: anywhere; }
        .error { color: var(--error-color); }
      </style>
      <ha-card>
        <div class="content">
          <div id="fields"></div>
          <div class="footer">
            <button type="button" disabled>Create task</button>
            <span role="status" aria-live="polite"></span>
          </div>
        </div>
      </ha-card>`;
    this.card = root.querySelector("ha-card");
    this.fields = root.querySelector("#fields");
    this.button = root.querySelector("button");
    this.status = root.querySelector("[role=status]");
    this.button.addEventListener("click", () => this.submit());
  }

  updateSchema() {
    if (!this.metadata) return;
    const values = this.form.data;
    this.scheduleSignature = JSON.stringify([values.frequency_type, values.week_pattern]);
    this.form.schema = buildSchema(this.config, this.metadata, values);
  }

  async refreshFields() {
    if (!this.card || !this.homeAssistant) return;
    const fields = this.homeAssistant.services?.donetick?.create_task?.fields;
    if (!fields?.name) {
      this.button.disabled = true;
      this.showStatus("Waiting for the Donetick create_task action.");
      return;
    }

    if (!this.form) {
      if (this.loading) return;
      this.loading = true;
      this.showStatus("Loading task fields…");
      try {
        await loadForm();
        this.form = document.createElement("ha-form");
        this.form.data = structuredClone(this.config.defaults);
        this.form.computeLabel = (field) => field.title ?? field.name;
        this.form.computeHelper = (field) => field.helper;
        this.form.addEventListener("value-changed", (event) => {
          const values = event.detail.value;
          if (this.scheduleSignature !== JSON.stringify([values.frequency_type, values.week_pattern])) {
            this.updateSchema();
          }
        });
        this.fields.append(this.form);
        this.showStatus("");
      } catch (error) {
        this.showStatus(`Could not load Home Assistant’s form: ${error.message ?? error}`, true);
        return;
      } finally {
        this.loading = false;
      }
    }

    this.form.hass = this.homeAssistant;
    const currentFields = this.homeAssistant.services?.donetick?.create_task?.fields;
    if (currentFields !== this.serviceFields && currentFields?.name) {
      this.serviceFields = currentFields;
      this.metadata = nativeFields(currentFields);
      this.updateSchema();
    }
    this.button.disabled = Boolean(this.pending) || !currentFields?.name;
  }

  showStatus(message, error = false) {
    this.status.textContent = message;
    this.status.classList.toggle("error", error);
  }

  async submit() {
    if (this.button.disabled) return;
    let data;
    try {
      const { fields, sections, defaults, hiddenFields } = this.config;
      const editable = new Set([...fields, ...Object.values(sections).flat()]);
      for (const name of hiddenFields) editable.delete(name);
      const values = Object.fromEntries(
        Object.entries(this.form.data).filter(([name]) => editable.has(name)),
      );
      const fixed = Object.fromEntries(Object.entries(defaults).filter(([name]) => !editable.has(name)));
      data = buildActionData({ ...fixed, ...values }, this.metadata);
    } catch (error) {
      this.showStatus(error.message, true);
      return;
    }

    this.pending = true;
    this.button.disabled = true;
    this.form.disabled = true;
    this.showStatus("Creating task…");
    try {
      await this.homeAssistant.callService("donetick", "create_task", data);
      this.form.data = structuredClone(this.config.defaults);
      this.updateSchema();
      this.showStatus(`Created “${data.name}”.`);
    } catch (error) {
      this.showStatus(error.message ?? String(error), true);
    } finally {
      this.pending = false;
      this.form.disabled = false;
      this.refreshFields();
    }
  }
}

if (!customElements.get(cardType)) customElements.define(cardType, DonetickCreateTaskCard);
window.customCards ??= [];
if (!window.customCards.some(({ type }) => type === cardType)) {
  window.customCards.push({
    type: cardType,
    name: "Donetick Create Task",
    description: "Create a Donetick task from a dashboard.",
  });
}
