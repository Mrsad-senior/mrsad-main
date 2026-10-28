/** Locale-aware formatting helpers (pure; the i18n provider binds the locale). */
import type { Risk } from '../api/types';

export type Lang = 'en' | 'ar';
export type Numerals = 'latn' | 'arab';

/**
 * BCP 47 locale for Intl. Arabic keeps the Gregorian calendar (ar-SA defaults to
 * Umm al-Qura) so audit timestamps line up with the English UI and exports.
 */
export function localeFor(lang: Lang, numerals: Numerals = 'latn'): string {
  return lang === 'ar' ? `ar-SA-u-ca-gregory-nu-${numerals}` : 'en-GB';
}

/** Accepts epoch seconds (API), epoch milliseconds, numeric strings or ISO strings. */
export function toDate(value: number | string | null | undefined): Date | null {
  if (value === null || value === undefined || value === '') return null;
  let n: number;
  if (typeof value === 'number') n = value;
  else if (/^-?\d+(\.\d+)?$/.test(value.trim())) n = Number(value);
  else {
    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? null : new Date(parsed);
  }
  if (!Number.isFinite(n)) return null;
  return new Date(Math.abs(n) < 1e12 ? n * 1000 : n);
}

export function formatNumber(locale: string, value: number | null | undefined, options?: Intl.NumberFormatOptions): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '–';
  return new Intl.NumberFormat(locale, options).format(value);
}

export function formatCompact(locale: string, value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '–';
  if (Math.abs(value) < 10_000) return formatNumber(locale, value);
  return new Intl.NumberFormat(locale, { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

export function formatDateTime(
  locale: string,
  value: number | string | null | undefined,
  options: Intl.DateTimeFormatOptions = { dateStyle: 'medium', timeStyle: 'medium' },
): string {
  const d = toDate(value);
  return d ? new Intl.DateTimeFormat(locale, options).format(d) : '–';
}

const RELATIVE_STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['second', 60],
  ['minute', 60],
  ['hour', 24],
  ['day', 30],
  ['month', 12],
  ['year', Number.POSITIVE_INFINITY],
];

export function formatRelative(locale: string, value: number | string | null | undefined, nowMs: number = Date.now()): string {
  const d = toDate(value);
  if (!d) return '–';
  let delta = (d.getTime() - nowMs) / 1000;
  const fmt = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
  for (const [unit, size] of RELATIVE_STEPS) {
    if (Math.abs(delta) < size) return fmt.format(Math.round(delta), unit);
    delta /= size;
  }
  return fmt.format(Math.round(delta), 'year');
}

export function formatMs(locale: string, ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return '–';
  const digits = ms < 10 ? 2 : ms < 100 ? 1 : 0;
  return new Intl.NumberFormat(locale, { style: 'unit', unit: 'millisecond', unitDisplay: 'short', maximumFractionDigits: digits }).format(ms);
}

export function shortHash(hash: string | null | undefined, size = 10): string {
  if (!hash) return '–';
  return hash.length > size ? `${hash.slice(0, size)}…` : hash;
}

export function truncate(text: string, max: number): string {
  const chars = Array.from(text);
  return chars.length > max ? `${chars.slice(0, max).join('')}…` : text;
}

/** Same thresholds as `Risk.from_score` in models.py. */
export function riskFromScore(score: number): Risk {
  if (score >= 0.85) return 'critical';
  if (score >= 0.6) return 'high';
  if (score >= 0.3) return 'medium';
  return 'low';
}

/** Value for `<input type="datetime-local">` from epoch seconds (local time). */
export function toLocalInput(epochSec: number | undefined): string {
  if (epochSec === undefined) return '';
  const d = new Date(epochSec * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fromLocalInput(value: string): number | undefined {
  if (!value) return undefined;
  const ms = new Date(value).getTime();
  return Number.isNaN(ms) ? undefined : Math.floor(ms / 1000);
}

/** Line numbers mentioned in validator messages ("line 12", "line 12, column 3"). */
export function errorLines(errors: readonly string[]): Set<number> {
  const lines = new Set<number>();
  for (const err of errors) {
    for (const match of err.matchAll(/\bline[s]?\s+(\d+)/gi)) lines.add(Number(match[1]));
  }
  return lines;
}

/** Agent ids declared in a policy YAML (best effort; used only for form suggestions). */
export function policyAgentIds(yaml: string): string[] {
  const ids: string[] = [];
  let inAgents = false;
  for (const line of yaml.split(/\r?\n/)) {
    if (/^agents\s*:/.test(line)) {
      inAgents = true;
      continue;
    }
    if (inAgents && /^\S/.test(line) && !line.startsWith('#')) inAgents = false;
    const m = inAgents ? /^\s*-\s*id\s*:\s*["']?([\w.-]+)["']?/.exec(line) : null;
    if (m) ids.push(m[1]);
  }
  return ids;
}

/** Pretty JSON that never throws (cycles / BigInt fall back to String()). */
export function safeJson(value: unknown, space = 2): string {
  try {
    return JSON.stringify(value, null, space) ?? String(value);
  } catch {
    return String(value);
  }
}

export function stringifyArg(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return String(value);
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return safeJson(value);
}
