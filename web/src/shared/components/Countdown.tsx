import { useMemo } from 'react';
import { useI18n } from '../i18n';
import { countdown, localeDigits } from '../lib/countdown';
import { Icon } from './Icon';

/** Time left until an approval expires; urgency shown by icon, text and a progress bar. */
export function Countdown({
  expiresAt,
  createdAt,
  now,
  showBar = false,
  compact = false,
}: {
  expiresAt: number;
  createdAt?: number;
  now: number;
  showBar?: boolean;
  compact?: boolean;
}) {
  const { t, locale } = useI18n();
  const digits = useMemo(() => localeDigits(locale), [locale]);
  const info = countdown(expiresAt, now, createdAt, digits);
  const expired = info.urgency === 'expired';
  const text = expired ? t('approvals.expired') : compact ? info.text : t('approvals.expiresIn', { time: info.text });

  return (
    <span className={`countdown countdown--${info.urgency}`}>
      <span className="countdown__label">
        <Icon name={expired ? 'x-circle' : info.urgency === 'normal' ? 'clock' : 'alert'} size={16} />
        {/* The visible clock ticks every second; screen readers get a static label instead. */}
        <span aria-hidden="true" className="countdown__text">
          {text}
        </span>
        <span className="visually-hidden">
          {expired ? t('approvals.expired') : t('approvals.expiresAround', { seconds: info.seconds })}
        </span>
      </span>
      {showBar ? (
        <span className="countdown__bar" aria-hidden="true">
          <span className="countdown__fill" style={{ inlineSize: `${Math.round(info.fraction * 100)}%` }} />
        </span>
      ) : null}
    </span>
  );
}
