import { useEffect, useState } from 'react';
import { APPROVAL_STATUSES, type ApprovalRecord, type ApprovalStatus } from '../../shared/api/types';
import { useApi } from '../../shared/app/auth';
import { useNow, useQuery } from '../../shared/app/hooks';
import { useLive, useLiveEvent } from '../../shared/app/live';
import { ApprovalStatusBadge, RiskBadge, RiskScoreBadge } from '../../shared/components/Badges';
import { Countdown } from '../../shared/components/Countdown';
import { DecisionConfirm } from '../../shared/components/DecisionConfirm';
import { Dialog } from '../../shared/components/Dialog';
import { ApprovalExplanation, approvalSummary } from '../../shared/components/Explain';
import { Icon } from '../../shared/components/Icon';
import { EmptyState, QueryView } from '../../shared/components/States';
import { useI18n } from '../../shared/i18n';
import { applyApprovalEvent, sortApprovals } from '../../shared/lib/approvals';
import { PageHeader, Section } from '../components/PageHeader';

export default function Approvals() {
  const api = useApi();
  const { t, fmtNumber } = useI18n();
  const live = useLive();
  const [statusFilter, setStatusFilter] = useState<ApprovalStatus | ''>('');
  const [detail, setDetail] = useState<ApprovalRecord | null>(null);
  const [deciding, setDeciding] = useState<{ record: ApprovalRecord; approve: boolean } | null>(null);
  const now = useNow(1000);

  const pending = useQuery((signal) => api.approvals({ status: 'pending', limit: 200 }, signal).then(sortApprovals), [api]);
  const history = useQuery(
    (signal) => api.approvals({ status: statusFilter || undefined, limit: 100 }, signal).then((list) => sortApprovals(list.filter((a) => a.status !== 'pending'))),
    [api, statusFilter],
  );

  useLiveEvent(
    (event, data) => {
      pending.setData((list) => applyApprovalEvent(list ?? [], event, data).filter((a) => a.status === 'pending'));
      if (event === 'approval.decided') history.reload();
      setDetail((current) => (current && (data as ApprovalRecord)?.id === current.id ? (data as ApprovalRecord) : current));
    },
    ['approval.requested', 'approval.decided'],
  );

  // Without a live stream, fall back to polling so the queue never goes stale.
  const { reload: reloadPending } = pending;
  useEffect(() => {
    if (live.status === 'open') return undefined;
    const timer = setInterval(reloadPending, 15_000);
    return () => clearInterval(timer);
  }, [live.status, reloadPending]);

  function onDecided(updated: ApprovalRecord) {
    setDeciding(null);
    pending.setData((list) => (list ?? []).filter((a) => a.id !== updated.id));
    setDetail((current) => (current?.id === updated.id ? updated : current));
    history.reload();
  }

  return (
    <div className="stack-lg">
      <PageHeader title={t('approvals.title')} subtitle={t('approvals.subtitle')} />

      <p className="banner banner--warn">
        <Icon name="clock" size={20} />
        <span>{t('approvals.autoRejectNotice')}</span>
      </p>

      <Section
        id="queue"
        title={
          <>
            {t('approvals.queue')}
            {pending.data?.length ? (
              <span className="badge badge--warn queue-count">{t('approvals.pendingCount', { count: fmtNumber(pending.data.length) })}</span>
            ) : null}
          </>
        }
      >
        <QueryView {...pending}>
          {(list) =>
            list.length === 0 ? (
              <EmptyState icon="shield-check" title={t('approvals.emptyQueue')} />
            ) : (
              <div className="table-wrap table-wrap--flush" aria-live="polite">
                <table className="table queue-table">
                  <thead>
                    <tr>
                      <th scope="col">{t('approvals.colTool')}</th>
                      <th scope="col">{t('approvals.colRequest')}</th>
                      <th scope="col">{t('approvals.colAgent')}</th>
                      <th scope="col">{t('approvals.colRiskScore')}</th>
                      <th scope="col">{t('approvals.colAutoReject')}</th>
                      <th scope="col">
                        <span className="visually-hidden">{t('app.actions')}</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.map((record, index) => (
                      <QueueRow
                        key={record.id}
                        record={record}
                        now={now}
                        urgent={index === 0}
                        onOpen={() => setDetail(record)}
                        onDecide={(approve) => setDeciding({ record, approve })}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        </QueryView>
      </Section>
      <p className="page-note">
        {live.status === 'open' ? t('approvals.liveHint') : t('approvals.pollHint')} · {t('approvals.timezone', { zone: timeZone() })}
      </p>

      <Section
        id="history"
        title={t('approvals.history')}
        actions={
          <label className="row small">
            <span>{t('approvals.filterStatus')}</span>
            <select className="select select--sm" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as ApprovalStatus | '')}>
              <option value="">{t('approvals.all')}</option>
              {APPROVAL_STATUSES.filter((s) => s !== 'pending').map((s) => (
                <option key={s} value={s}>
                  {t(`status.${s}`)}
                </option>
              ))}
            </select>
          </label>
        }
      >
        <QueryView {...history}>{(list) => <HistoryTable list={list} onOpen={setDetail} />}</QueryView>
      </Section>

      {detail ? (
        <Dialog
          open
          onClose={() => setDetail(null)}
          variant="drawer"
          className="review-drawer"
          title={t('approvals.reviewTitle')}
          footer={
            detail.status === 'pending' ? (
              <div className="review-decision">
                <p className="review-decision__note">{t('approvals.signedNote')}</p>
                <button type="button" className="btn btn--danger" onClick={() => setDeciding({ record: detail, approve: false })}>
                  {t('approvals.deny')}
                </button>
                <button type="button" className="btn btn--ghost" onClick={() => setDeciding({ record: detail, approve: true })}>
                  {t('approvals.approve')}
                </button>
              </div>
            ) : undefined
          }
        >
          <div className="review">
            {detail.status !== 'pending' ? <DecisionOutcome record={detail} onBack={() => setDetail(null)} /> : null}
            <ApprovalMeta record={detail} now={now} />
            <ApprovalExplanation record={detail} argsOpen layout="review" />
          </div>
        </Dialog>
      ) : null}

      {deciding ? (
        <DecisionConfirm record={deciding.record} approve={deciding.approve} onClose={() => setDeciding(null)} onDecided={onDecided} />
      ) : null}
    </div>
  );
}

/** Time zone the dates on this page are shown in (the browser's, as fmtDateTime uses it). */
function timeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

/** Figma "Decision recorded": the outcome of a decided request, in green or rose. */
function DecisionOutcome({ record, onBack }: { record: ApprovalRecord; onBack: () => void }) {
  const { t, tx, fmtDateTime } = useI18n();
  const approved = record.status === 'approved';
  const denied = record.status === 'denied';
  const tone = approved ? 'allow' : denied ? 'deny' : 'neutral';
  const meta = [
    record.id,
    record.decided_by,
    record.decided_at ? fmtDateTime(record.decided_at) : null,
    record.decided_by ? t('approvals.outcomeSigned') : null,
  ].filter(Boolean);
  return (
    <section className={`outcome outcome--${tone}`} role="status" aria-labelledby={`outcome-${record.id}`}>
      <h3 className="outcome__title" id={`outcome-${record.id}`}>
        {approved ? t('approvals.outcomeApproved') : denied ? t('approvals.outcomeDenied') : tx(`status.${record.status}`, record.status)}
      </h3>
      <p className="outcome__body">
        {approved ? t('approvals.outcomeApprovedBody') : denied ? t('approvals.outcomeDeniedBody') : t('approvals.outcomeClosedBody')}
      </p>
      <p className="outcome__meta">
        {meta.map((part, i) => (
          <span key={i}>
            {i > 0 ? ' · ' : null}
            <bdi>{part}</bdi>
          </span>
        ))}
      </p>
      <button type="button" className="btn btn--primary outcome__back" onClick={onBack}>
        {t('approvals.backToQueue')}
      </button>
    </section>
  );
}

function ApprovalMeta({ record, now }: { record: ApprovalRecord; now: number }) {
  const { t, fmtDateTime } = useI18n();
  return (
    <div className="approval-meta">
      <p className="approval-meta__crumbs">
        <span>{t('nav.approvals')}</span>
        <span aria-hidden="true"> / </span>
        <bdi className="mono">{record.id}</bdi>
        <span aria-hidden="true"> · </span>
        <bdi className="mono">{record.agent_id}</bdi>
      </p>
      <ApprovalStatusBadge status={record.status} />
      <RiskScoreBadge risk={record.risk} score={record.decision?.risk_score} withLabel />
      {record.status === 'pending' ? <Countdown expiresAt={record.expires_at} createdAt={record.created_at} now={now} /> : null}
      <span className="muted small approval-meta__requested">
        {t('approvals.requestedBy', { agent: record.agent_id })} · {fmtDateTime(record.created_at)}
      </span>
      {record.decided_by ? (
        <span className="muted small">
          {t('approvals.decidedBy', { user: record.decided_by })}
          {record.decided_at ? ` · ${fmtDateTime(record.decided_at)}` : ''}
        </span>
      ) : null}
      {record.note ? (
        <p className="approval-meta__note" dir="auto">
          “{record.note}”
        </p>
      ) : null}
    </div>
  );
}

/**
 * One row of the Figma "Actions awaiting your review" table. The first (most urgent) row is
 * highlighted, as in the design. Deny and approve stay available from the row, as icon
 * buttons beside "View", so the queue keeps its quick decisions.
 */
function QueueRow({
  record,
  now,
  urgent,
  onOpen,
  onDecide,
}: {
  record: ApprovalRecord;
  now: number;
  urgent: boolean;
  onOpen: () => void;
  onDecide: (approve: boolean) => void;
}) {
  const { t, lang } = useI18n();
  const expired = record.expires_at * 1000 <= now;
  return (
    <tr className={urgent ? 'queue-row--urgent' : undefined}>
      <td className="queue-table__tool">
        <bdi>{record.tool}</bdi>
      </td>
      <td className="queue-table__summary" dir="auto">
        {approvalSummary(record, lang, t('approvals.fallbackSummary', { agent: record.agent_id, tool: record.tool }))}
      </td>
      <td className="queue-table__agent">
        <bdi>{record.agent_id}</bdi>
      </td>
      <td>
        <RiskScoreBadge risk={record.risk} score={record.decision?.risk_score} />
      </td>
      <td className="queue-table__countdown">
        <Countdown expiresAt={record.expires_at} createdAt={record.created_at} now={now} compact />
      </td>
      <td>
        <div className="queue-table__actions">
          <button type="button" className="btn btn--ghost btn--sm queue-table__view" onClick={onOpen}>
            {t('app.view')}
          </button>
          <button
            type="button"
            className="icon-btn icon-btn--sm queue-table__deny"
            onClick={() => onDecide(false)}
            disabled={expired}
            aria-label={t('approvals.deny')}
            title={t('approvals.deny')}
          >
            <Icon name="x" size={18} />
          </button>
          <button
            type="button"
            className="icon-btn icon-btn--sm queue-table__approve"
            onClick={() => onDecide(true)}
            disabled={expired}
            aria-label={t('approvals.approve')}
            title={t('approvals.approve')}
          >
            <Icon name="check" size={18} />
          </button>
        </div>
      </td>
    </tr>
  );
}

function HistoryTable({ list, onOpen }: { list: ApprovalRecord[]; onOpen: (r: ApprovalRecord) => void }) {
  const { t, fmtDateTime } = useI18n();
  if (list.length === 0) return <EmptyState icon="clock" title={t('approvals.emptyHistory')} />;
  return (
    <div className="table-wrap table-wrap--flush">
      <table className="table table--interactive">
        <thead>
          <tr>
            <th scope="col">{t('approvals.colCreated')}</th>
            <th scope="col">{t('approvals.colTool')}</th>
            <th scope="col">{t('approvals.colAgent')}</th>
            <th scope="col">{t('approvals.colRisk')}</th>
            <th scope="col">{t('approvals.colStatus')}</th>
            <th scope="col">{t('approvals.colDecidedBy')}</th>
            <th scope="col">{t('approvals.colNote')}</th>
          </tr>
        </thead>
        <tbody>
          {list.map((r) => (
            <tr key={r.id} onClick={() => onOpen(r)}>
              <td>
                <button
                  type="button"
                  className="row-button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpen(r);
                  }}
                >
                  {fmtDateTime(r.created_at, { dateStyle: 'short', timeStyle: 'short' })}
                </button>
              </td>
              <td className="mono small">{r.tool}</td>
              <td className="mono small">{r.agent_id}</td>
              <td>
                <RiskBadge risk={r.risk} />
              </td>
              <td>
                <ApprovalStatusBadge status={r.status} />
              </td>
              <td>
                {r.decided_by ?? '–'}
                {r.decided_at ? <div className="muted small">{fmtDateTime(r.decided_at, { timeStyle: 'short' })}</div> : null}
              </td>
              <td className="small" dir="auto">
                {r.note ?? ''}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

