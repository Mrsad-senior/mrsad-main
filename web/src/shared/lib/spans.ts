/**
 * Detection-span highlighting.
 *
 * The detector (Python) reports offsets in Unicode *code points*, while JavaScript
 * strings index UTF-16 code units. All offsets here are therefore applied to
 * `Array.from(text)` so astral characters (emoji, some CJK) never shift a span or
 * split a surrogate pair. Segments are produced in logical (memory) order and
 * concatenate back to the exact input, so the browser's bidi algorithm lays out
 * Arabic, English and mixed text exactly as it would without highlighting.
 */

export interface SpanLike {
  start: number;
  end: number;
  text?: string;
  rule_id?: string | null;
  score?: number;
}

export interface Segment<S extends SpanLike = SpanLike> {
  text: string;
  /** Code-point offsets of this segment in the original text. */
  start: number;
  end: number;
  highlighted: boolean;
  /** Spans covering this segment (several when spans overlap). */
  spans: S[];
}

/** Split `text` into ordered plain/highlighted segments; overlapping spans are merged. */
export function toSegments<S extends SpanLike>(text: string, spans: readonly S[]): Segment<S>[] {
  const chars = Array.from(text);
  const length = chars.length;
  if (length === 0) return [];

  const valid = spans
    .map((span) => ({
      span,
      start: clamp(Math.floor(Number(span.start)), 0, length),
      end: clamp(Math.ceil(Number(span.end)), 0, length),
    }))
    .filter((s) => Number.isFinite(s.start) && Number.isFinite(s.end) && s.end > s.start)
    .sort((a, b) => a.start - b.start || b.end - a.end);

  // Boundaries where the set of covering spans may change.
  const cuts = new Set<number>([0, length]);
  for (const s of valid) {
    cuts.add(s.start);
    cuts.add(s.end);
  }
  const points = [...cuts].sort((a, b) => a - b);

  const raw: Segment<S>[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const start = points[i];
    const end = points[i + 1];
    const covering = valid.filter((s) => s.start <= start && s.end >= end).map((s) => s.span);
    raw.push({ text: chars.slice(start, end).join(''), start, end, highlighted: covering.length > 0, spans: covering });
  }

  // Merge neighbours with the same highlight state so overlaps render as one <mark>.
  const merged: Segment<S>[] = [];
  for (const seg of raw) {
    const prev = merged[merged.length - 1];
    if (prev && prev.highlighted === seg.highlighted) {
      prev.text += seg.text;
      prev.end = seg.end;
      for (const s of seg.spans) if (!prev.spans.includes(s)) prev.spans.push(s);
    } else {
      merged.push({ ...seg, spans: [...seg.spans] });
    }
  }
  return merged;
}

/**
 * Re-anchor spans against the text actually displayed. Offsets are trusted when
 * the slice matches `span.text`; otherwise (e.g. spans computed on a JSON dump or
 * on content that was later truncated) the span text is searched for. Spans that
 * cannot be located are returned in `unmatched` so the UI can still list them.
 */
export function resolveSpans<S extends SpanLike>(text: string, spans: readonly S[]): { located: S[]; unmatched: S[] } {
  const chars = Array.from(text);
  const located: S[] = [];
  const unmatched: S[] = [];
  for (const span of spans) {
    const slice = chars.slice(span.start, span.end).join('');
    if (!span.text || slice === span.text) {
      if (span.end > span.start && span.start < chars.length) located.push(span);
      else unmatched.push(span);
      continue;
    }
    const unitIndex = text.indexOf(span.text);
    if (unitIndex >= 0) {
      const start = Array.from(text.slice(0, unitIndex)).length;
      located.push({ ...span, start, end: start + Array.from(span.text).length });
    } else {
      unmatched.push(span);
    }
  }
  return { located, unmatched };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
