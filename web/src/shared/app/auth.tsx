import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { ApiClient, ApiError } from '../api/client';
import type { Role, User } from '../api/types';
import { hasStoredLang, useI18n } from '../i18n';
import { useToast } from './toast';

/** One client per page; tests pass their own through <ApiProvider client={...}>. */
export const defaultClient = new ApiClient();

const ApiContext = createContext<ApiClient>(defaultClient);

export function ApiProvider({ client, children }: { client: ApiClient; children: ReactNode }) {
  return <ApiContext.Provider value={client}>{children}</ApiContext.Provider>;
}

export function useApi(): ApiClient {
  return useContext(ApiContext);
}

type AuthStatus = 'checking' | 'signed-out' | 'signed-in';

interface AuthValue {
  status: AuthStatus;
  user: User | null;
  login(username: string, password: string): Promise<User>;
  logout(): void;
  hasRole(...roles: Role[]): boolean;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children, onLogout }: { children: ReactNode; onLogout?: () => void }) {
  const api = useApi();
  const toast = useToast();
  const { t, setLang } = useI18n();
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>(() => (api.getToken() ? 'checking' : 'signed-out'));
  const userRef = useRef<User | null>(null);
  userRef.current = user;

  const adoptUser = useCallback(
    (next: User) => {
      setUser(next);
      setStatus('signed-in');
      // A user's saved language applies only until they pick one on this device.
      if (!hasStoredLang() && (next.lang === 'en' || next.lang === 'ar')) setLang(next.lang);
    },
    [setLang],
  );

  useEffect(() => {
    if (!api.getToken()) return undefined;
    const controller = new AbortController();
    api
      .me(controller.signal)
      .then(adoptUser)
      .catch((err) => {
        if (controller.signal.aborted) return;
        if (err instanceof ApiError && err.status === 401) return; // handled by onUnauthorized
        // Server unreachable: keep the token, show the login form with the error.
        setStatus('signed-out');
        toast.error(err);
      });
    return () => controller.abort();
    // Runs once on mount: later token changes come from login()/logout() directly.
  }, []);

  useEffect(
    () =>
      api.onUnauthorized(() => {
        const wasSignedIn = userRef.current !== null;
        setUser(null);
        setStatus('signed-out');
        onLogout?.();
        if (wasSignedIn) toast.show('warning', t('auth.expired'));
      }),
    [api, onLogout, t, toast],
  );

  const login = useCallback(
    async (username: string, password: string) => {
      const res = await api.login(username, password);
      adoptUser(res.user);
      return res.user;
    },
    [api, adoptUser],
  );

  const logout = useCallback(() => {
    api.logout();
    setUser(null);
    setStatus('signed-out');
    onLogout?.();
  }, [api, onLogout]);

  const value = useMemo<AuthValue>(
    () => ({
      status,
      user,
      login,
      logout,
      hasRole: (...roles) => (user ? roles.includes(user.role) : false),
    }),
    [status, user, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
