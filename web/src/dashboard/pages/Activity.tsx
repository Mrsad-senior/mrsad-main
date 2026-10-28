import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { AuditEvent, AuditFilters, AuditVerifyReport } from '../../shared/api/types';
import { useApi } from '../../shared/app/auth';
import { saveBlob, useQuery } from '../../shared/app/hooks';
import { useLiveEvent } from '../../shared/app/live';
import { useToast } from '../../shared/app/toast';
import { DecisionBadge, InspectionBadge, RiskBadge } from '../../shared/components/Badges';
import { Icon } from '../../shared/components/Icon';
import { EmptyState, QueryView } from '../../shared/components/States';
import { useI18n } from '../../shared/i18n';
import { fromLocalInput, toLocalInput } from '../../shared/lib/format';
import { EventDrawer } from '../components/EventDrawer';
import { PageHeader } from '../components/PageHeader';

/** Event types written by the gateway, the API routers and the CLI (see BUILD_SPEC 5.2). */
export const EVENT_TYPES = [
  'tool_call.decision',
  'tool_result.inspection',
  'approval.requested',
  'approval.decided',
  'policy.activated',
  'agent.created',
  'agent.updated',
  'agent.key_rotated',
  'agent.deleted',
  'user.created',
  'user.updated',
  'user.deleted',
  'auth.login',
  'auth.login_failed',
  'system.started',
  'audit.verified',
] as const;

const DECISION_ACTIONS = ['allow', 'require_approval', 'deny'] as const;
const INSPECTION_ACTIONS = ['pass', 'flag', 'sanitize', 'block'] as const;
const PAGE_SIZES = [25, 50, 100] as const;
const TEXT_FILTERS = ['agent_id', 'tool', 'action', 'event_type', 'session_id', 'call_id', 'q'] as const;

/** Filters live in the URL (`#/activity?tool=send_email&offset=50`) so views can be shared. */
function filtersFromParams(params: URLSearchParams): AuditFilters {
  const f: AuditFilters = {};
  for (const key of TEXT_FILTERS) {
    const v = params.get(key);
    if (v) f[key] = v;
  }
  const since = Number(params.get('since'));
  const until = Number(params.get('until'));
  if (since) f.since = since;
  if (until) f.until = until;
  const limit = Number(params.get('limit'));
  f.limit = (PAGE_SIZES as readonly number[]).includes(limit) ? limit : 25;
  f.offset = Math.max(0, Number(params.get('offset')) || 0);
  return f;
}

function paramsFromFilters(f: AuditFilters, seq?: number | null): URLSearchParams {
  const p = new URLSearchParams();
  for (const [key, value] of Object.entries(f)) {
    if (value === undefined || value === '' || value === null) continue;
    if (key === 'offset' && !value) continue;
    if (key === 'limit' && value === 25) continue;
    p.set(key, String(value));
  }
  if (seq) p.set('seq', String(seq));
  return p;
}

