/** Countdown helpers for approval expiry (pure, so they are unit-testable). */

export type Urgency = 'normal' | 'soon' | 'critical' | 'expired';

export interface CountdownInfo {
  /** Remaining whole seconds (0 when expired). */
  seconds: number;
  /** Clock text, e.g. "1:05" or "1:02:03"; digits localised by `formatDigits`. */
  text: string;
  urgency: Urgency;
  /** Fraction of the approval window still left, 0..1 (1 when the window is unknown). */
  fraction: number;
}

/**
 * Format a remaining duration as a clock. Rounds *up* so "0:00" is only shown once the
 * deadline has actually passed (an approver must never see 0:00 on a live request).
 */
export function formatCountdown(remainingMs: number, formatDigits: (n: number, minDigits: number) => string = defaultDigits): string {
  if (!Number.isFinite(remainingMs) || remainingMs <= 0) return `${formatDigits(0, 1)}:${formatDigits(0, 2)}`;
  const total = Math.ceil(remainingMs / 1000);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (hours > 0) {
    return `${formatDigits(hours, 1)}:${formatDigits(minutes, 2)}:${formatDigits(seconds, 2)}`;
  }
  return `${formatDigits(minutes, 1)}:${formatDigits(seconds, 2)}`;
}

/** Urgency thresholds: under 30 s is critical, under 25% of the window (or 60 s) is soon. */
export function countdownUrgency(remainingMs: number, totalMs?: number): Urgency {
  if (!Number.isFinite(remainingMs) || remainingMs <= 0) return 'expired';
  if (remainingMs <= 30_000) return 'critical';
  const soonAt = totalMs && totalMs > 0 ? Math.max(60_000, totalMs * 0.25) : 60_000;
  return remainingMs <= soonAt ? 'soon' : 'normal';
}

/** Countdown for an approval whose timestamps are epoch seconds (as the API returns them). */
export function countdown(
  expiresAtSec: number,
  nowMs: number,
  createdAtSec?: number,
  formatDigits?: (n: number, minDigits: number) => string,
): CountdownInfo {
  const remainingMs = expiresAtSec * 1000 - nowMs;
  const totalMs = createdAtSec !== undefined ? (expiresAtSec - createdAtSec) * 1000 : undefined;
  const fraction = totalMs && totalMs > 0 ? Math.min(1, Math.max(0, remainingMs / totalMs)) : remainingMs > 0 ? 1 : 0;
  return {
    seconds: Math.max(0, Math.ceil(remainingMs / 1000)),
    text: formatCountdown(remainingMs, formatDigits),
    urgency: countdownUrgency(remainingMs, totalMs),
    fraction,
  };
}

function defaultDigits(n: number, minDigits: number): string {
  return String(n).padStart(minDigits, '0');
}

/** Digit formatter bound to a locale, e.g. Arabic-Indic digits for `ar-SA-u-nu-arab`. */
export function localeDigits(locale: string): (n: number, minDigits: number) => string {
  const cache = new Map<number, Intl.NumberFormat>();
  return (n, minDigits) => {
    let fmt = cache.get(minDigits);
    if (!fmt) {
      fmt = new Intl.NumberFormat(locale, { minimumIntegerDigits: minDigits, useGrouping: false });
      cache.set(minDigits, fmt);
    }
    return fmt.format(n);
  };
}
