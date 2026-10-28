import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ApiClient } from '../shared/api/client';
import type { ApprovalRecord } from '../shared/api/types';
import { ApiProvider, AuthProvider, defaultClient, useApi, useAuth } from '../shared/app/auth';
import { useNow, useOnline } from '../shared/app/hooks';
import { LiveProvider, useLive, useLiveEvent } from '../shared/app/live';
import { ThemeProvider } from '../shared/app/theme';
import { ToastProvider } from '../shared/app/toast';
import { ApprovalStatusBadge, RiskBadge } from '../shared/components/Badges';
import { Countdown } from '../shared/components/Countdown';
import { DecisionConfirm } from '../shared/components/DecisionConfirm';
import { Dialog } from '../shared/components/Dialog';
import { ApprovalExplanation } from '../shared/components/Explain';
import { Icon } from '../shared/components/Icon';
import { LoginForm } from '../shared/components/LoginForm';
import { LogoMark } from '../shared/components/Logo';
import { LangToggle, ThemeRadios } from '../shared/components/Prefs';
import { EmptyState, ErrorState, Spinner } from '../shared/components/States';
import { I18nProvider, useI18n } from '../shared/i18n';
import { applyApprovalEvent, isApprovalRecord, sortApprovals, upsertApproval } from '../shared/lib/approvals';
import { notificationPermission, type NotifyPermission, requestNotificationPermission, showSystemNotification } from '../shared/lib/notify';
import { ApprovalCard } from './ApprovalCard';
import {
  disablePushSubscription,
  ensurePushSubscription,
  parseApproverRoute,
  postToServiceWorker,
  registerServiceWorker,
  useHashRoute,
  useInstallPrompt,
} from './pwa';

export function ApproverApp({ client = defaultClient }: { client?: ApiClient }) {
  // Cached approval data must not outlive the session on a shared phone.
  const onLogout = useCallback(() => postToServiceWorker({ type: 'clear-api-cache' }), []);
  return (
    <ApiProvider client={client}>
      <I18nProvider>
        <ThemeProvider>
          <ToastProvider>
            <AuthProvider onLogout={onLogout}>
              <LiveProvider>
                <ApproverGate />
              </LiveProvider>
            </AuthProvider>
          </ToastProvider>
        </ThemeProvider>
      </I18nProvider>
    </ApiProvider>
  );
}

function ApproverGate() {
  const { status } = useAuth();
  const { t, lang } = useI18n();
  useEffect(() => postToServiceWorker({ type: 'set-lang', lang }), [lang]);
  useEffect(() => {
    document.title = `${t('pwa.title')} · مرصاد`;
  }, [t]);
  if (status === 'checking') {
    return (
      <main className="boot" id="main">
        <Spinner />
      </main>
    );
  }
  if (status === 'signed-out') return <LoginForm subtitle={t('pwa.title')} intro={t('auth.welcomeApprover')} />;
  return <ApproverHome />;
}

