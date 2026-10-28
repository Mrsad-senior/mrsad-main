/** Pure helpers for keeping approval lists in sync with live events. */
import type { ApprovalRecord } from '../api/types';

export function isApprovalRecord(value: unknown): value is ApprovalRecord {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as ApprovalRecord).id === 'string' &&
    typeof (value as ApprovalRecord).tool === 'string' &&
    typeof (value as ApprovalRecord).status === 'string'
  );
}

/** Insert or replace by id; pending items sorted by soonest expiry, others newest first. */
export function upsertApproval(list: readonly ApprovalRecord[], record: ApprovalRecord): ApprovalRecord[] {
  const next = list.filter((item) => item.id !== record.id);
  next.push(record);
  return sortApprovals(next);
}

export function sortApprovals(list: readonly ApprovalRecord[]): ApprovalRecord[] {
  return [...list].sort((a, b) => {
    if (a.status === 'pending' && b.status === 'pending') return a.expires_at - b.expires_at;
    if (a.status === 'pending') return -1;
    if (b.status === 'pending') return 1;
    return (b.decided_at ?? b.created_at) - (a.decided_at ?? a.created_at);
  });
}

/** Applies a stream event (`approval.requested` / `approval.decided`) to a cached list. */
export function applyApprovalEvent(list: readonly ApprovalRecord[], event: string, data: unknown): ApprovalRecord[] {
  if (!isApprovalRecord(data)) return [...list];
  if (event === 'approval.requested' || event === 'approval.decided') return upsertApproval(list, data);
  return [...list];
}
