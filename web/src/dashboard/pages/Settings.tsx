import { useState } from 'react';
import { useApi, useAuth } from '../../shared/app/auth';
import { useQuery } from '../../shared/app/hooks';
import { Icon } from '../../shared/components/Icon';
import { LangRadios, NumeralRadios, ThemeRadios } from '../../shared/components/Prefs';
import { useI18n } from '../../shared/i18n';
import { notificationPermission, type NotifyPermission, requestNotificationPermission } from '../../shared/lib/notify';
import { localStore } from '../../shared/lib/storage';
import { PageHeader, Section } from '../components/PageHeader';
import { DESKTOP_ALERTS_KEY } from '../Shell';

export default function Settings() {
  const api = useApi();
  const { user, logout } = useAuth();
  const { t, lang, fmtNumber, fmtDateTime } = useI18n();
  const health = useQuery((signal) => api.request<{ status: string; version?: string }>('GET', '/healthz', { signal }), [api]);
  const [permission, setPermission] = useState<NotifyPermission>(notificationPermission);
  const [alerts, setAlerts] = useState(localStore.getItem(DESKTOP_ALERTS_KEY) === 'on');

  async function toggleAlerts(on: boolean) {
    if (on && permission !== 'granted') {
      const result = await requestNotificationPermission();
      setPermission(result);
      if (result !== 'granted') return;
    }
    localStore.setItem(DESKTOP_ALERTS_KEY, on ? 'on' : 'off');
    setAlerts(on);
  }

  return (
    <div className="stack-lg">
      <PageHeader title={t('settings.title')} subtitle={t('settings.subtitle')} />
      <div className="grid-2">
        <Section id="appearance" title={t('settings.appearance')}>
          <div className="stack">
            <ThemeRadios />
            <p className="muted small">{t('settings.motion')}</p>
          </div>
        </Section>
        <Section id="language" title={t('settings.language')}>
          <div className="stack">
            <LangRadios />
            {lang === 'ar' ? <NumeralRadios /> : null}
            <p className="muted small">
              {t('settings.formatSample', { number: fmtNumber(1234567.89), date: fmtDateTime(Date.now(), { dateStyle: 'long' }) })}
            </p>
          </div>
        </Section>
        <Section id="alerts" title={t('settings.notifications')}>
          <div className="stack">
            <p className="muted">{t('settings.notificationsHint')}</p>
            {permission === 'unsupported' ? (
              <p className="banner banner--info">{t('settings.notificationsUnsupported')}</p>
            ) : permission === 'denied' ? (
              <p className="banner banner--warn">
                <Icon name="bell" size={16} />
                {t('settings.notificationsBlocked')}
              </p>
            ) : (
              <label className="switch">
                <input type="checkbox" checked={alerts && permission === 'granted'} onChange={(e) => void toggleAlerts(e.target.checked)} />
                <span className="switch__track" aria-hidden="true" />
                <span>{t('settings.enableNotifications')}</span>
              </label>
            )}
            <a className="btn btn--ghost" href="/approve" target="_blank" rel="noopener">
              <Icon name="smartphone" size={18} />
              {t('settings.approverLink')}
            </a>
            <p className="muted small">{t('settings.approverHint')}</p>
          </div>
        </Section>
        <Section id="account" title={t('settings.account')}>
          <dl className="kv">
            <div>
              <dt>{t('users.username')}</dt>
              <dd className="mono">{user?.username}</dd>
            </div>
            <div>
              <dt>{t('users.displayName')}</dt>
              <dd>{user?.display_name || '–'}</dd>
            </div>
            <div>
              <dt>{t('users.role')}</dt>
              <dd>{user ? t(`roles.${user.role}`) : '–'}</dd>
            </div>
          </dl>
          <p className="muted small settings-note">{t('settings.sessionNote')}</p>
          <button type="button" className="btn btn--ghost" onClick={logout}>
            <Icon name="logout" size={18} />
            {t('auth.signOut')}
          </button>
        </Section>
        <Section id="system" title={t('settings.system')}>
          <dl className="kv">
            <div>
              <dt>{t('settings.health')}</dt>
              <dd>
                {health.data?.status === 'ok' ? (
                  <span className="badge badge--allow">
                    <Icon name="check" size={12} />
                    {t('settings.healthOk')}
                  </span>
                ) : health.error ? (
                  <span className="badge badge--deny">
                    <Icon name="x" size={12} />
                    {t('settings.healthDown')}
                  </span>
                ) : (
                  '…'
                )}
              </dd>
            </div>
            <div>
              <dt>{t('settings.version')}</dt>
              <dd className="mono">{health.data?.version ?? '–'}</dd>
            </div>
            <div>
              <dt>{t('settings.uiVersion')}</dt>
              <dd className="mono">{import.meta.env.MODE === 'production' ? '0.1.0' : 'dev'}</dd>
            </div>
          </dl>
        </Section>
      </div>
    </div>
  );
}
