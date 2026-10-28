import { describe, expect, it } from 'vitest';
import { resolveSpans, toSegments } from '../src/shared/lib/spans';

const join = (segs: { text: string }[]) => segs.map((s) => s.text).join('');
const marked = (segs: { text: string; highlighted: boolean }[]) => segs.filter((s) => s.highlighted).map((s) => s.text);

describe('toSegments', () => {
  it('splits text into plain and highlighted parts that concatenate back to the input', () => {
    // Neutral placeholder text: the highlighting logic does not care what the span says.
    const text = 'Please SAMPLE-FLAGGED-TEXT now';
    const segs = toSegments(text, [{ start: 7, end: 26 }]);
    expect(join(segs)).toBe(text);
    expect(marked(segs)).toEqual(['SAMPLE-FLAGGED-TEXT']);
    expect(segs.map((s) => s.highlighted)).toEqual([false, true, false]);
  });

  it('merges overlapping and touching spans and sorts unsorted input', () => {
    const text = 'abcdefghij';
    const segs = toSegments(text, [
      { start: 6, end: 8, rule_id: 'b' },
      { start: 1, end: 4, rule_id: 'a' },
      { start: 3, end: 6, rule_id: 'c' },
    ]);
    expect(marked(segs)).toEqual(['bcdefgh']);
    expect(segs.find((s) => s.highlighted)?.spans.map((s) => s.rule_id).sort()).toEqual(['a', 'b', 'c']);
    expect(join(segs)).toBe(text);
  });

  it('clamps out-of-range offsets and ignores empty or invalid spans', () => {
    const text = 'hello';
    expect(marked(toSegments(text, [{ start: -5, end: 2 }]))).toEqual(['he']);
    expect(marked(toSegments(text, [{ start: 3, end: 99 }]))).toEqual(['lo']);
    expect(toSegments(text, [{ start: 4, end: 4 }, { start: 5, end: 2 }, { start: NaN, end: 3 }])).toEqual([
      { text: 'hello', start: 0, end: 5, highlighted: false, spans: [] },
    ]);
    expect(toSegments('', [{ start: 0, end: 3 }])).toEqual([]);
  });

  it('handles Arabic text with offsets in logical order (RTL safe)', () => {
    const text = 'مرحبا، هذا نص تجريبي مميز للاختبار فقط';
    const start = text.indexOf('نص');
    const end = text.indexOf('للاختبار') - 1;
    const segs = toSegments(text, [{ start, end }]);
    expect(marked(segs)).toEqual(['نص تجريبي مميز']);
    expect(join(segs)).toBe(text);
  });

  it('handles mixed Arabic/English text', () => {
    const text = 'Dear team, نص تجريبي and see sample.example';
    const segs = toSegments(text, [{ start: 11, end: 20 }, { start: 29, end: 43 }]);
    expect(marked(segs)).toEqual(['نص تجريبي', 'sample.example']);
    expect(join(segs)).toBe(text);
  });

  it('uses code-point offsets (Python) so emoji never shift or split spans', () => {
    // "🙂" is 1 code point but 2 UTF-16 units: a naive slice would be off by one.
    const text = '🙂🙂 SAMPLE this';
    const segs = toSegments(text, [{ start: 3, end: 9 }]);
    expect(marked(segs)).toEqual(['SAMPLE']);
    expect(join(segs)).toBe(text);
  });

  it('never splits combining marks when spans align to code points (tashkeel)', () => {
    const text = 'مَرْحَبًا بالعالم';
    const chars = Array.from(text);
    const segs = toSegments(text, [{ start: 0, end: chars.indexOf(' ') }]);
    expect(marked(segs)).toEqual(['مَرْحَبًا']);
  });
});

describe('resolveSpans', () => {
  it('keeps spans whose offsets match their text', () => {
    const text = 'xx SAMPLE yy';
    const { located, unmatched } = resolveSpans(text, [{ start: 3, end: 9, text: 'SAMPLE' }]);
    expect(located).toHaveLength(1);
    expect(unmatched).toHaveLength(0);
  });

  it('re-anchors spans computed on another representation by searching their text', () => {
    const text = 'Subject: hi\nSAMPLE-FLAGGED-TEXT';
    const { located } = resolveSpans(text, [{ start: 40, end: 59, text: 'SAMPLE-FLAGGED-TEXT' }]);
    expect(located[0].start).toBe(12);
    expect(marked(toSegments(text, located))).toEqual(['SAMPLE-FLAGGED-TEXT']);
  });

  it('reports spans that cannot be found (e.g. truncated content)', () => {
    const { located, unmatched } = resolveSpans('short', [{ start: 100, end: 120, text: 'not here' }]);
    expect(located).toEqual([]);
    expect(unmatched).toHaveLength(1);
  });
});
