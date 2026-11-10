import { type FormEvent, useId, useState } from 'react';
import { ApiError } from '../api/client';
import { useAuth } from '../app/auth';
import { errorMessage } from '../app/errors';
import { useI18n } from '../i18n';
import { Icon } from './Icon';
import { Logo } from './Logo';
import { LangToggle, ThemeToggle } from './Prefs';

const STEPS = ['auth.step1', 'auth.step2', 'auth.step3'] as const;

/**
 * Shared sign-in screen for the dashboard and the approver PWA (Figma "01 Sign in"):
 * a navy brand panel beside the form. Narrow screens show only the form.
 */
export function LoginForm({ subtitle, intro }: { subtitle?: string; intro: string }) {
  const { login } = useAuth();
  const { t, lang, fmtNumber } = useI18n();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const errorId = useId();

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!username.trim() || !password) {
      setError(t('auth.missing'));
      return;
    }
    setPending(true);
    setError('');
    try {
      await login(username.trim(), password);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setError(t('auth.invalid'));
      else if (err instanceof ApiError && err.status === 429) setError(t('auth.locked'));
      else setError(errorMessage(err, t));
      setPassword('');
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="login" id="main">
      <section className="login__brand" aria-labelledby="login-hero">
        <Logo size={36} />
        <p className="login__hero" id="login-hero">
          <span>{t('auth.heroLine1')}</span> <span>{t('auth.heroLine2')}</span>
        </p>
        <p className="login__lead">{intro}</p>
        <ol className="login__steps">
          {STEPS.map((key, i) => (
            <li key={key}>
              <span className="login__step-number" aria-hidden="true">
                {fmtNumber(i + 1, { minimumIntegerDigits: lang === 'ar' ? 1 : 2 })}
              </span>
              {t(key)}
            </li>
          ))}
        </ol>
        <p className="login__tagline">{t('auth.tagline')}</p>
      </section>

      <div className="login__panel">
        <div className="login__prefs">
          <ThemeToggle />
        </div>
        <form className="login__form" onSubmit={onSubmit} noValidate aria-describedby={error ? errorId : undefined}>
          <span className="login__logo">
            <Logo size={36} />
          </span>
          {subtitle ? <p className="login__eyebrow">{subtitle}</p> : null}
          <h1 className="login__title">{t('auth.welcomeBack')}</h1>
          <p className="login__prompt">{t('auth.signInPrompt')}</p>
          <div className="field">
            <label className="field__label" htmlFor="login-username">
              {t('auth.username')}
            </label>
            <input
              id="login-username"
              className="input"
              name="username"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              dir="ltr"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              aria-invalid={Boolean(error) || undefined}
              required
            />
          </div>
          <div className="field">
            <label className="field__label" htmlFor="login-password">
              {t('auth.password')}
            </label>
            <div className="input-group">
              <input
                id="login-password"
                className="input"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                dir="ltr"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-invalid={Boolean(error) || undefined}
                required
              />
              <button
                type="button"
                className="icon-btn"
                onClick={() => setShowPassword((v) => !v)}
                aria-pressed={showPassword}
                aria-label={showPassword ? t('auth.hidePassword') : t('auth.showPassword')}
              >
                <Icon name="eye" />
              </button>
            </div>
          </div>
          {error ? (
            <p className="form-error" id={errorId} role="alert">
              <Icon name="alert" size={16} />
              {error}
            </p>
          ) : null}
          <button type="submit" className="btn btn--primary btn--block btn--lg login__submit" disabled={pending} aria-busy={pending}>
            {pending ? t('auth.signingIn') : t('auth.signIn')}
          </button>
          <p className="login__note">{t('auth.protected')}</p>
          <LangToggle className="login__lang" />
        </form>
      </div>
    </main>
  );
}
