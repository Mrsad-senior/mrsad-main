/**
 * Component flows rendered against a fake backend whose responses mirror the implemented
 * routers. Text content is neutral (placeholder addresses on the reserved .example TLD).
 */
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { ApproverApp } from '../src/approver/App';
import Demo from '../src/dashboard/pages/Demo';
import Policies from '../src/dashboard/pages/Policies';
import Users from '../src/dashboard/pages/Users';
import { ApiClient, TOKEN_KEY } from '../src/shared/api/client';
import type { ApprovalRecord } from '../src/shared/api/types';
import { ApiProvider, AuthProvider } from '../src/shared/app/auth';
import { LiveProvider } from '../src/shared/app/live';
import { ThemeProvider } from '../src/shared/app/theme';
import { ToastProvider } from '../src/shared/app/toast';
import { I18nProvider } from '../src/shared/i18n';
import { memoryStore } from '../src/shared/lib/storage';
import { fakeFetch, json } from './helpers';

const ADMIN = { username: 'admin', role: 'admin', display_name: 'Admin', lang: 'en' };
const APPROVER = { username: 'noura', role: 'approver', display_name: 'Noura', lang: 'en' };

function makeClient(routes: Parameters<typeof fakeFetch>[0], user: Record<string, unknown> = ADMIN) {
  const fake = fakeFetch({ 'GET /api/auth/me': () => json(user), ...routes });
  return { client: new ApiClient({ fetchImpl: fake.fetch, storage: memoryStore({ [TOKEN_KEY]: 'jwt' }) }), calls: fake.calls };
}

function Providers({ client, children }: { client: ApiClient; children: ReactNode }) {
  return (
    <ApiProvider client={client}>
      <I18nProvider initial="en">
        <ThemeProvider>
          <ToastProvider>
            <AuthProvider>
              <LiveProvider>{children}</LiveProvider>
            </AuthProvider>
          </ToastProvider>
        </ThemeProvider>
      </I18nProvider>
    </ApiProvider>
  );
}

function pendingRecord(): ApprovalRecord {
  const now = Date.now() / 1000;
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
  return {
    id: 'ap_1',
    created_at: now - 5,
    expires_at: now + 115,
    status: 'pending',
    agent_id: 'email-crm-assistant',
    session_id: 's1',
    call_id: 'call_9',
    tool: 'send_email',
    arguments: { to: 'partner@sample.example', subject: 'Price list', body: 'Hello' },
    decision: {
      call_id: 'call_9',
      action: 'require_approval',
      reasons: [
        {
          layer: 'taint',
          code: 'TAINT_UNTRUSTED_DESTINATION',
          message: 'The recipient address was taken from the body of an e-mail.',
          message_ar: 'عنوان المستلم مأخوذ من نص رسالة بريد.',
          action: 'require_approval',
          rule_id: 'taint.untrusted_controls_destination',
          risk_score: 0.9,
          evidence: { tool: 'send_email', sink: 'external', ...match, matches: [match], match_count: 1 },
        },
      ],
      risk: 'critical',
      risk_score: 0.9,
      sink: 'external',
      policy_version: 'v1',
      approval_id: 'ap_1',
      approval_status: 'pending',
      latency_ms: 2,
      audit_seq: 5,
    },
    summary_en: 'Email & CRM Assistant wants to send an e-mail to partner@sample.example.',
    summary_ar: 'يريد المساعد إرسال بريد إلى partner@sample.example.',
    risk: 'critical',
    decided_by: null,
    decided_at: null,
    note: null,
  };
}

afterEach(() => {
  window.location.hash = '';
});

