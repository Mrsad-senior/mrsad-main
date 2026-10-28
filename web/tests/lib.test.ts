import { describe, expect, it } from 'vitest';
import { applyApprovalEvent, sortApprovals, upsertApproval } from '../src/shared/lib/approvals';
import { diffStats, lineDiff, splitLines } from '../src/shared/lib/diff';
import { errorLines, formatRelative, policyAgentIds, riskFromScore, toDate, truncate } from '../src/shared/lib/format';
import { extractProvenance, parseSourceRef, pauseReasons, snapshotSources } from '../src/shared/lib/provenance';
import type { ApprovalRecord, Reason } from '../src/shared/api/types';

describe('lineDiff', () => {
  it('reports additions, deletions and unchanged lines with line numbers', () => {
    const lines = lineDiff('a\nb\nc\n', 'a\nB\nc\nd\n');
    expect(lines.map((l) => `${l.type}:${l.text}`)).toEqual(['same:a', 'del:b', 'add:B', 'same:c', 'add:d']);
    expect(lines[2]).toMatchObject({ newLine: 2 });
    expect(lines[1]).toMatchObject({ oldLine: 2 });
    expect(diffStats(lines)).toEqual({ added: 2, removed: 1 });
  });

  it('handles identical, empty and CRLF inputs', () => {
    expect(diffStats(lineDiff('x\ny', 'x\ny'))).toEqual({ added: 0, removed: 0 });
    expect(lineDiff('', 'a').map((l) => l.type)).toEqual(['add']);
    expect(splitLines('a\r\nb\r\n')).toEqual(['a', 'b']);
  });
});

describe('format helpers', () => {
  it('toDate accepts epoch seconds, milliseconds and ISO strings', () => {
    expect(toDate(1_760_000_000)?.getTime()).toBe(1_760_000_000_000);
    expect(toDate(1_760_000_000_123)?.getTime()).toBe(1_760_000_000_123);
    expect(toDate('1760000000.5')?.getTime()).toBe(1_760_000_000_500);
    expect(toDate('2026-10-11T10:00:00Z')?.toISOString()).toBe('2026-10-11T10:00:00.000Z');
    expect(toDate(null)).toBeNull();
    expect(toDate('not a date')).toBeNull();
  });

  it('formats relative times', () => {
    const now = Date.UTC(2026, 9, 11, 12);
    expect(formatRelative('en-GB', now / 1000 - 120, now)).toBe('2 minutes ago');
    expect(formatRelative('en-GB', now / 1000 + 30, now)).toBe('in 30 seconds');
  });

  it('extracts validator line references and policy agent ids', () => {
    expect([...errorLines(['line 12: unknown key', 'Line 3, column 4', 'no line'])].sort((a, b) => a - b)).toEqual([3, 12]);
    const yaml = 'version: 1\nagents:\n  - id: email-crm-assistant\n    tools: {}\n  - id: "finance-bot"\nrules:\n  - id: not-an-agent\n';
    expect(policyAgentIds(yaml)).toEqual(['email-crm-assistant', 'finance-bot']);
  });

  it('maps risk scores like models.Risk.from_score', () => {
    expect([0.1, 0.3, 0.6, 0.85, 0.99].map(riskFromScore)).toEqual(['low', 'medium', 'high', 'critical', 'critical']);
  });

  it('truncates by code points', () => {
    expect(truncate('🙂🙂🙂', 2)).toBe('🙂🙂…');
    expect(truncate('abc', 5)).toBe('abc');
  });
});

const reason = (over: Partial<Reason>): Reason => ({
  layer: 'taint', code: 'TAINT_UNTRUSTED_DESTINATION', message: 'm', action: 'deny', risk_score: 0.9, evidence: {}, ...over,
});

