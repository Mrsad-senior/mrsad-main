/**
 * Server-Sent Events over `fetch`.
 *
 * The native EventSource API cannot send an Authorization header, and putting the
 * JWT in a query string would leak it into logs and history, so the stream is read
 * with fetch + a spec-compliant line parser (WHATWG HTML "event stream
 * interpretation"). Reconnects use exponential backoff with jitter and honour the
 * server's `retry:` field and `Last-Event-ID`.
 */

export interface SSEMessage {
  event: string;
  data: string;
  id?: string;
}

/** Incremental parser: feed it decoded text chunks, get complete messages back. */
export class SSEParser {
  private buffer = '';
  private dataLines: string[] = [];
  private eventType = '';
  private started = false;
  /** The previous chunk ended with "\r": a "\n" opening the next chunk completes that CRLF. */
  private skipLeadingLF = false;
  /** Last `id:` seen (persists across messages, as per the spec). */
  lastEventId: string | undefined;
  /** Reconnection delay requested by the server with `retry:`. */
  retryMs: number | undefined;

  feed(chunk: string): SSEMessage[] {
    if (!this.started && chunk.length > 0) {
      this.started = true;
      if (chunk.charCodeAt(0) === 0xfeff) chunk = chunk.slice(1);
    }
    if (this.skipLeadingLF && chunk.length > 0) {
      if (chunk[0] === '\n') chunk = chunk.slice(1);
      this.skipLeadingLF = false;
    }
    this.buffer += chunk;
    const out: SSEMessage[] = [];
    // A lone "\r" is a complete line ending (WHATWG), so a trailing "\r" is processed now rather
    // than held back; if the next chunk starts with "\n" it is skipped as the rest of a CRLF.
    let match: RegExpExecArray | null;
    const lineBreak = /\r\n|\r|\n/g;
    let consumed = 0;
    while ((match = lineBreak.exec(this.buffer)) !== null) {
      const line = this.buffer.slice(consumed, match.index);
      consumed = match.index + match[0].length;
      if (match[0] === '\r' && consumed === this.buffer.length) this.skipLeadingLF = true;
      const msg = this.processLine(line);
      if (msg) out.push(msg);
    }
    this.buffer = this.buffer.slice(consumed);
    return out;
  }

  private processLine(line: string): SSEMessage | null {
    if (line === '') return this.dispatch();
    if (line.startsWith(':')) return null; // comment / keep-alive
    const colon = line.indexOf(':');
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? '' : line.slice(colon + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    switch (field) {
      case 'event':
        this.eventType = value;
        break;
      case 'data':
        this.dataLines.push(value);
        break;
      case 'id':
        if (!value.includes('\0')) this.lastEventId = value;
        break;
      case 'retry':
        if (/^\d+$/.test(value)) this.retryMs = Number(value);
        break;
      default:
        break;
    }
    return null;
  }

  private dispatch(): SSEMessage | null {
    if (this.dataLines.length === 0) {
      this.eventType = '';
      return null;
    }
    const msg: SSEMessage = { event: this.eventType || 'message', data: this.dataLines.join('\n') };
    if (this.lastEventId !== undefined) msg.id = this.lastEventId;
    this.dataLines = [];
    this.eventType = '';
    return msg;
  }
}

export type StreamStatus = 'connecting' | 'open' | 'reconnecting' | 'closed';

export interface StreamOptions {
  url: string;
  getToken: () => string | null;
  onEvent: (event: string, data: unknown, raw: SSEMessage) => void;
  onStatus?: (status: StreamStatus) => void;
  /** 401 from the stream: the session is gone. The stream stops. */
  onUnauthorized?: () => void;
  fetchImpl?: typeof fetch;
  initialRetryMs?: number;
  maxRetryMs?: number;
  /** Injectable for tests. */
  sleep?: (ms: number, signal: AbortSignal) => Promise<void>;
}

export interface StreamHandle {
  close(): void;
  /** Resolves when the read loop has fully stopped (after close() or a fatal error). */
  done: Promise<void>;
}

const defaultSleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener('abort', () => {
      clearTimeout(timer);
      resolve();
    }, { once: true });
  });

function parseData(data: string): unknown {
  try {
    return JSON.parse(data);
  } catch {
    return data;
  }
}

export function connectStream(options: StreamOptions): StreamHandle {
  const controller = new AbortController();
  const fetchImpl = options.fetchImpl ?? ((input, init) => fetch(input, init));
  const sleep = options.sleep ?? defaultSleep;
  const initial = options.initialRetryMs ?? 1000;
  const max = options.maxRetryMs ?? 30_000;
  let closed = false;
  let lastEventId: string | undefined;
  let serverRetry: number | undefined;

  const setStatus = (status: StreamStatus) => options.onStatus?.(status);

  async function run(): Promise<void> {
    let attempt = 0;
    while (!closed) {
      setStatus(attempt === 0 ? 'connecting' : 'reconnecting');
      try {
        const headers: Record<string, string> = { Accept: 'text/event-stream', 'Cache-Control': 'no-cache' };
        const token = options.getToken();
        if (token) headers.Authorization = `Bearer ${token}`;
        if (lastEventId) headers['Last-Event-ID'] = lastEventId;
        const response = await fetchImpl(options.url, {
          headers,
          signal: controller.signal,
          cache: 'no-store',
          credentials: 'same-origin',
        });
        if (response.status === 401) {
          closed = true;
          options.onUnauthorized?.();
          break;
        }
        if (response.status === 403 || response.status === 404) {
          closed = true; // not retryable: role or deployment does not offer the stream
          break;
        }
        if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

        setStatus('open');
        attempt = 0;
        const parser = new SSEParser();
        const decoder = new TextDecoder();
        const reader = response.body.getReader();
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          for (const msg of parser.feed(decoder.decode(value, { stream: true }))) {
            options.onEvent(msg.event, parseData(msg.data), msg);
          }
          lastEventId = parser.lastEventId ?? lastEventId;
          serverRetry = parser.retryMs ?? serverRetry;
        }
      } catch {
        if (closed) break;
      }
      if (closed) break;
      attempt += 1;
      const base = serverRetry ?? initial;
      const delay = Math.min(max, base * 2 ** Math.min(attempt - 1, 10));
      await sleep(delay * (0.8 + Math.random() * 0.4), controller.signal);
    }
    setStatus('closed');
  }

  const done = run();
  return {
    close() {
      closed = true;
      controller.abort();
    },
    done,
  };
}
