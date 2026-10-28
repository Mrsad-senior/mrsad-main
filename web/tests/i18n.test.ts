/** Every UI string exists in both languages, with the same placeholders, and every key used in code exists. */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { ar } from '../src/shared/i18n/ar';
import { en } from '../src/shared/i18n/en';
import { buildI18n, interpolate, translate } from '../src/shared/i18n';

const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
const ARABIC = /[؀-ۿ]/;

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    return /\.(ts|tsx)$/.test(name) && !/i18n[/\\](en|ar)\.ts$/.test(full) ? [full] : [];
  });
}

describe('dictionaries', () => {
  const enKeys = Object.keys(en).sort();
  const arKeys = Object.keys(ar).sort();

  it('have exactly the same keys', () => {
    expect(arKeys).toEqual(enKeys);
  });

  it('have no empty strings', () => {
    for (const key of enKeys) {
      expect(en[key as keyof typeof en].trim(), `en ${key}`).not.toBe('');
      expect(ar[key as keyof typeof ar].trim(), `ar ${key}`).not.toBe('');
    }
  });

  it('use identical placeholders in both languages', () => {
    for (const key of enKeys) {
      expect(placeholders(ar[key as keyof typeof ar]), key).toEqual(placeholders(en[key as keyof typeof en]));
    }
  });

  it('really translates: Arabic values contain Arabic script (except pure symbols/identifiers)', () => {
    const exempt = new Set(['activity.colSeq', 'activity.range', 'activity.verifyHead']);
    const untranslated = arKeys.filter((k) => !exempt.has(k) && !ARABIC.test(ar[k as keyof typeof ar]));
    expect(untranslated).toEqual([]);
  });

  it('covers every literal key referenced in the source', () => {
    const root = resolve(__dirname, '../src');
    const used = new Set<string>();
    for (const file of sourceFiles(root)) {
      const text = readFileSync(file, 'utf8');
      for (const m of text.matchAll(/\bt\(\s*'([\w.]+)'/g)) used.add(m[1]);
    }
    expect(used.size).toBeGreaterThan(150);
    const missing = [...used].filter((k) => !(k in en));
    expect(missing).toEqual([]);
  });

  it('covers every dynamic key family used with tx()/t(`...`)', () => {
    const families: Record<string, string[]> = {
      action: ['allow', 'require_approval', 'deny'],
      inspection: ['pass', 'flag', 'sanitize', 'block'],
      risk: ['low', 'medium', 'high', 'critical'],
      layer: ['policy', 'ratelimit', 'taint', 'detector', 'approval', 'system'],
      status: ['pending', 'approved', 'denied', 'expired', 'cancelled'],
      label: ['benign', 'suspicious', 'injection'],
      detLang: ['en', 'ar', 'mixed', 'other'],
      sink: ['none', 'internal', 'external', 'dynamic'],
      trust: ['trusted', 'untrusted'],
      sensitivity: ['public', 'internal', 'confidential'],
      approvalMode: ['never', 'on_risk', 'always'],
      roles: ['admin', 'approver', 'auditor'],
      'users.roleHelp': ['admin', 'approver', 'auditor'],
      // Every event type the backend writes (gateway, API routers, CLI).
      event: [
        'tool_call.decision', 'tool_result.inspection', 'approval.requested', 'approval.decided', 'policy.activated',
        'agent.created', 'agent.updated', 'agent.key_rotated', 'agent.deleted', 'user.created', 'user.updated',
        'user.deleted', 'auth.login', 'auth.login_failed', 'system.started', 'audit.verified',
      ],
    };
    const missing = Object.entries(families).flatMap(([prefix, values]) => values.map((v) => `${prefix}.${v}`)).filter((k) => !(k in en));
    expect(missing).toEqual([]);
  });
});

describe('translate / interpolate', () => {
  it('fills placeholders and leaves unknown ones visible', () => {
    expect(interpolate('Hello {name} {missing}', { name: 'Noura' })).toBe('Hello Noura {missing}');
    expect(translate('ar', 'live.newApproval', { tool: 'send_email', agent: 'crm' })).toBe('طلب موافقة جديد: send_email من crm');
  });

  it('formats numbers and dates per language, with selectable Arabic-Indic digits', () => {
    const noop = () => undefined;
    expect(buildI18n('en', 'latn', noop, noop).fmtNumber(1234567)).toBe('1,234,567');
    expect(buildI18n('ar', 'latn', noop, noop).fmtNumber(42)).toBe('42');
    expect(buildI18n('ar', 'arab', noop, noop).fmtNumber(42)).toBe('٤٢');
    const ar = buildI18n('ar', 'latn', noop, noop);
    expect(ar.dir).toBe('rtl');
    // Gregorian calendar even in ar-SA (whose default is Umm al-Qura).
    expect(ar.fmtDateTime(Date.UTC(2026, 9, 11, 12), { year: 'numeric', timeZone: 'UTC' })).toContain('2026');
  });

  it('falls back for unknown dynamic keys', () => {
    const i = buildI18n('en', 'latn', () => undefined, () => undefined);
    expect(i.tx('event.custom.thing', 'custom.thing')).toBe('custom.thing');
    expect(i.tx('action.deny', 'x')).toBe('Denied');
  });
});
