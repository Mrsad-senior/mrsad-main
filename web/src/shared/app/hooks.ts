import { type DependencyList, useCallback, useEffect, useRef, useState } from 'react';
import { isAbort } from './errors';

export interface QueryState<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean;
  /** Refetch; keeps showing the previous data while loading (no layout jump). */
  reload(): void;
  setData(update: T | ((prev: T | undefined) => T)): void;
}

/** Fetch-on-mount helper with abort on unmount / dependency change. */
export function useQuery<T>(fetcher: (signal: AbortSignal) => Promise<T>, deps: DependencyList): QueryState<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetcherRef
      .current(controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setData(value);
        setError(null);
      })
      .catch((err) => {
        if (controller.signal.aborted || isAbort(err)) return;
        setError(err);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // `deps` is the caller's dependency list, forwarded on purpose.
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { data, error, loading, reload, setData };
}

/** Current time, re-rendering every `intervalMs` (for countdowns and relative times). */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return now;
}

/** Tracks navigator.onLine. */
export function useOnline(): boolean {
  const [online, setOnline] = useState(() => (typeof navigator === 'undefined' ? true : navigator.onLine !== false));
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener('online', up);
    window.addEventListener('offline', down);
    return () => {
      window.removeEventListener('online', up);
      window.removeEventListener('offline', down);
    };
  }, []);
  return online;
}

/** Wraps an async action with a pending flag; errors propagate to the caller. */
export function useAction<A extends unknown[], R>(action: (...args: A) => Promise<R>): [(...args: A) => Promise<R>, boolean] {
  const [pending, setPending] = useState(false);
  const ref = useRef(action);
  ref.current = action;
  const run = useCallback(async (...args: A) => {
    setPending(true);
    try {
      return await ref.current(...args);
    } finally {
      setPending(false);
    }
  }, []);
  return [run, pending];
}

/** Save a Blob as a file via a temporary object URL. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
