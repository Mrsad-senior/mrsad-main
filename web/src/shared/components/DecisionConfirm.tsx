import { useId, useRef, useState } from 'react';
import { ApiError } from '../api/client';
import type { ApprovalRecord } from '../api/types';
import { useApi } from '../app/auth';
import { useToast } from '../app/toast';
import { useI18n } from '../i18n';
import { RiskBadge } from './Badges';
import { Dialog } from './Dialog';
import { Icon } from './Icon';

/**
 * Second step of an approve/deny decision: restates what will happen, takes an optional
 * note, then calls the API. Used as a centred modal (dashboard) or a bottom sheet (PWA).
 */
export function DecisionConfirm({
  record,
  approve,
  variant = 'modal',
  onClose,
  onDecided,
}: {
  record: ApprovalRecord;
  approve: boolean;
  variant?: 'modal' | 'sheet';
  onClose: () => void;
  onDecided: (updated: ApprovalRecord) => void;
}) {
  const api = useApi();
  const toast = useToast();
  const { t } = useI18n();
  const [note, setNote] = useState('');
  const [pending, setPending] = useState(false);
  const noteId = useId();
  const confirmRef = useRef<HTMLButtonElement>(null);

  async function confirm() {
    setPending(true);
    try {
      const updated = await api.decideApproval(record.id, approve, note);
      toast.show(approve ? 'success' : 'info', approve ? t('approvals.approved') : t('approvals.denied'));
      onDecided(updated);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 409 || err.status === 400)) {
        toast.show('warning', t('approvals.alreadyDecidedGeneric'));
        onClose();
      } else {
        toast.error(err);
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog
      open
      onClose={onClose}
      variant={variant}
      size="sm"
      initialFocusRef={confirmRef}
      title={
        <>
          <Icon name={approve ? 'check-circle' : 'x-octagon'} />
          {approve ? t('approvals.confirmApprove') : t('approvals.confirmDeny')}
        </>
      }
      footer={
        <div className="decision-footer">
          <button type="button" className="btn btn--ghost btn--lg" onClick={onClose}>
            {t('app.cancel')}
          </button>
          <button
            ref={confirmRef}
            type="button"
            className={`btn btn--lg ${approve ? 'btn--approve' : 'btn--danger'}`}
            onClick={confirm}
            disabled={pending}
            aria-busy={pending}
          >
            <Icon name={approve ? 'check' : 'x'} />
            {approve ? t('approvals.approve') : t('approvals.deny')}
          </button>
        </div>
      }
    >
      <div className="stack">
        <div className="row">
          <RiskBadge risk={record.risk} withPrefix />
          <code className="code-inline">{record.tool}</code>
          <span className="muted small">{t('approvals.requestedBy', { agent: record.agent_id })}</span>
        </div>
        <p>{approve ? t('approvals.confirmApproveBody', { tool: record.tool }) : t('approvals.confirmDenyBody')}</p>
        <div className="field">
          <label className="field__label" htmlFor={noteId}>
            {t('approvals.note')}
          </label>
          <textarea
            id={noteId}
            className="textarea"
            rows={2}
            maxLength={500}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={t('approvals.notePlaceholder')}
            dir="auto"
          />
        </div>
      </div>
    </Dialog>
  );
}