describe('provenance', () => {
  it('reads single-match evidence', () => {
    const items = extractProvenance([
      reason({ evidence: { param: 'to', value: 'boss@evil.example', source_tool: 'read_email', source_call_id: 'call_1', field: 'body' } }),
    ]);
    expect(items).toEqual([
      expect.objectContaining({ param: 'to', value: 'boss@evil.example', sourceTool: 'read_email', sourceCallId: 'call_1', field: 'body' }),
    ]);
  });

  it('reads nested match lists and inherits the parameter name', () => {
    const items = extractProvenance([
      reason({
        code: 'TAINT_CONFIDENTIAL_TO_EXTERNAL',
        evidence: { param: 'body', matches: [{ value: '0551234567', kind: 'phone', tool: 'get_customer', call_id: 'call_9', field: 'phone', sensitivity: 'confidential' }] },
      }),
    ]);
    expect(items[0]).toMatchObject({ param: 'body', value: '0551234567', sourceTool: 'get_customer', sourceCallId: 'call_9', sensitivity: 'confidential' });
  });

  it('parses session-level source references', () => {
    const items = extractProvenance([reason({ code: 'TAINT_UNTRUSTED_TO_EXTERNAL', evidence: { untrusted_sources: ['read_email:call_2', 'fetch_url'] } })]);
    expect(items.map((i) => [i.sourceTool, i.sourceCallId])).toEqual([['read_email', 'call_2'], ['fetch_url', undefined]]);
    expect(parseSourceRef('read_document#call_x')).toEqual({ sourceTool: 'read_document', sourceCallId: 'call_x' });
  });

  it('ignores non-taint reasons without source info and de-duplicates', () => {
    const r = reason({ evidence: { source_tool: 'a', source_call_id: 'c', field: 'f' } });
    expect(extractProvenance([r, r, reason({ layer: 'policy', code: 'CONSTRAINT_VIOLATION', evidence: { param: 'to', operator: 'domain_in' } })])).toHaveLength(1);
  });

  it('falls back to the snapshot sources', () => {
    expect(snapshotSources({ session_id: 's', agent_id: 'a', untrusted_sources: ['read_email:call_1'], max_sensitivity: 'internal', injection_detected: false, values: [], call_count: 1 })).toEqual([
      { code: 'SESSION_UNTRUSTED', sourceTool: 'read_email', sourceCallId: 'call_1' },
    ]);
  });

  it('orders "why paused" reasons by risk and drops informational ones', () => {
    const list = pauseReasons([
      reason({ layer: 'policy', code: 'TOOL_RISK', action: 'allow', risk_score: 0.3 }),
      reason({ code: 'A', action: 'require_approval', risk_score: 0.6 }),
      reason({ code: 'B', action: 'deny', risk_score: 0.9 }),
    ]);
    expect(list.map((r) => r.code)).toEqual(['B', 'A']);
  });
});

const record = (id: string, status: ApprovalRecord['status'], expires: number, decidedAt?: number): ApprovalRecord => ({
  id, status, created_at: 0, expires_at: expires, agent_id: 'a', session_id: 's', call_id: 'c', tool: 't', arguments: {},
  decision: { call_id: 'c', action: 'require_approval', reasons: [], risk: 'high', risk_score: 0.7, sink: 'external', policy_version: 'v', latency_ms: 1 },
  summary_en: '', summary_ar: '', risk: 'high', decided_at: decidedAt ?? null,
});

describe('approval list sync', () => {
  it('sorts pending by soonest expiry, then decided by newest', () => {
    const sorted = sortApprovals([record('d1', 'approved', 1, 50), record('p2', 'pending', 200), record('p1', 'pending', 100), record('d2', 'denied', 1, 90)]);
    expect(sorted.map((r) => r.id)).toEqual(['p1', 'p2', 'd2', 'd1']);
  });

  it('applies stream events by upserting records and ignores malformed data', () => {
    let list = [record('p1', 'pending', 100)];
    list = applyApprovalEvent(list, 'approval.requested', record('p2', 'pending', 50));
    expect(list.map((r) => r.id)).toEqual(['p2', 'p1']);
    list = applyApprovalEvent(list, 'approval.decided', { ...record('p2', 'approved', 50), decided_by: 'noura' });
    expect(list.find((r) => r.id === 'p2')?.status).toBe('approved');
    expect(applyApprovalEvent(list, 'approval.requested', { nonsense: true })).toHaveLength(2);
    expect(upsertApproval([], record('x', 'pending', 1))).toHaveLength(1);
  });
});
