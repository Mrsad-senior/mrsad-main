import { lazy, Suspense } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import type { ApiClient } from '../shared/api/client';
import type { Role } from '../shared/api/types';
import { ApiProvider, AuthProvider, defaultClient, useAuth } from '../shared/app/auth';
import { LiveProvider } from '../shared/app/live';
import { ThemeProvider } from '../shared/app/theme';
import { ToastProvider } from '../shared/app/toast';
import { LoginForm } from '../shared/components/LoginForm';
import { EmptyState, Spinner } from '../shared/components/States';
import { I18nProvider, useI18n } from '../shared/i18n';
import { Shell } from './Shell';

// Pages are code-split: charts (Recharts) only load with the Overview page.
const Overview = lazy(() => import('./pages/Overview'));
const Activity = lazy(() => import('./pages/Activity'));
const Approvals = lazy(() => import('./pages/Approvals'));
const Policies = lazy(() => import('./pages/Policies'));
const Agents = lazy(() => import('./pages/Agents'));
const Users = lazy(() => import('./pages/Users'));
const Tools = lazy(() => import('./pages/Tools'));
const Playground = lazy(() => import('./pages/Playground'));
const Demo = lazy(() => import('./pages/Demo'));
const Settings = lazy(() => import('./pages/Settings'));

export function DashboardApp({ client = defaultClient }: { client?: ApiClient }) {
  return (
    <ApiProvider client={client}>
      <I18nProvider>
        <ThemeProvider>
          <ToastProvider>
            <AuthProvider>
              <LiveProvider>
                <Gate />
              </LiveProvider>
            </AuthProvider>
          </ToastProvider>
        </ThemeProvider>
      </I18nProvider>
    </ApiProvider>
  );
}

function Gate() {
  const { status } = useAuth();
  const { t } = useI18n();
  if (status === 'checking') {
    return (
      <main className="boot" id="main">
        <Spinner />
      </main>
    );
  }
  if (status === 'signed-out') return <LoginForm subtitle={t('app.console')} intro={t('auth.welcome')} />;
  return (
    <HashRouter>
      <Shell>
        <Suspense fallback={<Spinner />}>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/activity" element={<Guard roles={['admin', 'auditor']}><Activity /></Guard>} />
            <Route path="/approvals" element={<Guard roles={['admin', 'approver']}><Approvals /></Guard>} />
            <Route path="/policies" element={<Guard roles={['admin', 'auditor']}><Policies /></Guard>} />
            <Route path="/agents" element={<Guard roles={['admin']}><Agents /></Guard>} />
            <Route path="/users" element={<Guard roles={['admin']}><Users /></Guard>} />
            <Route path="/tools" element={<Guard roles={['admin', 'auditor']}><Tools /></Guard>} />
            <Route path="/playground" element={<Playground />} />
            <Route path="/demo" element={<Demo />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </Shell>
    </HashRouter>
  );
}

/** Client-side role check mirrors the API's; the server remains the authority. */
function Guard({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const { hasRole } = useAuth();
  const { t } = useI18n();
  if (!hasRole(...roles)) {
    return (
      <EmptyState icon="lock" title={t('errors.forbidden')}>
        <p>{t('errors.roleNeeded', { roles: roles.map((r) => t(`roles.${r}`)).join(' / ') })}</p>
      </EmptyState>
    );
  }
  return <>{children}</>;
}
