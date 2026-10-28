/**
 * Mirsad mark: a watchtower roof above an open eye ("mirsad" = watch post).
 * Same geometry as public/assets/favicon.svg and scripts/gen-icons.mjs.
 */
export function LogoMark({ size = 32, title }: { size?: number; title?: string }) {
  return (
    <svg
      className="logo-mark"
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      {title ? <title>{title}</title> : null}
      <rect width="64" height="64" rx="14" className="logo-mark__bg" />
      <path
        d="M14 29 32 15 50 29"
        fill="none"
        className="logo-mark__fg-stroke"
        strokeWidth="5.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M12 42Q32 24 52 42Q32 60 12 42Z" className="logo-mark__fg" />
      <circle cx="32" cy="42" r="7.5" className="logo-mark__bg" />
      <circle cx="32" cy="42" r="3" className="logo-mark__fg" />
    </svg>
  );
}

/** Mark + bilingual wordmark "Mirsad | مرصاد". */
export function Logo({ size = 32, subtitle }: { size?: number; subtitle?: string }) {
  return (
    <span className="logo">
      <LogoMark size={size} />
      <span className="logo__text">
        <span className="logo__word">
          <span lang="en">Mirsad</span>
          <span className="logo__sep" aria-hidden="true">
            |
          </span>
          <span lang="ar">مرصاد</span>
        </span>
        {subtitle ? <span className="logo__subtitle">{subtitle}</span> : null}
      </span>
    </span>
  );
}
