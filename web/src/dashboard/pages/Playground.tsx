import { type FormEvent, useRef, useState } from 'react';
import type { DetectionResult } from '../../shared/api/types';
import { useApi } from '../../shared/app/auth';
import { useQuery } from '../../shared/app/hooks';
import { useToast } from '../../shared/app/toast';
import { DetectionLabelBadge } from '../../shared/components/Badges';
import { ScoreGauge } from '../../shared/components/Gauge';
import { HighlightedText } from '../../shared/components/Highlight';
import { Icon } from '../../shared/components/Icon';
import { EmptyState } from '../../shared/components/States';
import { useI18n } from '../../shared/i18n';
import { BUILTIN_SAMPLES, MAX_SAMPLE_CHARS, type PlaygroundSample, sampleLabel } from '../../shared/lib/samples';
import { PageHeader, Section } from '../components/PageHeader';

export default function Playground() {
  const api = useApi();
  const toast = useToast();
  const { t, lang, fmtNumber, fmtMs } = useI18n();
  const teamSamples = useQuery((signal) => api.playgroundSamples(signal), [api]);
  const [text, setText] = useState('');
  const [result, setResult] = useState<{ text: string; detection: DetectionResult } | null>(null);
  const [pending, setPending] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  async function scan(e?: FormEvent) {
    e?.preventDefault();
    if (!text.trim()) return;
    setPending(true);
    try {
      const detection = await api.scan(text);
      setResult({ text, detection });
    } catch (err) {
      toast.error(err);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="stack-lg">
      <PageHeader title={t('playground.title')} subtitle={t('playground.subtitle')} />
      <div className="grid-2 grid-2--wide-start">
        <Section id="input" title={t('playground.input')}>
          <form className="stack" onSubmit={scan}>
            <SampleButtons
              label={t('playground.samples')}
              samples={BUILTIN_SAMPLES}
              lang={lang}
              onPick={(s) => {
                setText(s.text);
                setResult(null);
                inputRef.current?.focus();
              }}
            />
            {teamSamples.data?.length ? (
              <SampleButtons
                label={t('playground.teamSamples')}
                samples={teamSamples.data}
                lang={lang}
                onPick={(s) => {
                  setText(s.text);
                  setResult(null);
                  inputRef.current?.focus();
                }}
              />
            ) : null}
            <p className="muted small">{t('playground.samplesNote')}</p>
            <label className="visually-hidden" htmlFor="scan-text">
              {t('playground.input')}
            </label>
            <textarea
              ref={inputRef}
              id="scan-text"
              className="textarea"
              rows={10}
              maxLength={MAX_SAMPLE_CHARS}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) void scan();
              }}
              placeholder={t('playground.placeholder')}
              dir="auto"
              aria-describedby="scan-hint"
            />
            <div className="row row--between">
              <span className="muted small" id="scan-hint">
                {t('playground.chars', { count: fmtNumber(Array.from(text).length) })} · {t('playground.shortcut')}
              </span>
              <button type="submit" className="btn btn--primary" disabled={!text.trim() || pending} aria-busy={pending}>
                <Icon name="search" size={18} />
                {pending ? t('playground.scanning') : t('playground.scan')}
              </button>
            </div>
          </form>
        </Section>

        <Section id="result" title={t('playground.result')}>
          <div aria-live="polite">
            {result ? (
              <div className="stack">
                <div className="detection-summary">
                  <ScoreGauge value={result.detection.score} label={t('playground.score')} />
                  <dl className="kv kv--tight">
                    <div>
                      <dt>{t('playground.label')}</dt>
                      <dd>
                        <DetectionLabelBadge label={result.detection.label} size="lg" />
                      </dd>
                    </div>
                    <div>
                      <dt>{t('playground.language')}</dt>
                      <dd>{t(`detLang.${result.detection.language}`)}</dd>
                    </div>
                    <div>
                      <dt>{t('playground.modelScore')}</dt>
                      <dd>{fmtNumber(result.detection.model_score, { maximumFractionDigits: 3 })}</dd>
                    </div>
                    <div>
                      <dt>{t('playground.ruleScore')}</dt>
                      <dd>{fmtNumber(result.detection.rule_score, { maximumFractionDigits: 3 })}</dd>
                    </div>
                    <div>
                      <dt>{t('playground.latency')}</dt>
                      <dd>{fmtMs(result.detection.latency_ms)}</dd>
                    </div>
                  </dl>
                </div>
              </div>
            ) : (
              <EmptyState icon="beaker" title={t('playground.empty')} />
            )}
          </div>
        </Section>
      </div>

      {result ? (
        <div className="grid-2 grid-2--wide-start">
          <Section id="spans" title={t('playground.spans')}>
            {result.detection.spans.length === 0 ? <p className="muted">{t('playground.noSpans')}</p> : null}
            <HighlightedText text={result.text} spans={result.detection.spans} />
            {result.detection.spans.length ? (
              <div className="table-wrap spans-table">
                <table className="table table--compact">
                  <thead>
                    <tr>
                      <th scope="col">{t('playground.colText')}</th>
                      <th scope="col">{t('playground.colRule')}</th>
                      <th scope="col" className="num">
                        {t('playground.colScore')}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.detection.spans.map((s, i) => (
                      <tr key={`${s.start}-${i}`}>
                        <td dir="auto">{s.text}</td>
                        <td className="mono small">{s.rule_id ?? t('playground.model')}</td>
                        <td className="num">{fmtNumber(s.score, { maximumFractionDigits: 2 })}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </Section>
          <Section id="signals" title={t('playground.signals')}>
            {result.detection.signals.length === 0 ? (
              <p className="muted">{t('playground.noSignals')}</p>
            ) : (
              <ul className="signal-list">
                {result.detection.signals.map((s) => (
                  <li key={s} className="tag">
                    <Icon name="alert" size={12} /> {s}
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      ) : null}
    </div>
  );
}

function SampleButtons({
  label,
  samples,
  lang,
  onPick,
}: {
  label: string;
  samples: readonly PlaygroundSample[];
  lang: 'en' | 'ar';
  onPick: (sample: PlaygroundSample) => void;
}) {
  return (
    <div className="row" role="group" aria-label={label}>
      <span className="muted small">{label}:</span>
      {samples.map((s) => (
        <button key={s.id} type="button" className="btn btn--ghost btn--sm" onClick={() => onPick(s)}>
          {sampleLabel(s, lang)}
        </button>
      ))}
    </div>
  );
}
