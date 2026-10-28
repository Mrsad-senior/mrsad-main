import { useMemo } from 'react';
import type { DetectionSpan } from '../api/types';
import { useI18n } from '../i18n';
import { resolveSpans, toSegments } from '../lib/spans';

interface Props {
  text: string;
  spans: readonly DetectionSpan[];
  className?: string;
  /** Show spans that could not be located in `text` below the content. */
  showUnmatched?: boolean;
}

/**
 * Renders text with detector spans wrapped in <mark>. Marks are not bidi-isolated,
 * so highlighting never changes how mixed Arabic/English text is laid out; the
 * container uses dir="auto" so each block follows its own first strong character.
 */
export function HighlightedText({ text, spans, className, showUnmatched = true }: Props) {
  const { t, fmtNumber } = useI18n();
  const { segments, unmatched } = useMemo(() => {
    const { located, unmatched: missing } = resolveSpans(text, spans);
    return { segments: toSegments(text, located), unmatched: missing };
  }, [text, spans]);

  return (
    <div className={`highlight ${className ?? ''}`}>
      <p className="highlight__text" dir="auto">
        {segments.map((seg) =>
          seg.highlighted ? (
            <mark
              key={seg.start}
              className="highlight__mark"
              title={seg.spans
                .map((s) => `${s.rule_id ?? t('playground.model')} · ${fmtNumber(s.score, { maximumFractionDigits: 2 })}`)
                .join('\n')}
            >
              {seg.text}
            </mark>
          ) : (
            <span key={seg.start}>{seg.text}</span>
          ),
        )}
      </p>
      {showUnmatched && unmatched.length > 0 ? (
        <div className="highlight__unmatched">
          <p className="muted">{t('drawer.spansUnmatched')}</p>
          <ul>
            {unmatched.map((s, i) => (
              <li key={`${s.start}-${i}`}>
                <mark className="highlight__mark" dir="auto">
                  {s.text}
                </mark>
                {s.rule_id ? <code className="muted"> {s.rule_id}</code> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
