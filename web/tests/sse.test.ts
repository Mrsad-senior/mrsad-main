import { describe, expect, it, vi } from 'vitest';
import { connectStream, SSEParser, type StreamStatus } from '../src/shared/api/sse';
import { json, streamResponse } from './helpers';

describe('SSEParser', () => {
  it('parses named events with JSON data', () => {
    const p = new SSEParser();
    expect(p.feed('event: approval.requested\ndata: {"id":"ap_1"}\n\n')).toEqual([{ event: 'approval.requested', data: '{"id":"ap_1"}' }]);
  });

  it('handles messages split across chunks, CRLF and lone CR line endings', () => {
    const p = new SSEParser();
    expect(p.feed('event: audit.ev')).toEqual([]);
    expect(p.feed('ent\r\ndata: {"seq":')).toEqual([]);
    expect(p.feed('5}\r')).toEqual([]); // line ends at "\r"; a following "\n" belongs to the same CRLF
    expect(p.feed('\n\r\n')).toEqual([{ event: 'audit.event', data: '{"seq":5}' }]);
    expect(p.feed('data: a\rdata: b\r\r')).toEqual([{ event: 'message', data: 'a\nb' }]);
  });

  it('does not treat a CRLF split across chunks as an extra blank line', () => {
    const p = new SSEParser();
    expect(p.feed('data: x\r')).toEqual([]);
    expect(p.feed('\ndata: y\r')).toEqual([]);
    expect(p.feed('\n\r\n')).toEqual([{ event: 'message', data: 'x\ny' }]);
    // Empty chunks keep the pending-CR state.
    expect(p.feed('data: z\r')).toEqual([]);
    expect(p.feed('')).toEqual([]);
    expect(p.feed('\n\n')).toEqual([{ event: 'message', data: 'z' }]);
  });

  it('joins multi-line data, ignores comments/unknown fields, tracks id and retry', () => {
    const p = new SSEParser();
    const out = p.feed(': keep-alive\nid: 42\nretry: 5000\nfoo: bar\ndata: line1\ndata:line2\n\n');
    expect(out).toEqual([{ event: 'message', data: 'line1\nline2', id: '42' }]);
    expect(p.retryMs).toBe(5000);
    expect(p.lastEventId).toBe('42');
  });

  it('does not dispatch events without data and strips a leading BOM', () => {
    const p = new SSEParser();
    expect(p.feed('﻿event: ping\n\n')).toEqual([]);
    expect(p.feed('data: x\n\n')).toEqual([{ event: 'message', data: 'x' }]);
  });

  it('keeps Arabic text intact', () => {
    const p = new SSEParser();
    expect(p.feed('data: {"summary_ar":"يريد الوكيل إرسال بريد"}\n\n')[0].data).toContain('يريد الوكيل');
  });
});

describe('connectStream', () => {
  it('sends the bearer token, dispatches parsed events and reconnects after the stream ends', async () => {
    const events: [string, unknown][] = [];
    const statuses: StreamStatus[] = [];
    let call = 0;
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      call += 1;
      expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer jwt');
      if (call === 1) return streamResponse(['id: 7\nevent: approval.requested\ndata: {"id":"ap_1","tool":"send_email"}\n\n', 'data: plain\n\n']);
      if (call === 2) {
        expect((init?.headers as Record<string, string>)['Last-Event-ID']).toBe('7');
        return json({ detail: 'expired' }, 401);
      }
      throw new Error('unexpected');
    });
    const onUnauthorized = vi.fn();
    const handle = connectStream({
      url: '/api/stream',
      getToken: () => 'jwt',
      fetchImpl: fetchImpl as unknown as typeof fetch,
      onEvent: (name, data) => events.push([name, data]),
      onStatus: (s) => statuses.push(s),
      onUnauthorized,
      sleep: () => Promise.resolve(),
    });
    await handle.done;
    expect(events).toEqual([
      ['approval.requested', { id: 'ap_1', tool: 'send_email' }],
      ['message', 'plain'],
    ]);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(statuses).toEqual(['connecting', 'open', 'reconnecting', 'closed']);
  });

  it('retries with backoff on network errors and stops on close()', async () => {
    const delays: number[] = [];
    let handle: ReturnType<typeof connectStream> | null = null;
    const fetchImpl = vi.fn(async () => {
      throw new TypeError('network down');
    });
    handle = connectStream({
      url: '/api/stream',
      getToken: () => null,
      fetchImpl: fetchImpl as unknown as typeof fetch,
      onEvent: () => undefined,
      initialRetryMs: 1000,
      maxRetryMs: 4000,
      sleep: async (ms) => {
        delays.push(ms);
        if (delays.length === 4) handle?.close();
      },
    });
    await handle.done;
    expect(delays).toHaveLength(4);
    // 1 s, 2 s, 4 s, then capped at 4 s (each with +/-20% jitter).
    [1000, 2000, 4000, 4000].forEach((base, i) => {
      expect(delays[i]).toBeGreaterThanOrEqual(base * 0.8);
      expect(delays[i]).toBeLessThanOrEqual(base * 1.2);
    });
  });

  it('stops without retrying when the stream is forbidden', async () => {
    const fetchImpl = vi.fn(async () => json({ detail: 'no' }, 403));
    const handle = connectStream({ url: '/x', getToken: () => 't', fetchImpl: fetchImpl as unknown as typeof fetch, onEvent: () => undefined, sleep: () => Promise.resolve() });
    await handle.done;
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
