import { type ReactNode, useEffect, useRef } from 'react';

let navigated = false;

/** Called by the shell on client-side navigation so the next page heading takes focus. */
export function markNavigation(): void {
  navigated = true;
}

/**
 * Page title block. Sets document.title and, after an in-app navigation, moves focus
 * to the heading so screen-reader users hear where they landed (SPA focus management).
 */
export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  const ref = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    document.title = `${title} · Mirsad | مرصاد`;
  }, [title]);

  useEffect(() => {
    if (navigated) {
      navigated = false;
      ref.current?.focus();
    }
  }, []);

  return (
    <div className="page-header">
      <div className="page-header__text">
        <h1 ref={ref} tabIndex={-1}>
          {title}
        </h1>
        {subtitle ? <p className="page-header__subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="page-header__actions">{actions}</div> : null}
    </div>
  );
}

export function Section({ title, subtitle, actions, children, id }: { title: ReactNode; subtitle?: string; actions?: ReactNode; children: ReactNode; id?: string }) {
  const headingId = id ? `${id}-title` : undefined;
  return (
    <section className="card" aria-labelledby={headingId}>
      <div className="card__header">
        <div>
          <h2 className="card__title" id={headingId}>
            {title}
          </h2>
          {subtitle ? <p className="card__subtitle">{subtitle}</p> : null}
        </div>
        {actions ? <div className="row">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}
