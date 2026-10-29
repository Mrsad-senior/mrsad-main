/**
 * Typed client for the Mirsad REST API (BUILD_SPEC section 8).
 *
 * The JWT lives in memory and is mirrored to sessionStorage so a reload keeps the
 * session but closing the tab ends it (no long-lived token on disk). Any 401 on an
 * authenticated request clears the token and notifies `onUnauthorized` listeners,
 * which the auth provider turns into a logout.
 */
import { type PlaygroundSample, parseSampleFile, SAMPLES_URL } from '../lib/samples';
import { type KeyValueStore, sessionStore } from '../lib/storage';
import type {
  Agent,
  AgentCreate,
  AgentWithKey,
  ApprovalRecord,
  ApprovalStatus,
  AuditEvent,
  AuditEventPage,
  AuditFilters,
  AuditVerifyReport,
  DemoChatRequest,
  DemoChatResponse,
  DemoScenario,
  DemoState,
  DetectionResult,
  DiscoveredTool,
  Health,
  LoginResponse,
  PoliciesResponse,
  PolicyActivation,
  PolicyDetail,
  ReplayReport,
  StatsOverview,
  TimeseriesPoint,
  ToolProfile,
  User,
  UserCreate,
  UserCreated,
  UserPatch,
  ValidateResponse,
  VapidResponse,
} from './types';

