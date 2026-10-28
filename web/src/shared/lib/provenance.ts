/**
 * "Where did the data come from?" — turns taint-layer reason evidence into a flat list
 * an approver can read. The taint area guarantees evidence names the source tool,
 * call id and field. Shapes produced by `mirsad/taint/rules.py`, plus older/looser ones:
 *   {param, value, kind, source_tool, source_call_id, field, source_trust, source_sensitivity}
 *   {..., matches: [{param, value, source_tool, source_call_id, field, ...}, ...]}
 *   {source_tool, source_call_id, sources: [{tool, call_id}, ...]}   (session-level rules)
 *   {untrusted_sources: ["read_email:call_1", ...]}                  (legacy string refs)
 */
import type { Reason, SessionSnapshot } from '../api/types';

export interface ProvenanceItem {
  code: string;
  param?: string;
  value?: string;
  kind?: string;
  sourceTool?: string;
  sourceCallId?: string;
  field?: string;
  trust?: string;
  sensitivity?: string;
}

type Obj = Record<string, unknown>;

const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v);
const str = (v: unknown): string | undefined =>
  typeof v === 'string' && v !== '' ? v : typeof v === 'number' ? String(v) : undefined;

function fromObject(code: string, o: Obj, nested: boolean, inherited: Partial<ProvenanceItem> = {}): ProvenanceItem | null {
  const sourceTool = str(o.source_tool) ?? (nested ? str(o.tool) ?? str(o.source) : undefined);
  const sourceCallId = str(o.source_call_id) ?? (nested ? str(o.call_id) : undefined);
  const field = str(o.field) ?? str(o.field_path) ?? str(o.source_field);
  if (!sourceTool && !sourceCallId && !field) return null;
  return {
    code,
    param: str(o.param) ?? str(o.argument) ?? str(o.arg) ?? inherited.param,
    value: str(o.value) ?? str(o.matched) ?? str(o.match) ?? inherited.value,
    kind: str(o.kind),
    sourceTool,
    sourceCallId,
    field,
    trust: str(o.source_trust) ?? str(o.trust),
    sensitivity: str(o.source_sensitivity) ?? str(o.sensitivity),
  };
}

/** Parses "tool:call_id", "tool#call_id" or "tool/call_id" source references. */
export function parseSourceRef(ref: string): { sourceTool: string; sourceCallId?: string } {
  const m = /^([^:#/\s]+)[:#/]([^\s]+)$/.exec(ref.trim());
  return m ? { sourceTool: m[1], sourceCallId: m[2] } : { sourceTool: ref.trim() };
}

export function extractProvenance(reasons: readonly Reason[]): ProvenanceItem[] {
  const items: ProvenanceItem[] = [];
  for (const reason of reasons) {
    const ev = isObj(reason.evidence) ? reason.evidence : {};
    const isTaint = reason.layer === 'taint';
    const top = fromObject(reason.code, ev, false);
    if (top) items.push(top);

    const inherited = { param: str(ev.param) ?? str(ev.argument), value: str(ev.value) };
    for (const [key, value] of Object.entries(ev)) {
      if (!Array.isArray(value)) continue;
      for (const entry of value) {
        if (isObj(entry)) {
          const item = fromObject(reason.code, entry, true, inherited);
          if (item) items.push(item);
        } else if (typeof entry === 'string' && /source/i.test(key) && isTaint) {
          items.push({ code: reason.code, ...parseSourceRef(entry) });
        }
      }
    }
    for (const [key, value] of Object.entries(ev)) {
      if (isObj(value) && /source|origin|match/i.test(key)) {
        const item = fromObject(reason.code, value, true, inherited);
        if (item) items.push(item);
      }
    }
  }
  return dedupe(items);
}

/** Session-level fallback: untrusted sources recorded in a taint snapshot (audit events). */
export function snapshotSources(snapshot: SessionSnapshot | null | undefined): ProvenanceItem[] {
  if (!snapshot) return [];
  return dedupe(snapshot.untrusted_sources.map((ref) => ({ code: 'SESSION_UNTRUSTED', ...parseSourceRef(ref) })));
}

function dedupe(items: ProvenanceItem[]): ProvenanceItem[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = JSON.stringify([item.code, item.param, item.value, item.sourceTool, item.sourceCallId, item.field]);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/** Reasons worth showing as "why paused": anything that did not simply allow, plus risky info. */
export function pauseReasons(reasons: readonly Reason[]): Reason[] {
  const relevant = reasons.filter((r) => r.action !== 'allow' || r.risk_score >= 0.6);
  return (relevant.length ? relevant : reasons).slice().sort((a, b) => b.risk_score - a.risk_score);
}
