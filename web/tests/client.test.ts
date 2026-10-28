import { describe, expect, it, vi } from 'vitest';
import { ApiClient, ApiError, buildQuery, filenameFromDisposition, formatDetail, normalizeTools, TOKEN_KEY } from '../src/shared/api/client';
import { memoryStore } from '../src/shared/lib/storage';
import { fakeFetch, json } from './helpers';

const USER = { username: 'noura', role: 'approver', display_name: 'Noura', lang: 'ar' };

describe('helpers', () => {
  it('buildQuery skips empty values and encodes the rest', () => {
    expect(buildQuery({ a: 1, b: '', c: undefined, d: null, e: 'x y', f: false })).toBe('?a=1&e=x+y&f=false');
    expect(buildQuery({})).toBe('');
  });

  it('formatDetail handles FastAPI string and validation errors', () => {
    expect(formatDetail('Policy invalid')).toBe('Policy invalid');
    expect(formatDetail([{ loc: ['body', 'yaml_text'], msg: 'field required' }])).toBe('yaml_text: field required');
    expect(formatDetail(undefined)).toBe('');
  });

  it('filenameFromDisposition reads plain and RFC 5987 names', () => {
    expect(filenameFromDisposition('attachment; filename="audit.csv"', 'x')).toBe('audit.csv');
    expect(filenameFromDisposition("attachment; filename*=UTF-8''%D8%B3%D8%AC%D9%84.json", 'x')).toBe('سجل.json');
    expect(filenameFromDisposition(null, 'fallback.json')).toBe('fallback.json');
  });

  it('normalizeTools accepts the loosely specified /api/tools shapes', () => {
    const profile = { tool: 'send_email', allowed: true, trust: 'trusted', sensitivity: 'internal', sink: 'dynamic', sink_params: ['to'], risk: 'medium', approval: 'on_risk', scan: false };
    expect(normalizeTools([{ name: 'send_email', profiles: { crm: profile } }])[0].profiles.crm.risk).toBe('medium');
    expect(normalizeTools({ tools: [{ name: 'a', profiles: [{ agent_id: 'crm', profile }] }] })[0].profiles.crm.tool).toBe('send_email');
    expect(normalizeTools([{ tool: 'b' }])[0]).toMatchObject({ name: 'b', profiles: {} });
  });
});

