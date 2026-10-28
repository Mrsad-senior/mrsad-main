/**
 * The client against the response/request shapes of the *implemented* backend
 * (src/mirsad/api/routers/*.py, src/mirsad/taint/rules.py, demo/scenarios.py), which
 * differ from BUILD_SPEC section 8 in a few places.
 */
import { describe, expect, it } from 'vitest';
import { parseApproverRoute } from '../src/approver/pwa';
import { scenarioAttack, scenarioLabel, scenarioPrompt } from '../src/dashboard/pages/Demo';
import { ApiClient, TOKEN_KEY } from '../src/shared/api/client';
import type { DemoScenario, Reason } from '../src/shared/api/types';
import { extractProvenance } from '../src/shared/lib/provenance';
import { BUILTIN_SAMPLES, MAX_SAMPLES, parseSampleFile } from '../src/shared/lib/samples';
import { memoryStore } from '../src/shared/lib/storage';
import { fakeFetch, json } from './helpers';

const client = (routes: Parameters<typeof fakeFetch>[0]) => {
  const fake = fakeFetch(routes);
  return { api: new ApiClient({ fetchImpl: fake.fetch, storage: memoryStore({ [TOKEN_KEY]: 'jwt' }) }), calls: fake.calls };
};

describe('demo endpoints', () => {
  it('chat sends only the fields the strict server model accepts', async () => {
    const { api, calls } = client({
      'POST /api/demo/chat': () =>
        json({ reply: 'ok', session_id: 'demo-1', protected: false, stopped_reason: 'max_steps', steps: [], attacker_inbox: [] }),
    });
    const res = await api.demoChat({ message: 'hi', protected: false, lang: 'ar' });
    expect(Object.keys(calls[0].body as object).sort()).toEqual(['lang', 'message', 'protected']);
    expect(res).toMatchObject({ session_id: 'demo-1', protected: false, stopped_reason: 'max_steps' });
    await api.demoChat({ message: 'again', protected: true, session_id: 'demo-1' });
    expect(calls[1].body).toEqual({ message: 'again', protected: true, session_id: 'demo-1' });
  });

  it('applies a scenario through POST /api/demo/scenarios/{id}/apply', async () => {
    const { api, calls } = client({
      'POST /api/demo/scenarios/s%201/apply': () => json({ scenario: { id: 's 1' }, state: { world: {}, attacker_inbox: [] } }),
    });
    const res = await api.applyDemoScenario('s 1');
    expect(calls[0].method).toBe('POST');
    expect(res.scenario.id).toBe('s 1');
  });

  it('reads scenario titles, prompts and attack descriptions in the UI language', () => {
    const s: DemoScenario = {
      id: 'x',
      title_en: 'Summarise',
      title_ar: 'تلخيص',
      user_prompt_en: 'Read E001',
      user_prompt_ar: '',
      expected_attack: { tool: 'send_email', description_en: 'Sends data out', description_ar: 'يرسل البيانات' },
    };
    expect(scenarioLabel(s, 'ar')).toBe('تلخيص');
    expect(scenarioPrompt(s, 'ar')).toBe('Read E001'); // falls back to English
    expect(scenarioAttack(s, 'en')).toBe('Sends data out');
    expect(scenarioLabel({ id: 'only-id' }, 'en')).toBe('only-id');
  });
});

describe('users, policies and push', () => {
  it('createUser omits the password to get a generated one, and accepts the legacy bare record', async () => {
    const user = { username: 'noura', role: 'approver', display_name: '', lang: 'ar', created_at: 1, disabled: false };
    let legacy = false;
    const { api, calls } = client({
      'POST /api/users': () => (legacy ? json(user, 201) : json({ user, generated_password: 'GENERATED-PLACEHOLDER' }, 201)),
    });
    const res = await api.createUser({ username: 'noura', role: 'approver', lang: 'ar' });
    expect(calls[0].body).toEqual({ username: 'noura', role: 'approver', lang: 'ar' });
    expect(res.generated_password).toBe('GENERATED-PLACEHOLDER');
    legacy = true;
    const old = await api.createUser({ username: 'noura', role: 'approver', password: 'long-enough-1' });
    expect(old).toEqual({ user, generated_password: null });
    expect((calls[1].body as Record<string, unknown>).password).toBe('long-enough-1');
  });

  it('rolls back a policy version with POST /api/policies/{version}/activate', async () => {
    const { api, calls } = client({
      'POST /api/policies/abc123/activate': () => json({ version: 'abc123', yaml_text: 'version: 1', active: true, mode: 'monitor', previous_version: 'def' }),
    });
    const res = await api.rollbackPolicy('abc123');
    expect(calls[0].method).toBe('POST');
    expect(res.mode).toBe('monitor');
  });

  it('treats a VAPID key without a private key (enabled=false) as "push unavailable"', async () => {
    let enabled = false;
    const { api, calls } = client({
      'GET /api/push/vapid': () => json({ public_key: enabled ? 'BPub' : '', enabled }),
      'POST /api/push/unsubscribe': () => json(null, 204),
    });
    expect(await api.vapidKey()).toBeNull();
    enabled = true;
    expect(await api.vapidKey()).toBe('BPub');
    await api.pushUnsubscribe('https://push.example/abc');
    expect(calls[2].body).toEqual({ endpoint: 'https://push.example/abc' });
  });
});

