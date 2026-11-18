class DonetickRewardsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) { this.config = config; }
  set hass(hass) { this._hass = hass; this.render(); }
  getCardSize() { return 3; }

  render() {
    if (!this._hass || !this.config) return;

    const entry = this.config.config_entry_id || this.config.entry_id;
    const userId = this.config.user_id === undefined || this.config.user_id === '' ? undefined : Number(this.config.user_id);
    const rewards = Object.values(this._hass.states).filter(state =>
      state.entity_id.startsWith('sensor.') &&
      (!entry || String(state.attributes?.config_entry_id || '') === String(entry)) &&
      Number.isInteger(Number(state.attributes?.reward_id)) &&
      state.attributes?.description !== undefined);
    const balances = Object.values(this._hass.states).filter(state =>
      state.entity_id.startsWith('number.') &&
      (!entry || String(state.attributes?.config_entry_id || '') === String(entry)) &&
      (userId === undefined || Number(state.attributes?.donetick_user_id) === userId) &&
      state.attributes?.donetick_user_id !== undefined);
    const selectedMember = Object.values(this._hass.states)
      .filter(state => state.entity_id.startsWith('todo.') && (!entry || String(state.attributes?.config_entry_id || '') === String(entry)))
      .flatMap(state => state.attributes?.circle_members || [])
      .find(member => Number(member.user_id) === userId);
    const claimantName = selectedMember?.display_name || selectedMember?.username || `User ${userId}`;

    this.shadowRoot.innerHTML = `<style>
      ha-card { padding: 12px; }
      h2 { margin: 0 0 8px; font-size: 20px; font-weight: 500; }
      .balances { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 8px; }
      .claimant { margin: 0 0 8px; color: var(--secondary-text-color); font-size: 13px; }
      .balance { display: inline-flex; align-items: center; gap: 4px; min-height: 24px; padding: 0 7px; border-radius: 12px; background: var(--secondary-background-color); color: var(--secondary-text-color); font-size: 12px; }
      .balance ha-icon { --mdc-icon-size: 14px; }
      .row { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-top: 1px solid var(--divider-color); }
      .reward { display: flex; flex: 1; min-width: 0; flex-direction: column; align-items: flex-start; justify-content: center; gap: 2px; min-height: 44px; color: var(--primary-text-color); }
      .name { overflow-wrap: anywhere; line-height: 20px; }
      .description { margin: 0; color: var(--secondary-text-color); font-size: 12px; line-height: 16px; overflow-wrap: anywhere; }
      .task-points { display: inline-flex; flex-shrink: 0; align-items: center; gap: 3px; padding: 0 5px; border-radius: 10px; background: var(--secondary-background-color); color: var(--secondary-text-color); font-size: 11px; line-height: 18px; white-space: nowrap; }
      .task-points ha-icon { --mdc-icon-size: 12px; }
      button { display: inline-flex; flex-shrink: 0; align-items: center; justify-content: center; gap: 6px; box-sizing: border-box; min-width: 44px; min-height: 44px; padding: 5px 8px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--primary-color); font: inherit; font-size: 12px; cursor: pointer; }
      button:hover:not(:disabled) { background: var(--secondary-background-color); }
      button:focus-visible { outline: 2px solid var(--primary-color); }
      button:disabled { opacity: .5; cursor: default; }
      .empty { margin: 8px 0 0; color: var(--secondary-text-color); }
      .error { margin: 8px 0 0; color: var(--error-color); }
    </style>
    <ha-card>
      <h2>${this.escape(this.config.title || 'Donetick rewards')}</h2>
      ${userId === undefined ? '<p class="empty">Choose who this card is for in the card settings.</p>' : ''}
      ${userId !== undefined ? `<p class="claimant">Claiming as <strong>${this.escape(claimantName)}</strong></p>` : ''}
      ${balances.length ? `<div class="balances" aria-label="Point balances">${balances.map(state => {
        const name = state.attributes.friendly_name || state.entity_id;
        return `<span class="balance"><ha-icon icon="mdi:account-circle-outline" aria-hidden="true"></ha-icon><span>${this.escape(name)}: <strong>${this.escape(state.state)}</strong></span></span>`;
      }).join('')}</div>` : ''}
      <div class="rewards">${rewards.length ? rewards.map(state => {
        const rewardId = Number(state.attributes.reward_id);
        const configEntryId = state.attributes.config_entry_id || entry;
        const key = `${configEntryId}/${userId || 'owner'}/${rewardId}`;
        const requested = this._requested?.has(key);
        const name = state.attributes.friendly_name || state.entity_id;
        const description = state.attributes.description || '';
        const points = state.state;
        return `<section class="row">
          <div class="reward"><strong class="name">${this.escape(name)}</strong>${description ? `<p class="description">${this.escape(description)}</p>` : ''}</div>
          <span class="task-points" title="${this.escape(points)} points"><ha-icon icon="mdi:star-outline" aria-hidden="true"></ha-icon>${this.escape(points)}</span>
          <button type="button" data-key="${this.escape(key)}" data-reward="${rewardId}" data-entry="${this.escape(configEntryId || '')}" data-user="${userId || ''}" ${requested || userId === undefined ? 'disabled' : ''}>${requested ? 'Requested' : 'Request'}</button>
        </section>`;
      }).join('') : '<p class="empty">No active rewards found. Check the Donetick connection and API token permissions.</p>'}</div>
    </ha-card>`;

    this.shadowRoot.querySelectorAll('button[data-reward]').forEach(button => button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const serviceData = { reward_id: Number(button.dataset.reward) };
        if (button.dataset.entry) serviceData.config_entry_id = button.dataset.entry;
        if (button.dataset.user) serviceData.user_id = Number(button.dataset.user);
        await this._hass.callService('donetick', 'redeem_reward', serviceData);
        this._requested = this._requested || new Set();
        this._requested.add(button.dataset.key);
        this.render();
      } catch (error) {
        button.disabled = false;
        button.textContent = 'Retry';
        this._hass.callService('persistent_notification', 'create', {
          title: 'Donetick reward', message: error.message || 'Could not request reward',
        });
      }
    }));
  }

  escape(value) {
    return String(value).replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[char]));
  }

  static getConfigElement() { return document.createElement('donetick-rewards-card-editor'); }
  static getStubConfig() { return {}; }
}

