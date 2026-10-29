/**
 * TypeScript mirror of `src/mirsad/models.py` plus the REST response shapes actually
 * implemented in `src/mirsad/api/routers/*.py` (a superset of BUILD_SPEC section 8).
 * Timestamps from the backend are epoch *seconds* (floats).
 */

export type Action = 'allow' | 'require_approval' | 'deny';
export type Trust = 'trusted' | 'untrusted';
export type Sensitivity = 'public' | 'internal' | 'confidential';
export type SinkKind = 'none' | 'internal' | 'external';
export type Risk = 'low' | 'medium' | 'high' | 'critical';
export type Layer = 'policy' | 'ratelimit' | 'taint' | 'detector' | 'approval' | 'system';
export type InspectionAction = 'pass' | 'flag' | 'sanitize' | 'block';
export type DetectionLabel = 'benign' | 'suspicious' | 'injection';
export type DetectedLanguage = 'en' | 'ar' | 'mixed' | 'other';
export type ApprovalStatus = 'pending' | 'approved' | 'denied' | 'expired' | 'cancelled';
export type Role = 'admin' | 'approver' | 'auditor';
export type Lang = 'en' | 'ar';

export const ACTIONS: readonly Action[] = ['allow', 'require_approval', 'deny'];
export const RISKS: readonly Risk[] = ['low', 'medium', 'high', 'critical'];
export const LAYERS: readonly Layer[] = ['policy', 'ratelimit', 'taint', 'detector', 'approval', 'system'];
export const ROLES: readonly Role[] = ['admin', 'approver', 'auditor'];
export const APPROVAL_STATUSES: readonly ApprovalStatus[] = ['pending', 'approved', 'denied', 'expired', 'cancelled'];

export interface ToolCall {
  call_id: string;
  session_id: string;
  agent_id: string;
  tool: string;
  arguments: Record<string, unknown>;
  ts: number;
}

export interface ToolResult {
  call_id: string;
  session_id: string;
  agent_id: string;
  tool: string;
  content: string;
  structured?: unknown;
  is_error?: boolean;
}

export interface Reason {
  layer: Layer;
  code: string;
  message: string;
  message_ar?: string | null;
  action: Action;
  rule_id?: string | null;
  risk_score: number;
  evidence: Record<string, unknown>;
}

export interface Decision {
  call_id: string;
  action: Action;
  reasons: Reason[];
  risk: Risk;
  risk_score: number;
  sink: SinkKind;
  policy_version: string;
  approval_id?: string | null;
  approval_status?: string | null;
  latency_ms: number;
  audit_seq?: number | null;
}

export interface DetectionSpan {
  start: number;
  end: number;
  text: string;
  rule_id?: string | null;
  score: number;
}

export interface DetectionResult {
  score: number;
  label: DetectionLabel;
  language: DetectedLanguage;
  spans: DetectionSpan[];
  signals: string[];
  model_score: number;
  rule_score: number;
  layer_scores?: Record<string, number>;
  layer_reasons?: Record<string, string>;
  latency_ms: number;
}

export interface InspectionOutcome {
  call_id: string;
  action: InspectionAction;
  content: string;
  structured?: unknown;
  trust: Trust;
  sensitivity: Sensitivity;
  detection?: DetectionResult | null;
  reasons: Reason[];
  latency_ms: number;
  audit_seq?: number | null;
}

export interface GatewayResponse {
  decision: Decision;
  result?: InspectionOutcome | null;
  error?: string | null;
}

export interface ToolProfile {
  tool: string;
  allowed: boolean;
  trust: Trust;
  sensitivity: Sensitivity;
  sink: 'none' | 'internal' | 'external' | 'dynamic';
  sink_params: string[];
  risk: Risk;
  approval: 'never' | 'on_risk' | 'always';
  scan: boolean;
  matched_rule?: string | null;
}

export interface TaintedValue {
  value: string;
  kind: 'email' | 'url' | 'domain' | 'iban' | 'phone' | 'number' | 'id' | 'ngram';
  field?: string | null;
  source_tool: string;
  source_call_id: string;
  trust: Trust;
  sensitivity: Sensitivity;
  trusted_field: boolean;
}

export interface SessionSnapshot {
  session_id: string;
  agent_id: string;
  untrusted_sources: string[];
  max_sensitivity: Sensitivity;
  injection_detected: boolean;
  values: TaintedValue[];
  call_count: number;
}

export interface AuditEvent {
  seq: number;
  ts: number;
  event_type: string;
  session_id?: string | null;
  agent_id?: string | null;
  tool?: string | null;
  call_id?: string | null;
  action?: string | null;
  risk?: string | null;
  policy_version?: string | null;
  payload: Record<string, unknown>;
  prev_hash: string;
  hash: string;
}

export interface ApprovalRecord {
  id: string;
  created_at: number;
  expires_at: number;
  status: ApprovalStatus;
  agent_id: string;
  session_id: string;
  call_id: string;
  tool: string;
  arguments: Record<string, unknown>;
  decision: Decision;
  summary_en: string;
  summary_ar: string;
  risk: Risk;
  decided_by?: string | null;
  decided_at?: number | null;
  note?: string | null;
}

// ------------------------------------------------------------------ REST shapes (section 8)

export interface User {
  username: string;
  role: Role;
  display_name: string;
  lang: Lang | string;
  created_at?: number | string | null;
  disabled?: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: 'bearer';
  /** Token lifetime in seconds. */
  expires_in?: number;
  user: User;
}

export interface Health {
  status: string;
  version?: string;
}

export interface AuditEventPage {
  items: AuditEvent[];
  total: number;
}

