import { vi } from 'vitest';

export interface Recorded {
  url: string;
  method: string;
  headers: Record<string, string>;
  body: unknown;
}

type Handler = (req: Recorded) => Response | Promise<Response>;

export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

/**
 * Fake fetch routed by "METHOD /path" (query string ignored for matching). Unmatched
 * requests return 404 so components degrade the way they would against a partial API.
 */
export function fakeFetch(routes: Record<string, Handler>) {
  const calls: Recorded[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const method = (init.method ?? 'GET').toUpperCase();
    const headers = Object.fromEntries(Object.entries((init.headers ?? {}) as Record<string, string>));
    let body: unknown = init.body;
    if (typeof body === 'string') {
      try {
        body = JSON.parse(body);
      } catch {
        /* keep raw */
      }
    }
    const req = { url, method, headers, body };
    calls.push(req);
    const path = new URL(url, 'http://localhost').pathname;
    const handler = routes[`${method} ${path}`];
    if (init.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    return handler ? handler(req) : json({ detail: 'Not Found' }, 404);
  });
  return { fetch: fn as unknown as typeof fetch, calls };
}

/** A response whose body streams the given chunks (for SSE tests). */
export function streamResponse(chunks: string[], status = 200): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream, { status, headers: { 'Content-Type': 'text/event-stream' } });
}
