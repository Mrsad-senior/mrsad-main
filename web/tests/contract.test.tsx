/**
 * Contract tests on responses captured from a running Mirsad server (smoke test of
 * 2026-10-11): an approval created by the guard API after an agent read an e-mail and then
 * tried to send one outside the organisation, and the matching `tool_call.decision` audit
 * event. Content is neutral (a price-list e-mail, `.example` addresses).
 */
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { parsePayload } from '../src/dashboard/components/EventDrawer';
import type { ApprovalRecord, AuditEvent } from '../src/shared/api/types';
import { ApprovalExplanation } from '../src/shared/components/Explain';
import { I18nProvider } from '../src/shared/i18n';
import { extractProvenance, pauseReasons, snapshotSources } from '../src/shared/lib/provenance';
import approvalJson from './fixtures/approval-record.json';
import auditJson from './fixtures/audit-decision-event.json';

const record = approvalJson as unknown as ApprovalRecord;
const event = auditJson as unknown as AuditEvent;

describe('captured approval record', () => {
  it('yields the "data came from" source and the reasons that paused the call', () => {
    const items = extractProvenance(record.decision.reasons);
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ code: 'TAINT_UNTRUSTED_TO_EXTERNAL', sourceTool: 'read_email', sourceCallId: 'call_r1' });
    // The informational TOOL_RISK (allow, 0.3) is not a reason for the pause.
    expect(pauseReasons(record.decision.reasons).map((r) => r.code).sort()).toEqual(['CONSTRAINT_VIOLATION', 'TAINT_UNTRUSTED_TO_EXTERNAL']);
  });

  it('renders the bilingual explanation the approver reads', () => {
    const { unmount } = render(
      <I18nProvider initial="en">
        <ApprovalExplanation record={record} />
      </I18nProvider>,
    );
    expect(screen.getByText(/wants to send an email to buyer@other.example/)).toBeTruthy();
    const from = screen.getByRole('heading', { name: /Where the data came from/ }).closest('section') as HTMLElement;
    expect(within(from).getByText('read_email')).toBeTruthy();
    expect(within(from).getByText('call_r1')).toBeTruthy();
    unmount();

    render(
      <I18nProvider initial="ar">
        <ApprovalExplanation record={record} />
      </I18nProvider>,
    );
    expect(screen.getByText(record.summary_ar)).toBeTruthy();
    expect(screen.getByRole('heading', { name: /لماذا أوقفه مرصاد/ })).toBeTruthy();
  });
});

describe('captured tool_call.decision audit event', () => {
  it('is parsed into reasons, arguments, sink, risk score and session taint state', () => {
    const parsed = parsePayload(event);
    expect(parsed.reasons.map((r) => r.code)).toEqual(['TOOL_RISK', 'CONSTRAINT_VIOLATION', 'TAINT_UNTRUSTED_TO_EXTERNAL']);
    expect(parsed.args).toMatchObject({ to: 'buyer@other.example' });
    expect(parsed.sink).toBe('external');
    expect(parsed.riskScore).toBeGreaterThan(0.5);
    expect(parsed.enforced).toBeUndefined(); // enforced=true: no "monitor mode" tag
    expect(snapshotSources(parsed.snapshot)).toEqual([{ code: 'SESSION_UNTRUSTED', sourceTool: 'read_email', sourceCallId: 'call_r1' }]);
  });
});
