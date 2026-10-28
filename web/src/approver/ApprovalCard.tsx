import type { ApprovalRecord } from '../shared/api/types';
import { ApprovalStatusBadge, RiskBadge, riskIcon } from '../shared/components/Badges';
import { Countdown } from '../shared/components/Countdown';
import { approvalSummary } from '../shared/components/Explain';
import { Icon } from '../shared/components/Icon';
import { useI18n } from '../shared/i18n';

/**
 * One request in the approver list. The whole card is a single large button (>= 44 px);
 * risk is conveyed by stripe colour + icon + text label, never colour alone.
 */
export function ApprovalCard({ record, now, onOpen }: { record: ApprovalRecord; now: number; onOpen: (id: string) => void }) {
  const { t, lang, fmtRelative } = useI18n();
  const summary = approvalSummary(record, lang, t('approvals.fallbackSummary', { agent: record.agent_id, tool: record.tool }));
  const pending = record.status === 'pending';
  return (
    <li className={`a-card risk--${record.risk}`}>
      <button type="button" className="a-card__button" onClick={() => onOpen(record.id)}>
        <span className="a-card__stripe" aria-hidden="true">
          <Icon name={riskIcon(record.risk)} size={20} />
        </span>
        <span className="a-card__content">
          <span className="a-card__top">
            <RiskBadge risk={record.risk} withPrefix />
            {pending ? (
              <Countdown expiresAt={record.expires_at} createdAt={record.created_at} now={now} compact />
            ) : (
              <ApprovalStatusBadge status={record.status} />
            )}
          </span>
          <span className="a-card__title">
            <code>{record.tool}</code>
            <span className="muted"> · {record.agent_id}</span>
          </span>
          <span className="a-card__summary" dir="auto">
            {summary}
          </span>
          <span className="a-card__meta muted">
            {pending
              ? fmtRelative(record.created_at, now)
              : record.decided_by
                ? t('approvals.decidedBy', { user: record.decided_by })
                : fmtRelative(record.decided_at ?? record.created_at, now)}
          </span>
        </span>
        <Icon name="chevron-right" className="a-card__chevron" />
      </button>
    </li>
  );
}
