import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { localStore } from '../lib/storage';

export type ThemeChoice = 'system' | 'light' | 'dark';

const THEME_KEY = 'mirsad.theme';

interface ThemeValue {
  theme: ThemeChoice;
  /** The theme actually shown (system resolved via prefers-color-scheme). */
  resolved: 'light' | 'dark';
  setTheme(theme: ThemeChoice): void;
  cycle(): void;
}

const ThemeContext = createContext<ThemeValue | null>(null);

/** Applied synchronously so components that read CSS variables during render see the new theme. */
function applyTheme(choice: ThemeChoice): void {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  if (choice === 'system') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', choice);
}

function systemDark(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia('(prefers-color-scheme: dark)').matches
    : false;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeChoice>(() => {
    const stored = localStore.getItem(THEME_KEY);
    const initial: ThemeChoice = stored === 'light' || stored === 'dark' ? stored : 'system';
    applyTheme(initial);
    return initial;
  });
  const [isSystemDark, setSystemDark] = useState(systemDark);

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return undefined;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => setSystemDark(mq.matches);
    mq.addEventListener?.('change', onChange);
    return () => mq.removeEventListener?.('change', onChange);
  }, []);

  useEffect(() => applyTheme(theme), [theme]);

  const setTheme = useCallback((next: ThemeChoice) => {
    if (next === 'system') localStore.removeItem(THEME_KEY);
    else localStore.setItem(THEME_KEY, next);
    applyTheme(next);
    setThemeState(next);
  }, []);

  const resolved: 'light' | 'dark' = theme === 'system' ? (isSystemDark ? 'dark' : 'light') : theme;

  const value = useMemo<ThemeValue>(
    () => ({
      theme,
      resolved,
      setTheme,
      cycle: () => setTheme(theme === 'system' ? 'light' : theme === 'light' ? 'dark' : 'system'),
    }),
    [theme, resolved, setTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used inside <ThemeProvider>');
  return ctx;
}

/** Reads CSS custom properties (for chart libraries that need concrete colours). */
export function readCssVars<K extends string>(names: readonly K[]): Record<K, string> {
  const style = getComputedStyle(document.documentElement);
  const out = {} as Record<K, string>;
  for (const name of names) out[name] = style.getPropertyValue(`--${name}`).trim();
  return out;
}
