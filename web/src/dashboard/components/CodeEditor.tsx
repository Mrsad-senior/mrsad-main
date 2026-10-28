import { forwardRef, type KeyboardEvent, useImperativeHandle, useMemo, useRef } from 'react';
import { type DiffLine, diffStats, lineDiff } from '../../shared/lib/diff';
import { useI18n } from '../../shared/i18n';

export interface CodeEditorHandle {
  goToLine(line: number): void;
}

/**
 * Plain <textarea> editor with a line-number gutter (no editor library). Tab inserts two
 * spaces; Esc then Tab moves focus out, so keyboard users are never trapped (WCAG 2.1.2).
 */
export const CodeEditor = forwardRef<
  CodeEditorHandle,
  {
    value: string;
    onChange?: (value: string) => void;
    readOnly?: boolean;
    errorLines?: ReadonlySet<number>;
    label: string;
    describedBy?: string;
    id?: string;
    rows?: number;
  }
>(function CodeEditor({ value, onChange, readOnly, errorLines, label, describedBy, id, rows = 24 }, ref) {
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const gutterRef = useRef<HTMLDivElement>(null);
  const escaped = useRef(false);
  const lineCount = useMemo(() => value.split('\n').length, [value]);

  useImperativeHandle(ref, () => ({
    goToLine(line: number) {
      const area = areaRef.current;
      if (!area) return;
      const lines = area.value.split('\n');
      const target = Math.min(Math.max(1, line), lines.length);
      const start = lines.slice(0, target - 1).reduce((n, l) => n + l.length + 1, 0);
      area.focus();
      area.setSelectionRange(start, start + lines[target - 1].length);
      const lineHeight = parseFloat(getComputedStyle(area).lineHeight) || 20;
      area.scrollTop = Math.max(0, (target - 4) * lineHeight);
    },
  }));

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Escape') {
      escaped.current = true;
      return;
    }
    if (e.key === 'Tab' && !readOnly && !escaped.current && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      const area = e.currentTarget;
      const { selectionStart, selectionEnd } = area;
      const next = `${area.value.slice(0, selectionStart)}  ${area.value.slice(selectionEnd)}`;
      onChange?.(next);
      requestAnimationFrame(() => area.setSelectionRange(selectionStart + 2, selectionStart + 2));
      return;
    }
    escaped.current = false;
  }

  return (
    <div className={`code-editor${readOnly ? ' code-editor--readonly' : ''}`} dir="ltr">
      <div className="code-editor__gutter" ref={gutterRef} aria-hidden="true">
        {Array.from({ length: lineCount }, (_, i) => (
          <span key={i} className={errorLines?.has(i + 1) ? 'code-editor__ln code-editor__ln--error' : 'code-editor__ln'}>
            {i + 1}
          </span>
        ))}
      </div>
      <textarea
        ref={areaRef}
        id={id}
        className="code-editor__area"
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        onKeyDown={onKeyDown}
        onScroll={(e) => {
          if (gutterRef.current) gutterRef.current.scrollTop = e.currentTarget.scrollTop;
        }}
        readOnly={readOnly}
        rows={rows}
        spellCheck={false}
        autoCapitalize="off"
        autoComplete="off"
        autoCorrect="off"
        wrap="off"
        aria-label={label}
        aria-describedby={describedBy}
        aria-invalid={errorLines && errorLines.size > 0 ? true : undefined}
      />
    </div>
  );
});

/** Unified line diff with old/new line numbers; +/- signs make it readable without colour. */
export function DiffView({ oldText, newText }: { oldText: string; newText: string }) {
  const { t, fmtNumber } = useI18n();
  const lines = useMemo(() => lineDiff(oldText, newText), [oldText, newText]);
  const stats = diffStats(lines);
  if (stats.added === 0 && stats.removed === 0) return <p className="muted">{t('policies.noChanges')}</p>;
  return (
    <div className="stack-sm">
      <p className="row small">
        <span className="badge badge--allow">+ {t('policies.added', { count: fmtNumber(stats.added) })}</span>
        <span className="badge badge--deny">− {t('policies.removed', { count: fmtNumber(stats.removed) })}</span>
      </p>
      <div className="diff" role="table" aria-label={t('policies.diffLabel')}>
        {collapse(lines).map((line, i) =>
          line === null ? (
            <div key={`gap-${i}`} className="diff__line diff__gap" role="row">
              <span role="cell" className="diff__ln">
                ⋯
              </span>
            </div>
          ) : (
            <div key={i} className={`diff__line diff__line--${line.type}`} role="row">
              <span role="cell" className="diff__ln">
                {line.oldLine ?? ''}
              </span>
              <span role="cell" className="diff__ln">
                {line.newLine ?? ''}
              </span>
              <span role="cell" className="diff__sign">
                {line.type === 'add' ? '+' : line.type === 'del' ? '−' : ' '}
              </span>
              <span role="cell">{line.text || ' '}</span>
            </div>
          ),
        )}
      </div>
    </div>
  );
}

/** Keep 3 lines of context around changes; replace long unchanged runs with a gap marker. */
function collapse(lines: DiffLine[], context = 3): (DiffLine | null)[] {
  const keep = new Array<boolean>(lines.length).fill(false);
  lines.forEach((line, i) => {
    if (line.type === 'same') return;
    for (let k = Math.max(0, i - context); k <= Math.min(lines.length - 1, i + context); k++) keep[k] = true;
  });
  const out: (DiffLine | null)[] = [];
  let gap = false;
  lines.forEach((line, i) => {
    if (keep[i]) {
      out.push(line);
      gap = false;
    } else if (!gap) {
      out.push(null);
      gap = true;
    }
  });
  return out;
}
