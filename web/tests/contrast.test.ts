/**
 * WCAG 2.1 contrast checks for the design tokens (both themes):
 * 4.5:1 for text pairs (SC 1.4.3) and 3:1 for UI components / graphics (SC 1.4.11).
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const css = readFileSync(resolve(__dirname, '../src/shared/styles/tokens.css'), 'utf8');

function block(selectorStart: string): Record<string, string> {
  const start = css.indexOf(selectorStart);
  if (start < 0) throw new Error(`missing block ${selectorStart}`);
  const open = css.indexOf('{', start);
  let depth = 0;
  let end = open;
  for (let i = open; i < css.length; i++) {
    if (css[i] === '{') depth++;
    if (css[i] === '}' && --depth === 0) {
      end = i;
      break;
    }
  }
  const vars: Record<string, string> = {};
  for (const m of css.slice(open + 1, end).matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) vars[m[1]] = m[2].toLowerCase();
  return vars;
}

const light = block(':root {');
const darkMedia = block(':root:not([data-theme="light"])');
const darkToggle = block(':root[data-theme="dark"]');
const dark = { ...light, ...darkToggle };

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const TEXT_PAIRS: [string, string][] = [
  ['text', 'bg'], ['text', 'surface'], ['text', 'surface-2'], ['text', 'surface-3'],
  ['text-muted', 'bg'], ['text-muted', 'surface'], ['text-muted', 'surface-2'],
  ['text-subtle', 'bg'], ['text-subtle', 'surface'],
  ['on-primary', 'primary'], ['on-primary', 'primary-hover'],
  ['primary-text', 'surface'], ['primary-text', 'bg'], ['primary-text', 'surface-2'],
  ['on-primary-soft', 'primary-soft'],
  ['on-danger', 'danger'], ['on-danger', 'danger-hover'],
  ['on-approve', 'approve'], ['on-approve', 'approve-hover'],
  ['nav-text', 'nav-bg'], ['nav-muted', 'nav-bg'], ['nav-active-text', 'nav-active-bg'], ['nav-text', 'nav-active-bg'],
  ['allow-fg', 'allow-bg'], ['deny-fg', 'deny-bg'], ['warn-fg', 'warn-bg'], ['info-fg', 'info-bg'],
  ['neutral-fg', 'neutral-bg'], ['serious-fg', 'serious-bg'], ['critical-fg', 'critical-bg'],
  ...['policy', 'ratelimit', 'taint', 'detector', 'approval', 'system'].map((l) => [`layer-${l}-fg`, `layer-${l}-bg`] as [string, string]),
  ['mark-fg', 'mark-bg'], ['diff-add-fg', 'diff-add-bg'], ['diff-del-fg', 'diff-del-bg'],
  ['chart-axis', 'surface'],
];

const UI_PAIRS: [string, string][] = [
  ['focus', 'bg'], ['focus', 'surface'],
  ['border-strong', 'surface'], ['border-strong', 'bg'],
  ['primary', 'surface'], ['danger', 'surface'], ['approve', 'surface'],
  ['mark-line', 'surface'],
  ['chart-allow', 'surface'], ['chart-approval', 'surface'], ['chart-deny', 'surface'], ['chart-injection', 'surface'], ['chart-accent', 'surface'],
];

describe.each([
  ['light', light],
  ['dark', dark],
])('%s theme contrast', (_name, vars) => {
  it.each(TEXT_PAIRS)('text %s on %s >= 4.5:1', (fg, bg) => {
    expect(vars[fg], fg).toBeDefined();
    expect(vars[bg], bg).toBeDefined();
    expect(contrast(vars[fg], vars[bg])).toBeGreaterThanOrEqual(4.5);
  });
  it.each(UI_PAIRS)('UI %s on %s >= 3:1', (fg, bg) => {
    expect(contrast(vars[fg], vars[bg])).toBeGreaterThanOrEqual(3);
  });
});

describe('theme blocks', () => {
  it('OS-dark and toggle-dark define identical colours', () => {
    expect(darkMedia).toEqual(darkToggle);
  });
  it('dark theme overrides every light colour token', () => {
    const missing = Object.keys(light).filter((k) => !(k in darkToggle));
    expect(missing).toEqual([]);
  });
});
