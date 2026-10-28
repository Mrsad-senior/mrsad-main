import type { ReactNode } from 'react';
import { ApiError } from '../api/client';
import { errorMessage } from '../app/errors';
import { useI18n } from '../i18n';
import { Icon, type IconName } from './Icon';

export function Spinner({ label, inline }: { label?: string; inline?: boolean }) {
  const { t } = useI18n();
  return (
    <span className={`spinner-wrap${inline ? ' spinner-wrap--inline' : ''}`} role="status">
      <span className="spinner" aria-hidden="true" />
      <span className={inline ? 'visually-hidden' : 'muted'}>{label ?? t('app.loading')}</span>
    </span>
  );
}

export function EmptyState({ icon = 'inbox', title, children }: { icon?: IconName; title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <Icon name={icon} size={32} className="empty__icon" />
      <p className="empty__title">{title}</p>
      {children ? <div className="empty__body">{children}</div> : null}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  const forbidden = error instanceof ApiError && error.status === 403;
  return (
    <div className="empty empty--error" role="alert">
      <Icon name={forbidden ? 'lock' : 'alert'} size={32} className="empty__icon" />
      <p className="empty__title">{forbidden ? t('errors.forbidden') : t('errors.loadFailed')}</p>
      {!forbidden ? <p className="muted">{errorMessage(error, t)}</p> : null}
      {onRetry && !forbidden ? (
        <button type="button" className="btn btn--ghost" onClick={onRetry}>
          <Icon name="refresh" size={16} />
          {t('app.retry')}
        </button>
      ) : null}
    </div>
  );
}

/** Loading / error / content switch that keeps old content visible while refetching. */
export function QueryView<T>({
  data,
  error,
  loading,
  reload,
  children,
}: {
  data: T | undefined;
  error: unknown;
  loading: boolean;
  reload: () => void;
  children: (data: T) => ReactNode;
}) {
  if (data === undefined) {
    if (error) return <ErrorState error={error} onRetry={reload} />;
    if (loading) return <Spinner />;
    return null;
  }
  return <div className={loading ? 'is-refreshing' : undefined}>{children(data)}</div>;
}
