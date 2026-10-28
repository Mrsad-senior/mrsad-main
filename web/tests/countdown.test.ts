import { describe, expect, it } from 'vitest';
import { countdown, countdownUrgency, formatCountdown, localeDigits } from '../src/shared/lib/countdown';

describe('formatCountdown', () => {
  it('formats minutes and seconds, rounding up', () => {
    expect(formatCountdown(125_000)).toBe('2:05');
    expect(formatCountdown(59_001)).toBe('1:00');
    expect(formatCountdown(1)).toBe('0:01');
    expect(formatCountdown(9_000)).toBe('0:09');
  });

  it('shows hours when needed', () => {
    expect(formatCountdown(3_723_000)).toBe('1:02:03');
  });

  it('shows 0:00 only once expired, including invalid input', () => {
    expect(formatCountdown(0)).toBe('0:00');
    expect(formatCountdown(-5000)).toBe('0:00');
    expect(formatCountdown(Number.NaN)).toBe('0:00');
  });

  it('can localise digits (Arabic-Indic)', () => {
    expect(formatCountdown(125_000, localeDigits('ar-SA-u-nu-arab'))).toBe('٢:٠٥');
    expect(formatCountdown(125_000, localeDigits('ar-SA-u-nu-latn'))).toBe('2:05');
  });
});

describe('urgency', () => {
  it('escalates as the deadline approaches', () => {
    expect(countdownUrgency(10 * 60_000, 20 * 60_000)).toBe('normal');
    expect(countdownUrgency(50_000, 120_000)).toBe('soon');
    expect(countdownUrgency(20_000, 120_000)).toBe('critical');
    expect(countdownUrgency(0, 120_000)).toBe('expired');
    expect(countdownUrgency(90_000)).toBe('normal');
  });

  it('computes the remaining fraction from epoch-second timestamps', () => {
    const now = 1_000_000_000;
    const info = countdown(now / 1000 + 30, now, now / 1000 - 90);
    expect(info.seconds).toBe(30);
    expect(info.fraction).toBeCloseTo(0.25);
    expect(info.text).toBe('0:30');
    expect(info.urgency).toBe('critical');
    expect(countdown(now / 1000 - 1, now).urgency).toBe('expired');
  });
});