export const TOKEN_KEY = 'mirsad.token';

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail || `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }

  /** True when the request never reached the server (offline, DNS, CORS, aborted). */
  get isNetwork(): boolean {
    return this.status === 0;
  }
}

export type QueryValue = string | number | boolean | null | undefined;

export interface RequestOptions {
  body?: unknown;
  query?: Record<string, QueryValue>;
  signal?: AbortSignal;
  /** How to read the response body. Defaults to JSON (or undefined for 204). */
  expect?: 'json' | 'text' | 'blob';
  /** Login must not trigger the global 401 -> logout behaviour. */
  skipAuthHandling?: boolean;
}

export interface ApiClientOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  storage?: KeyValueStore;
}

export interface Download {
  blob: Blob;
  filename: string;
}

/** Builds `?a=1&b=x` skipping empty values; keys keep insertion order. */
export function buildQuery(query?: Record<string, QueryValue>): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue;
    params.append(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : '';
}

/** FastAPI errors: `{"detail": "..."}` or validation errors `{"detail": [{loc, msg}, ...]}`. */
export function formatDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (d && typeof d === 'object' && 'msg' in d) {
          const loc = Array.isArray((d as { loc?: unknown }).loc)
            ? ((d as { loc: unknown[] }).loc.filter((p) => p !== 'body').join('.'))
            : '';
          return loc ? `${loc}: ${String((d as { msg: unknown }).msg)}` : String((d as { msg: unknown }).msg);
        }
        return typeof d === 'string' ? d : JSON.stringify(d);
      })
      .join('; ');
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail);
  return '';
}

export function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const star = /filename\*\s*=\s*(?:UTF-8'')?([^;]+)/i.exec(header);
  if (star) {
    try {
      return decodeURIComponent(star[1].trim().replace(/^"|"$/g, ''));
    } catch {
      /* fall through */
    }
  }
  const plain = /filename\s*=\s*"?([^";]+)"?/i.exec(header);
  return plain ? plain[1].trim() : fallback;
}

function asArray<T>(raw: unknown, ...keys: string[]): T[] {
  if (Array.isArray(raw)) return raw as T[];
  if (raw && typeof raw === 'object') {
    for (const key of keys) {
      const value = (raw as Record<string, unknown>)[key];
      if (Array.isArray(value)) return value as T[];
    }
  }
  return [];
}

/**
 * `/api/tools` is only loosely specified, so accept: a list or `{tools: [...]}`;
 * per-agent profiles as `profiles: {agent: profile}`, `profiles: [{agent_id, profile}]`,
 * or a single `profile`.
 */
export function normalizeTools(raw: unknown): DiscoveredTool[] {
  return asArray<Record<string, unknown>>(raw, 'tools', 'items').map((item) => {
    const profiles: Record<string, ToolProfile> = {};
    const p = item.profiles ?? item.agents;
    if (Array.isArray(p)) {
      for (const entry of p as Record<string, unknown>[]) {
        const agent = String(entry.agent_id ?? entry.agent ?? entry.id ?? '');
        const profile = (entry.profile ?? entry) as ToolProfile;
        if (agent) profiles[agent] = profile;
      }
    } else if (p && typeof p === 'object') {
      Object.assign(profiles, p as Record<string, ToolProfile>);
    } else if (item.profile && typeof item.profile === 'object') {
      profiles[String(item.agent_id ?? '*')] = item.profile as ToolProfile;
    }
    return {
      name: String(item.name ?? item.tool ?? ''),
      description: typeof item.description === 'string' ? item.description : undefined,
      upstream: typeof item.upstream === 'string' ? item.upstream : undefined,
      input_schema: (item.input_schema ?? item.inputSchema) as Record<string, unknown> | undefined,
      profiles,
    };
  });
}

export class ApiClient {
  private token: string | null;
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly storage: KeyValueStore;
  private readonly unauthorizedListeners = new Set<() => void>();

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? '').replace(/\/$/, '');
    this.fetchImpl = options.fetchImpl ?? ((input, init) => fetch(input, init));
    this.storage = options.storage ?? sessionStore;
    this.token = this.storage.getItem(TOKEN_KEY);
  }

  // ---------------------------------------------------------------- token handling

  getToken(): string | null {
    return this.token;
  }

  setToken(token: string | null): void {
    this.token = token;
    if (token) this.storage.setItem(TOKEN_KEY, token);
    else this.storage.removeItem(TOKEN_KEY);
  }

  /** Register a callback for "session is no longer valid"; returns an unsubscribe function. */
  onUnauthorized(listener: () => void): () => void {
    this.unauthorizedListeners.add(listener);
    return () => this.unauthorizedListeners.delete(listener);
  }

  /** Called by the SSE reader too, so a 401 on the stream also logs the user out. */
  handleUnauthorized(): void {
    this.setToken(null);
    for (const listener of [...this.unauthorizedListeners]) listener();
  }

  url(path: string, query?: Record<string, QueryValue>): string {
    return `${this.baseUrl}${path}${buildQuery(query)}`;
  }

  get fetcher(): typeof fetch {
    return this.fetchImpl;
  }

  // ---------------------------------------------------------------- core request

  async request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
    const headers: Record<string, string> = { Accept: options.expect === 'json' || !options.expect ? 'application/json' : '*/*' };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    let body: BodyInit | undefined;
    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(options.body);
    }

    let response: Response;
    try {
      response = await this.fetchImpl(this.url(path, options.query), {
        method,
        headers,
        body,
        signal: options.signal,
        credentials: 'same-origin',
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') throw err;
      throw new ApiError(0, err instanceof Error ? err.message : 'Network error');
    }

    if (response.status === 401 && !options.skipAuthHandling) {
      this.handleUnauthorized();
    }
    if (!response.ok) {
      throw new ApiError(response.status, await readErrorDetail(response));
    }
    if (response.status === 204) return undefined as T;
    if (options.expect === 'blob') return (await response.blob()) as T;
    if (options.expect === 'text') return (await response.text()) as T;
    const text = await response.text();
    if (!text) return undefined as T;
    try {
      return JSON.parse(text) as T;
    } catch {
      throw new ApiError(response.status, 'Invalid JSON response');
    }
  }

  private get<T>(path: string, query?: Record<string, QueryValue>, signal?: AbortSignal): Promise<T> {
    return this.request<T>('GET', path, { query, signal });
  }

  // ---------------------------------------------------------------- auth & system

  health(): Promise<Health> {
    return this.get('/healthz');
  }

  async login(username: string, password: string): Promise<LoginResponse> {
    const res = await this.request<LoginResponse>('POST', '/api/auth/login', {
      body: { username, password },
      skipAuthHandling: true,
    });
    this.setToken(res.access_token);
    return res;
  }

  logout(): void {
    this.setToken(null);
  }

  me(signal?: AbortSignal): Promise<User> {
    return this.get('/api/auth/me', undefined, signal);
  }

  // ---------------------------------------------------------------- detector

  scan(text: string, signal?: AbortSignal): Promise<DetectionResult> {
    return this.request('POST', '/api/detector/scan', { body: { text }, signal });
  }

  /** Optional deployment-provided playground samples (a static file); [] when absent or invalid. */
  async playgroundSamples(signal?: AbortSignal): Promise<PlaygroundSample[]> {
    try {
      const response = await this.fetchImpl(this.url(SAMPLES_URL), { signal, credentials: 'same-origin', cache: 'no-cache' });
      if (!response.ok) return [];
      return parseSampleFile(await response.json());
    } catch {
      return [];
    }
  }

  // ---------------------------------------------------------------- approvals & push

  async approvals(params: { status?: ApprovalStatus; limit?: number } = {}, signal?: AbortSignal): Promise<ApprovalRecord[]> {
    return asArray<ApprovalRecord>(await this.get('/api/approvals', params, signal), 'items', 'approvals');
  }

  approval(id: string): Promise<ApprovalRecord> {
    return this.get(`/api/approvals/${encodeURIComponent(id)}`);
  }

  decideApproval(id: string, approve: boolean, note?: string): Promise<ApprovalRecord> {
    const body: { approve: boolean; note?: string } = { approve };
    if (note && note.trim()) body.note = note.trim();
    return this.request('POST', `/api/approvals/${encodeURIComponent(id)}/decision`, { body });
  }

  /** VAPID public key, or null when the server cannot deliver Web Push (no keys configured). */
  async vapidKey(): Promise<string | null> {
    try {
      const res = await this.get<VapidResponse>('/api/push/vapid');
      if (!res || res.enabled === false) return null;
      return res.public_key ? res.public_key : null;
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 501 || err.status === 503)) return null;
      throw err;
    }
  }

  pushSubscribe(subscription: PushSubscriptionJSON): Promise<void> {
    return this.request('POST', '/api/push/subscribe', { body: subscription });
  }

  pushUnsubscribe(endpoint: string): Promise<void> {
    return this.request('POST', '/api/push/unsubscribe', { body: { endpoint } });
  }

  // ---------------------------------------------------------------- audit

  auditEvents(filters: AuditFilters = {}, signal?: AbortSignal): Promise<AuditEventPage> {
    return this.get('/api/audit/events', { ...filters }, signal);
  }

  auditEvent(seq: number): Promise<AuditEvent> {
    return this.get(`/api/audit/events/${seq}`);
  }

  verifyAudit(): Promise<AuditVerifyReport> {
    return this.request('POST', '/api/audit/verify');
  }

  replay(seq: number): Promise<ReplayReport> {
    return this.request('POST', `/api/audit/events/${seq}/replay`);
  }

  async exportAudit(format: 'json' | 'csv', filters: Omit<AuditFilters, 'limit' | 'offset'> = {}): Promise<Download> {
    const query = { format, ...filters };
    const headers: Record<string, string> = {};
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    let response: Response;
    try {
      response = await this.fetchImpl(this.url('/api/audit/export', query), { headers, credentials: 'same-origin' });
    } catch (err) {
      throw new ApiError(0, err instanceof Error ? err.message : 'Network error');
    }
    if (response.status === 401) this.handleUnauthorized();
    if (!response.ok) throw new ApiError(response.status, await readErrorDetail(response));
    const fallback = `mirsad-audit-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.${format}`;
    return {
      blob: await response.blob(),
      filename: filenameFromDisposition(response.headers.get('Content-Disposition'), fallback),
    };
  }

  // ---------------------------------------------------------------- stats

  statsOverview(hours = 24, signal?: AbortSignal): Promise<StatsOverview> {
    return this.get('/api/stats/overview', { hours }, signal);
  }

  async timeseries(hours = 24, bucketMinutes = 60, signal?: AbortSignal): Promise<TimeseriesPoint[]> {
    return asArray<TimeseriesPoint>(
      await this.get('/api/stats/timeseries', { hours, bucket_minutes: bucketMinutes }, signal),
      'items',
      'points',
    );
  }

  // ---------------------------------------------------------------- policies

  policies(signal?: AbortSignal): Promise<PoliciesResponse> {
    return this.get('/api/policies', undefined, signal);
  }

  policy(version: string): Promise<PolicyDetail> {
    return this.get(`/api/policies/${encodeURIComponent(version)}`);
  }

  validatePolicy(yamlText: string): Promise<{ valid: boolean; errors: string[] }> {
    return this.request<ValidateResponse>('POST', '/api/policies/validate', { body: { yaml_text: yamlText } }).then((r) => ({
      valid: Boolean(r?.valid),
      errors: Array.isArray(r?.errors) ? r.errors.map(String) : [],
    }));
  }

  activatePolicy(yamlText: string, comment?: string): Promise<PolicyActivation> {
    return this.request('PUT', '/api/policies', { body: { yaml_text: yamlText, comment: comment || undefined } });
  }

  /** Re-activate a stored version (rollback). */
  rollbackPolicy(version: string): Promise<PolicyActivation> {
    return this.request('POST', `/api/policies/${encodeURIComponent(version)}/activate`);
  }

  // ---------------------------------------------------------------- agents

  async agents(signal?: AbortSignal): Promise<Agent[]> {
    return asArray<Agent>(await this.get('/api/agents', undefined, signal), 'items', 'agents');
  }

  createAgent(agent: AgentCreate): Promise<AgentWithKey> {
    return this.request('POST', '/api/agents', { body: agent });
  }

  rotateAgentKey(id: string): Promise<AgentWithKey> {
    return this.request('POST', `/api/agents/${encodeURIComponent(id)}/rotate-key`);
  }

  updateAgent(id: string, patch: Partial<Pick<Agent, 'name' | 'description' | 'disabled' | 'policy_agent_id'>>): Promise<Agent> {
    return this.request('PATCH', `/api/agents/${encodeURIComponent(id)}`, { body: patch });
  }

  deleteAgent(id: string): Promise<void> {
    return this.request('DELETE', `/api/agents/${encodeURIComponent(id)}`);
  }

  // ---------------------------------------------------------------- users

  async users(signal?: AbortSignal): Promise<User[]> {
    return asArray<User>(await this.get('/api/users', undefined, signal), 'items', 'users');
  }

  /** Omit `password` to have the server generate one; it is returned once in `generated_password`. */
  async createUser(user: UserCreate): Promise<UserCreated> {
    const body: Record<string, unknown> = { username: user.username, role: user.role };
    if (user.password) body.password = user.password;
    if (user.display_name) body.display_name = user.display_name;
    if (user.lang) body.lang = user.lang;
    const res = await this.request<UserCreated | User>('POST', '/api/users', { body });
    // Older servers returned the bare user record.
    return res && typeof res === 'object' && 'user' in res ? res : { user: res as User, generated_password: null };
  }

  updateUser(username: string, patch: UserPatch): Promise<User> {
    return this.request('PATCH', `/api/users/${encodeURIComponent(username)}`, { body: patch });
  }

  deleteUser(username: string): Promise<void> {
    return this.request('DELETE', `/api/users/${encodeURIComponent(username)}`);
  }

  // ---------------------------------------------------------------- tools

  async tools(signal?: AbortSignal): Promise<DiscoveredTool[]> {
    return normalizeTools(await this.get('/api/tools', undefined, signal));
  }

  // ---------------------------------------------------------------- demo

  async demoChat(req: DemoChatRequest, signal?: AbortSignal): Promise<DemoChatResponse> {
    // The server's request model forbids unknown fields: send exactly these keys.
    const body: DemoChatRequest = { message: req.message, protected: req.protected };
    if (req.session_id) body.session_id = req.session_id;
    if (req.lang) body.lang = req.lang;
    if (req.sector) body.sector = req.sector;
    const res = await this.request<DemoChatResponse>('POST', '/api/demo/chat', { body, signal });
    return {
      reply: res?.reply ?? '',
      session_id: res?.session_id ?? req.session_id ?? '',
      protected: res?.protected ?? req.protected,
      stopped_reason: res?.stopped_reason ?? 'completed',
      steps: Array.isArray(res?.steps) ? res.steps : [],
      attacker_inbox: Array.isArray(res?.attacker_inbox) ? res.attacker_inbox : [],
    };
  }

  /** Plant an arbitrary, previously unseen note in a fake invoice or patient record. */
  demoCustomContent(payload: string, sector: 'finance' | 'healthcare'): Promise<{ state: DemoState }> {
    return this.request('POST', `/api/demo/custom-content?sector=${encodeURIComponent(sector)}`, { body: { payload } });
  }

  demoReset(sector = 'general'): Promise<DemoState> {
    return this.request('POST', `/api/demo/reset?sector=${encodeURIComponent(sector)}`);
  }

  demoState(signal?: AbortSignal, sector = 'general'): Promise<DemoState> {
    return this.get(`/api/demo/state?sector=${encodeURIComponent(sector)}`, undefined, signal);
  }

  async demoScenarios(signal?: AbortSignal, sector = 'general'): Promise<DemoScenario[]> {
    return asArray<DemoScenario>(await this.get(`/api/demo/scenarios?sector=${encodeURIComponent(sector)}`, undefined, signal), 'scenarios', 'items');
  }

  /** Resets the demo world and plants the scenario's content (the "load scenario" action). */
  applyDemoScenario(id: string, sector = 'general'): Promise<{ scenario: DemoScenario; state: DemoState }> {
    return this.request('POST', `/api/demo/scenarios/${encodeURIComponent(id)}/apply?sector=${encodeURIComponent(sector)}`);
  }
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const text = await response.text();
    if (!text) return response.statusText || '';
    try {
      const json = JSON.parse(text) as { detail?: unknown };
      return formatDetail(json.detail ?? json) || response.statusText || '';
    } catch {
      return text.length > 300 ? `${text.slice(0, 300)}…` : text;
    }
  } catch {
    return response.statusText || '';
  }
}
