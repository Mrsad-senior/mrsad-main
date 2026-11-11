import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { AuditEvent, AuditVerifyReport } from '../../shared/api/types';
import { useApi, useAuth } from '../../shared/app/auth';
import { useQuery } from '../../shared/app/hooks';
import { useToast } from '../../shared/app/toast';
import { Icon } from '../../shared/components/Icon';
import { EmptyState, QueryView } from '../../shared/components/States';
import { useI18n } from '../../shared/i18n';
import { browserTimeZone } from '../../shared/lib/format';
import { PageHeader, Section } from '../components/PageHeader';

/** Rows in "Recent audit entries"; the full log stays on the Activity page. */
const RECENT_LIMIT = 10;

/** The result of one chain check: a fresh "Verify now", or the last `audit.verified` entry. */
interface Verification {
  ok: boolean;
  checked: number | null;
  firstBadSeq: number | null;
  /** The verifier's explanation; only a fresh report carries it. */
  message: string | null;
  /** Epoch seconds. */
  at: number;
  by: string | null;
}

function fromEvent(event: AuditEvent): Verification {
  const p = event.payload ?? {};
  return {
    ok: p.ok === true,
    checked: typeof p.checked === 'number' ? p.checked : null,
    firstBadSeq: typeof p.first_bad_seq === 'number' ? p.first_bad_seq : null,
    message: null,
    at: event.ts,
    by: typeof p.by === 'string' ? p.by : null,
  };
}

function fromReport(report: AuditVerifyReport, by: string | null): Verification {
  return {
    ok: report.ok,
    checked: report.checked,
    firstBadSeq: report.first_bad_seq ?? null,
    message: report.message || null,
    at: Date.now() / 1000,
    by,
  };
}

/** Figma style "f42a…91c8": enough of both ends to match a row with the next one. */
function hashEnds(hash: string | null | undefined): string {
  if (!hash) return '–';
  return hash.length > 12 ? `${hash.slice(0, 4)}…${hash.slice(-4)}` : hash;
}

/**
 * Figma "05 Audit integrity". The chain card shows the last recorded verification, so opening
 * the page writes nothing to the log; "Verify now" runs a fresh check of the whole chain.
 */
export default function Audit() {
  const api = useApi();
  const toast = useToast();
  const { user } = useAuth();
  const { t, tx, fmtDateTime } = useI18n();
  const [fresh, setFresh] = useState<Verification | null>(null);
  const [verifying, setVerifying] = useState(false);

  const last = useQuery(
    (signal) => api.auditEvents({ event_type: 'audit.verified', limit: 1 }, signal).then((page) => page.items[0] ?? null),
    [api],
  );
  const recent = useQuery((signal) => api.auditEvents({ limit: RECENT_LIMIT }, signal), [api]);

  async function verify() {
    setVerifying(true);
    try {
      setFresh(fromReport(await api.verifyAudit(), user?.username ?? null));
      recent.reload(); // the check itself is logged as an `audit.verified` entry
    } catch (err) {
      toast.error(err);
    } finally {
      setVerifying(false);
    }
  }

  return (
    <div className="stack-lg">
      <PageHeader title={t('audit.title')} subtitle={t('audit.subtitle')} />

      <QueryView {...last}>
        {(event) => (
          <ChainCard verification={fresh ?? (event ? fromEvent(event) : null)} verifying={verifying} onVerify={verify} />
        )}
      </QueryView>

      <Section
        id="recent"
        title={t('audit.recent')}
        actions={
          <Link className="btn btn--ghost btn--sm" to="/activity">
            {t('audit.viewAll')}
          </Link>
        }
      >
        <QueryView {...recent}>
          {(page) =>
            page.items.length === 0 ? (
              <EmptyState icon="database" title={t('audit.empty')} />
            ) : (
              <div className="table-wrap table-wrap--flush">
                <table className="table audit-table">
                  <thead>
                    <tr>
                      <th scope="col">{t('audit.colEntry')}</th>
                      <th scope="col">{t('audit.colTime')}</th>
                      <th scope="col">{t('audit.colEvent')}</th>
                      <th scope="col">{t('audit.colHash')}</th>
                      <th scope="col">{t('audit.colPrevHash')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {page.items.map((event) => {
                      const detail = event.tool ?? event.agent_id;
                      return (
                        <tr key={event.seq}>
                          <td>
                            <Link className="row-button" to={`/activity?seq=${event.seq}`} aria-label={t('activity.openEvent', { seq: event.seq })}>
                              #{event.seq}
                            </Link>
                          </td>
                          <td className="nowrap">{fmtDateTime(event.ts, { dateStyle: 'short', timeStyle: 'medium' })}</td>
                          <td>
                            {tx(`event.${event.event_type}`, event.event_type)}
                            {detail ? (
                              <span className="muted">
                                {' · '}
                                <bdi>{detail}</bdi>
                              </span>
                            ) : null}
                          </td>
                          <td>
                            <span className="mono audit-hash" dir="ltr" title={event.hash}>
                              {hashEnds(event.hash)}
                            </span>
                          </td>
                          <td>
                            <span className="mono audit-hash" dir="ltr" title={event.prev_hash}>
                              {hashEnds(event.prev_hash)}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )
          }
        </QueryView>
      </Section>

      <p className="page-note">
        {t('audit.footnote')} · {t('approvals.timezone', { zone: browserTimeZone() })}
      </p>
    </div>
  );
}

function ChainCard({ verification: v, verifying, onVerify }: { verification: Verification | null; verifying: boolean; onVerify: () => void }) {
  const { t, fmtNumber, fmtDateTime } = useI18n();
  const state = !v ? 'unknown' : v.ok ? 'ok' : 'broken';
  const title = state === 'ok' ? t('activity.chainValid') : state === 'broken' ? t('activity.chainBroken') : t('audit.notVerified');
  const seq = v?.firstBadSeq ?? '?';
  const body = !v
    ? t('audit.notVerifiedBody')
    : v.ok
      ? t('activity.chainValidBody', { count: v.checked === null ? '?' : fmtNumber(v.checked) })
      : v.message
        ? t('activity.verifyFail', { seq, message: v.message })
        : t('audit.brokenAt', { seq });
  const meta = v
    ? [
        t('audit.lastVerified', { time: fmtDateTime(v.at, { dateStyle: 'medium', timeStyle: 'medium' }) }),
        v.by ? t('audit.verifiedBy', { user: v.by }) : null,
        t('audit.linked'),
      ].filter((part): part is string => Boolean(part))
    : [];

  return (
    <section className={`chain-card chain-card--${state}`} aria-labelledby="chain-title" aria-live="polite">
      <div className="chain-card__head">
        <h2 className="chain-card__title" id="chain-title">
          <Icon name={state === 'ok' ? 'check' : state === 'broken' ? 'shield-alert' : 'shield'} size={26} strokeWidth={2.4} />
          {title}
        </h2>
        <button type="button" className="btn btn--ghost btn--sm" onClick={onVerify} disabled={verifying} aria-busy={verifying}>
          <Icon name="shield-check" size={16} />
          {t('overview.verifyNow')}
        </button>
      </div>
      <p className="chain-card__body">{body}</p>
      {meta.length ? (
        <p className="chain-card__meta">
          {meta.map((part, i) => (
            <span key={part}>
              {i > 0 ? ' · ' : null}
              <bdi>{part}</bdi>
            </span>
          ))}
        </p>
      ) : null}
    </section>
  );
}