export default function Activity() {
  const api = useApi();
  const toast = useToast();
  const { t, tx, fmtNumber, fmtDateTime } = useI18n();
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => filtersFromParams(params), [params]);
  const openSeq = Number(params.get('seq')) || null;
  const [newEvents, setNewEvents] = useState(0);
  const [verify, setVerify] = useState<AuditVerifyReport | null>(null);
  const [verifying, setVerifying] = useState(false);

  const query = useQuery((signal) => api.auditEvents(filters, signal), [api, JSON.stringify(filters)]);
  useEffect(() => setNewEvents(0), [query.data]);
  useLiveEvent(() => setNewEvents((n) => n + 1), ['audit.event']);

  const update = (next: AuditFilters, seq: number | null = openSeq) => setParams(paramsFromFilters(next, seq));
  const openEvent = (seq: number | null) => update(filters, seq);

  async function runVerify() {
    setVerifying(true);
    try {
      const report = await api.verifyAudit();
      setVerify(report);
    } catch (err) {
      toast.error(err);
    } finally {
      setVerifying(false);
    }
  }

  async function runExport(format: 'json' | 'csv') {
    try {
      const { limit: _l, offset: _o, ...rest } = filters;
      const file = await api.exportAudit(format, rest);
      saveBlob(file.blob, file.filename);
      toast.success(t('activity.exported'));
    } catch (err) {
      toast.error(err);
    }
  }

  const page = query.data;
  const limit = filters.limit ?? 25;
  const offset = filters.offset ?? 0;
  const items = page?.items ?? [];
  const selected = items.find((e) => e.seq === openSeq) ?? null;

  return (
    <div className="stack-lg">
      <PageHeader
        title={t('activity.title')}
        subtitle={t('activity.subtitle')}
        actions={
          <>
            <button type="button" className="btn btn--ghost btn--sm" onClick={runVerify} disabled={verifying} aria-busy={verifying}>
              <Icon name="shield-check" size={16} />
              {t('activity.verify')}
            </button>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => runExport('json')}>
              <Icon name="download" size={16} />
              {t('activity.exportJson')}
            </button>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => runExport('csv')}>
              <Icon name="download" size={16} />
              {t('activity.exportCsv')}
            </button>
          </>
        }
      />

      {verify ? (
        <div className={`banner banner--${verify.ok ? 'allow' : 'deny'}`} role="status">
          <Icon name={verify.ok ? 'shield-check' : 'shield-alert'} />
          <div className="banner__body">
            <strong>
              {verify.ok
                ? t('activity.verifyOk', { count: fmtNumber(verify.checked) })
                : t('activity.verifyFail', { seq: verify.first_bad_seq ?? '?', message: verify.message })}
            </strong>
            <span className="small mono">
              {t('activity.verifyHead', { seq: verify.head_seq, hash: verify.head_hash.slice(0, 16) })}
            </span>
          </div>
          <button type="button" className="icon-btn icon-btn--sm" onClick={() => setVerify(null)} aria-label={t('app.close')}>
            <Icon name="x" />
          </button>
        </div>
      ) : null}

      <FilterForm initial={filters} onApply={(f) => update({ ...f, limit, offset: 0 }, null)} />

      {newEvents > 0 ? (
        <button type="button" className="banner banner--info new-events" onClick={query.reload}>
          <Icon name="refresh" />
          <span>{t('activity.newEvents', { count: fmtNumber(newEvents) })}</span>
        </button>
      ) : null}

      <section className="card" aria-labelledby="events-title">
        <h2 id="events-title" className="visually-hidden">
          {t('activity.events')}
        </h2>
        <QueryView {...query}>
          {(data) =>
            data.items.length === 0 ? (
              <EmptyState icon="search" title={t('activity.empty')} />
            ) : (
              <>
                <div className="table-wrap">
                  <table className="table table--interactive">
                    <thead>
                      <tr>
                        <th scope="col">{t('activity.colSeq')}</th>
                        <th scope="col">{t('activity.colTime')}</th>
                        <th scope="col">{t('activity.colEvent')}</th>
                        <th scope="col">{t('activity.colAgent')}</th>
                        <th scope="col">{t('activity.colTool')}</th>
                        <th scope="col">{t('activity.colAction')}</th>
                        <th scope="col">{t('activity.colRisk')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.items.map((event) => (
                        <tr key={event.seq} onClick={() => openEvent(event.seq)} aria-selected={event.seq === openSeq}>
                          <td>
                            <button
                              type="button"
                              className="row-button"
                              onClick={(e) => {
                                e.stopPropagation();
                                openEvent(event.seq);
                              }}
                              aria-label={t('activity.openEvent', { seq: event.seq })}
                            >
                              #{event.seq}
                            </button>
                          </td>
                          <td className="nowrap">{fmtDateTime(event.ts, { dateStyle: 'short', timeStyle: 'medium' })}</td>
                          <td>{tx(`event.${event.event_type}`, event.event_type)}</td>
                          <td className="mono small">{event.agent_id ?? '–'}</td>
                          <td className="mono small">{event.tool ?? '–'}</td>
                          <td>
                            <ActionCell event={event} />
                          </td>
                          <td>{event.risk ? <RiskBadge risk={event.risk} /> : '–'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <nav className="pager" aria-label={t('activity.paging')}>
                  <label className="row small">
                    <span>{t('activity.pageSize')}</span>
                    <select className="select select--sm" value={limit} onChange={(e) => update({ ...filters, limit: Number(e.target.value), offset: 0 })}>
                      {PAGE_SIZES.map((n) => (
                        <option key={n} value={n}>
                          {fmtNumber(n)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <span className="muted small" aria-live="polite">
                    {t('activity.range', {
                      from: fmtNumber(Math.min(data.total, offset + 1)),
                      to: fmtNumber(Math.min(data.total, offset + data.items.length)),
                      total: fmtNumber(data.total),
                    })}
                  </span>
                  <div className="row">
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      disabled={offset === 0}
                      onClick={() => update({ ...filters, offset: Math.max(0, offset - limit) })}
                    >
                      <Icon name="chevron-left" size={16} />
                      {t('activity.prev')}
                    </button>
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      disabled={offset + limit >= data.total}
                      onClick={() => update({ ...filters, offset: offset + limit })}
                    >
                      {t('activity.next')}
                      <Icon name="chevron-right" size={16} />
                    </button>
                  </div>
                </nav>
              </>
            )
          }
        </QueryView>
      </section>

      {openSeq ? (
        <EventDrawer
          seq={openSeq}
          initial={selected}
          onClose={() => openEvent(null)}
          onFilter={(key, value) => update({ [key]: value, limit, offset: 0 }, null)}
        />
      ) : null}
    </div>
  );
}

function ActionCell({ event }: { event: AuditEvent }) {
  if (!event.action) return <>–</>;
  if ((INSPECTION_ACTIONS as readonly string[]).includes(event.action)) return <InspectionBadge action={event.action} />;
  return <DecisionBadge action={event.action} />;
}

function FilterForm({ initial, onApply }: { initial: AuditFilters; onApply: (f: AuditFilters) => void }) {
  const { t, tx } = useI18n();
  const [draft, setDraft] = useState<AuditFilters>(initial);
  useEffect(() => setDraft(initial), [initial]);
  const set = <K extends keyof AuditFilters>(key: K, value: AuditFilters[K]) => setDraft((d) => ({ ...d, [key]: value || undefined }));

  function submit(e: FormEvent) {
    e.preventDefault();
    const { limit: _l, offset: _o, ...rest } = draft;
    onApply(rest);
  }

  return (
    <form className="card filters" onSubmit={submit} role="search" aria-label={t('activity.filters')}>
      <div className="form-grid">
        <div className="field">
          <label className="field__label" htmlFor="f-q">
            {t('activity.text')}
          </label>
          <input id="f-q" className="input" type="search" value={draft.q ?? ''} onChange={(e) => set('q', e.target.value)} dir="auto" />
        </div>
        <div className="field">
          <label className="field__label" htmlFor="f-agent">
            {t('activity.agent')}
          </label>
          <input id="f-agent" className="input" value={draft.agent_id ?? ''} onChange={(e) => set('agent_id', e.target.value)} dir="ltr" />
        </div>
        <div className="field">
          <label className="field__label" htmlFor="f-tool">
            {t('activity.tool')}
          </label>
          <input id="f-tool" className="input" value={draft.tool ?? ''} onChange={(e) => set('tool', e.target.value)} dir="ltr" />
        </div>
        <div className="field">
          <label className="field__label" htmlFor="f-action">
            {t('activity.action')}
          </label>
          <select id="f-action" className="select" value={draft.action ?? ''} onChange={(e) => set('action', e.target.value)}>
            <option value="">{t('activity.any')}</option>
            <optgroup label={t('activity.decisions')}>
              {DECISION_ACTIONS.map((a) => (
                <option key={a} value={a}>
                  {t(`action.${a}`)}
                </option>
              ))}
            </optgroup>
            <optgroup label={t('activity.inspections')}>
              {INSPECTION_ACTIONS.map((a) => (
                <option key={a} value={a}>
                  {t(`inspection.${a}`)}
                </option>
              ))}
            </optgroup>
          </select>
        </div>
        <div className="field">
          <label className="field__label" htmlFor="f-type">
            {t('activity.eventType')}
          </label>
          <select id="f-type" className="select" value={draft.event_type ?? ''} onChange={(e) => set('event_type', e.target.value)}>
            <option value="">{t('activity.any')}</option>
            {EVENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {tx(`event.${type}`, type)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label className="field__label" htmlFor="f-session">
            {t('activity.session')}
          </label>
          <input id="f-session" className="input" value={draft.session_id ?? ''} onChange={(e) => set('session_id', e.target.value)} dir="ltr" />
        </div>
        <div className="field">
          <label className="field__label" htmlFor="f-call">
            {t('activity.callId')}
          </label>
          <input id="f-call" className="input" value={draft.call_id ?? ''} onChange={(e) => set('call_id', e.target.value)} dir="ltr" />
        </div>
        <div className="field">
          <label className="field__label" htmlFor="f-since">
            {t('activity.since')}
          </label>
          <input
            id="f-since"
            className="input"
            type="datetime-local"
            value={toLocalInput(draft.since)}
            onChange={(e) => set('since', fromLocalInput(e.target.value))}
          />
        </div>
        <div className="field">
          <label className="field__label" htmlFor="f-until">
            {t('activity.until')}
          </label>
          <input
            id="f-until"
            className="input"
            type="datetime-local"
            value={toLocalInput(draft.until)}
            onChange={(e) => set('until', fromLocalInput(e.target.value))}
          />
        </div>
      </div>
      <div className="row filters__actions">
        <button type="submit" className="btn btn--primary btn--sm">
          <Icon name="filter" size={16} />
          {t('app.apply')}
        </button>
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={() => {
            setDraft({});
            onApply({});
          }}
        >
          {t('app.reset')}
        </button>
      </div>
    </form>
  );
}
