import { createContext, type ReactNode, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { connectStream, type StreamStatus } from '../api/sse';
import { useApi, useAuth } from './auth';

export type LiveListener = (event: string, data: unknown) => void;

interface LiveValue {
  status: StreamStatus;
  subscribe(listener: LiveListener): () => void;
}

const LiveContext = createContext<LiveValue>({ status: 'closed', subscribe: () => () => undefined });

/** One `/api/stream` connection per page, shared by every component that listens. */
export function LiveProvider({ children }: { children: ReactNode }) {
  const api = useApi();
  const { status: authStatus } = useAuth();
  const [status, setStatus] = useState<StreamStatus>('closed');
  const listeners = useRef(new Set<LiveListener>());

  useEffect(() => {
    if (authStatus !== 'signed-in') {
      setStatus('closed');
      return undefined;
    }
    const handle = connectStream({
      url: api.url('/api/stream'),
      getToken: () => api.getToken(),
      fetchImpl: api.fetcher,
      onStatus: setStatus,
      onUnauthorized: () => api.handleUnauthorized(),
      onEvent: (event, data) => {
        for (const listener of [...listeners.current]) {
          try {
            listener(event, data);
          } catch (err) {
            console.error('live listener failed', err);
          }
        }
      },
    });
    return () => handle.close();
  }, [api, authStatus]);

  const value = useMemo<LiveValue>(
    () => ({
      status,
      subscribe(listener) {
        listeners.current.add(listener);
        return () => listeners.current.delete(listener);
      },
    }),
    [status],
  );

  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}

export function useLive(): LiveValue {
  return useContext(LiveContext);
}

/** Subscribe to stream events; `names` filters by event name (all events when omitted). */
export function useLiveEvent(handler: LiveListener, names?: readonly string[]): void {
  const { subscribe } = useLive();
  const handlerRef = useRef(handler);
  handlerRef.current = handler;
  const key = names?.join('|') ?? '';
  useEffect(() => {
    const filter = key ? new Set(key.split('|')) : null;
    return subscribe((event, data) => {
      if (!filter || filter.has(event)) handlerRef.current(event, data);
    });
  }, [subscribe, key]);
}
