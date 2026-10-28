import { useEffect, useState } from 'react';
import { APPROVAL_STATUSES, type ApprovalRecord, type ApprovalStatus } from '../../shared/api/types';
import { useApi } from '../../shared/app/auth';
import { useNow, useQuery } from '../../shared/app/hooks';
import { useLive, useLiveEvent } from '../../shared/app/live';
import { ApprovalStatusBadge, RiskBadge, riskIcon } from '../../shared/components/Badges';
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
  const { t } = useI18n();
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

      <Section
        id="queue"
        title={
          <>
            <Icon name="inbox" size={18} />
            {t('approvals.queue')}
            {pending.data?.length ? <span className="count-pill">{pending.data.length}</span> : null}
          </>
        }
        subtitle={live.status === 'open' ? t('approvals.liveHint') : t('approvals.pollHint')}
      >
        <QueryView {...pending}>
          {(list) =>
            list.length === 0 ? (
              <EmptyState icon="shield-check" title={t('approvals.emptyQueue')} />
            ) : (
              <ul className="queue" aria-live="polite">
                {list.map((record) => (
                  <QueueCard
                    key={record.id}
                    record={record}
                    now={now}
                    onOpen={() => setDetail(record)}
                    onDecide={(approve) => setDeciding({ record, approve })}
                  />
                ))}
              </ul>
            )
          }
        </QueryView>
      </Section>

      <Section
        id="history"
        title={
          <>
            <Icon name="clock" size={18} />
            {t('approvals.history')}
          </>
        }
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
          title={
            <>
              <RiskBadge risk={detail.risk} />
              <code className="code-inline">{detail.tool}</code>
            </>
          }
          footer={
            detail.status === 'pending' ? (
              <>
                <button type="button" className="btn btn--danger" onClick={() => setDeciding({ record: detail, approve: false })}>
                  <Icon name="x" />
                  {t('approvals.deny')}
                </button>
                <button type="button" className="btn btn--approve" onClick={() => setDeciding({ record: detail, approve: true })}>
                  <Icon name="check" />
                  {t('approvals.approve')}
                </button>
              </>
            ) : undefined
          }
        >
          <ApprovalMeta record={detail} now={now} />
          <ApprovalExplanation record={detail} argsOpen />
        </Dialog>
      ) : null}

      {deciding ? (
        <DecisionConfirm record={deciding.record} approve={deciding.approve} onClose={() => setDeciding(null)} onDecided={onDecided} />
      ) : null}
    </div>
  );
}

function ApprovalMeta({ record, now }: { record: ApprovalRecord; now: number }) {
  const { t, fmtDateTime } = useI18n();
  return (
    <div className="approval-meta">
      <ApprovalStatusBadge status={record.status} />
      {record.status === 'pending' ? <Countdown expiresAt={record.expires_at} createdAt={record.created_at} now={now} showBar /> : null}
      <span className="muted small">
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

function QueueCard({ record, now, onOpen, onDecide }: { record: ApprovalRecord; now: number; onOpen: () => void; onDecide: (approve: boolean) => void }) {
  const { t, lang } = useI18n();
  const expired = record.expires_at * 1000 <= now;
  return (
    <li className={`queue-card risk--${record.risk}`}>
      <div className="queue-card__stripe" aria-hidden="true">
        <Icon name={riskIcon(record.risk)} size={18} />
      </div>
      <div className="queue-card__main">
        <div className="row row--between">
          <div className="row">
            <RiskBadge risk={record.risk} />
            <code className="code-inline">{record.tool}</code>
            <span className="muted small">{t('approvals.requestedBy', { agent: record.agent_id })}</span>
          </div>
          <Countdown expiresAt={record.expires_at} createdAt={record.created_at} now={now} showBar />
        </div>
        <p className="queue-card__summary" dir="auto">
          {approvalSummary(record, lang, t('approvals.fallbackSummary', { agent: record.agent_id, tool: record.tool }))}
        </p>
        <div className="row">
          <button type="button" className="btn btn--ghost btn--sm" onClick={onOpen}>
            <Icon name="eye" size={16} />
            {t('approvals.review')}
          </button>
          <span className="spacer" />
          <button type="button" className="btn btn--danger btn--sm" onClick={() => onDecide(false)} disabled={expired}>
            <Icon name="x" size={16} />
            {t('approvals.deny')}
          </button>
          <button type="button" className="btn btn--approve btn--sm" onClick={() => onDecide(true)} disabled={expired}>
            <Icon name="check" size={16} />
            {t('approvals.approve')}
          </button>
        </div>
      </div>
    </li>
  );
}

function HistoryTable({ list, onOpen }: { list: ApprovalRecord[]; onOpen: (r: ApprovalRecord) => void }) {
  const { t, fmtDateTime } = useI18n();
  if (list.length === 0) return <EmptyState icon="clock" title={t('approvals.emptyHistory')} />;
  return (
    <div className="table-wrap">
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

