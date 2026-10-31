import { useI18n } from '../i18n';
import { Icon } from './Icon';

/** Full-page notice shown instead of the app when the deployment is missing settings. */
export function ConfigError({ missing }: { missing: readonly string[] }) {
  const { t } = useI18n();
  return (
    <main className="boot" id="main">
      <div className="empty empty--error" role="alert">
        <Icon name="alert" size={32} className="empty__icon" />
        <p className="empty__title">{t('errors.configMissing')}</p>
        <p className="muted">{t('errors.configMissingBody')}</p>
        <ul className="mono" dir="ltr">
          {missing.map((name) => (
            <li key={name}>{name}</li>
          ))}
        </ul>
      </div>
    </main>
  );
}
