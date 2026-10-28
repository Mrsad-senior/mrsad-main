import { useState } from 'react';
import type { AuditEvent, AuditVerifyReport, DetectionResult, Reason, ReplayReport, SessionSnapshot } from '../../shared/api/types';
import { useApi } from '../../shared/app/auth';
import { saveBlob, useQuery } from '../../shared/app/hooks';
import { useToast } from '../../shared/app/toast';
import { DecisionBadge, DetectionLabelBadge, InspectionBadge, RiskBadge } from '../../shared/components/Badges';
import { CopyButton } from '../../shared/components/CopyButton';
import { Dialog } from '../../shared/components/Dialog';
import { ArgumentsList, ProvenanceList, ReasonTable } from '../../shared/components/Explain';
import { ScoreGauge } from '../../shared/components/Gauge';
import { HighlightedText } from '../../shared/components/Highlight';
import { Icon } from '../../shared/components/Icon';
import { JsonView } from '../../shared/components/JsonView';
import { ErrorState, Spinner } from '../../shared/components/States';
import { useI18n } from '../../shared/i18n';
import { safeJson, shortHash } from '../../shared/lib/format';
import { extractProvenance, snapshotSources } from '../../shared/lib/provenance';

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v);

/** Pulls the well-known parts out of an audit payload (shapes per BUILD_SPEC sections 5-6). */
export function parsePayload(event: AuditEvent) {
  const p = isObj(event.payload) ? event.payload : {};
  const decision = isObj(p.decision) ? p.decision : undefined;
  const reasons = (Array.isArray(p.reasons) ? p.reasons : Array.isArray(decision?.reasons) ? decision.reasons : []) as Reason[];
  const call = isObj(p.call) ? p.call : undefined;
  const args = (isObj(call?.arguments) ? call.arguments : isObj(p.arguments) ? p.arguments : undefined) as Obj | undefined;
  const result = isObj(p.result) ? p.result : undefined;
  const detection = (isObj(p.detection) ? p.detection : isObj(result?.detection) ? result.detection : undefined) as DetectionResult | undefined;
  const content =
    typeof result?.content === 'string' ? result.content : typeof p.content === 'string' ? p.content : typeof p.text === 'string' ? p.text : undefined;
  const snapshot = (isObj(p.snapshot) ? p.snapshot : undefined) as SessionSnapshot | undefined;
  const riskScore = typeof p.risk_score === 'number' ? p.risk_score : typeof decision?.risk_score === 'number' ? decision.risk_score : undefined;
  const sink = typeof p.sink === 'string' ? p.sink : typeof decision?.sink === 'string' ? decision.sink : undefined;
  const enforced = p.enforced === false ? false : undefined;
  return { reasons, args, detection, content, snapshot, riskScore, sink, enforced };
}

const REPLAYABLE = new Set(['tool_call.decision', 'tool_result.inspection']);
const INSPECTION = new Set(['pass', 'flag', 'sanitize', 'block']);

export type TraceKey = 'call_id' | 'session_id';

export function EventDrawer({
  seq,
  initial,
  onClose,
  onFilter,
}: {
  seq: number;
  initial: AuditEvent | null;
  onClose: () => void;
  /** Show every event of the same call or session in the list behind the drawer. */
  onFilter?: (key: TraceKey, value: string) => void;
}) {
  const api = useApi();
  const { t, tx } = useI18n();
  const query = useQuery<AuditEvent>(() => (initial ? Promise.resolve(initial) : api.auditEvent(seq)), [seq]);
  const event = query.data;

  return (
    <Dialog
      open
      onClose={onClose}
      variant="drawer"
      title={
        <>
          <span className="mono">#{seq}</span>
          {event ? <span>{tx(`event.${event.event_type}`, event.event_type)}</span> : null}
        </>
      }
    >
      {event ? <EventBody event={event} onFilter={onFilter} /> : query.error ? <ErrorState error={query.error} onRetry={query.reload} /> : <Spinner label={t('app.loading')} />}
    </Dialog>
  );
}

