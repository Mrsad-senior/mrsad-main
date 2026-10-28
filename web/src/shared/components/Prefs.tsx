import { type ThemeChoice, useTheme } from '../app/theme';
import { useI18n } from '../i18n';
import { Icon } from './Icon';

/** Toggles EN <-> AR; the button text is the *target* language, written in that language. */
export function LangToggle({ className }: { className?: string }) {
  const { lang, setLang, t } = useI18n();
  const target = lang === 'ar' ? 'en' : 'ar';
  return (
    <button
      type="button"
      className={`btn btn--ghost btn--sm lang-toggle ${className ?? ''}`}
      onClick={() => setLang(target)}
      aria-label={t(target === 'ar' ? 'prefs.switchToArabic' : 'prefs.switchToEnglish')}
      lang={target}
    >
      <Icon name="globe" size={18} />
      <span>{target === 'ar' ? 'العربية' : 'English'}</span>
    </button>
  );
}

const THEME_ICON: Record<ThemeChoice, 'monitor' | 'sun' | 'moon'> = { system: 'monitor', light: 'sun', dark: 'moon' };
const THEME_KEY = { system: 'prefs.themeSystem', light: 'prefs.themeLight', dark: 'prefs.themeDark' } as const;

export function ThemeToggle() {
  const { theme, cycle } = useTheme();
  const { t } = useI18n();
  const label = t('prefs.themeToggle', { theme: t(THEME_KEY[theme]) });
  return (
    <button type="button" className="icon-btn" onClick={cycle} aria-label={label} title={label}>
      <Icon name={THEME_ICON[theme]} />
    </button>
  );
}

/** Radio group for the Settings page / approver menu. */
export function ThemeRadios() {
  const { theme, setTheme } = useTheme();
  const { t } = useI18n();
  return (
    <fieldset className="segmented">
      <legend className="field__label">{t('prefs.theme')}</legend>
      {(['system', 'light', 'dark'] as const).map((choice) => (
        <label key={choice} className="segmented__option">
          <input type="radio" name="theme" value={choice} checked={theme === choice} onChange={() => setTheme(choice)} />
          <span>
            <Icon name={THEME_ICON[choice]} size={16} />
            {t(THEME_KEY[choice])}
          </span>
        </label>
      ))}
    </fieldset>
  );
}

export function LangRadios() {
  const { lang, setLang, t } = useI18n();
  return (
    <fieldset className="segmented">
      <legend className="field__label">{t('prefs.language')}</legend>
      <label className="segmented__option">
        <input type="radio" name="lang" value="en" checked={lang === 'en'} onChange={() => setLang('en')} />
        <span lang="en">English</span>
      </label>
      <label className="segmented__option">
        <input type="radio" name="lang" value="ar" checked={lang === 'ar'} onChange={() => setLang('ar')} />
        <span lang="ar">العربية</span>
      </label>
    </fieldset>
  );
}

export function NumeralRadios() {
  const { numerals, setNumerals, t } = useI18n();
  return (
    <fieldset className="segmented">
      <legend className="field__label">{t('prefs.numerals')}</legend>
      <label className="segmented__option">
        <input type="radio" name="numerals" value="latn" checked={numerals === 'latn'} onChange={() => setNumerals('latn')} />
        <span>{t('prefs.numeralsLatn')}</span>
      </label>
      <label className="segmented__option">
        <input type="radio" name="numerals" value="arab" checked={numerals === 'arab'} onChange={() => setNumerals('arab')} />
        <span>{t('prefs.numeralsArab')}</span>
      </label>
    </fieldset>
  );
}
