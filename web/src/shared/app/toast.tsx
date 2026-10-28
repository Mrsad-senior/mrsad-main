import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from '../components/Icon';
import { useI18n } from '../i18n';
import { errorMessage, isAbort } from './errors';

export type ToastKind = 'success' | 'error' | 'info' | 'warning';

interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastValue {
  show(kind: ToastKind, message: string): void;
  success(message: string): void;
  info(message: string): void;
  /** Shows a localised message for any error (ApiError, network, ...); aborts are ignored. */
  error(err: unknown): void;
}

const ToastContext = createContext<ToastValue | null>(null);
const DURATION: Record<ToastKind, number> = { success: 4500, info: 5000, warning: 7000, error: 9000 };
const ICON: Record<ToastKind, Parameters<typeof Icon>[0]['name']> = {
  success: 'check-circle',
  info: 'info',
  warning: 'alert',
  error: 'x-octagon',
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: number) => {
    setToasts((list) => list.filter((toast) => toast.id !== id));
    const timer = timers.current.get(id);
    if (timer) clearTimeout(timer);
    timers.current.delete(id);
  }, []);

  const show = useCallback(
    (kind: ToastKind, message: string) => {
      if (!message) return;
      const id = nextId.current++;
      setToasts((list) => {
        // Collapse duplicates (e.g. several requests failing because the server is down).
        if (list.some((toast) => toast.message === message && toast.kind === kind)) return list;
        return [...list.slice(-3), { id, kind, message }];
      });
      timers.current.set(id, setTimeout(() => dismiss(id), DURATION[kind]));
    },
    [dismiss],
  );

  useEffect(() => {
    const map = timers.current;
    return () => map.forEach((timer) => clearTimeout(timer));
  }, []);

  const value = useMemo<ToastValue>(
    () => ({
      show,
      success: (message) => show('success', message),
      info: (message) => show('info', message),
      error: (err) => {
        if (isAbort(err)) return;
        show('error', typeof err === 'string' ? err : errorMessage(err, t));
      },
    }),
    [show, t],
  );

  const polite = toasts.filter((toast) => toast.kind !== 'error');
  const assertive = toasts.filter((toast) => toast.kind === 'error');

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toasts">
        <div role="status" aria-live="polite" aria-atomic="false" className="toasts__region">
          {polite.map((toast) => (
            <ToastItem key={toast.id} toast={toast} onDismiss={dismiss} closeLabel={t('app.close')} />
          ))}
        </div>
        <div role="alert" aria-live="assertive" aria-atomic="false" className="toasts__region">
          {assertive.map((toast) => (
            <ToastItem key={toast.id} toast={toast} onDismiss={dismiss} closeLabel={t('app.close')} />
          ))}
        </div>
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ toast, onDismiss, closeLabel }: { toast: Toast; onDismiss: (id: number) => void; closeLabel: string }) {
  return (
    <div className={`toast toast--${toast.kind}`}>
      <Icon name={ICON[toast.kind]} className="toast__icon" />
      <p className="toast__message">{toast.message}</p>
      <button type="button" className="icon-btn icon-btn--sm" onClick={() => onDismiss(toast.id)} aria-label={closeLabel}>
        <Icon name="x" />
      </button>
    </div>
  );
}

export function useToast(): ToastValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
  return ctx;
}
