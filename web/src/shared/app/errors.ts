import { ApiError } from '../api/client';
import type { I18n } from '../i18n';

/** Localised, user-facing message for any thrown value (server detail appended when useful). */
export function errorMessage(err: unknown, t: I18n['t']): string {
  if (err instanceof ApiError) {
    const base = (() => {
      switch (true) {
        case err.status === 0:
          return t('errors.network');
        case err.status === 401:
          return t('errors.unauthorized');
        case err.status === 403:
          return t('errors.forbidden');
        case err.status === 404:
          return t('errors.notFound');
        case err.status === 409:
          return t('errors.conflict');
        case err.status === 413:
          return t('errors.tooLarge');
        case err.status === 422 || err.status === 400:
          return t('errors.validation');
        case err.status === 429:
          return t('errors.rateLimited');
        case err.status >= 500:
          return t('errors.server');
        default:
          return t('errors.generic');
      }
    })();
    const detail = err.detail && err.status !== 0 && err.status < 500 ? err.detail : '';
    return detail && detail !== base ? `${base} (${detail})` : base;
  }
  if (err instanceof Error && err.name === 'AbortError') return '';
  return t('errors.generic');
}

export function isAbort(err: unknown): boolean {
  return err instanceof DOMException ? err.name === 'AbortError' : err instanceof Error && err.name === 'AbortError';
}
