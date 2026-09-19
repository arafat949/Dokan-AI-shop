// One shared object holds what the page knows. Modules subscribe to re-draw when it changes.

export const state = {
  config: {},
  products: [],
  categories: [],
  cart: { items: [], total: 0, count: 0 },
};

const listeners = new Set();

export function subscribe(listener) {
  listeners.add(listener);
}

export function update(changes) {
  Object.assign(state, changes);
  listeners.forEach((listener) => listener(state));
}