describe('ApiClient', () => {
  it('logs in, stores the JWT in session storage and sends it as a Bearer token', async () => {
    const storage = memoryStore();
    const { fetch, calls } = fakeFetch({
      'POST /api/auth/login': () => json({ access_token: 'jwt-1', token_type: 'bearer', user: USER }),
      'GET /api/auth/me': () => json(USER),
    });
    const api = new ApiClient({ fetchImpl: fetch, storage });
    const res = await api.login('noura', 'pw');
    expect(res.user.username).toBe('noura');
    expect(storage.getItem(TOKEN_KEY)).toBe('jwt-1');
    expect(calls[0].body).toEqual({ username: 'noura', password: 'pw' });
    await api.me();
    expect(calls[1].headers.Authorization).toBe('Bearer jwt-1');
    // A new client (e.g. after reload) picks the token up again.
    expect(new ApiClient({ fetchImpl: fetch, storage }).getToken()).toBe('jwt-1');
  });

  it('turns a 401 into logout: token cleared and listeners notified', async () => {
    const storage = memoryStore({ [TOKEN_KEY]: 'stale' });
    const { fetch } = fakeFetch({ 'GET /api/approvals': () => json({ detail: 'expired' }, 401) });
    const api = new ApiClient({ fetchImpl: fetch, storage });
    const listener = vi.fn();
    api.onUnauthorized(listener);
    await expect(api.approvals()).rejects.toMatchObject({ status: 401 });
    expect(listener).toHaveBeenCalledTimes(1);
    expect(api.getToken()).toBeNull();
    expect(storage.getItem(TOKEN_KEY)).toBeNull();
  });

  it('does not trigger logout for a failed login (wrong password)', async () => {
    const { fetch } = fakeFetch({ 'POST /api/auth/login': () => json({ detail: 'Invalid credentials' }, 401) });
    const api = new ApiClient({ fetchImpl: fetch, storage: memoryStore() });
    const listener = vi.fn();
    api.onUnauthorized(listener);
    const err = await api.login('x', 'y').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.detail).toBe('Invalid credentials');
    expect(listener).not.toHaveBeenCalled();
  });

  it('reports network failures as status 0', async () => {
    const api = new ApiClient({ fetchImpl: () => Promise.reject(new TypeError('Failed to fetch')), storage: memoryStore() });
    const err = await api.health().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.isNetwork).toBe(true);
  });

  it('builds audit queries with filters and handles 204 responses', async () => {
    const { fetch, calls } = fakeFetch({
      'GET /api/audit/events': () => json({ items: [], total: 0 }),
      'DELETE /api/users/sara': () => new Response(null, { status: 204 }),
    });
    const api = new ApiClient({ fetchImpl: fetch, storage: memoryStore({ [TOKEN_KEY]: 't' }) });
    await api.auditEvents({ tool: 'send_email', action: 'deny', limit: 25, offset: 0, q: '' });
    expect(calls[0].url).toBe('/api/audit/events?tool=send_email&action=deny&limit=25&offset=0');
    await expect(api.deleteUser('sara')).resolves.toBeUndefined();
  });

  it('sends approval decisions with a trimmed optional note', async () => {
    const { fetch, calls } = fakeFetch({ 'POST /api/approvals/ap_1/decision': () => json({ id: 'ap_1', status: 'approved' }) });
    const api = new ApiClient({ fetchImpl: fetch, storage: memoryStore() });
    await api.decideApproval('ap_1', true, '  looks fine ');
    await api.decideApproval('ap_1', false, '   ');
    expect(calls[0].body).toEqual({ approve: true, note: 'looks fine' });
    expect(calls[1].body).toEqual({ approve: false });
  });

  it('validates policies and normalises the response', async () => {
    const { fetch, calls } = fakeFetch({ 'POST /api/policies/validate': () => json({ valid: false, errors: ['line 3: bad key'] }) });
    const api = new ApiClient({ fetchImpl: fetch, storage: memoryStore() });
    await expect(api.validatePolicy('version: 1')).resolves.toEqual({ valid: false, errors: ['line 3: bad key'] });
    expect(calls[0].body).toEqual({ yaml_text: 'version: 1' });
  });

  it('downloads exports with auth and the server file name', async () => {
    const { fetch, calls } = fakeFetch({
      'GET /api/audit/export': () => new Response('seq,ts\n1,2\n', { status: 200, headers: { 'Content-Disposition': 'attachment; filename="audit.csv"' } }),
    });
    const api = new ApiClient({ fetchImpl: fetch, storage: memoryStore({ [TOKEN_KEY]: 'tok' }) });
    const file = await api.exportAudit('csv', { tool: 'fetch_url' });
    expect(file.filename).toBe('audit.csv');
    expect(file.blob.size).toBe('seq,ts\n1,2\n'.length);
    expect(calls[0].url).toBe('/api/audit/export?format=csv&tool=fetch_url');
    expect(calls[0].headers.Authorization).toBe('Bearer tok');
  });

  it('treats a missing VAPID endpoint or empty key as "push unavailable"', async () => {
    const api1 = new ApiClient({ fetchImpl: fakeFetch({}).fetch, storage: memoryStore() });
    await expect(api1.vapidKey()).resolves.toBeNull();
    const api2 = new ApiClient({ fetchImpl: fakeFetch({ 'GET /api/push/vapid': () => json({ public_key: '' }) }).fetch, storage: memoryStore() });
    await expect(api2.vapidKey()).resolves.toBeNull();
    const api3 = new ApiClient({ fetchImpl: fakeFetch({ 'GET /api/push/vapid': () => json({ public_key: 'BKey' }) }).fetch, storage: memoryStore() });
    await expect(api3.vapidKey()).resolves.toBe('BKey');
  });

  it('accepts list or wrapped list responses and fills demo defaults', async () => {
    const { fetch } = fakeFetch({
      'GET /api/agents': () => json({ items: [{ id: 'a', name: 'A', policy_agent_id: 'x' }] }),
      'POST /api/demo/chat': () => json({ reply: 'hi' }),
    });
    const api = new ApiClient({ fetchImpl: fetch, storage: memoryStore() });
    expect((await api.agents())[0].id).toBe('a');
    expect(await api.demoChat({ message: 'x', protected: true, session_id: 's1' })).toEqual({
      reply: 'hi',
      session_id: 's1',
      protected: true,
      stopped_reason: 'completed',
      steps: [],
      attacker_inbox: [],
    });
  });
});