describe('taint provenance (real evidence shapes from taint/rules.py)', () => {
  const reason = (code: string, evidence: Record<string, unknown>): Reason => ({
    layer: 'taint',
    code,
    message: 'm',
    action: 'require_approval',
    risk_score: 0.9,
    evidence,
  });

  it('reads source_trust / source_sensitivity and de-duplicates the first match', () => {
    const match = {
      param: 'to',
      destination: 'partner@sample.example',
      match: 'exact',
      domain: 'sample.example',
      kind: 'email',
      value: 'partner@sample.example',
      source_tool: 'read_email',
      source_call_id: 'call_3',
      field: 'body',
      source_trust: 'untrusted',
      source_sensitivity: 'internal',
    };
    const items = extractProvenance([
      reason('TAINT_UNTRUSTED_DESTINATION', { tool: 'send_email', sink: 'external', ...match, matches: [match], match_count: 1 }),
    ]);
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      param: 'to',
      value: 'partner@sample.example',
      sourceTool: 'read_email',
      sourceCallId: 'call_3',
      field: 'body',
      trust: 'untrusted',
      sensitivity: 'internal',
    });
  });

  it('lists the session-level sources of TAINT_UNTRUSTED_TO_EXTERNAL', () => {
    const items = extractProvenance([
      reason('TAINT_UNTRUSTED_TO_EXTERNAL', {
        tool: 'fetch_url',
        sink: 'external',
        source_tool: 'read_email',
        source_call_id: 'call_2',
        field: null,
        sources: [
          { tool: 'read_email', call_id: 'call_2' },
          { tool: 'fetch_url', call_id: 'call_1' },
        ],
        source_count: 2,
      }),
    ]);
    expect(items.map((i) => `${i.sourceTool}:${i.sourceCallId}`)).toEqual(['read_email:call_2', 'fetch_url:call_1']);
  });
});

describe('approver routes', () => {
  it('accepts the PWA link and the link the server puts in Web Push payloads', () => {
    expect(parseApproverRoute('/a/ap_1')).toEqual({ view: 'detail', id: 'ap_1' });
    expect(parseApproverRoute('/approvals/ap%2F2')).toEqual({ view: 'detail', id: 'ap/2' });
    expect(parseApproverRoute('/history')).toEqual({ view: 'history' });
    expect(parseApproverRoute('/')).toEqual({ view: 'pending' });
    expect(parseApproverRoute('/a/%E0%A4%A')).toEqual({ view: 'pending' }); // malformed escape
  });
});

describe('playground samples', () => {
  it('ships neutral built-in samples in English, Arabic and mixed text', () => {
    expect(BUILTIN_SAMPLES.map((s) => s.lang).sort()).toEqual(['ar', 'en', 'mixed']);
    for (const s of BUILTIN_SAMPLES) expect(s.label_en && s.label_ar && s.text).toBeTruthy();
  });

  it('parses the team file defensively', () => {
    expect(parseSampleFile({ samples: [] })).toEqual([]);
    expect(parseSampleFile('nonsense')).toEqual([]);
    const parsed = parseSampleFile({
      samples: [
        { id: 'a', label_en: 'First', label_ar: 'الأول', lang: 'ar', text: 'SAMPLE-FLAGGED-TEXT' },
        { label: 'No lang', text: 'text' },
        { label_en: 'Empty', text: '   ' },
        42,
      ],
    });
    expect(parsed).toEqual([
      { id: 'a', label_en: 'First', label_ar: 'الأول', lang: 'ar', text: 'SAMPLE-FLAGGED-TEXT' },
      { id: 'team-2', label_en: 'No lang', label_ar: 'No lang', lang: 'en', text: 'text' },
    ]);
    const many = Array.from({ length: MAX_SAMPLES + 5 }, (_, i) => ({ text: `t${i}` }));
    expect(parseSampleFile(many)).toHaveLength(MAX_SAMPLES);
  });

  it('loads the optional file and falls back to [] when it is missing or broken', async () => {
    let mode: 'ok' | 'missing' | 'broken' = 'ok';
    const { api } = client({
      'GET /assets/playground-samples.json': () =>
        mode === 'ok'
          ? json({ samples: [{ label_en: 'Team', text: 'SAMPLE-FLAGGED-TEXT' }] })
          : mode === 'missing'
            ? json({ detail: 'Not found' }, 404)
            : new Response('{not json', { status: 200 }),
    });
    expect((await api.playgroundSamples()).map((s) => s.label_en)).toEqual(['Team']);
    mode = 'missing';
    expect(await api.playgroundSamples()).toEqual([]);
    mode = 'broken';
    expect(await api.playgroundSamples()).toEqual([]);
  });
});