describe('approver PWA', () => {
  function approverBackend() {
    const record = pendingRecord();
    return makeClient(
      {
        'GET /api/approvals': (req) => json(req.url.includes('status=pending') ? [record] : [record]),
        'GET /api/approvals/ap_1': () => json(record),
        'POST /api/approvals/ap_1/decision': (req) =>
          json({ ...record, status: 'approved', decided_by: 'noura', decided_at: Date.now() / 1000, note: (req.body as { note?: string }).note ?? null }),
      },
      APPROVER,
    );
  }

  it('lists the pending request, explains it and approves it after confirmation', async () => {
    const { client, calls } = approverBackend();
    render(<ApproverApp client={client} />);

    const card = await screen.findByRole('button', { name: /send_email/ });
    expect(card.textContent).toContain('partner@sample.example');
    fireEvent.click(card);

    const article = await screen.findByRole('article');
    // Plain-language summary, why it was paused, and where the data came from.
    expect(within(article).getByText(/wants to send an e-mail/)).toBeTruthy();
    expect(within(article).getByText(/taken from the body of an e-mail/)).toBeTruthy();
    expect(within(article).getByText('read_email')).toBeTruthy();
    expect(within(article).getAllByText(/Untrusted/).length).toBeGreaterThan(0);

    fireEvent.click(within(article).getByRole('button', { name: 'Approve' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Approve this action?')).toBeTruthy();
    expect(calls.some((c) => c.method === 'POST')).toBe(false); // nothing sent before confirming
    fireEvent.change(within(dialog).getByRole('textbox'), { target: { value: '  expected partner  ' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Approve' }));

    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/api/approvals/ap_1/decision'))).toBe(true));
    const post = calls.find((c) => c.method === 'POST');
    expect(post?.body).toEqual({ approve: true, note: 'expected partner' });
  });

  it('renders right-to-left in Arabic with the Arabic summary and reason', async () => {
    window.localStorage.setItem('mirsad.lang', 'ar');
    window.location.hash = '#/a/ap_1';
    const { client } = approverBackend();
    render(<ApproverApp client={client} />);
    const article = await screen.findByRole('article');
    expect(document.documentElement.dir).toBe('rtl');
    expect(document.documentElement.lang).toBe('ar');
    expect(within(article).getByText('لماذا أوقفه مرصاد')).toBeTruthy();
    expect(within(article).getByText(/يريد المساعد إرسال بريد/)).toBeTruthy();
    expect(within(article).getByText('عنوان المستلم مأخوذ من نص رسالة بريد.')).toBeTruthy();
    expect(within(article).getByRole('button', { name: 'موافقة' })).toBeTruthy();
  });

  it('opens the detail directly from a Web Push deep link (#/approvals/<id>)', async () => {
    window.location.hash = '#/approvals/ap_1';
    const { client } = approverBackend();
    render(<ApproverApp client={client} />);
    const article = await screen.findByRole('article');
    expect(within(article).getByRole('heading', { level: 1 }).textContent).toBe('send_email');
    expect(within(article).getByRole('button', { name: 'Deny' })).toBeTruthy();
  });
});

describe('demo console', () => {
  const scenario = {
    id: 'sample-scenario',
    title_en: 'Summarise the sample e-mail',
    title_ar: 'تلخيص الرسالة التجريبية',
    user_prompt_en: 'Read e-mail E001 and summarise it.',
    user_prompt_ar: 'اقرأ الرسالة E001 ولخّصها.',
    setup: [{ vector: 'email', target_id: 'E001', payload: 'SAMPLE-FLAGGED-TEXT', position: 'end' }],
    expected_attack: { category: 'exfiltration', tool: 'send_email', description_en: 'Sends customer data to an outside address.', description_ar: 'يرسل بيانات العملاء إلى عنوان خارجي.' },
  };
  const emptyWorld = { counts: { emails: 12 }, outbox: [], http_log: [], deleted: [], exports: [], transfers: [], notes_log: [], side_effects: [] };

  it('loads a scenario via the apply endpoint, never shows the planted content and chats without extra fields', async () => {
    const { client, calls } = makeClient({
      'GET /api/demo/scenarios': () => json([scenario]),
      'GET /api/demo/state': () => json({ world: emptyWorld, attacker_inbox: [] }),
      'POST /api/demo/scenarios/sample-scenario/apply': () => json({ scenario, state: { world: emptyWorld, attacker_inbox: [] } }),
      'POST /api/demo/chat': () =>
        json({
          reply: 'Summary sent.',
          session_id: 'demo-1',
          protected: false,
          stopped_reason: 'completed',
          steps: [{ tool: 'read_email', arguments: { email_id: 'E001' }, decision: null, result_preview: 'Invoice', inspection: null, blocked: false }],
          attacker_inbox: [{ channel: 'email', to: ['collector@sample.example'], subject: 'Data', body_preview: 'rows', body_chars: 4, ts: 1 }],
        }),
    });
    render(
      <Providers client={client}>
        <Demo />
      </Providers>,
    );

    const select = await screen.findByLabelText('Attack scenario');
    await screen.findByRole('option', { name: 'Summarise the sample e-mail' });
    fireEvent.change(select, { target: { value: 'sample-scenario' } });
    fireEvent.click(screen.getByRole('button', { name: 'Load scenario' }));

    const input = (await screen.findByDisplayValue('Read e-mail E001 and summarise it.')) as HTMLTextAreaElement;
    expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/apply'))).toBe(true);
    expect(screen.getByText('Sends customer data to an outside address.')).toBeTruthy();
    expect(screen.queryByText(/SAMPLE-FLAGGED-TEXT/)).toBeNull();

    fireEvent.click(screen.getByRole('checkbox')); // protection off
    fireEvent.submit(input.closest('form') as HTMLFormElement);

    expect(await screen.findByText('Summary sent.')).toBeTruthy();
    const chat = calls.find((c) => c.url.endsWith('/api/demo/chat'));
    expect(chat?.body).toEqual({ message: 'Read e-mail E001 and summarise it.', protected: false, lang: 'en' });
    expect(await screen.findByText('collector@sample.example')).toBeTruthy();
    expect(screen.getByText('1 leaked')).toBeTruthy();
  });

  it('explains how to enable the demo when the endpoints are not mounted', async () => {
    const { client } = makeClient({});
    render(
      <Providers client={client}>
        <Demo />
      </Providers>,
    );
    expect(await screen.findByText('Demo mode is not enabled on this server.')).toBeTruthy();
  });
});

describe('users page', () => {
  it('creates a user with a server-generated password and shows it once', async () => {
    const created = { username: 'noura.a', role: 'approver', display_name: '', lang: 'en', created_at: 2, disabled: false };
    const { client, calls } = makeClient({
      'GET /api/users': () => json([{ ...ADMIN, created_at: 1, disabled: false }]),
      'POST /api/users': () => json({ user: created, generated_password: 'GENERATED-PLACEHOLDER' }, 201),
    });
    render(
      <Providers client={client}>
        <Users />
      </Providers>,
    );
    fireEvent.click(await screen.findByRole('button', { name: 'New user' }));
    const dialog = await screen.findByRole('dialog');
    const create = within(dialog).getByRole('button', { name: 'Create' }) as HTMLButtonElement;
    fireEvent.change(within(dialog).getByLabelText('Username'), { target: { value: '_bad' } });
    expect(create.disabled).toBe(true); // same rule as the server: must start with a letter or digit
    fireEvent.change(within(dialog).getByLabelText('Username'), { target: { value: 'noura.a' } });
    expect(create.disabled).toBe(false);
    fireEvent.click(create);

    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true));
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ username: 'noura.a', role: 'approver', lang: 'en' });
    const reveal = await screen.findByRole('dialog', { name: /Password for noura.a/ });
    expect(within(reveal).getByText('GENERATED-PLACEHOLDER')).toBeTruthy();
    const done = within(reveal).getByRole('button', { name: 'Done' }) as HTMLButtonElement;
    expect(done.disabled).toBe(true);
    fireEvent.click(within(reveal).getByRole('checkbox'));
    expect(done.disabled).toBe(false);
  });

  it('requires 10+ characters when the admin types the password', async () => {
    const { client } = makeClient({ 'GET /api/users': () => json([]) });
    render(
      <Providers client={client}>
        <Users />
      </Providers>,
    );
    fireEvent.click(await screen.findByRole('button', { name: 'New user' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('Username'), { target: { value: 'noura' } });
    fireEvent.click(within(dialog).getByRole('checkbox'));
    const create = within(dialog).getByRole('button', { name: 'Create' }) as HTMLButtonElement;
    fireEvent.change(within(dialog).getByLabelText('Initial password'), { target: { value: '123456789' } });
    expect(create.disabled).toBe(true);
    fireEvent.change(within(dialog).getByLabelText('Initial password'), { target: { value: '1234567890' } });
    expect(create.disabled).toBe(false);
  });
});

describe('policies page', () => {
  it('rolls back to an older version after confirmation', async () => {
    const v2 = { version: 'b'.repeat(64), yaml_text: 'version: 1\n', created_at: 2, created_by: 'admin', active: true, comment: null };
    const v1 = { version: 'a'.repeat(64), created_at: 1, created_by: 'admin', active: false, comment: 'first' };
    const { client, calls } = makeClient({
      'GET /api/policies': () => json({ active: v2, versions: [{ ...v2, yaml_text: undefined }, v1] }),
      [`POST /api/policies/${v1.version}/activate`]: () => json({ ...v1, yaml_text: 'version: 1\n', active: true, mode: 'enforce' }),
    });
    render(
      <Providers client={client}>
        <Policies />
      </Providers>,
    );
    const buttons = await screen.findAllByRole('button', { name: 'Activate this version' });
    expect(buttons).toHaveLength(1); // not offered for the active version
    fireEvent.click(buttons[0]);
    const dialog = await screen.findByRole('dialog', { name: 'Roll back to this version?' });
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Activate this version' }));
    });
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.endsWith(`/api/policies/${v1.version}/activate`))).toBe(true));
  });
});
