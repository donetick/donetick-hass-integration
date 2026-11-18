const editorTag = "donetick-create-task-editor";
const mainGroup = "main";
const availableGroup = "available";
const appearance = [
  { name: "title", title: "Card title", selector: { text: {} } },
  { name: "submit_label", title: "Submit button text", selector: { text: {} } },
  { name: "show_help", title: "Show detailed field help", selector: { boolean: {} } },
];
const arrowControls = [["up", -1], ["down", 1]];

function element(tag, text) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  return node;
}

function iconButton(icon, label, callback, disabled = false) {
  const button = element("ha-icon-button");
  button.label = label;
  button.disabled = disabled;
  const glyph = element("ha-icon");
  glyph.icon = `mdi:${icon}`;
  button.append(glyph);
  button.addEventListener("click", callback);
  return button;
}

function panel(header, expanded = false) {
  const node = element("details");
  node.open = expanded;
  node.append(element("summary", header));
  return node;
}

function populateOnOpen(section, populate) {
  section.firstElementChild.addEventListener("click", (event) => {
    if (!event.defaultPrevented && !section.open) populate();
  });
  section.addEventListener("toggle", () => {
    if (section.open) populate();
  });
  if (section.open) populate();
}

export function registerEditor(configure, nativeFields) {
  if (customElements.get(editorTag)) return editorTag;

  class DonetickCreateTaskEditor extends HTMLElement {
    setConfig(config) {
      configure(config);
      if (!this.shadowRoot) this.renderEditor();
      if (JSON.stringify(config) === JSON.stringify(this.config)) return;
      this.config = config;
      this.pendingDefaults = new Set();
      this.refresh();
    }

    set hass(hass) {
      this.homeAssistant = hass;
      const fields = hass.services?.donetick?.create_task?.fields;
      if (fields !== this.serviceFields) {
        this.serviceFields = fields;
        this.metadata = nativeFields(fields ?? {});
        if (this.config) this.refresh();
      }
      if (this.appearanceForm) this.appearanceForm.hass = hass;
      if (this.defaultsSection?.open) {
        for (const { selector } of this.defaultRows.values()) {
          if (selector) selector.hass = hass;
        }
      }
    }

    renderEditor() {
      const root = this.attachShadow({ mode: "open" });
      root.innerHTML = `
        <style>
          :host {
            display: grid;
            grid-template-columns: minmax(0, 1fr);
            gap: 16px;
            min-width: 0;
          }
          ha-form, ha-selector, details { display: block; min-width: 0; }
          .panel {
            border: 1px solid var(--divider-color);
            border-radius: var(--ha-card-border-radius, 12px);
          }
          summary {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            min-height: 44px;
            padding-inline: 12px;
            cursor: pointer;
            list-style: none;
            font-weight: 500;
          }
          summary::-webkit-details-marker { display: none; }
          summary::after {
            content: "";
            box-sizing: border-box;
            width: 8px;
            height: 8px;
            flex: none;
            margin-inline-end: 4px;
            border: solid var(--secondary-text-color);
            border-width: 0 2px 2px 0;
            transform: rotate(45deg);
          }
          details[open] > summary::after { transform: rotate(225deg); }
          .groups { display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; padding: 0 8px 8px; }
          .group-list { padding-inline: 24px 8px; }
          .defaults {
            display: grid;
            grid-template-columns: minmax(0, 1fr);
            gap: 12px;
            padding-block-end: 12px;
            padding-inline: 24px 12px;
          }
          .default-picker { display: grid; gap: 6px; color: var(--secondary-text-color); }
          .default-picker select {
            width: 100%;
            min-height: 44px;
            padding: 8px;
            font: inherit;
            color: var(--primary-text-color);
            background: var(--card-background-color);
            border: 1px solid var(--divider-color);
            border-radius: 8px;
          }
          .row {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            align-items: center;
            gap: 8px;
            min-width: 0;
            min-height: 44px;
            padding-block: 4px;
          }
          .row + .row { border-top: 1px solid var(--divider-color); }
          .field-label { overflow-wrap: anywhere; }
          .row[data-hidden] .field-label { color: var(--secondary-text-color); }
          .actions { display: flex; align-items: center; }
          ha-icon-button {
            --ha-icon-button-size: 40px;
            color: var(--secondary-text-color);
          }
          ha-icon { --mdc-icon-size: 20px; }
          .empty { color: var(--secondary-text-color); padding-block: 8px; }
          .status { color: var(--error-color); }
          .status:empty { display: none; }
        </style>
        <ha-form id="appearance"></ha-form>
        <details class="panel" open>
          <summary>Field layout</summary>
          <div class="groups" id="layout"></div>
        </details>
        <details class="panel" id="defaults-section">
          <summary>Default values</summary>
          <div class="defaults" id="defaults"></div>
        </details>
        <div class="status" role="status"></div>`;

      this.appearanceForm = root.querySelector("#appearance");
      this.appearanceForm.schema = appearance;
      this.appearanceForm.computeLabel = (field) => field.title;
      this.appearanceForm.addEventListener("value-changed", (event) => {
        const { title, submit_label, show_help } = event.detail.value;
        this.commit({ title: title || undefined, submit_label: submit_label || undefined, show_help });
      });
      this.layout = root.querySelector("#layout");
      this.defaultsPanel = root.querySelector("#defaults");
      this.defaultsSection = root.querySelector("#defaults-section");
      this.defaultRows = new Map();
      populateOnOpen(this.defaultsSection, () => {
        if (this.defaultsDirty) this.renderDefaults();
      });
      this.status = root.querySelector(".status");
    }

    commit(changes) {
      const config = { ...this.config, ...changes };
      for (const key of Object.keys(changes)) {
        if (config[key] === undefined) delete config[key];
      }
      try {
        configure(config);
      } catch (error) {
        this.status.textContent = error.message;
        return false;
      }
      this.status.textContent = "";
      if (JSON.stringify(config) === JSON.stringify(this.config)) return true;
      this.config = config;
      this.dispatchEvent(new CustomEvent("config-changed", {
        detail: { config }, bubbles: true, composed: true,
      }));
      return true;
    }

    refresh() {
      const { title, submit_label, show_help } = this.config;
      this.appearanceForm.hass = this.homeAssistant;
      this.appearanceForm.data = { title, submit_label, show_help: Boolean(show_help) };
      this.renderLayout();
      this.defaultsDirty = true;
      if (this.defaultsSection.open) this.renderDefaults();
    }

    groups() {
      const { fields, sections } = configure(this.config);
      const groups = [
        { id: mainGroup, title: "Main fields", fields },
        ...Object.entries(sections).map(([title, names]) => ({
          id: `section:${title}`, title, fields: names,
        })),
      ];
      const placed = new Set(groups.flatMap((group) => group.fields));
      const available = Object.keys(this.metadata ?? {}).filter((name) => !placed.has(name));
      if (available.length) groups.push({ id: availableGroup, title: "Available fields", fields: available });
      return groups;
    }

    saveGroups(groups) {
      return this.commit({
        fields: groups[0].fields,
        sections: Object.fromEntries(groups.filter(({ id }) => id !== mainGroup && id !== availableGroup)
          .map(({ title, fields }) => [title, fields])),
      });
    }

    addField(name, groups) {
      const { sections } = configure({});
      const category = Object.entries(sections).find(([, fields]) => fields.includes(name))?.[0];
      const destination = groups.find(({ id }) => id === `section:${category}`) ?? groups[0];
      destination.fields = [...destination.fields, name];
      if (this.saveGroups(groups)) this.renderLayout();
    }

    renderLayout() {
      const expanded = new Map(Array.from(this.layout.children, (node) => [node.dataset.group, node.open]));
      const groups = this.groups();
      this.syncNameVisibility = undefined;
      this.layout.replaceChildren();

      for (const group of groups) {
        const section = panel(group.title, expanded.get(group.id) ?? group.id === mainGroup);
        section.dataset.group = group.id;
        populateOnOpen(section, () => {
          if (section.childElementCount === 1) section.append(this.renderGroup(group, groups));
        });
        this.layout.append(section);
      }
    }

    renderGroup(group, groups) {
      const list = element("div");
      list.className = "group-list";
      if (!group.fields.length) {
        const empty = element("div", "No fields in this section.");
        empty.className = "empty";
        list.append(empty);
        return list;
      }

      const controls = new Map();
      const syncOrder = () => group.fields.forEach((name, index) => {
        const entry = controls.get(name);
        entry.up.disabled = index === 0;
        entry.down.disabled = index === group.fields.length - 1;
      });

      for (const name of group.fields) {
        const title = this.metadata?.[name]?.name ?? name;
        const row = element("div");
        row.className = "row";
        const label = element("span", title);
        label.className = "field-label";
        const actions = element("div");
        actions.className = "actions";

        if (group.id === availableGroup) {
          actions.append(iconButton("plus", `Add ${title}`, () => this.addField(name, groups)));
        } else {
          const entry = { row };
          for (const [direction, offset] of arrowControls) {
            entry[direction] = iconButton(`arrow-${direction}`, `Move ${title} ${direction}`, () => {
              const position = group.fields.indexOf(name);
              const next = position + offset;
              if (next < 0 || next >= group.fields.length) return;
              const previous = group.fields;
              const fields = [...previous];
              [fields[position], fields[next]] = [fields[next], fields[position]];
              group.fields = fields;
              if (!this.saveGroups(groups)) {
                group.fields = previous;
                return;
              }
              const neighbor = controls.get(previous[next]).row;
              // Move the sibling so the focused arrow stays attached.
              if (offset < 0) list.insertBefore(neighbor, row.nextElementSibling);
              else list.insertBefore(neighbor, row);
              syncOrder();
            });
            actions.append(entry[direction]);
          }

          const visibility = iconButton("eye-outline", "", () => {
            const hiddenFields = new Set(this.config.hidden_fields ?? []);
            if (hiddenFields.has(name)) hiddenFields.delete(name);
            else hiddenFields.add(name);
            if (this.commit({ hidden_fields: [...hiddenFields] })) syncVisibility();
          });
          const syncVisibility = () => {
            const hidden = this.config.hidden_fields?.includes(name) ?? false;
            row.toggleAttribute("data-hidden", hidden);
            visibility.label = `${hidden ? "Show" : "Hide"} ${title}`;
            visibility.firstElementChild.icon = hidden ? "mdi:eye-off-outline" : "mdi:eye-outline";
            visibility.disabled = name === "name" && !this.config.defaults?.name?.trim?.();
          };
          if (name === "name") this.syncNameVisibility = syncVisibility;
          syncVisibility();
          actions.append(visibility);
          controls.set(name, entry);
        }

        row.append(label, actions);
        list.append(row);
      }
      if (group.id !== availableGroup) syncOrder();
      return list;
    }

    renderDefaults() {
      if (!this.homeAssistant) return;
      this.defaultsDirty = false;
      if (!this.defaultPicker) {
        const label = element("label", "Add a default");
        label.className = "default-picker";
        this.defaultPicker = element("select");
        this.defaultPicker.addEventListener("change", () => {
          if (!this.defaultPicker.value) return;
          this.pendingDefaults.add(this.defaultPicker.value);
          this.renderDefaults();
        });
        label.append(this.defaultPicker);
        this.defaultsPanel.append(label);
      }

      const defaults = this.config.defaults ?? {};
      const names = new Set([...Object.keys(defaults), ...this.pendingDefaults]);
      const metadata = this.metadata ?? {};
      for (const [name, entry] of this.defaultRows) {
        if (!names.has(name)) {
          entry.row.remove();
          this.defaultRows.delete(name);
        }
      }

      const available = Object.entries(metadata).filter(([name]) => !names.has(name));
      const choices = JSON.stringify(available.map(([name, field]) => [name, field.name]));
      if (choices !== this.defaultChoices) {
        const placeholder = element("option", "Choose a field");
        placeholder.value = "";
        const options = available.map(([name, field]) => {
          const choice = element("option", field.name ?? name);
          choice.value = name;
          return choice;
        });
        this.defaultPicker.replaceChildren(placeholder, ...options);
        this.defaultPicker.disabled = !options.length;
        this.defaultChoices = choices;
      }
      this.defaultPicker.value = "";

      for (const name of names) {
        const field = metadata[name];
        let entry = this.defaultRows.get(name);
        if (!entry || entry.field !== field) {
          const previous = entry?.row;
          entry = this.createDefaultRow(name, field);
          if (previous) previous.replaceWith(entry.row);
          else this.defaultsPanel.append(entry.row);
          this.defaultRows.set(name, entry);
        }
        if (entry.selector) {
          entry.selector.hass = this.homeAssistant;
          if (entry.selector.value !== defaults[name]) entry.selector.value = defaults[name];
        }
      }
    }

    createDefaultRow(name, field) {
      const row = element("div");
      row.className = "row";
      const title = field?.name ?? name;
      let selector;
      if (field) {
        selector = element("ha-selector");
        selector.name = name;
        selector.label = title;
        selector.selector = field.selector ?? { text: {} };
        selector.addEventListener("value-changed", (event) => {
          const { value } = event.detail;
          const next = { ...this.config.defaults };
          if (value === undefined || value === "") delete next[name];
          else next[name] = value;
          this.commit({ defaults: next });
          selector.value = this.config.defaults?.[name];
          if (name === "name") this.syncNameVisibility?.();
        });
        row.append(selector);
      } else {
        const label = element("span", title);
        label.className = "field-label";
        row.append(label);
      }

      row.append(iconButton("close", `Clear the default for ${title}`, () => {
        const next = { ...this.config.defaults };
        delete next[name];
        if (this.commit({ defaults: next })) {
          this.pendingDefaults.delete(name);
          if (name === "name") this.syncNameVisibility?.();
          this.renderDefaults();
        }
      }));
      return { row, field, selector };
    }
  }

  customElements.define(editorTag, DonetickCreateTaskEditor);
  return editorTag;
}
