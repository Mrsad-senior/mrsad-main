/** Web Storage access that never throws (private mode, blocked storage, SSR/tests). */

export interface KeyValueStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

function wrap(pick: () => Storage | undefined): KeyValueStore {
  return {
    getItem(key) {
      try {
        return pick()?.getItem(key) ?? null;
      } catch {
        return null;
      }
    },
    setItem(key, value) {
      try {
        pick()?.setItem(key, value);
      } catch {
        /* storage full or blocked: the in-memory state still works */
      }
    },
    removeItem(key) {
      try {
        pick()?.removeItem(key);
      } catch {
        /* ignore */
      }
    },
  };
}

export const localStore: KeyValueStore = wrap(() => (typeof window !== 'undefined' ? window.localStorage : undefined));
export const sessionStore: KeyValueStore = wrap(() => (typeof window !== 'undefined' ? window.sessionStorage : undefined));

export function memoryStore(initial: Record<string, string> = {}): KeyValueStore {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
    removeItem: (key) => void data.delete(key),
  };
}