function ApproverHome() {
  const api = useApi();
  const live = useLive();
  const online = useOnline();
  const { t, fmtNumber } = useI18n();
  const now = useNow(1000);
  const [path, navigate] = useHashRoute();
  const [records, setRecords] = useState<ApprovalRecord[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [announcement, setAnnouncement] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const registration = useRef<ServiceWorkerRegistration | null>(null);

  const load = useCallback(async () => {
    try {
      const [pending, recent] = await Promise.all([api.approvals({ status: 'pending', limit: 100 }), api.approvals({ limit: 100 })]);
      setRecords(sortApprovals([...recent.filter((r) => !pending.some((p) => p.id === r.id)), ...pending]));
      setLoadError(null);
    } catch (err) {
      setLoadError(err);
    } finally {
      setLoaded(true);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  // Service worker + push once signed in; notification clicks deep-link via postMessage.
  useEffect(() => {
    let cancelled = false;
    void registerServiceWorker().then((reg) => {
      if (cancelled) return;
      registration.current = reg;
      if (reg && notificationPermission() === 'granted') void ensurePushSubscription(api, reg);
    });
    const onMessage = (event: MessageEvent) => {
      const data = event.data as { type?: string; url?: string } | null;
      if (data?.type === 'open' && data.url) {
        const hash = new URL(data.url, window.location.origin).hash.replace(/^#/, '');
        if (hash) navigate(hash);
      }
    };
    navigator.serviceWorker?.addEventListener('message', onMessage);
    return () => {
      cancelled = true;
      navigator.serviceWorker?.removeEventListener('message', onMessage);
    };
  }, [api, navigate]);

  useLiveEvent(
    (event, data) => {
      setRecords((list) => applyApprovalEvent(list, event, data));
      if (event === 'approval.requested' && isApprovalRecord(data)) {
        const message = t('live.newApproval', { tool: data.tool, agent: data.agent_id });
        setAnnouncement(message);
        if (document.hidden) {
          void showSystemNotification({
            title: t('pwa.notifTitle', { tool: data.tool }),
            body: message,
            tag: `approval-${data.id}`,
            url: `/approve#/a/${encodeURIComponent(data.id)}`,
          });
        }
      }
    },
    ['approval.requested', 'approval.decided'],
  );

  // Poll when the live stream is down (and catch up as soon as it reconnects).
  useEffect(() => {
    if (live.status === 'open') {
      void load();
      return undefined;
    }
    const timer = setInterval(() => void load(), 20_000);
    return () => clearInterval(timer);
  }, [live.status, load]);

  const pending = useMemo(() => records.filter((r) => r.status === 'pending'), [records]);
  const history = useMemo(() => records.filter((r) => r.status !== 'pending'), [records]);
  const route = parseApproverRoute(path);
  const detailId = route.view === 'detail' ? route.id : null;
  const tab: 'pending' | 'history' = route.view === 'history' ? 'history' : 'pending';
  const detail = detailId ? records.find((r) => r.id === detailId) : undefined;

  const onDecided = (updated: ApprovalRecord) => setRecords((list) => upsertApproval(list, updated));

  return (
    <div className="approver-shell">
      <header className="a-header">
        <LogoMark size={30} />
        <div className="a-header__title">
          <span className="a-header__name">{t('pwa.title')}</span>
          <LiveDot status={live.status} />
        </div>
        <span className="spacer" />
        <LangToggle className="a-header__lang" />
        <button type="button" className="icon-btn icon-btn--touch" onClick={() => setMenuOpen(true)} aria-label={t('pwa.menu')}>
          <Icon name="settings" />
        </button>
      </header>

      {!online ? (
        <p className="a-banner banner banner--warn" role="status">
          <Icon name="wifi-off" />
          <span>{t('pwa.offline')}</span>
        </p>
      ) : null}

      <main id="main" className="a-main" tabIndex={-1}>
        {detailId ? (
          <DetailView
            id={detailId}
            record={detail}
            now={now}
            loaded={loaded}
            online={online}
            onBack={() => navigate('/')}
            onDecided={onDecided}
            onLoaded={(r) => setRecords((list) => upsertApproval(list, r))}
          />
        ) : (
          <>
            <InstallHint />
            <AlertsCard registration={registration.current} />
            <div className="tabs a-tabs" role="tablist" aria-label={t('pwa.tabs')}>
              <TabButton id="pending" selected={tab === 'pending'} onSelect={() => navigate('/')}>
                {t('pwa.pending')}
                {pending.length ? <span className="count-pill">{fmtNumber(pending.length)}</span> : null}
              </TabButton>
              <TabButton id="history" selected={tab === 'history'} onSelect={() => navigate('/history')}>
                {t('pwa.history')}
              </TabButton>
            </div>
            <section id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} className="a-panel">
              {!loaded ? (
                <Spinner />
              ) : loadError && records.length === 0 ? (
                <ErrorState error={loadError} onRetry={() => void load()} />
              ) : tab === 'pending' ? (
                pending.length === 0 ? (
                  <EmptyState icon="shield-check" title={t('pwa.emptyPending')}>
                    <p>{t('pwa.emptyPendingHint')}</p>
                  </EmptyState>
                ) : (
                  <ul className="a-list">
                    {pending.map((r) => (
                      <ApprovalCard key={r.id} record={r} now={now} onOpen={(id) => navigate(`/a/${encodeURIComponent(id)}`)} />
                    ))}
                  </ul>
                )
              ) : history.length === 0 ? (
                <EmptyState icon="clock" title={t('pwa.emptyHistory')} />
              ) : (
                <ul className="a-list">
                  {history.map((r) => (
                    <ApprovalCard key={r.id} record={r} now={now} onOpen={(id) => navigate(`/a/${encodeURIComponent(id)}`)} />
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </main>

      <div className="visually-hidden" role="status" aria-live="assertive">
        {announcement}
      </div>

      {menuOpen ? <MenuSheet onClose={() => setMenuOpen(false)} registration={registration.current} /> : null}
      {loadError && records.length > 0 ? <StaleNotice onRetry={() => void load()} /> : null}
    </div>
  );
}

/** Shown when a refresh failed but older data is still on screen. */
function StaleNotice({ onRetry }: { onRetry: () => void }) {
  const { t } = useI18n();
  return (
    <button type="button" className="a-stale banner banner--warn" onClick={onRetry}>
      <Icon name="refresh" />
      <span>{t('pwa.stale')}</span>
    </button>
  );
}

function TabButton({ id, selected, onSelect, children }: { id: string; selected: boolean; onSelect: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      role="tab"
      id={`tab-${id}`}
      className="tab"
      aria-selected={selected}
      aria-controls={`panel-${id}`}
      tabIndex={selected ? 0 : -1}
      onClick={onSelect}
      onKeyDown={(e) => {
        // Arrow keys move between tabs (WAI-ARIA tabs pattern); direction follows reading order.
        if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
        const tabs = Array.from(e.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]') ?? []);
        const index = tabs.indexOf(e.currentTarget);
        const rtl = document.documentElement.dir === 'rtl';
        const forward = (e.key === 'ArrowRight') !== rtl;
        const next = tabs[(index + (forward ? 1 : -1) + tabs.length) % tabs.length];
        next?.focus();
        next?.click();
      }}
    >
      {children}
    </button>
  );
}

function LiveDot({ status }: { status: string }) {
  const { t } = useI18n();
  const label =
    status === 'open' ? t('live.connected') : status === 'connecting' ? t('live.connecting') : status === 'reconnecting' ? t('live.reconnecting') : t('live.offline');
  return (
    <span className={`live live--${status}`}>
      <span className="live__dot" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

function DetailView({
  id,
  record,
  now,
  loaded,
  online,
  onBack,
  onDecided,
  onLoaded,
}: {
  id: string;
  record: ApprovalRecord | undefined;
  now: number;
  loaded: boolean;
  online: boolean;
  onBack: () => void;
  onDecided: (r: ApprovalRecord) => void;
  onLoaded: (r: ApprovalRecord) => void;
}) {
  const api = useApi();
  const { t, fmtDateTime } = useI18n();
  const [deciding, setDeciding] = useState<boolean | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [decidedHere, setDecidedHere] = useState(false);
  const headingRef = useRef<HTMLHeadingElement>(null);

  // Deep links (notification clicks) may point at a request not in the list yet.
  useEffect(() => {
    if (record || !loaded) return;
    api.approval(id).then(onLoaded).catch(setError);
  }, [api, id, record, loaded, onLoaded]);

  useEffect(() => headingRef.current?.focus(), [id]);

  if (!record) {
    return (
      <div className="a-detail">
        <BackButton onBack={onBack} />
        {error ? <ErrorState error={error} /> : <Spinner />}
      </div>
    );
  }

  const pending = record.status === 'pending';
  const expired = pending && record.expires_at * 1000 <= now;

  return (
    <article className={`a-detail risk--${record.risk}`} aria-labelledby="detail-title">
      <BackButton onBack={onBack} />
      <header className="a-detail__header">
        <div className="row">
          <RiskBadge risk={record.risk} withPrefix size="lg" />
          {!pending ? <ApprovalStatusBadge status={record.status} /> : null}
        </div>
        <h1 id="detail-title" ref={headingRef} tabIndex={-1} className="a-detail__title">
          <code>{record.tool}</code>
        </h1>
        <p className="muted">
          {t('approvals.requestedBy', { agent: record.agent_id })} · {fmtDateTime(record.created_at, { timeStyle: 'short' })}
        </p>
        {pending ? (
          <div className="a-detail__countdown">
            <span className="muted small">{t('pwa.timeLeft')}</span>
            <Countdown expiresAt={record.expires_at} createdAt={record.created_at} now={now} showBar />
          </div>
        ) : null}
      </header>

      {!pending && !decidedHere && record.decided_by ? (
        <p className="banner banner--info" role="status">
          <Icon name="info" />
          <span>
            {t('approvals.alreadyDecided', { user: record.decided_by })}
            {record.decided_at ? ` · ${fmtDateTime(record.decided_at, { timeStyle: 'short' })}` : ''}
          </span>
        </p>
      ) : null}
      {record.note ? (
        <p className="approval-meta__note" dir="auto">
          “{record.note}”
        </p>
      ) : null}

      <ApprovalExplanation record={record} />

      {pending ? (
        <div className="a-actions">
          <button type="button" className="btn btn--danger a-actions__btn" onClick={() => setDeciding(false)} disabled={expired || !online}>
            <Icon name="x" size={22} />
            {t('approvals.deny')}
          </button>
          <button type="button" className="btn btn--approve a-actions__btn" onClick={() => setDeciding(true)} disabled={expired || !online}>
            <Icon name="check" size={22} />
            {t('approvals.approve')}
          </button>
        </div>
      ) : null}

      {deciding !== null ? (
        <DecisionConfirm
          record={record}
          approve={deciding}
          variant="sheet"
          onClose={() => setDeciding(null)}
          onDecided={(updated) => {
            setDeciding(null);
            setDecidedHere(true);
            onDecided(updated);
            onBack();
          }}
        />
      ) : null}
    </article>
  );
}

function BackButton({ onBack }: { onBack: () => void }) {
  const { t } = useI18n();
  return (
    <button type="button" className="btn btn--ghost a-back" onClick={onBack}>
      <Icon name="arrow-left" />
      {t('app.back')}
    </button>
  );
}

function InstallHint() {
  const { t } = useI18n();
  const { mode, install, dismiss } = useInstallPrompt();
  if (!mode) return null;
  return (
    <section className="a-hint card" aria-labelledby="install-title">
      <Icon name="smartphone" size={24} />
      <div className="a-hint__body">
        <h2 id="install-title" className="a-hint__title">
          {t('pwa.install')}
        </h2>
        <p className="muted small">{mode === 'ios' ? t('pwa.installIos') : t('pwa.installBody')}</p>
        <div className="row">
          {mode === 'prompt' ? (
            <button type="button" className="btn btn--primary btn--sm" onClick={() => void install()}>
              {t('pwa.installButton')}
            </button>
          ) : null}
          <button type="button" className="btn btn--ghost btn--sm" onClick={dismiss}>
            {t('pwa.dismiss')}
          </button>
        </div>
      </div>
    </section>
  );
}

function useNotificationsToggle(registration: ServiceWorkerRegistration | null) {
  const api = useApi();
  const [permission, setPermission] = useState<NotifyPermission>(notificationPermission);
  const enable = async () => {
    const result = await requestNotificationPermission();
    setPermission(result);
    if (result === 'granted') await ensurePushSubscription(api, registration);
  };
  return { permission, enable };
}

function AlertsCard({ registration }: { registration: ServiceWorkerRegistration | null }) {
  const { t } = useI18n();
  const { permission, enable } = useNotificationsToggle(registration);
  if (permission !== 'default') return null;
  return (
    <section className="a-hint card" aria-labelledby="alerts-title">
      <Icon name="bell" size={24} />
      <div className="a-hint__body">
        <h2 id="alerts-title" className="a-hint__title">
          {t('pwa.enableAlerts')}
        </h2>
        <p className="muted small">{t('pwa.alertsBody')}</p>
        <button type="button" className="btn btn--primary btn--sm" onClick={() => void enable()}>
          <Icon name="bell" size={16} />
          {t('pwa.enableAlerts')}
        </button>
      </div>
    </section>
  );
}

function MenuSheet({ onClose, registration }: { onClose: () => void; registration: ServiceWorkerRegistration | null }) {
  const { t } = useI18n();
  const api = useApi();
  const { user, logout } = useAuth();
  const [signingOut, setSigningOut] = useState(false);
  const { permission, enable } = useNotificationsToggle(registration);
  return (
    <Dialog open onClose={onClose} variant="sheet" title={t('pwa.menu')}>
      <div className="stack">
        <p className="row">
          <Icon name="user" />
          <strong>{user?.display_name || user?.username}</strong>
          <span className="muted">{user ? t(`roles.${user.role}`) : ''}</span>
        </p>
        <ThemeRadios />
        <div className="stack-sm">
          <p className="field__label">{t('settings.notifications')}</p>
          {permission === 'granted' ? (
            <p className="banner banner--allow">
              <Icon name="bell" size={16} />
              {t('pwa.alertsOn')}
            </p>
          ) : permission === 'denied' ? (
            <p className="banner banner--warn">{t('pwa.alertsBlocked')}</p>
          ) : permission === 'unsupported' ? (
            <p className="banner banner--info">{t('settings.notificationsUnsupported')}</p>
          ) : (
            <button type="button" className="btn btn--ghost btn--lg btn--block" onClick={() => void enable()}>
              <Icon name="bell" />
              {t('pwa.enableAlerts')}
            </button>
          )}
        </div>
        <a className="btn btn--ghost btn--lg btn--block" href="/">
          <Icon name="grid" />
          {t('pwa.openDashboard')}
        </a>
        <button
          type="button"
          className="btn btn--ghost btn--lg btn--block"
          disabled={signingOut}
          aria-busy={signingOut}
          onClick={async () => {
            setSigningOut(true);
            await disablePushSubscription(api, registration);
            onClose();
            logout();
          }}
        >
          <Icon name="logout" />
          {t('auth.signOut')}
        </button>
        <p className="muted small">{t('settings.sessionNote')}</p>
      </div>
    </Dialog>
  );
}