class DonetickRewardsCardEditor extends HTMLElement {
  setConfig(config) { this.config = { ...config }; this.render(); }
  set hass(hass) { this._hass = hass; this.render(); }

  render() {
    if (!this._hass || !this.config) return;
    const states = Object.values(this._hass.states);
    const rewards = states.filter(state => state.entity_id.startsWith('sensor.') && state.attributes?.config_entry_id && state.attributes?.reward_id !== undefined);
    const lists = states.filter(state => state.entity_id.startsWith('todo.') && Array.isArray(state.attributes?.circle_members));
    const entryIds = [...new Set(rewards.map(state => String(state.attributes.config_entry_id)))];
    const selectedEntry = this.config.config_entry_id || (entryIds.length === 1 ? entryIds[0] : '');
    const matchingLists = lists.filter(state => !selectedEntry || String(state.attributes.config_entry_id) === selectedEntry);
    const members = matchingLists
      .flatMap(state => state.attributes.circle_members || [])
      .filter(member => member.is_active !== false)
      .reduce((unique, member) => unique.some(item => Number(item.user_id) === Number(member.user_id)) ? unique : [...unique, member], []);
    const mappings = matchingLists.reduce((mapping, state) => ({ ...mapping, ...(state.attributes.donetick_user_mapping || {}) }), {});
    const personOptions = Object.entries(mappings)
      .flatMap(([haUserId, donetickUserId]) => {
        const person = states.find(state => state.entity_id.startsWith('person.') && String(state.attributes?.user_id || '') === String(haUserId));
        return person ? [{ value: Number(donetickUserId), label: person.attributes.friendly_name || person.entity_id }] : [];
      })
      .filter(option => Number.isInteger(option.value) && option.value > 0)
      .reduce((unique, option) => unique.some(item => item.value === option.value) ? unique : [...unique, option], []);
    const userOptions = personOptions.length ? personOptions : members.map(member => ({ value: Number(member.user_id), label: member.display_name || member.username || `User ${member.user_id}` }));
    this._schema = [
      { name: 'title', selector: { text: {} } },
      { name: 'config_entry_id', required: entryIds.length > 1, selector: { select: { mode: 'dropdown', options: entryIds.map(id => ({ value: id, label: id })) } } },
      { name: 'user_id', required: true, selector: { select: { mode: 'dropdown', options: userOptions } } },
    ];
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    if (!this._form) {
      this.shadowRoot.innerHTML = '<style>:host{display:block}ha-form{display:block}</style><ha-form></ha-form>';
      this._form = this.shadowRoot.querySelector('ha-form');
      this._form.computeLabel = schema => ({ title: 'Card title', config_entry_id: 'Donetick integration', user_id: 'Claim rewards for' }[schema.name] || schema.name);
      this._form.computeHelper = schema => ({ config_entry_id: 'Choose the Donetick circle shown on this card.', user_id: 'Mapped Home Assistant people appear here when available; otherwise choose a circle member. Requests use this member’s points.' }[schema.name]);
      this._form.addEventListener('value-changed', event => {
        event.stopPropagation();
        const values = event.detail.value || {};
        const updated = { ...this.config };
        const entryChanged = values.config_entry_id !== (this.config.config_entry_id || selectedEntry);
        for (const key of ['title', 'config_entry_id', 'user_id']) {
          const value = values[key];
          if (value === '' || value === undefined || value === null) delete updated[key];
          else updated[key] = key === 'user_id' ? Number(value) : value;
        }
        if (entryChanged) delete updated.user_id;
        if (JSON.stringify(updated) !== JSON.stringify(this.config)) {
          this.config = updated;
          this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: updated }, bubbles: true, composed: true }));
        }
      });
    }
    const schemaSignature = JSON.stringify(this._schema);
    if (this._schemaSignature !== schemaSignature) {
      this._schemaSignature = schemaSignature;
      this._form.schema = this._schema;
    }
    if (this._form.hass !== this._hass) this._form.hass = this._hass;
    const formData = { title: this.config.title || '', config_entry_id: this.config.config_entry_id || selectedEntry, user_id: this.config.user_id === undefined ? undefined : Number(this.config.user_id) };
    const dataSignature = JSON.stringify(formData);
    if (this._dataSignature !== dataSignature) {
      this._dataSignature = dataSignature;
      this._form.data = formData;
    }
  }

  change(update) {
    this.config = { ...this.config, ...update };
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: this.config }, bubbles: true, composed: true }));
  }

}

if (!customElements.get('donetick-rewards-card')) customElements.define('donetick-rewards-card', DonetickRewardsCard);
if (!customElements.get('donetick-rewards-card-editor')) customElements.define('donetick-rewards-card-editor', DonetickRewardsCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === 'donetick-rewards-card')) {
  window.customCards.push({ type: 'donetick-rewards-card', name: 'Donetick Rewards', description: 'Browse and request Donetick rewards' });
}
