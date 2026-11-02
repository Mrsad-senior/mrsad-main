import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, missingEnv } from '../src/shared/app/config';
import { ConfigError } from '../src/shared/components/ConfigError';
import { I18nProvider } from '../src/shared/i18n';

describe('missingEnv', () => {
  it('requires nothing outside the Cloudflare build', () => {
    expect(missingEnv({ MODE: 'production' })).toEqual([]);
    expect(missingEnv({ MODE: 'test' })).toEqual([]);
  });

  it('lists each missing or blank variable in the Cloudflare build', () => {
    expect(missingEnv({ MODE: 'cloudflare', VITE_SUPABASE_URL: '  ' })).toEqual([
      'VITE_SUPABASE_URL',
      'VITE_SUPABASE_ANON_KEY',
    ]);
  });

  it('passes when both are set', () => {
    expect(
      missingEnv({
        MODE: 'cloudflare',
        VITE_SUPABASE_URL: 'https://project.supabase.co',
        VITE_SUPABASE_ANON_KEY: 'anon-key',
      }),
    ).toEqual([]);
  });
});

describe('apiBaseUrl', () => {
  it('stays same-origin outside the Cloudflare build', () => {
    expect(apiBaseUrl({ MODE: 'production', VITE_API_BASE_URL: 'https://api.example.com' })).toBe('');
    expect(apiBaseUrl({ MODE: 'test', VITE_API_BASE_URL: 'https://api.example.com' })).toBe('');
  });

  it('uses VITE_API_BASE_URL in the Cloudflare build, without a trailing slash', () => {
    expect(apiBaseUrl({ MODE: 'cloudflare', VITE_API_BASE_URL: ' https://api.example.com/ ' })).toBe(
      'https://api.example.com',
    );
  });

  it('falls back to same-origin /api when it is empty', () => {
    expect(apiBaseUrl({ MODE: 'cloudflare', VITE_API_BASE_URL: '  ' })).toBe('');
    expect(apiBaseUrl({ MODE: 'cloudflare' })).toBe('');
  });
});

describe('ConfigError', () => {
  it('names the missing variables', () => {
    render(
      <I18nProvider>
        <ConfigError missing={['VITE_SUPABASE_ANON_KEY']} />
      </I18nProvider>,
    );
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toContain('This site is not configured');
    expect(alert.textContent).toContain('VITE_SUPABASE_ANON_KEY');
  });
});
