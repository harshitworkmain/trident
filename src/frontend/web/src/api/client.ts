import type {
  AuditEntry, RovKey,
  Alert, Capacity, ApiErrorBody, Breakdown, Bucket, GeoReport, Metric, Mission, ModelsReport, Performance, RovCommand, RovTrackPoint, SensorsReport, DeviceAction, DeviceCommand, DeviceSummary, FlatFrame, Forecast, ModelCard,
  Page, PublicSummary, ResponseTimes, Rov, VisionTicket, SosDetail, SosRecord, SosStatus, SmsTestRequest, SmsTestResponse, SosSubmit, SosSubmitResponse,
  SosTrack, StateTransition, Summary, Team, TimeSeries, TokenResponse, User, WeatherCurrent,
} from './types';

export const API_BASE = '/api/v1';

// ─── Errors ──────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId: string | null,
    public details?: Record<string, unknown>,
  ) {
    super(message);
  }
  get isConflict() { return this.status === 409; }
  get isServer() { return this.status >= 500; }
}

type ErrorListener = (err: ApiError) => void;
const errorListeners = new Set<ErrorListener>();
/** The toast layer subscribes here so every 5xx surfaces with its request id. */
export function onApiError(fn: ErrorListener) {
  errorListeners.add(fn);
  return () => { errorListeners.delete(fn); };
}

// ─── Tokens ──────────────────────────────────────────────────────────────────
// Trade-off: the access token lives only in memory, so an XSS payload cannot lift it from
// storage and it dies with the tab. The refresh token is in localStorage so a reload keeps the
// session; that is readable by injected script, which is why the server rotates it on every use
// and revokes the whole family on reuse, and why the CSP is strict. An httpOnly cookie would be
// stronger but the contract passes refresh tokens in the body.

const REFRESH_KEY = 'trident.refresh';
let accessToken: string | null = null;
let accessExp = 0;

type AuthListener = (user: User | null) => void;
const authListeners = new Set<AuthListener>();
export function onAuthChange(fn: AuthListener) {
  authListeners.add(fn);
  return () => { authListeners.delete(fn); };
}

function readRefresh(): string | null {
  try { return localStorage.getItem(REFRESH_KEY); } catch { return null; }
}
function writeRefresh(v: string | null) {
  try {
    if (v) localStorage.setItem(REFRESH_KEY, v);
    else localStorage.removeItem(REFRESH_KEY);
  } catch { /* storage blocked: session lasts until reload */ }
}

function applyTokens(t: TokenResponse) {
  accessToken = t.access_token;
  accessExp = Date.now() + t.expires_in * 1000;
  writeRefresh(t.refresh_token);
  authListeners.forEach((fn) => fn(t.user));
}

export function clearSession() {
  accessToken = null;
  accessExp = 0;
  writeRefresh(null);
  authListeners.forEach((fn) => fn(null));
}

export function getAccessToken() { return accessToken; }
export function hasRefreshToken() { return readRefresh() !== null; }

let refreshInFlight: Promise<boolean> | null = null;

/** Single-flight: concurrent 401s share one refresh request, so a rotated token is never reused. */
export function refreshSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  const rt = readRefresh();
  if (!rt) return Promise.resolve(false);
  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: rt }),
      });
      if (!res.ok) {
        if (res.status === 401 || res.status === 403) clearSession();
        return false;
      }
      applyTokens((await res.json()) as TokenResponse);
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

/** For the WebSocket: refresh first if the access token is about to expire. */
export async function freshAccessToken(): Promise<string | null> {
  if (accessToken && Date.now() < accessExp - 30_000) return accessToken;
  const ok = await refreshSession();
  return ok ? accessToken : null;
}

// ─── Request core ────────────────────────────────────────────────────────────

interface RequestOpts {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
  headers?: Record<string, string>;
  auth?: boolean; // default true
  signal?: AbortSignal;
  /** Abort after this many ms and fail as a network error (code `timeout`). */
  timeoutMs?: number;
}

function buildUrl(path: string, query?: RequestOpts['query']) {
  const qs = new URLSearchParams();
  if (query) for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null && v !== '') qs.set(k, String(v));
  const s = qs.toString();
  return `${API_BASE}${path}${s ? `?${s}` : ''}`;
}

async function toError(res: Response): Promise<ApiError> {
  let body: Partial<ApiErrorBody> = {};
  try { body = (await res.json()) as ApiErrorBody; } catch { /* non-JSON error page */ }
  const requestId = body.request_id ?? res.headers.get('X-Request-ID');
  const detail = (body as { detail?: unknown }).detail; // FastAPI default shape, just in case
  return new ApiError(
    res.status,
    body.error?.code ?? (res.status === 409 ? 'conflict' : 'http_' + res.status),
    body.error?.message ?? (typeof detail === 'string' ? detail : res.statusText || 'Request failed'),
    requestId ?? null,
    body.error?.details,
  );
}

