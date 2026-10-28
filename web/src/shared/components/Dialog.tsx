import { type ReactNode, useEffect, useId, useRef } from 'react';
import { useI18n } from '../i18n';
import { Icon } from './Icon';

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  /** modal: centred; drawer: side panel (inline-end); sheet: bottom sheet (mobile). */
  variant?: 'modal' | 'drawer' | 'sheet';
  size?: 'sm' | 'md' | 'lg';
  /** Element to focus first (defaults to the dialog itself). */
  initialFocusRef?: React.RefObject<HTMLElement | null>;
  className?: string;
}

/**
 * Native <dialog> with showModal(): the browser provides focus trapping, inert
 * background, Esc to close and top-layer stacking. Focus returns to the opener.
 */
export function Dialog({ open, onClose, title, children, footer, variant = 'modal', size = 'md', initialFocusRef, className }: DialogProps) {
  const { t } = useI18n();
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return undefined;
    if (open && !dialog.open) {
      const opener = document.activeElement as HTMLElement | null;
      if (typeof dialog.showModal === 'function') dialog.showModal();
      else dialog.setAttribute('open', '');
      (initialFocusRef?.current ?? dialog).focus?.();
      return () => {
        if (dialog.open) {
          if (typeof dialog.close === 'function') dialog.close();
          else dialog.removeAttribute('open');
        }
        opener?.focus?.();
      };
    }
    return undefined;
  }, [open, initialFocusRef]);

  if (!open) return null;

  return (
    <dialog
      ref={ref}
      className={`dialog dialog--${variant} dialog--${size} ${className ?? ''}`}
      aria-labelledby={titleId}
      tabIndex={-1}
      onCancel={(event) => {
        event.preventDefault();
        onCloseRef.current();
      }}
      onClick={(event) => {
        // A click on the backdrop targets the <dialog> element itself.
        if (event.target === ref.current) onCloseRef.current();
      }}
    >
      <div className="dialog__panel">
        <header className="dialog__header">
          <h2 id={titleId} className="dialog__title">
            {title}
          </h2>
          <button type="button" className="icon-btn" onClick={() => onCloseRef.current()} aria-label={t('app.close')}>
            <Icon name="x" />
          </button>
        </header>
        <div className="dialog__body">{children}</div>
        {footer ? <footer className="dialog__footer">{footer}</footer> : null}
      </div>
    </dialog>
  );
}

export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel,
  tone = 'primary',
  pending,
  onConfirm,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  body?: ReactNode;
  confirmLabel: string;
  tone?: 'primary' | 'danger';
  pending?: boolean;
  onConfirm: () => void;
  onClose: () => void;
  children?: ReactNode;
}) {
  const { t } = useI18n();
  const cancelRef = useRef<HTMLButtonElement>(null);
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      size="sm"
      initialFocusRef={cancelRef}
      footer={
        <>
          <button ref={cancelRef} type="button" className="btn btn--ghost" onClick={onClose}>
            {t('app.cancel')}
          </button>
          <button type="button" className={`btn btn--${tone}`} onClick={onConfirm} disabled={pending} aria-busy={pending}>
            {confirmLabel}
          </button>
        </>
      }
    >
      {body ? <div className="stack-sm">{body}</div> : null}
      {children}
    </Dialog>
  );
}
