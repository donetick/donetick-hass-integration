import assert from 'node:assert/strict';

let signalWaiting;
const waiting = new Promise(resolve => { signalWaiting = resolve; });
function registry(onWait = () => {}) {
  const definitions = new Map();
  const pending = new Map();
  return {
    get: name => definitions.get(name),
    define(name, constructor) {
      assert.equal(definitions.has(name), false, `Duplicate registration: ${name}`);
      definitions.set(name, constructor);
      pending.get(name)?.(constructor);
    },
    whenDefined(name) {
      onWait(name);
      if (definitions.has(name)) return Promise.resolve(definitions.get(name));
      return new Promise(resolve => pending.set(name, resolve));
    }
  };
}

// Reproduce an extra module loading before HA's registry polyfill.
const nativeRegistry = registry(name => {
  assert.equal(name, 'home-assistant');
  signalWaiting();
});
globalThis.customElements = nativeRegistry;
globalThis.HTMLElement = class NativeHTMLElement {};
globalThis.window = {};
const cardUrl = new URL('../custom_components/donetick/frontend/donetick-user-todo-card.js', import.meta.url);
const loading = import(cardUrl);
let timeout;
try {
  await Promise.race([
    waiting,
    loading.then(() => { throw new Error('Card loaded before HA initialized'); }),
    new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error('Startup wait not reached')), 2000); })
  ]);
} finally {
  clearTimeout(timeout);
}
assert.equal(nativeRegistry.get('donetick-user-todo-card'), undefined);
assert.equal(window.customCards, undefined);

// HA replaces these globals, then defines home-assistant in the native registry
// as well as its new scoped registry. The old whenDefined promise now resolves.
const scopedRegistry = registry();
const PatchedHTMLElement = class {};
globalThis.customElements = scopedRegistry;
globalThis.HTMLElement = PatchedHTMLElement;
const HomeAssistant = class extends PatchedHTMLElement {};
scopedRegistry.define('home-assistant', HomeAssistant);
nativeRegistry.define('home-assistant', HomeAssistant);
await loading;
for (const name of ['donetick-user-todo-card', 'donetick-user-todo-editor']) {
  const constructor = scopedRegistry.get(name);
  assert.ok(constructor, `${name} registered in the final registry`);
  assert.equal(Object.getPrototypeOf(constructor.prototype), PatchedHTMLElement.prototype);
  assert.equal(nativeRegistry.get(name), undefined);
}
assert.equal(window.customCards.length, 1);

// Loading through a manual resource after startup remains safe and idempotent.
const originalCard = scopedRegistry.get('donetick-user-todo-card');
await import(`${cardUrl}?manual-resource`);
assert.equal(scopedRegistry.get('donetick-user-todo-card'), originalCard);
assert.equal(window.customCards.length, 1);
console.log('Frontend startup race regression passed');