export async function request<T>(path: string, opts: RequestOpts = {}): Promise<T> {
  const { method = 'GET', body, query, headers = {}, auth = true, timeoutMs } = opts;
  let signal = opts.signal;
  let timedOut = false;
  let timer: number | undefined;
  if (timeoutMs) {
    const ctl = new AbortController();
    opts.signal?.addEventListener('abort', () => ctl.abort());
    timer = window.setTimeout(() => { timedOut = true; ctl.abort(); }, timeoutMs);
    signal = ctl.signal;
  }
  try {
    return await requestOnce<T>(path, method, body, query, headers, auth, signal);
  } catch (e) {
    if (timedOut) throw new ApiError(0, 'timeout', 'The server took too long to answer. Check your connection.', null);
    throw e;
  } finally {
    window.clearTimeout(timer);
  }
}

async function requestOnce<T>(
  path: string, method: string, body: unknown, query: RequestOpts['query'], headers: Record<string, string>, auth: boolean, signal?: AbortSignal,
): Promise<T> {
  const send = () => {
    const h: Record<string, string> = { Accept: 'application/json', ...headers };
    if (body !== undefined) h['Content-Type'] = 'application/json';
    if (auth && accessToken) h.Authorization = `Bearer ${accessToken}`;
    return fetch(buildUrl(path, query), { method, headers: h, body: body === undefined ? undefined : JSON.stringify(body), signal });
  };

  let res: Response;
  try {
    res = await send();
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ApiError(0, 'network', 'Cannot reach the server. Check your connection.', null);
  }

  if (res.status === 401 && auth && hasRefreshToken()) {
    if (await refreshSession()) res = await send();
  }
  if (res.status === 401 && auth) clearSession();

  if (!res.ok) {
    const err = await toError(res);
    if (err.isServer) errorListeners.forEach((fn) => fn(err));
    throw err;
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

/** Lists are `{items, next_cursor}` per the contract, but /teams and /devices are documented as bare arrays. */
export function asItems<T>(v: T[] | Page<T> | { items: T[] } | null | undefined): T[] {
  if (!v) return [];
  return Array.isArray(v) ? v : v.items ?? [];
}

// ─── Endpoints ───────────────────────────────────────────────────────────────

export const api = {
  // auth
  async login(username: string, password: string) {
    const t = await request<TokenResponse>('/auth/login', { method: 'POST', body: { username, password }, auth: false });
    applyTokens(t);
    return t.user;
  },
  async logout() {
    const rt = readRefresh();
    try { if (rt) await request<void>('/auth/logout', { method: 'POST', body: { refresh_token: rt } }); } catch { /* best effort */ }
    clearSession();
  },
  me: () => request<User>('/auth/me'),

  // public
  publicSummary: () => request<PublicSummary>('/public/summary', { auth: false }),
  submitSos: (body: SosSubmit, idempotencyKey: string, timeoutMs = 20_000) =>
    request<SosSubmitResponse>('/sos', { method: 'POST', body, auth: false, headers: { 'Idempotency-Key': idempotencyKey }, timeoutMs }),
  trackSos: (ref: string, token: string) =>
    request<SosTrack>(`/sos/track/${encodeURIComponent(ref)}`, { query: { token }, auth: false }),

  // sos
  listSos: (q: { status?: string; priority_max?: number; type?: string; q?: string; since?: string; limit?: number } = {}) =>
    request<Page<SosRecord>>('/sos', { query: { limit: 200, ...q } }),
  getSos: (ref: string) => request<SosDetail>(`/sos/${encodeURIComponent(ref)}`),
  setSosStatus: (ref: string, status: SosStatus, version: number, note?: string) =>
    request<SosRecord>(`/sos/${encodeURIComponent(ref)}/status`, { method: 'PATCH', body: { status, version, note: note || undefined } }),
  assignSos: (ref: string, team_id: Team['id'], version: number) =>
    request<SosRecord>(`/sos/${encodeURIComponent(ref)}/assign`, { method: 'POST', body: { team_id, version } }),
  /** Moves a team from a lower-priority `assigned` request to this one; 409 `conflict` if either changed. */
  reallocateSos: (ref: string, body: { team_id: Team['id']; from_reference_id: string; version: number; from_version: number }) =>
    request<SosRecord>(`/sos/${encodeURIComponent(ref)}/reallocate`, { method: 'POST', body }),
  capacity: () => request<Capacity>('/dispatch/capacity'),
  /** Confirms (device_id) or removes (null) the wearable linked to a request. */
  linkSosDevice: (ref: string, device_id: string | null) =>
    request<SosRecord>(`/sos/${encodeURIComponent(ref)}/link-device`, { method: 'POST', body: { device_id } }),
  addSosNote: (ref: string, text: string) =>
    request<unknown>(`/sos/${encodeURIComponent(ref)}/notes`, { method: 'POST', body: { text } }),

  // teams
  teams: () => request<Team[] | Page<Team>>('/teams').then(asItems),
  patchTeam: (id: Team['id'], body: { is_available?: boolean; capacity?: number }) =>
    request<Team>(`/teams/${id}`, { method: 'PATCH', body }),

  // devices
  devices: () => request<DeviceSummary[] | Page<DeviceSummary>>('/devices').then(asItems),
  registerDevice: (device_id: string, label: string) =>
    request<{ device_id: string; api_key: string }>('/devices', { method: 'POST', body: { device_id, label } }),
  rotateKey: (id: string) => request<{ api_key: string }>(`/devices/${encodeURIComponent(id)}/rotate-key`, { method: 'POST' }),
  sendCommand: (id: string, action: DeviceAction, params: Record<string, unknown> = {}) =>
    request<DeviceCommand>(`/devices/${encodeURIComponent(id)}/commands`, { method: 'POST', body: { action, params } }),
  frames: (id: string, since?: string, limit = 400) =>
    request<FlatFrame[] | Page<FlatFrame>>(`/devices/${encodeURIComponent(id)}/frames`, { query: { since, limit } }).then(asItems),
  states: (id: string, since?: string) =>
    request<StateTransition[] | Page<StateTransition>>(`/devices/${encodeURIComponent(id)}/states`, { query: { since } }).then(asItems),

  // alerts
  alerts: (status?: string) => request<Alert[] | Page<Alert>>('/alerts', { query: { status, limit: 200 } }).then(asItems),
  ackAlert: (id: Alert['id']) => request<Alert>(`/alerts/${id}/ack`, { method: 'POST' }),
  resolveAlert: (id: Alert['id'], note?: string) => request<Alert>(`/alerts/${id}/resolve`, { method: 'POST', body: { note } }),

  // weather
  weatherCurrent: () => request<WeatherCurrent>('/weather/current'),
  forecast: (hours = 48) => request<Forecast>('/weather/forecast', { query: { hours } }),
  modelCard: () => request<ModelCard>('/weather/model'),

  // analytics
  summary: () => request<Summary>('/analytics/summary'),
  timeseries: (metric: Metric, bucket: Bucket, since?: string) =>
    request<TimeSeries>('/analytics/timeseries', { query: { metric, bucket, since } }),
  breakdown: (by: 'type' | 'status' | 'priority') => request<Breakdown>('/analytics/breakdown', { query: { by } }),
  responseTimes: () => request<ResponseTimes>('/analytics/response-times'),
  sensors: () => request<SensorsReport>('/analytics/sensors'),
  performance: () => request<Performance>('/analytics/performance'),
  geo: () => request<GeoReport>('/analytics/geo'),
  models: () => request<ModelsReport>('/analytics/models'),

  // rov
  rovs: () => request<Rov[] | Page<Rov>>('/rov').then(asItems),
  rovAction: (id: string, action: 'deploy' | 'recall' | 'stop' | 'reset' | 'takeover' | 'release', reference_id?: string) =>
    request<Rov>(`/rov/${encodeURIComponent(id)}/${action}`, { method: 'POST', body: action === 'deploy' ? { reference_id } : undefined }),
  rovControl: (id: string, command: RovCommand, speed_pct: number) =>
    request<Rov>(`/rov/${encodeURIComponent(id)}/control`, { method: 'POST', body: { command, speed_pct } }),
  rovTrack: (id: string, minutes = 30) =>
    request<RovTrackPoint[] | Page<RovTrackPoint>>(`/rov/${encodeURIComponent(id)}/track`, { query: { minutes } }).then(asItems),
  /** Admin: key for the serial bridge (src/rov/bridge.py). Marks the unit as real hardware, ending its simulation. */
  rovBridgeKey: (id: string, video_url?: string) =>
    request<RovKey>(`/rov/${encodeURIComponent(id)}/bridge-key`, { method: 'POST', body: { video_url: video_url || undefined } }),
  /** Admin: key for the computer-vision worker (src/cv/vision) next to the unit. */
  rovVisionKey: (id: string) => request<RovKey>(`/rov/${encodeURIComponent(id)}/vision-key`, { method: 'POST' }),
  /** Single-use ticket for the annotated MJPEG stream; use `url` within `expires_in` seconds, then fetch a new one. */
  rovVisionTicket: (id: string) => request<VisionTicket>(`/rov/${encodeURIComponent(id)}/vision/ticket`, { method: 'POST' }),
  missions: () => request<Mission[] | Page<Mission>>('/missions').then(asItems),

  // users (admin)
  users: () => request<User[] | Page<User>>('/users').then(asItems),
  createUser: (body: { username: string; display_name: string; password: string; role: string; team_id?: User['team_id'] }) =>
    request<User>('/users', { method: 'POST', body }),
  patchUser: (id: User['id'], body: Partial<{ display_name: string; role: string; team_id: User['team_id']; is_active: boolean; password: string }>) =>
    request<User>(`/users/${id}`, { method: 'PATCH', body }),
  /** Admin: runs a message through the SMS intake parser as if it arrived at /sms/inbound. 503 when SMS is not configured. */
  smsTest: (body: SmsTestRequest) => request<SmsTestResponse>('/sms/test', { method: 'POST', body }),
  /** Admin: the audit log, newest first. */
  audit: (limit = 200) => request<AuditEntry[] | Page<AuditEntry>>('/audit', { query: { limit } }).then(asItems),
};
