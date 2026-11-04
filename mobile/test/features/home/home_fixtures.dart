import 'package:mirsad/features/home/domain/entities/overview_stats.dart';
import 'package:mirsad/features/home/domain/entities/tool_activity.dart';

/// `GET /api/stats/overview?hours=24`, shaped like the gateway's `Overview`.
Map<String, dynamic> overviewJson({bool? auditOk = true}) {
  return {
    'hours': 24.0,
    'total_calls': 14,
    'allowed': 10,
    'denied': 3,
    'approvals_required': 1,
    'approvals_pending': 1,
    'injections_detected': 2,
    'results_sanitized': 1,
    'results_blocked': 1,
    'results_inspected': 6,
    'median_latency_ms': 0.225,
    'p95_latency_ms': 0.229,
    'audit_ok': auditOk,
    'audit_head_seq': 41,
    'by_tool': [
      {'tool': 'send_email', 'allowed': 1, 'denied': 1, 'approval': 0},
      {'tool': 'transfer_funds', 'allowed': 2, 'denied': 2, 'approval': 1},
      {'tool': 'get_account_balance', 'allowed': 7, 'denied': 0, 'approval': 0},
    ],
    'by_layer': [
      {'layer': 'policy', 'count': 2},
    ],
  };
}

const overviewStats = OverviewStats(
  windowHours: 24,
  totalCalls: 14,
  allowed: 10,
  denied: 3,
  heldForReview: 1,
  waitingNow: 1,
  injectionsDetected: 2,
  auditOk: true,
  medianLatencyMs: 0.225,
  p95LatencyMs: 0.229,
  tools: [
    ToolActivity(tool: 'send_email', allowed: 1, denied: 1, held: 0),
    ToolActivity(tool: 'transfer_funds', allowed: 2, denied: 2, held: 1),
    ToolActivity(tool: 'get_account_balance', allowed: 7, denied: 0, held: 0),
  ],
);
