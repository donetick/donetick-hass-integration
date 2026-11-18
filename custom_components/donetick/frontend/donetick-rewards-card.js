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
    const rewards = Object.values(this._hass.states).filter(state =>
      state.entity_id.startsWith('sensor.') &&
      (!entry || String(state.attributes?.config_entry_id || '') === String(entry)) &&
      Number.isInteger(Number(state.attributes?.reward_id)) &&
      state.attributes?.description !== undefined);
    const balances = Object.values(this._hass.states).filter(state =>
      state.entity_id.startsWith('number.') &&
      (!entry || String(state.attributes?.config_entry_id || '') === String(entry)) &&
      state.attributes?.donetick_user_id !== undefined);

    this.shadowRoot.innerHTML = `<style>
      ha-card { padding: 12px; }
      h2 { margin: 0 0 8px; font-size: 20px; font-weight: 500; }
      .balances { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 8px; }
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
      ${balances.length ? `<div class="balances" aria-label="Point balances">${balances.map(state => {
        const name = state.attributes.friendly_name || state.entity_id;
        return `<span class="balance"><ha-icon icon="mdi:account-circle-outline" aria-hidden="true"></ha-icon><span>${this.escape(name)}: <strong>${this.escape(state.state)}</strong></span></span>`;
      }).join('')}</div>` : ''}
      <div class="rewards">${rewards.length ? rewards.map(state => {
        const rewardId = Number(state.attributes.reward_id);
        const configEntryId = state.attributes.config_entry_id || entry;
        const key = `${configEntryId}/${rewardId}`;
        const requested = this._requested?.has(key);
        const name = state.attributes.friendly_name || state.entity_id;
        const description = state.attributes.description || '';
        const points = state.state;
        return `<section class="row">
          <div class="reward"><strong class="name">${this.escape(name)}</strong>${description ? `<p class="description">${this.escape(description)}</p>` : ''}</div>
          <span class="task-points" title="${this.escape(points)} points"><ha-icon icon="mdi:star-outline" aria-hidden="true"></ha-icon>${this.escape(points)}</span>
          <button type="button" data-key="${this.escape(key)}" data-reward="${rewardId}" data-entry="${this.escape(configEntryId || '')}" ${requested ? 'disabled' : ''}>${requested ? 'Requested' : 'Request'}</button>
        </section>`;
      }).join('') : '<p class="empty">No active rewards found. Check the Donetick connection and API token permissions.</p>'}</div>
    </ha-card>`;

    this.shadowRoot.querySelectorAll('button[data-reward]').forEach(button => button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const serviceData = { reward_id: Number(button.dataset.reward) };
        if (button.dataset.entry) serviceData.config_entry_id = button.dataset.entry;
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
    const entries = Object.values(this._hass.states)
      .filter(state => state.entity_id.startsWith('sensor.') && state.attributes?.config_entry_id && state.attributes?.reward_id !== undefined)
      .map(state => state.attributes.config_entry_id);
    const unique = [...new Set(entries)];
    this.innerHTML = `<label>Title<input id="title" value="${this.escape(this.config.title || '')}"></label><label>Donetick integration<select id="entry"><option value="">All integrations</option>${unique.map(id => `<option value="${this.escape(id)}" ${this.config.config_entry_id === id ? 'selected' : ''}>${this.escape(id)}</option>`).join('')}</select></label>`;
    this.querySelector('#title').addEventListener('change', event => this.change({ title: event.target.value }));
    this.querySelector('#entry').addEventListener('change', event => this.change({ config_entry_id: event.target.value || undefined }));
  }

  change(update) {
    this.config = { ...this.config, ...update };
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: this.config }, bubbles: true, composed: true }));
  }

  escape(value) {
    return String(value).replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[char]));
  }
}

if (!customElements.get('donetick-rewards-card')) customElements.define('donetick-rewards-card', DonetickRewardsCard);
if (!customElements.get('donetick-rewards-card-editor')) customElements.define('donetick-rewards-card-editor', DonetickRewardsCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === 'donetick-rewards-card')) {
  window.customCards.push({ type: 'donetick-rewards-card', name: 'Donetick Rewards', description: 'Browse and request Donetick rewards' });
}
