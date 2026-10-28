/** Explaining a decision: reasons, data provenance and call arguments. */
import { useState } from 'react';
import type { ApprovalRecord, Reason } from '../api/types';
import { useI18n } from '../i18n';
import { stringifyArg, truncate } from '../lib/format';
import { extractProvenance, type ProvenanceItem, pauseReasons } from '../lib/provenance';
import { DecisionBadge, LayerChip } from './Badges';
import { Icon } from './Icon';
import { JsonView } from './JsonView';

export function reasonText(reason: Reason, lang: 'en' | 'ar'): string {
  return lang === 'ar' && reason.message_ar ? reason.message_ar : reason.message;
}

/** Full reasons table (dashboard). */
export function ReasonTable({ reasons }: { reasons: readonly Reason[] }) {
  const { t, lang, fmtNumber } = useI18n();
  if (reasons.length === 0) return <p className="muted">{t('drawer.noReasons')}</p>;
  return (
    <div className="table-wrap">
      <table className="table table--compact">
        <thead>
          <tr>
            <th scope="col">{t('drawer.colLayer')}</th>
            <th scope="col">{t('drawer.colCode')}</th>
            <th scope="col">{t('drawer.colMessage')}</th>
            <th scope="col">{t('drawer.colAction')}</th>
            <th scope="col" className="num">
              {t('drawer.colScore')}
            </th>
          </tr>
        </thead>
        <tbody>
          {reasons.map((reason, i) => (
            <tr key={`${reason.code}-${i}`}>
              <td>
                <LayerChip layer={reason.layer} />
              </td>
              <td>
                <code className="code-inline">{reason.code}</code>
                {reason.rule_id ? <div className="muted small">{reason.rule_id}</div> : null}
              </td>
              <td>
                <span dir="auto">{reasonText(reason, lang)}</span>
                {reason.evidence && Object.keys(reason.evidence).length > 0 ? (
                  <details className="evidence">
                    <summary>{t('drawer.evidence')}</summary>
                    <JsonView value={reason.evidence} openDepth={2} />
                  </details>
                ) : null}
              </td>
              <td>
                <DecisionBadge action={reason.action} />
              </td>
              <td className="num">{fmtNumber(reason.risk_score, { maximumFractionDigits: 2 })}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Plain-language bullets (approver): the reasons that actually caused the pause. */
export function WhyPaused({ reasons }: { reasons: readonly Reason[] }) {
  const { t, lang } = useI18n();
  const items = pauseReasons(reasons);
  if (items.length === 0) return <p className="muted">{t('approvals.noReasons')}</p>;
  return (
    <ul className="why-list">
      {items.map((reason, i) => (
        <li key={`${reason.code}-${i}`} className={`why-list__item why-list__item--${reason.action}`}>
          <Icon name={reason.action === 'deny' ? 'x-octagon' : reason.action === 'require_approval' ? 'pause' : 'info'} size={18} />
          <div>
            <p dir="auto">{reasonText(reason, lang)}</p>
            <LayerChip layer={reason.layer} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function ProvenanceList({ items, emptyText }: { items: readonly ProvenanceItem[]; emptyText?: string }) {
  const { t } = useI18n();
  if (items.length === 0) return <p className="muted">{emptyText ?? t('approvals.noProvenance')}</p>;
  return (
    <ul className="prov-list">
      {items.map((item, i) => (
        <li key={i} className="prov-list__item">
          <Icon name="database" size={18} className="prov-list__icon" />
          <div className="prov-list__body">
            {item.value ? (
              <p className="prov-list__value">
                <bdi className="mono">{truncate(item.value, 120)}</bdi>
                {item.param ? <span className="muted"> {t('prov.inArg', { param: item.param })}</span> : null}
              </p>
            ) : null}
            <p>
              {t('prov.from')} <strong className="mono">{item.sourceTool ?? t('app.unknown')}</strong>
              {item.field ? <span className="muted"> · {t('prov.field', { field: item.field })}</span> : null}
            </p>
            <p className="prov-list__meta">
              {item.sourceCallId ? <code className="code-inline">{item.sourceCallId}</code> : null}
              {item.trust ? <span className={`tag tag--${item.trust}`}>{t(item.trust === 'untrusted' ? 'trust.untrusted' : 'trust.trusted')}</span> : null}
              {item.sensitivity ? <span className="tag">{tSens(t, item.sensitivity)}</span> : null}
              <code className="muted small">{item.code}</code>
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function tSens(t: ReturnType<typeof useI18n>['t'], s: string): string {
  if (s === 'public') return t('sensitivity.public');
  if (s === 'confidential') return t('sensitivity.confidential');
  return t('sensitivity.internal');
}

const LONG_VALUE = 280;

/** Collapsible argument list; arguments named in taint evidence are flagged. */
export function ArgumentsList({
  args,
  flagged = [],
  defaultOpen = false,
}: {
  args: Record<string, unknown>;
  flagged?: readonly string[];
  defaultOpen?: boolean;
}) {
  const { t, fmtNumber } = useI18n();
  const entries = Object.entries(args ?? {});
  return (
    <details className="args" open={defaultOpen}>
      <summary className="args__summary">
        <Icon name="chevron-down" size={18} className="args__chevron" />
        {t('approvals.arguments', { count: fmtNumber(entries.length) })}
      </summary>
      {entries.length === 0 ? (
        <p className="muted">{t('app.none')}</p>
      ) : (
        <dl className="args__list">
          {entries.map(([key, value]) => (
            <ArgRow key={key} name={key} value={value} flagged={flagged.includes(key)} />
          ))}
        </dl>
      )}
    </details>
  );
}

function ArgRow({ name, value, flagged }: { name: string; value: unknown; flagged: boolean }) {
  const { t } = useI18n();
  const text = stringifyArg(value);
  const [expanded, setExpanded] = useState(false);
  const long = Array.from(text).length > LONG_VALUE;
  return (
    <div className={`args__row${flagged ? ' args__row--flagged' : ''}`}>
      <dt className="mono">
        {name}
        {flagged ? (
          <span className="tag tag--untrusted">
            <Icon name="alert" size={12} /> {t('approvals.flaggedArg')}
          </span>
        ) : null}
      </dt>
      <dd>
        <pre className="args__value" dir="auto">
          {long && !expanded ? truncate(text, LONG_VALUE) : text}
        </pre>
        {long ? (
          <button type="button" className="btn btn--link btn--sm" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}>
            {expanded ? t('app.showLess') : t('app.showMore')}
          </button>
        ) : null}
      </dd>
    </div>
  );
}

export function approvalSummary(record: ApprovalRecord, lang: 'en' | 'ar', fallback: string): string {
  const text = lang === 'ar' ? record.summary_ar || record.summary_en : record.summary_en || record.summary_ar;
  return text || fallback;
}

/** Summary + why paused + provenance + arguments (shared by dashboard and PWA). */
export function ApprovalExplanation({ record, argsOpen = false }: { record: ApprovalRecord; argsOpen?: boolean }) {
  const { t, lang } = useI18n();
  const reasons = record.decision?.reasons ?? [];
  const provenance = extractProvenance(reasons);
  const flagged = provenance.map((p) => p.param).filter((p): p is string => Boolean(p));
  return (
    <div className="explain">
      <section aria-labelledby={`sum-${record.id}`} className="explain__section">
        <h3 id={`sum-${record.id}`} className="explain__title">
          {t('approvals.summary')}
        </h3>
        <p className="explain__summary" dir="auto">
          {approvalSummary(record, lang, t('approvals.fallbackSummary', { agent: record.agent_id, tool: record.tool }))}
        </p>
      </section>
      <section aria-labelledby={`why-${record.id}`} className="explain__section">
        <h3 id={`why-${record.id}`} className="explain__title">
          <Icon name="pause" size={18} /> {t('approvals.whyPaused')}
        </h3>
        <WhyPaused reasons={reasons} />
      </section>
      <section aria-labelledby={`from-${record.id}`} className="explain__section">
        <h3 id={`from-${record.id}`} className="explain__title">
          <Icon name="database" size={18} /> {t('approvals.dataFrom')}
        </h3>
        <ProvenanceList items={provenance} />
      </section>
      <ArgumentsList args={record.arguments} flagged={flagged} defaultOpen={argsOpen} />
    </div>
  );
}
