import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import type { ApprovalRecord, Role } from '../shared/api/types';
import { useApi, useAuth } from '../shared/app/auth';
import { useLive, useLiveEvent } from '../shared/app/live';
import { Icon, type IconName } from '../shared/components/Icon';
import { Logo } from '../shared/components/Logo';
import { LangToggle, ThemeToggle } from '../shared/components/Prefs';
import { type MessageKey, useI18n } from '../shared/i18n';
import { localStore } from '../shared/lib/storage';
import { showSystemNotification } from '../shared/lib/notify';
import { markNavigation } from './components/PageHeader';

interface NavItem {
  to: string;
  label: MessageKey;
  icon: IconName;
  roles?: Role[];
  badge?: 'approvals';
}

const NAV: { group: MessageKey; items: NavItem[] }[] = [
  {
    group: 'nav.groupMonitor',
    items: [
      { to: '/', label: 'nav.overview', icon: 'grid' },
      { to: '/activity', label: 'nav.activity', icon: 'activity', roles: ['admin', 'auditor'] },
      { to: '/approvals', label: 'nav.approvals', icon: 'inbox', roles: ['admin', 'approver'], badge: 'approvals' },
    ],
  },
  {
    group: 'nav.groupGovern',
    items: [
      { to: '/policies', label: 'nav.policies', icon: 'file-text', roles: ['admin', 'auditor'] },
      { to: '/agents', label: 'nav.agents', icon: 'key', roles: ['admin'] },
      { to: '/users', label: 'nav.users', icon: 'users', roles: ['admin'] },
      { to: '/tools', label: 'nav.tools', icon: 'tool', roles: ['admin', 'auditor'] },
    ],
  },
  {
    group: 'nav.groupExplore',
    items: [
      { to: '/playground', label: 'nav.playground', icon: 'beaker' },
      { to: '/demo', label: 'nav.demo', icon: 'chat' },
    ],
  },
  { group: 'nav.groupSystem', items: [{ to: '/settings', label: 'nav.settings', icon: 'settings' }] },
];

export const DESKTOP_ALERTS_KEY = 'mirsad.desktopAlerts';

export function Shell({ children }: { children: ReactNode }) {
  const { t, fmtNumber } = useI18n();
  const { user, logout, hasRole } = useAuth();
  const api = useApi();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [pending, setPending] = useState<number | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const mainRef = useRef<HTMLElement>(null);
  const canApprove = hasRole('admin', 'approver');

  // Route change: close the mobile menu and let the next page heading take focus.
  const firstRender = useRef(true);
  useEffect(() => {
    setMenuOpen(false);
    if (firstRender.current) firstRender.current = false;
    else markNavigation();
  }, [location.pathname]);

  const refreshPending = useCallback(() => {
    if (!canApprove) return;
    api
      .approvals({ status: 'pending', limit: 200 })
      .then((list) => setPending(list.length))
      .catch(() => setPending(null));
  }, [api, canApprove]);

  useEffect(refreshPending, [refreshPending]);

  useLiveEvent(
    (event, data) => {
      refreshPending();
      if (event !== 'approval.requested' || !canApprove) return;
      const record = data as Partial<ApprovalRecord>;
      const message = t('live.newApproval', { tool: record.tool ?? '?', agent: record.agent_id ?? '?' });
      setAnnouncement(message);
      if (document.hidden && localStore.getItem(DESKTOP_ALERTS_KEY) === 'on') {
        void showSystemNotification({
          title: t('pwa.notifTitle', { tool: record.tool ?? '?' }),
          body: message,
          tag: `approval-${record.id ?? 'new'}`,
          url: '/#/approvals',
        });
      }
    },
    ['approval.requested', 'approval.decided'],
  );

  useEffect(() => {
    if (!menuOpen) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [menuOpen]);

  return (
    <div className={`shell${menuOpen ? ' shell--menu-open' : ''}`}>
      <a
        className="skip-link"
        href="#main"
        onClick={(e) => {
          e.preventDefault(); // HashRouter owns the hash; move focus instead of navigating.
          mainRef.current?.focus();
        }}
      >
        {t('app.skipToContent')}
      </a>

      <aside className="sidebar" id="sidebar" aria-label={t('nav.sidebar')}>
        <div className="sidebar__brand">
          <Logo size={36} subtitle={t('app.console')} />
          <button type="button" className="icon-btn sidebar__close" onClick={() => setMenuOpen(false)} aria-label={t('nav.closeMenu')}>
            <Icon name="x" />
          </button>
        </div>
        <nav aria-label={t('nav.main')} className="sidebar__nav">
          {NAV.map((section) => {
            const items = section.items.filter((item) => !item.roles || hasRole(...item.roles));
            if (items.length === 0) return null;
            return (
              <div key={section.group} className="nav-group">
                <p className="nav-group__title" id={`nav-${section.group}`}>
                  {t(section.group)}
                </p>
                <ul aria-labelledby={`nav-${section.group}`}>
                  {items.map((item) => (
                    <li key={item.to}>
                      <NavLink to={item.to} end={item.to === '/'} className="nav-link">
                        <Icon name={item.icon} />
                        <span className="nav-link__label">{t(item.label)}</span>
                        {item.badge === 'approvals' && pending ? (
                          <span className="count-pill" aria-label={t('nav.pendingCount', { count: pending })}>
                            {fmtNumber(pending)}
                          </span>
                        ) : null}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>
        <div className="sidebar__footer">
          <a className="nav-link" href="/approve" target="_blank" rel="noopener">
            <Icon name="smartphone" />
            <span className="nav-link__label">{t('nav.approverApp')}</span>
            <Icon name="external" size={14} />
          </a>
        </div>
      </aside>
      <button type="button" className="shell__scrim" aria-hidden="true" tabIndex={-1} onClick={() => setMenuOpen(false)} />

      <div className="shell__main">
        <header className="topbar">
          <button
            type="button"
            className="icon-btn topbar__menu"
            onClick={() => setMenuOpen(true)}
            aria-label={t('nav.openMenu')}
            aria-controls="sidebar"
            aria-expanded={menuOpen}
          >
            <Icon name="menu" />
          </button>
          <span className="topbar__brand">
            <Logo size={28} />
          </span>
          <span className="spacer" />
          <LiveStatus />
          <LangToggle />
          <ThemeToggle />
          <div className="topbar__user">
            <Icon name="user" size={18} />
            <span className="topbar__user-text">
              <span className="topbar__user-name">{user?.display_name || user?.username}</span>
              <span className="topbar__user-role">{user ? t(`roles.${user.role}`) : ''}</span>
            </span>
          </div>
          <button type="button" className="icon-btn" onClick={logout} aria-label={t('auth.signOut')} title={t('auth.signOut')}>
            <Icon name="logout" />
          </button>
        </header>
        <main id="main" ref={mainRef} tabIndex={-1} className="page">
          {children}
        </main>
      </div>
      <div className="visually-hidden" role="status" aria-live="polite">
        {announcement}
      </div>
    </div>
  );
}

function LiveStatus() {
  const { status } = useLive();
  const { t } = useI18n();
  const label =
    status === 'open'
      ? t('live.connected')
      : status === 'connecting'
        ? t('live.connecting')
        : status === 'reconnecting'
          ? t('live.reconnecting')
          : t('live.offline');
  return (
    <span className={`live live--${status}`} title={t('live.title')}>
      <span className="live__dot" aria-hidden="true" />
      <span className="live__text">{label}</span>
    </span>
  );
}
