import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  formatCompact,
  formatDateTime,
  formatMs,
  formatNumber,
  formatRelative,
  type Lang,
  localeFor,
  type Numerals,
} from '../lib/format';
import { localStore } from '../lib/storage';
import { ar } from './ar';
import { en, type MessageKey } from './en';

export type { MessageKey } from './en';
export type { Lang, Numerals } from '../lib/format';

export const dictionaries: Record<Lang, Record<MessageKey, string>> = { en, ar };

const LANG_KEY = 'mirsad.lang';
const NUMERALS_KEY = 'mirsad.numerals';

export type Vars = Record<string, string | number>;

/** Replace `{name}` placeholders; unknown placeholders are left visible to surface bugs. */
export function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) => (name in vars ? String(vars[name]) : whole));
}

export function translate(lang: Lang, key: MessageKey, vars?: Vars): string {
  const template = dictionaries[lang][key] ?? dictionaries.en[key] ?? key;
  return interpolate(template, vars);
}

export function isMessageKey(key: string): key is MessageKey {
  return Object.prototype.hasOwnProperty.call(en, key);
}

export interface I18n {
  lang: Lang;
  dir: 'ltr' | 'rtl';
  locale: string;
  numerals: Numerals;
  setLang(lang: Lang): void;
  setNumerals(numerals: Numerals): void;
  t(key: MessageKey, vars?: Vars): string;
  /** Translate a dynamic key (e.g. `event.${type}`), falling back to `fallback`. */
  tx(key: string, fallback: string, vars?: Vars): string;
  fmtNumber(value: number | null | undefined, options?: Intl.NumberFormatOptions): string;
  fmtCompact(value: number | null | undefined): string;
  fmtPercent(fraction: number | null | undefined): string;
  fmtDateTime(value: number | string | null | undefined, options?: Intl.DateTimeFormatOptions): string;
  fmtRelative(value: number | string | null | undefined, nowMs?: number): string;
  fmtMs(value: number | null | undefined): string;
}

function initialLang(): Lang {
  const stored = localStore.getItem(LANG_KEY);
  if (stored === 'en' || stored === 'ar') return stored;
  if (typeof navigator !== 'undefined' && navigator.language?.toLowerCase().startsWith('ar')) return 'ar';
  return 'en';
}

export function hasStoredLang(): boolean {
  const stored = localStore.getItem(LANG_KEY);
  return stored === 'en' || stored === 'ar';
}

function initialNumerals(): Numerals {
  return localStore.getItem(NUMERALS_KEY) === 'arab' ? 'arab' : 'latn';
}

export function buildI18n(lang: Lang, numerals: Numerals, setLang: (l: Lang) => void, setNumerals: (n: Numerals) => void): I18n {
  const locale = localeFor(lang, numerals);
  return {
    lang,
    dir: lang === 'ar' ? 'rtl' : 'ltr',
    locale,
    numerals,
    setLang,
    setNumerals,
    t: (key, vars) => translate(lang, key, vars),
    tx: (key, fallback, vars) => (isMessageKey(key) ? translate(lang, key, vars) : interpolate(fallback, vars)),
    fmtNumber: (value, options) => formatNumber(locale, value, options),
    fmtCompact: (value) => formatCompact(locale, value),
    fmtPercent: (fraction) => formatNumber(locale, fraction, { style: 'percent', maximumFractionDigits: 1 }),
    fmtDateTime: (value, options) => formatDateTime(locale, value, options),
    fmtRelative: (value, nowMs) => formatRelative(locale, value, nowMs),
    fmtMs: (value) => formatMs(locale, value),
  };
}

const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ children, initial }: { children: ReactNode; initial?: Lang }) {
  const [lang, setLangState] = useState<Lang>(() => initial ?? initialLang());
  const [numerals, setNumeralsState] = useState<Numerals>(initialNumerals);

  const setLang = useCallback((next: Lang) => {
    localStore.setItem(LANG_KEY, next);
    setLangState(next);
  }, []);
  const setNumerals = useCallback((next: Numerals) => {
    localStore.setItem(NUMERALS_KEY, next);
    setNumeralsState(next);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    root.lang = lang;
    root.dir = lang === 'ar' ? 'rtl' : 'ltr';
  }, [lang]);

  const value = useMemo(() => buildI18n(lang, numerals, setLang, setNumerals), [lang, numerals, setLang, setNumerals]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used inside <I18nProvider>');
  return ctx;
}
