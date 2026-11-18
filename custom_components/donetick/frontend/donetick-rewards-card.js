class DonetickRewardsCard extends HTMLElement {
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
      state.entity_id.startsWith('number.') && (!entry || String(state.attributes?.config_entry_id || '') === String(entry)) &&
      state.attributes?.donetick_user_id !== undefined);
    this.innerHTML = `<ha-card><div class="card-content"><h2>${this.config.title || 'Donetick rewards'}</h2>${balances.length ? `<div class="balances">${balances.map(state => `<span>${this.escape(state.attributes.friendly_name || state.entity_id)}: <strong>${state.state} points</strong></span>`).join('')}</div>` : ''}${
      rewards.length ? rewards.map(state => {
        const key = `${state.attributes.config_entry_id}/${state.attributes.reward_id}`;
        const requested = this._requested?.has(key);
        return `<section><div><strong>${this.escape(state.attributes.friendly_name || state.entity_id)}</strong><div>${this.escape(state.attributes.description || '')}</div></div><div class="price">${state.state} points</div><mwc-button data-key="${this.escape(key)}" data-reward="${state.attributes.reward_id}" data-entry="${this.escape(entry || state.attributes.config_entry_id)}" ${requested ? 'disabled' : ''}>${requested ? 'Requested' : 'Request'}</mwc-button></section>`;
      }).join('') : '<p>No active rewards found. Check the Donetick connection and API token permissions.</p>'
    }</div></ha-card><style>section{display:flex;align-items:center;gap:10px;padding:12px 0;border-top:1px solid var(--divider-color)}section>div:first-child{flex:1}.price{white-space:nowrap;color:var(--secondary-text-color)}h2{font-size:1.2em;margin:0 0 12px}.balances{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px;color:var(--secondary-text-color)}.card-content p{color:var(--secondary-text-color)}</style>`;
    this.querySelectorAll('mwc-button').forEach(button => button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const serviceData = {reward_id: Number(button.dataset.reward)};
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
  escape(value) { return String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char])); }
  static getConfigElement() { return document.createElement('donetick-rewards-card-editor'); }
  static getStubConfig() { return {}; }
}

class DonetickRewardsCardEditor extends HTMLElement {
  setConfig(config) { this.config = {...config}; this.render(); }
  set hass(hass) { this._hass = hass; this.render(); }
  render() {
    if (!this._hass || !this.config) return;
    const entries = Object.values(this._hass.states).filter(state => state.entity_id.startsWith('sensor.') && state.attributes?.config_entry_id && state.attributes?.reward_id !== undefined).map(state => state.attributes.config_entry_id);
    const unique = [...new Set(entries)];
    this.innerHTML = `<label>Title<input id="title" value="${this.config.title || ''}"></label><label>Donetick integration<select id="entry"><option value="">All integrations</option>${unique.map(id => `<option value="${id}" ${this.config.config_entry_id === id ? 'selected' : ''}>${id}</option>`).join('')}</select></label>`;
    this.querySelector('#title').addEventListener('change', event => this.change({title:event.target.value}));
    this.querySelector('#entry').addEventListener('change', event => this.change({config_entry_id:event.target.value || undefined}));
  }
  change(update) { this.config={...this.config,...update}; this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:this.config},bubbles:true,composed:true})); }
}

if (!customElements.get('donetick-rewards-card')) customElements.define('donetick-rewards-card',DonetickRewardsCard);
if (!customElements.get('donetick-rewards-card-editor')) customElements.define('donetick-rewards-card-editor',DonetickRewardsCardEditor);
window.customCards=window.customCards||[];
if (!window.customCards.some(card=>card.type==='donetick-rewards-card')) window.customCards.push({type:'donetick-rewards-card',name:'Donetick Rewards',description:'Browse and request Donetick rewards'});