function EventBody({ event, onFilter }: { event: AuditEvent; onFilter?: (key: TraceKey, value: string) => void }) {
  const api = useApi();
  const toast = useToast();
  const { t, tx, fmtDateTime, fmtNumber } = useI18n();
  const parsed = parsePayload(event);
  const [replay, setReplay] = useState<ReplayReport | null>(null);
  const [verify, setVerify] = useState<AuditVerifyReport | null>(null);
  const [busy, setBusy] = useState<'replay' | 'verify' | null>(null);
  const provenance = extractProvenance(parsed.reasons);
  const sessionSources = provenance.length === 0 ? snapshotSources(parsed.snapshot) : [];

  async function run(kind: 'replay' | 'verify') {
    setBusy(kind);
    try {
      if (kind === 'replay') setReplay(await api.replay(event.seq));
      else setVerify(await api.verifyAudit());
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(null);
    }
  }

  function exportEvent() {
    saveBlob(new Blob([safeJson(event)], { type: 'application/json' }), `mirsad-audit-event-${event.seq}.json`);
  }

  return (
    <div className="stack-lg">
      <div className="row">
        {REPLAYABLE.has(event.event_type) ? (
          <button type="button" className="btn btn--ghost btn--sm" onClick={() => run('replay')} disabled={busy !== null} aria-busy={busy === 'replay'}>
            <Icon name="play" size={16} />
            {t('drawer.replay')}
          </button>
        ) : null}
        <button type="button" className="btn btn--ghost btn--sm" onClick={() => run('verify')} disabled={busy !== null} aria-busy={busy === 'verify'}>
          <Icon name="shield-check" size={16} />
          {t('activity.verify')}
        </button>
        <button type="button" className="btn btn--ghost btn--sm" onClick={exportEvent}>
          <Icon name="download" size={16} />
          {t('drawer.exportEvent')}
        </button>
        {onFilter && event.call_id ? (
          <button type="button" className="btn btn--ghost btn--sm" onClick={() => onFilter('call_id', event.call_id as string)}>
            <Icon name="filter" size={16} />
            {t('drawer.traceCall')}
          </button>
        ) : null}
        {onFilter && event.session_id ? (
          <button type="button" className="btn btn--ghost btn--sm" onClick={() => onFilter('session_id', event.session_id as string)}>
            <Icon name="filter" size={16} />
            {t('drawer.traceSession')}
          </button>
        ) : null}
      </div>

      <div aria-live="polite" className="stack-sm">
        {replay ? (
          <div className={`banner banner--${replay.match ? 'allow' : 'deny'}`}>
            <Icon name={replay.match ? 'check-circle' : 'diff'} />
            <div className="banner__body">
              <strong>
                {replay.match
                  ? t('drawer.replayMatch', { action: tActionLike(t, replay.replayed_action) })
                  : t('drawer.replayMismatch', { original: tActionLike(t, replay.original_action), replayed: tActionLike(t, replay.replayed_action) })}
              </strong>
              {replay.details ? (
                <details>
                  <summary>{t('app.details')}</summary>
                  <JsonView value={replay.details} openDepth={2} />
                </details>
              ) : null}
            </div>
          </div>
        ) : null}
        {verify ? (
          <div className={`banner banner--${verify.ok ? 'allow' : 'deny'}`}>
            <Icon name={verify.ok ? 'shield-check' : 'shield-alert'} />
            <div className="banner__body">
              <strong>
                {verify.ok
                  ? t('activity.verifyOk', { count: fmtNumber(verify.checked) })
                  : t('activity.verifyFail', { seq: verify.first_bad_seq ?? '?', message: verify.message })}
              </strong>
            </div>
          </div>
        ) : null}
      </div>

      <section className="stack-sm" aria-labelledby="ev-summary">
        <h3 id="ev-summary">{t('drawer.summary')}</h3>
        <dl className="kv">
          <div>
            <dt>{t('activity.colTime')}</dt>
            <dd>{fmtDateTime(event.ts)}</dd>
          </div>
          <div>
            <dt>{t('activity.colAction')}</dt>
            <dd>
              {event.action ? INSPECTION.has(event.action) ? <InspectionBadge action={event.action} /> : <DecisionBadge action={event.action} /> : '–'}
              {parsed.enforced === false ? <span className="tag">{t('drawer.notEnforced')}</span> : null}
            </dd>
          </div>
          <div>
            <dt>{t('activity.colRisk')}</dt>
            <dd>
              {event.risk ? <RiskBadge risk={event.risk} /> : '–'}
              {parsed.riskScore !== undefined ? <span className="muted small"> {fmtNumber(parsed.riskScore, { maximumFractionDigits: 2 })}</span> : null}
            </dd>
          </div>
          <div>
            <dt>{t('activity.colAgent')}</dt>
            <dd className="mono">{event.agent_id ?? '–'}</dd>
          </div>
          <div>
            <dt>{t('activity.colTool')}</dt>
            <dd className="mono">{event.tool ?? '–'}</dd>
          </div>
          <div>
            <dt>{t('drawer.sink')}</dt>
            <dd>{parsed.sink ? tx(`sink.${parsed.sink}`, parsed.sink) : '–'}</dd>
          </div>
          <div>
            <dt>{t('drawer.session')}</dt>
            <dd className="mono small">{event.session_id ?? '–'}</dd>
          </div>
          <div>
            <dt>{t('drawer.callId')}</dt>
            <dd className="mono small">{event.call_id ?? '–'}</dd>
          </div>
          <div>
            <dt>{t('drawer.policyVersion')}</dt>
            <dd className="mono small" title={event.policy_version ?? undefined}>
              {shortHash(event.policy_version, 12)}
            </dd>
          </div>
        </dl>
      </section>

      {parsed.reasons.length > 0 || event.event_type === 'tool_call.decision' ? (
        <section className="stack-sm" aria-labelledby="ev-reasons">
          <h3 id="ev-reasons">{t('drawer.reasons')}</h3>
          <ReasonTable reasons={parsed.reasons} />
        </section>
      ) : null}

      {parsed.detection ? (
        <section className="stack-sm" aria-labelledby="ev-detection">
          <h3 id="ev-detection">{t('drawer.detection')}</h3>
          <div className="detection-summary">
            <ScoreGauge value={parsed.detection.score} label={t('playground.score')} size={150} />
            <div className="stack-sm">
              <DetectionLabelBadge label={parsed.detection.label} size="lg" />
              <p className="small muted">
                {t('playground.language')}: {t(`detLang.${parsed.detection.language}`)} · {t('playground.modelScore')}:{' '}
                {fmtNumber(parsed.detection.model_score, { maximumFractionDigits: 2 })} · {t('playground.ruleScore')}:{' '}
                {fmtNumber(parsed.detection.rule_score, { maximumFractionDigits: 2 })}
              </p>
              {parsed.detection.signals.length ? (
                <ul className="signal-list">
                  {parsed.detection.signals.map((s) => (
                    <li key={s} className="tag">
                      {s}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </div>
          {parsed.content !== undefined ? (
            <>
              <h4 className="small muted">{t('drawer.content')}</h4>
              <HighlightedText text={parsed.content} spans={parsed.detection.spans ?? []} />
            </>
          ) : null}
        </section>
      ) : null}

      {parsed.reasons.some((r) => r.layer === 'taint') || parsed.snapshot ? (
        <section className="stack-sm" aria-labelledby="ev-taint">
          <h3 id="ev-taint">{t('drawer.provenance')}</h3>
          <ProvenanceList items={provenance.length ? provenance : sessionSources} emptyText={t('drawer.provenanceEmpty')} />
          {parsed.snapshot ? <SnapshotTable snapshot={parsed.snapshot} /> : null}
        </section>
      ) : null}

      {parsed.args ? (
        <section aria-label={t('drawer.arguments')}>
          <ArgumentsList args={parsed.args} flagged={provenance.map((p) => p.param).filter((p): p is string => Boolean(p))} defaultOpen />
        </section>
      ) : null}

      <section className="stack-sm" aria-labelledby="ev-hash">
        <h3 id="ev-hash">{t('drawer.hashes')}</h3>
        <dl className="kv kv--hash">
          <div>
            <dt>{t('drawer.prevHash')}</dt>
            <dd className="mono small hash">{event.prev_hash}</dd>
          </div>
          <div>
            <dt>{t('drawer.hash')}</dt>
            <dd className="mono small hash">
              {event.hash} <CopyButton text={event.hash} />
            </dd>
          </div>
        </dl>
      </section>

      <section className="stack-sm">
        <JsonView value={event} label={t('drawer.raw')} openDepth={1} />
      </section>
    </div>
  );
}

function tActionLike(t: ReturnType<typeof useI18n>['t'], action: string | null): string {
  switch (action) {
    case 'allow':
    case 'require_approval':
    case 'deny':
      return t(`action.${action}`);
    case 'pass':
    case 'flag':
    case 'sanitize':
    case 'block':
      return t(`inspection.${action}`);
    default:
      return action ?? '–';
  }
}

function SnapshotTable({ snapshot }: { snapshot: SessionSnapshot }) {
  const { t, fmtNumber } = useI18n();
  const values = snapshot.values ?? [];
  return (
    <details className="snapshot">
      <summary>
        {t('drawer.sessionState')} ·{' '}
        {t('drawer.snapshotSummary', {
          sources: fmtNumber(snapshot.untrusted_sources?.length ?? 0),
          values: fmtNumber(values.length),
        })}
        {snapshot.injection_detected ? (
          <span className="badge badge--deny">
            <Icon name="shield-alert" size={14} />
            {t('drawer.injectionSeen')}
          </span>
        ) : null}
      </summary>
      {values.length ? (
        <div className="table-wrap">
          <table className="table table--compact">
            <thead>
              <tr>
                <th scope="col">{t('drawer.colValue')}</th>
                <th scope="col">{t('drawer.colKind')}</th>
                <th scope="col">{t('drawer.colSource')}</th>
                <th scope="col">{t('drawer.colField')}</th>
                <th scope="col">{t('drawer.colTrust')}</th>
                <th scope="col">{t('drawer.colSensitivity')}</th>
              </tr>
            </thead>
            <tbody>
              {values.slice(0, 200).map((v, i) => (
                <tr key={`${v.value}-${i}`}>
                  <td className="mono small">
                    <bdi>{v.value}</bdi>
                  </td>
                  <td>{v.kind}</td>
                  <td className="mono small">
                    {v.source_tool}
                    <div className="muted">{v.source_call_id}</div>
                  </td>
                  <td className="mono small">
                    {v.field ?? '–'}
                    {v.trusted_field ? <span className="tag tag--trusted">{t('drawer.trustedField')}</span> : null}
                  </td>
                  <td>
                    <span className={`tag tag--${v.trust}`}>{t(`trust.${v.trust}`)}</span>
                  </td>
                  <td>{t(`sensitivity.${v.sensitivity}`)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted">{t('drawer.provenanceEmpty')}</p>
      )}
    </details>
  );
}
