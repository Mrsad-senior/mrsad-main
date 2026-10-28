import { useEffect, useState } from 'react';
import { useI18n } from '../i18n';
import { Icon } from './Icon';

async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall back below (e.g. insecure context) */
  }
  try {
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.className = 'visually-hidden';
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand('copy');
    area.remove();
    return ok;
  } catch {
    return false;
  }
}

export function CopyButton({ text, label, variant = 'ghost' }: { text: string; label?: string; variant?: 'ghost' | 'primary' }) {
  const { t } = useI18n();
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle');

  useEffect(() => {
    if (state === 'idle') return undefined;
    const timer = setTimeout(() => setState('idle'), 2000);
    return () => clearTimeout(timer);
  }, [state]);

  const text_ = state === 'copied' ? t('app.copied') : state === 'failed' ? t('app.copyFailed') : (label ?? t('app.copy'));
  return (
    <button
      type="button"
      className={`btn btn--${variant} btn--sm`}
      onClick={async () => setState((await copyText(text)) ? 'copied' : 'failed')}
    >
      <Icon name={state === 'copied' ? 'check' : 'copy'} size={16} />
      <span aria-live="polite">{text_}</span>
    </button>
  );
}