export interface AuditFilters {
  agent_id?: string;
  tool?: string;
  action?: string;
  event_type?: string;
  session_id?: string;
  call_id?: string;
  since?: number;
  until?: number;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface AuditVerifyReport {
  ok: boolean;
  checked: number;
  head_seq: number;
  head_hash: string;
  first_bad_seq?: number | null;
  message: string;
}

export interface ReplayReport {
  seq: number;
  event_type: string;
  original_action: string | null;
  replayed_action: string | null;
  match: boolean;
  details: Record<string, unknown> | string | null;
}

export interface ToolStats {
  tool: string;
  allowed: number;
  denied: number;
  approval: number;
}

export interface LayerStats {
  layer: Layer | string;
  count: number;
}

export interface StatsOverview {
  hours?: number;
  total_calls: number;
  allowed: number;
  denied: number;
  approvals_required: number;
  approvals_pending: number;
  injections_detected: number;
  results_sanitized: number;
  /** Not in BUILD_SPEC; returned by the stats router. */
  results_blocked?: number;
  results_inspected?: number;
  median_latency_ms: number | null;
  p95_latency_ms: number | null;
  audit_ok: boolean | null;
  audit_head_seq?: number | null;
  by_tool: ToolStats[];
  by_layer: LayerStats[];
}

export interface TimeseriesPoint {
  t: number | string;
  allowed: number;
  denied: number;
  require_approval: number;
  injections: number;
}

export interface PolicyVersion {
  version: string;
  created_at: number | string;
  created_by: string | null;
  active?: boolean;
  comment?: string | null;
}

export interface PolicyDetail extends PolicyVersion {
  yaml_text: string;
}

export interface PoliciesResponse {
  active: PolicyDetail | null;
  versions: PolicyVersion[];
}

/** `PUT /api/policies` and `POST /api/policies/{version}/activate` (rollback). */
export interface PolicyActivation extends PolicyDetail {
  previous_version?: string | null;
  mode?: 'enforce' | 'monitor' | string;
  agents?: string[];
}

export interface ValidateResponse {
  valid: boolean;
  errors: string[];
}

export interface Agent {
  id: string;
  name: string;
  description?: string | null;
  policy_agent_id: string;
  key_prefix?: string | null;
  created_at?: number | string | null;
  disabled?: boolean;
  last_seen_at?: number | string | null;
}

export interface AgentCreate {
  id: string;
  name: string;
  policy_agent_id: string;
  description?: string;
}

export interface AgentWithKey {
  agent: Agent;
  api_key: string;
  /** e.g. the policy agent id is not defined in the active policy (its calls will be denied). */
  warnings?: string[];
}

export interface UserCreate {
  username: string;
  /** Omit to let the server generate a strong password (returned once). */
  password?: string;
  role: Role;
  display_name?: string;
  lang?: Lang;
}

export interface UserCreated {
  user: User;
  /** Present only when the server generated the password; shown exactly once. */
  generated_password?: string | null;
}

export type UserPatch = Partial<Pick<User, 'role' | 'display_name' | 'lang' | 'disabled'>> & { password?: string };

/** `/api/tools` is loosely specified ("discovered upstream tools + profile per agent"); see normalizeTools(). */
export interface DiscoveredTool {
  name: string;
  description?: string;
  upstream?: string;
  input_schema?: Record<string, unknown>;
  profiles: Record<string, ToolProfile>;
}

export interface DemoStep {
  tool: string;
  arguments: Record<string, unknown>;
  decision?: Decision | null;
  result_preview?: string | null;
  inspection?: InspectionOutcome | null;
  /** True when Mirsad stopped the call (protected mode only). */
  blocked?: boolean;
}

/** `POST /api/demo/chat` body. The server model forbids extra fields. */
export interface DemoChatRequest {
  sector?: "general" | "finance" | "healthcare";
  message: string;
  session_id?: string;
  protected: boolean;
  lang?: Lang;
}

/** Something that left the organisation (see `attacker_inbox()` in api/routers/demo.py). */
export interface AttackerInboxItem {
  channel?: 'email' | 'http' | string;
  to?: string[];
  subject?: string | null;
  body_preview?: string;
  body_chars?: number;
  url?: string;
  domain?: string;
  ts?: number | null;
  [key: string]: unknown;
}

export interface DemoChatResponse {
  reply: string;
  session_id: string;
  protected?: boolean;
  /** completed | max_steps | max_rounds */
  stopped_reason?: string;
  steps: DemoStep[];
  attacker_inbox: AttackerInboxItem[];
}

/** `World.snapshot()` from demo/world.py: side effects of everything the agent did. */
export interface DemoWorld {
  counts?: Record<string, number>;
  outbox?: Record<string, unknown>[];
  http_log?: Record<string, unknown>[];
  deleted?: string[];
  exports?: Record<string, unknown>[];
  transfers?: Record<string, unknown>[];
  notes_log?: Record<string, unknown>[];
  side_effects?: Record<string, unknown>[];
}

export interface DemoState {
  world: DemoWorld;
  attacker_inbox: AttackerInboxItem[];
}

/**
 * Curated scenario from demo/scenarios.py: a benign user request plus planted content.
 * The UI only shows the titles, the user prompt and the abstract attack description;
 * it never displays the planted payload (`setup[].payload`).
 */
export interface DemoScenario {
  id: string;
  title_en?: string;
  title_ar?: string;
  user_prompt_en?: string;
  user_prompt_ar?: string;
  expected_attack?: {
    category?: string;
    tool?: string;
    description_en?: string;
    description_ar?: string;
  };
  [key: string]: unknown;
}

export interface VapidResponse {
  public_key: string | null;
  /** False when the server has no VAPID private key (push cannot be delivered). */
  enabled?: boolean;
}

/** Server-sent events published on `/api/stream`. */
export type StreamEventName = 'approval.requested' | 'approval.decided' | 'audit.event' | string;
