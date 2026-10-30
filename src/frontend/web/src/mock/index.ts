// In-app mock backend for VITE_MOCK=1: fake REST (via a fetch wrapper scoped to /api/v1) and a
// fake WebSocket that follows the §2 event contract. Loaded by a dynamic import in main.tsx only
// when the flag is set, so the real build never contains it.
import { setSocketFactory, type SocketLike } from '../api/live';
import { EMERGENCY_TYPES, type Alert, type Capacity, type CapacitySuggestion, type DeviceAction, type EmergencyType, type SosStatus, type Topic, type User } from '../api/types';
import { alertLevelOf, allowedTransitions } from '../lib/states';
import {
  alerts, devices, deviceSims, forecast, iso, jitter, makeSos, MIN, modelCard, newRef, nextAlertId, pick,
  rand, sampleVitals, scoreSos, sosRows, assignEvent, teams, transitions, users, weatherCurrent, type SosRow,
} from './data';
import { audit, auditLog, HttpError, setEmitter } from './http';
import { rovRoute, rovStep, setVisionCamera, visionRoute, visionStep } from './rov';
import * as an from './analytics';

// ─── Event bus ───────────────────────────────────────────────────────────────

const sockets = new Set<MockSocket>();
const seqs: Record<string, number> = {};
function emit(topic: Topic, data: unknown) {
  seqs[topic] = (seqs[topic] ?? 0) + 1;
  const msg = JSON.stringify({ type: 'event', topic, seq: seqs[topic], ts: iso(), data });
  sockets.forEach((s) => s.deliver(msg));
}
setEmitter(emit);

class MockSocket implements SocketLike {
  readyState = 0;
  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  constructor() {
    setTimeout(() => {
      this.readyState = 1;
      sockets.add(this);
      this.onopen?.(new Event('open'));
      this.deliver(JSON.stringify({ type: 'hello', server_time: iso(), topics: ['sos', 'alerts', 'devices', 'weather', 'rov', 'system'] }));
    }, 250);
  }
  deliver(data: string) {
    if (this.readyState === 1) this.onmessage?.(new MessageEvent('message', { data }));
  }
  send(data: string) {
    if (JSON.parse(data).type === 'ping') this.deliver(JSON.stringify({ type: 'pong', server_time: iso() }));
  }
  close() {
    if (this.readyState === 3) return;
    this.readyState = 3;
    sockets.delete(this);
    setTimeout(() => this.onclose?.(new CloseEvent('close', { code: 1000 })), 0);
  }
}

// ─── Simulation loop ─────────────────────────────────────────────────────────

let tick = 0;
const isOpen = (r: SosRow) => !['resolved', 'cancelled'].includes(r.status);
const freeTeams = () => teams.filter((t) => t.is_available && t.current_load < t.capacity);
const waitingMin = (r: SosRow) => (isOpen(r) && !r.assigned_team ? Math.floor((Date.now() - Date.parse(r.queued_at ?? r.created_at)) / MIN) : null);
const AGEING_MIN = 20;

/** The staff view of a row, with the capacity fields derived the way the backend does. */
function publicSos(r: SosRow) {
  const { history: _h, notes: _n, assignments: _a, tracking_token: _t, queued_at: _q, ...rec } = r;
  void _h; void _n; void _a; void _t; void _q;
  const waiting = waitingMin(r);
  // Priority ageing: an unassigned request says how long it has waited.
  const reasons = r.priority_reasons.filter((x) => !/^waiting \d+ min$/.test(x));
  if (waiting !== null && waiting >= AGEING_MIN && r.priority <= 3) reasons.push(`waiting ${waiting} min`);
  return {
    ...rec,
    priority_reasons: reasons,
    source: r.source ?? 'web',
    duplicate_of: r.duplicate_of ?? null,
    waiting_min: waiting,
    awaiting_resources: waiting !== null && r.priority <= 2 && freeTeams().length === 0,
  };
}

/** GET /dispatch/capacity: ok, strained (one team free or fewer) or exhausted, with team-move suggestions. */
function capacity(): Capacity {
  const free = freeTeams().length;
  const status = free === 0 ? 'exhausted' : free <= 1 ? 'strained' : 'ok';
  const urgent = sosRows.filter((r) => r.priority <= 2 && waitingMin(r) !== null)
    .sort((a, b) => a.priority - b.priority || (waitingMin(b) ?? 0) - (waitingMin(a) ?? 0));
  const suggestions: CapacitySuggestion[] = [];
  if (status !== 'ok') {
    // Donors: requests whose team is assigned but has not left, least urgent first.
    const donors = sosRows.filter((r) => r.status === 'assigned' && r.assigned_team).sort((a, b) => b.priority - a.priority || a.priority_score - b.priority_score);
    const used = new Set<string>();
    for (const w of urgent) {
      const d = donors.find((x) => !used.has(x.reference_id) && x.priority >= w.priority + 2);
      if (!d) continue;
      used.add(d.reference_id);
      suggestions.push({
        for_reference_id: w.reference_id, team_id: d.assigned_team!.id, team_name: d.assigned_team!.name,
        from_reference_id: d.reference_id, from_priority: d.priority,
        reason: `${d.reference_id} is P${d.priority} and its team has not left yet; ${w.reference_id} (P${w.priority}) has waited ${waitingMin(w)} min`,
      });
    }
  }
  return {
    status, teams_free: free, teams_total: teams.length,
    waiting: urgent.map((r) => ({ reference_id: r.reference_id, priority: r.priority, waiting_min: waitingMin(r) ?? 0, emergency_type: r.emergency_type })),
    suggestions, updated_at: iso(),
  };
}

let lastCapacity = '';
/** Pushes a `system` capacity event when anything but the timestamp changed. */
function emitCapacityIfChanged() {
  const c = capacity();
  const sig = JSON.stringify({ ...c, updated_at: '' });
  if (sig === lastCapacity) return;
  lastCapacity = sig;
  emit('system', { event: 'capacity', ...c });
}

function stepSim() {
  tick++;
  const now = iso();
  for (const sim of deviceSims) {
    const d = devices.find((x) => x.device_id === sim.id)!;
    if (!d.online) continue;
    const v = sampleVitals(sim, tick * 1.5);
    an.recordFrame(d.device_id);
    d.last_seen = now;
    d.battery_v = Math.max(3.3, (d.battery_v ?? 4) - 0.00015);
    if (d.location) d.location = { lat: d.location.lat + jitter(0, 0.00004), lng: d.location.lng + jitter(0, 0.00004) };
    emit('devices', {
      event: 'frame', device_id: d.device_id,
      summary: {
        bpm: v.bpm, spo2: v.spo2, temp_skin_c: v.temp, eda_us: v.eda, acc_std_g: v.acc, battery_v: +d.battery_v.toFixed(3),
        lat: d.location?.lat ?? null, lng: d.location?.lng ?? null, state: d.state.ml_health_state, risk: d.state.risk, heads: d.heads,
        alert_level: d.state.alert_level,
      },
    });
  }

  // Every ~45 s a device changes state; sometimes critical, which opens an alert.
  if (tick % 30 === 0) {
    const d = pick(devices.filter((x) => x.online && x.device_id !== 'TRD-W03'));
    const sim = deviceSims.find((s) => s.id === d.device_id)!;
    const goingBad = d.state.ml_health_state === 'STABLE';
    const state = goingBad ? pick(['ELEVATED_STRESS', 'HYPOTHERMIA_RISK', 'ELEVATED_STRESS', 'CRUSH_ENTRAPMENT']) : 'STABLE';
    const level = alertLevelOf(state);
    d.state = {
      ml_health_state: state, alert_level: level, risk: level === 'critical' ? 0.8 : level === 'advisory' ? 0.35 : 0.05,
      evidence: state === 'HYPOTHERMIA_RISK' ? ['skin temp 31.2 °C falling 0.4 °C/min', 'wet 18 min'] : state === 'CRUSH_ENTRAPMENT' ? ['fall p=0.71', 'immobile, HR rising 96 → 121'] : state === 'ELEVATED_STRESS' ? ['stress p=0.89, activity rest'] : ['HR trusted'],
    };
    sim.base.bpm = state === 'CRUSH_ENTRAPMENT' ? 118 : state === 'ELEVATED_STRESS' ? 102 : 76;
    sim.base.temp = state === 'HYPOTHERMIA_RISK' ? 31.2 : 33.5;
    (transitions[d.device_id] ??= []).push({ state, alert_level: level, risk: d.state.risk, evidence: d.state.evidence, at: now });
    emit('devices', { event: 'state', device_id: d.device_id, summary: { state: d.state, heads: d.heads } });
    if (level === 'critical') {
      const a: Alert = { id: nextAlertId(), device_id: d.device_id, state, risk: d.state.risk, evidence: d.state.evidence, status: 'open', opened_at: now };
      alerts.unshift(a);
      emit('alerts', { event: 'opened', alert: a });
    }
  }

  // A new public SOS roughly every 40 s.
  if (tick % 27 === 0) {
    const r = makeSos(Math.floor(rand() * 40), 'pending', 0.1);
    r.reference_id = newRef();
    if (tick % 54 === 0) { r.source = 'sms'; r.email = undefined; r.additional_info = `SOS P${r.people_to_rescue} I${r.people_injured} T${r.emergency_type}`; }
    sosRows.unshift(r);
    emit('sos', { event: 'created', sos: publicSos(r) });
  }

  // "Another dispatcher" moves something along: also what makes 409s reproducible.
  if (tick % 17 === 0) {
    // Low-priority assigned teams are held back (the capacity demo needs a team that has not left).
    const open = sosRows.filter((r) => ['triaged', 'assigned', 'en_route'].includes(r.status) && !(r.status === 'assigned' && r.priority >= 4));
    if (open.length) {
      const r = pick(open);
      const next = allowedTransitions(r.status).find((s) => s !== 'cancelled');
      if (next) changeStatus(r, next, 'A. Bose (dispatcher)');
    }
  }

  // Every ~90 s a band in a non-STABLE state stops reporting: the server opens a LOST_CONTACT alert.
  if (tick % 60 === 45) {
    const cands = devices.filter((x) => x.online && x.device_id !== 'TRD-W03' && x.state.ml_health_state !== 'STABLE');
    if (cands.length) {
      const d = pick(cands);
      d.online = false;
      emit('devices', { event: 'offline', device_id: d.device_id, summary: {} });
      const a: Alert = { id: nextAlertId(), device_id: d.device_id, state: 'LOST_CONTACT', risk: Math.max(0.6, d.state.risk), evidence: [`last seen 45 s ago in ${d.state.ml_health_state}`], status: 'open', opened_at: now };
      alerts.unshift(a);
      emit('alerts', { event: 'opened', alert: a });
      setTimeout(() => { d.online = true; emit('devices', { event: 'online', device_id: d.device_id, summary: {} }); }, 40_000);
    }
  }

  // Every ~2 min a victim presses the SOS button on their band: the server opens an SOS_BUTTON alert.
  if (tick % 80 === 25) {
    const cands = devices.filter((x) => x.online);
    if (cands.length) {
      const d = pick(cands);
      const a: Alert = { id: nextAlertId(), device_id: d.device_id, state: 'SOS_BUTTON', risk: Math.max(0.9, d.state.risk), evidence: ['SOS button held 3 s', `state ${d.state.ml_health_state}`], status: 'open', opened_at: now };
      alerts.unshift(a);
      emit('alerts', { event: 'opened', alert: a });
    }
  }

  emitCapacityIfChanged();

  // Escalate open critical alerts older than 2 min (mirrors the alert_escalation job).
  if (tick % 20 === 0) {
    for (const a of alerts) {
      if (a.status === 'open' && !a.escalated && Date.now() - Date.parse(a.opened_at) > 2 * MIN) {
        a.escalated = true;
        emit('alerts', { event: 'escalated', alert: a });
      }
    }
  }

}

function changeStatus(r: SosRow, status: SosStatus, by: string, note?: string) {
  r.status = status;
  r.version++;
  r.updated_at = iso();
  r.history.push({ kind: 'status', status, at: r.updated_at, by, actor: by, text: note, note });
  if (note) r.notes.push({ id: Date.now(), text: note, author: by, at: r.updated_at });
  emit('sos', { event: 'updated', sos: publicSos(r) });
}

// ─── REST ────────────────────────────────────────────────────────────────────

const tokens = new Map<string, User>();
const refresh = new Map<string, User>();
const idem = new Map<string, unknown>();
let reqN = 0;


function issue(u: User) {
  const access = `mock-at-${u.username}-${Math.random().toString(36).slice(2)}`;
  const rt = `mock-rt-${u.username}-${Math.random().toString(36).slice(2)}`;
  tokens.set(access, u);
  refresh.set(rt, u);
  const { password: _p, ...user } = u as User & { password?: string };
  void _p;
  return { access_token: access, refresh_token: rt, token_type: 'bearer', expires_in: 900, user };
}

function need(u: User | undefined, roles?: User['role'][]): User {
  if (!u) throw new HttpError(401, 'unauthenticated', 'Sign in required');
  if (roles && !roles.includes(u.role)) throw new HttpError(403, 'forbidden', `Your role (${u.role}) cannot do this`);
  return u;
}

const findSos = (ref: string) => {
  const r = sosRows.find((x) => x.reference_id === ref);
  if (!r) throw new HttpError(404, 'not_found', `No SOS ${ref}`);
  return r;
};

function detail(r: SosRow) {
  const { tracking_token: _t, ...rest } = r;
  void _t;
  return { ...rest, linked_device: r.device_id ? devices.find((d) => d.device_id === r.device_id) ?? null : null };
}

function frames(id: string, limit: number) {
  const sim = deviceSims.find((s) => s.id === id);
  if (!sim) throw new HttpError(404, 'not_found', `No device ${id}`);
  const d = devices.find((x) => x.device_id === id)!;
  const n = Math.min(limit, 400);
  const out = [];
  for (let i = n; i > 0; i--) {
    const t = tick * 1.5 - i * 1.5;
    const v = sampleVitals(sim, t);
    out.push({
      seq: 10_000 + tick - i, ts: iso(i * 1500),
      ppg_bpm: v.bpm, ppg_spo2: v.spo2, temp_skin_c: v.temp, eda_us: v.eda, imu_acc_std_g: v.acc, power_batt_v: d.battery_v,
      fusion: { ml_health_state: d.state.ml_health_state, ml_risk_score: d.state.risk, alert_level: d.state.alert_level, evidence: d.state.evidence, heads: d.heads },
    });
  }
  return out;
}


async function route(method: string, path: string, q: URLSearchParams, body: Record<string, unknown>, headers: Headers): Promise<[number, unknown]> {
  const auth = headers.get('Authorization')?.replace(/^Bearer /, '');
  const user = auth ? tokens.get(auth) : undefined;
  const m = (re: RegExp) => path.match(re);
  let g: RegExpMatchArray | null;

  // auth
  if (method === 'POST' && path === '/auth/login') {
    const u = users.find((x) => x.username === body.username && x.password === body.password);
    if (!u) throw new HttpError(401, 'invalid_credentials', 'Wrong username or password');
    return [200, issue(u)];
  }
  if (method === 'POST' && path === '/auth/refresh') {
    // Tokens embed the username so a page reload (fresh mock memory) keeps the demo session.
    const rtStr = String(body.refresh_token);
    const u = refresh.get(rtStr) ?? users.find((x) => rtStr.startsWith(`mock-rt-${x.username}-`));
    if (!u) throw new HttpError(401, 'invalid_refresh', 'Session expired');
    refresh.delete(String(body.refresh_token));
    return [200, issue(u)];
  }
  if (method === 'POST' && path === '/auth/logout') { refresh.delete(String(body.refresh_token)); return [204, null]; }
  if (method === 'GET' && path === '/auth/me') { const u = need(user); return [200, u]; }

  // public
  if (method === 'GET' && path === '/public/summary') {
    return [200, {
      teams_available: teams.filter((t) => t.is_available && t.current_load < t.capacity).length, teams_total: teams.length,
      sos_open: sosRows.filter((r) => !['resolved', 'cancelled'].includes(r.status)).length,
      sos_resolved_24h: sosRows.filter((r) => r.status === 'resolved').length + 41,
      devices_online: devices.filter((d) => d.online).length,
      weather: { temp_c: 27.4, hazards: forecast(48).hazards.map((h) => ({ type: h.type, level: h.level })) },
      sms_number: '+91 90000 00112', // demo number
      updated_at: iso(),
    }];
  }
  if (method === 'POST' && path === '/sos') {
    const key = headers.get('Idempotency-Key');
    if (key && idem.has(key)) return [200, idem.get(key)];
    for (const f of ['name', 'phone', 'address']) if (!body[f]) throw new HttpError(422, 'validation_error', `${f} is required`, { field: f });
    const r = makeSos(0, 'pending', 0);
    // Possible duplicate: an earlier open request from the same phone or within ~100 m.
    const near = (a: SosRow) => body.latitude != null && a.latitude != null && a.longitude != null
      && Math.hypot((a.latitude - Number(body.latitude)) * 111_000, (a.longitude - Number(body.longitude)) * 108_000) < 100;
    const dup = sosRows.find((a) => isOpen(a) && (a.phone === body.phone || near(a)));
    Object.assign(r, body, scoreSos(body as never), { reference_id: newRef(), created_at: iso(), updated_at: iso(), notes: [], assignments: [], history: [{ status: 'pending', at: iso(), by: 'public form' }], version: 1, assigned_team: null, source: 'web', duplicate_of: dup?.reference_id ?? null, queued_at: undefined, device_verified: false });
    sosRows.unshift(r);
    emit('sos', { event: 'created', sos: publicSos(r) });
    const res = { reference_id: r.reference_id, tracking_token: r.tracking_token, priority: r.priority, status: r.status };
    if (key) idem.set(key, res);
    setTimeout(() => { if (r.status === 'pending') changeStatus(r, 'triaged', 'auto-triage'); }, 12_000);
    return [201, res];
  }
  if (method === 'GET' && (g = m(/^\/sos\/track\/([^/]+)$/))) {
    const r = findSos(decodeURIComponent(g[1]));
    if (q.get('token') !== r.tracking_token) throw new HttpError(404, 'not_found', 'Reference or tracking token not recognised');
    const team = r.assigned_team ? teams.find((t) => t.id === r.assigned_team!.id) : null;
    return [200, { reference_id: r.reference_id, status: r.status, priority: r.priority, created_at: r.created_at, updated_at: r.updated_at, team_name: team?.name ?? null, eta_min: ['assigned', 'en_route'].includes(r.status) ? 18 : null, history: r.history.map(({ status, at }) => ({ status, at })) }];
  }

  // everything below is staff
  const u = need(user);

  if (method === 'GET' && path === '/sos') {
    let rows = sosRows.slice();
    const st = q.get('status');
    if (st) rows = rows.filter((r) => st.split(',').includes(r.status));
    const term = q.get('q')?.toLowerCase();
    if (term) rows = rows.filter((r) => `${r.reference_id} ${r.name} ${r.address}`.toLowerCase().includes(term));
    return [200, { items: rows.map(publicSos), next_cursor: null }];
  }
  if (method === 'GET' && (g = m(/^\/sos\/([^/]+)$/))) return [200, detail(findSos(decodeURIComponent(g[1])))];
  if (method === 'PATCH' && (g = m(/^\/sos\/([^/]+)\/status$/))) {
    const r = findSos(decodeURIComponent(g[1]));
    need(u, ['admin', 'dispatcher', 'responder']);
    if (u.role === 'responder' && String(r.assigned_team?.id) !== String(u.team_id)) throw new HttpError(403, 'forbidden', 'Responders can only update SOS assigned to their team');
    if (body.version !== r.version) throw new HttpError(409, 'conflict', 'This SOS was changed by someone else', { current_version: r.version });
    const to = body.status as SosStatus;
    if (!allowedTransitions(r.status).includes(to)) throw new HttpError(409, 'invalid_transition', `Cannot move from ${r.status} to ${to}`);
    changeStatus(r, to, u.display_name, body.note as string | undefined);
    return [200, publicSos(r)];
  }
  if (method === 'POST' && (g = m(/^\/sos\/([^/]+)\/link-device$/))) {
    need(u, ['admin', 'dispatcher']);
    const r = findSos(decodeURIComponent(g[1]));
    const id = body.device_id == null || body.device_id === '' ? null : String(body.device_id);
    if (id && !devices.some((d) => d.device_id === id)) throw new HttpError(422, 'validation_error', `${id} is not a registered wearable`, { field: 'device_id' });
    r.device_id = id ?? undefined;
    r.device_verified = !!id;
    r.version++;
    r.updated_at = iso();
    // Like the server: a link change is a note, not a status event.
    r.notes.push({ id: Date.now(), text: id ? `Wearable ${id} confirmed` : 'Wearable link removed', author: u.display_name, at: r.updated_at });
    emit('sos', { event: 'updated', sos: publicSos(r) });
    return [200, publicSos(r)];
  }
  if (method === 'POST' && (g = m(/^\/sos\/([^/]+)\/assign$/))) {
    need(u, ['admin', 'dispatcher']);
    const r = findSos(decodeURIComponent(g[1]));
    if (body.version !== r.version) throw new HttpError(409, 'conflict', 'This SOS was changed by someone else', { current_version: r.version });
    const t = teams.find((x) => String(x.id) === String(body.team_id));
    if (!t) throw new HttpError(404, 'not_found', 'No such team');
    if (t.current_load >= t.capacity) throw new HttpError(409, 'team_full', `${t.name} is at capacity`);
    t.current_load++;
    r.assigned_team = { id: t.id, name: t.name };
    r.status = 'assigned';
    r.version++;
    r.updated_at = iso();
    const ev = assignEvent(t, u.display_name, r.updated_at, `Assigned ${t.name}`);
    r.assignments.push(ev.assignment);
    r.history.push(ev.history);
    audit(u.username, 'sos.assign', r.reference_id, { team_id: t.id });
    emit('sos', { event: 'assigned', sos: publicSos(r) });
    emitCapacityIfChanged();
    return [200, publicSos(r)];
  }
  if (method === 'POST' && (g = m(/^\/sos\/([^/]+)\/reallocate$/))) {
    need(u, ['admin', 'dispatcher']);
    const r = findSos(decodeURIComponent(g[1]));
    const from = findSos(String(body.from_reference_id));
    if (body.version !== r.version || body.from_version !== from.version) throw new HttpError(409, 'conflict', 'One of the requests was changed by someone else', { current_version: r.version, from_current_version: from.version });
    if (from.status !== 'assigned' || String(from.assigned_team?.id) !== String(body.team_id)) throw new HttpError(409, 'conflict', `${from.reference_id} no longer has that team waiting to leave`);
    if (r.assigned_team || !isOpen(r)) throw new HttpError(409, 'conflict', `${r.reference_id} already has a team or is closed`);
    const team = from.assigned_team!;
    const at = iso();
    from.assigned_team = null;
    from.status = 'triaged';
    from.version++;
    from.updated_at = at;
    from.queued_at = at;
    const fromText = `${team.name} moved to ${r.reference_id}; back in the queue`;
    from.history.push({ kind: 'status', status: 'triaged', at, by: u.display_name, actor: u.display_name, text: fromText, note: fromText });
    r.assigned_team = team;
    r.status = 'assigned';
    r.version++;
    r.updated_at = at;
    const ev = assignEvent(team, u.display_name, at, `${team.name} moved from ${from.reference_id}`);
    r.assignments.push(ev.assignment);
    r.history.push(ev.history);
    emit('sos', { event: 'updated', sos: publicSos(from) });
    emit('sos', { event: 'assigned', sos: publicSos(r) });
    emitCapacityIfChanged();
    return [200, publicSos(r)];
  }
  if (method === 'GET' && path === '/dispatch/capacity') return [200, capacity()];
  if (method === 'POST' && (g = m(/^\/sos\/([^/]+)\/notes$/))) {
    need(u, ['admin', 'dispatcher', 'responder']);
    const r = findSos(decodeURIComponent(g[1]));
    const note = { id: Date.now(), text: String(body.text ?? ''), author: u.display_name, at: iso() };
    r.notes.push(note);
    emit('sos', { event: 'note', sos: publicSos(r) });
    return [201, note];
  }

  if (method === 'GET' && path === '/teams') return [200, teams];
  if (method === 'PATCH' && (g = m(/^\/teams\/([^/]+)$/))) {
    need(u, ['admin', 'dispatcher']);
    const t = teams.find((x) => String(x.id) === g![1]);
    if (!t) throw new HttpError(404, 'not_found', 'No such team');
    Object.assign(t, body);
    audit(u.username, 'team.update', t.name, body);
    return [200, t];
  }

  if (method === 'GET' && path === '/devices') return [200, devices];
  if (method === 'POST' && path === '/devices') {
    need(u, ['admin']);
    const id = String(body.device_id ?? '').trim();
    if (!/^[A-Za-z0-9_-]{3,32}$/.test(id)) throw new HttpError(422, 'validation_error', 'device_id must be 3-32 letters, digits, - or _');
    if (devices.some((d) => d.device_id === id)) throw new HttpError(409, 'exists', `${id} is already registered`);
    audit(u.username, 'device.register', id);
    devices.push({ device_id: id, label: String(body.label || id), online: false, last_seen: null, battery_v: null, location: null, boot_id: null, state: { ml_health_state: 'STABLE', alert_level: 'none', risk: 0, evidence: [] }, heads: {} });
    return [201, { device_id: id, api_key: `tdk_${crypto.getRandomValues(new Uint32Array(4)).join('').slice(0, 32)}` }];
  }
  if (method === 'POST' && (g = m(/^\/devices\/([^/]+)\/rotate-key$/))) {
    need(u, ['admin']);
    audit(u.username, 'device.rotate_key', decodeURIComponent(g[1]));
    return [200, { api_key: `tdk_${crypto.getRandomValues(new Uint32Array(4)).join('').slice(0, 32)}` }];
  }
  if (method === 'POST' && (g = m(/^\/devices\/([^/]+)\/commands$/))) {
    need(u, ['admin', 'dispatcher']);
    // Mirrors the server's CommandIn validator.
    const params = (body.params ?? {}) as Record<string, unknown>;
    if (body.action === 'set_geofence' && !['lat', 'lng', 'radius_km'].every((k) => typeof params[k] === 'number' && Number.isFinite(params[k])))
      throw new HttpError(422, 'validation_error', 'set_geofence needs numeric lat, lng, radius_km');
    if (body.action === 'buzz') {
      const ms = params.ms ?? 500;
      if (!(typeof ms === 'number' && Number.isInteger(ms) && ms >= 50 && ms <= 10_000)) throw new HttpError(422, 'validation_error', 'buzz ms must be 50..10000');
    }
    return [201, { id: `cmd_${Date.now().toString(36)}`, action: body.action as DeviceAction, params: body.params ?? {}, status: 'queued', created_at: iso() }];
  }
  if (method === 'GET' && (g = m(/^\/devices\/([^/]+)\/frames$/))) return [200, { items: frames(decodeURIComponent(g[1]), Number(q.get('limit') ?? 400)), next_cursor: null }];
  if (method === 'GET' && (g = m(/^\/devices\/([^/]+)\/states$/))) return [200, transitions[decodeURIComponent(g[1])] ?? []];

  if (method === 'GET' && path === '/alerts') {
    const st = q.get('status');
    return [200, { items: alerts.filter((a) => !st || a.status === st), next_cursor: null }];
  }
  if (method === 'POST' && (g = m(/^\/alerts\/([^/]+)\/(ack|resolve)$/))) {
    need(u, ['admin', 'dispatcher', 'responder']);
    const a = alerts.find((x) => String(x.id) === g![1]);
    if (!a) throw new HttpError(404, 'not_found', 'No such alert');
    if (g[2] === 'ack') { a.status = 'acked'; a.acked_by = u.display_name; a.acked_at = iso(); }
    else { a.status = 'resolved'; a.resolved_at = iso(); }
    emit('alerts', { event: g[2] === 'ack' ? 'acked' : 'resolved', alert: a });
    return [200, a];
  }

  if (method === 'GET' && path === '/weather/current') return [200, weatherCurrent()];
  if (method === 'GET' && path === '/weather/forecast') return [200, forecast(Number(q.get('hours') ?? 48))];
  if (method === 'GET' && path === '/weather/model') return [200, modelCard()];

  if (method === 'GET' && path === '/analytics/summary') {
    const open = sosRows.filter((r) => !['resolved', 'cancelled'].includes(r.status));
    return [200, {
      sos_open: open.length, sos_critical: open.filter((r) => r.priority <= 1).length, avg_response_min: an.avgResponseMin(),
      teams_available: teams.filter((t) => t.is_available && t.current_load < t.capacity).length,
      devices_online: devices.filter((d) => d.online).length, alerts_open: alerts.filter((a) => a.status === 'open').length,
    }];
  }
  if (method === 'GET' && path === '/analytics/timeseries') return [200, an.timeseries(q.get('metric') ?? 'sos_created', q.get('bucket') ?? 'hour', q.get('since'))];
  if (method === 'GET' && path === '/analytics/sensors') return [200, an.sensors()];
  if (method === 'GET' && path === '/analytics/performance') return [200, an.performance()];
  if (method === 'GET' && path === '/analytics/geo') return [200, an.geo()];
  if (method === 'GET' && path === '/analytics/models') return [200, an.models()];
  if (method === 'GET' && path === '/analytics/breakdown') {
    const by = q.get('by') ?? 'type';
    const counts = new Map<string, number>();
    for (const r of sosRows) {
      const k = by === 'type' ? r.emergency_type : by === 'status' ? r.status : `P${r.priority}`;
      counts.set(k, (counts.get(k) ?? 0) + 1);
    }
    return [200, { by, items: [...counts].map(([key, count]) => ({ key, count })).sort((a, b) => b.count - a.count) }];
  }
  if (method === 'GET' && path === '/analytics/response-times') return [200, an.responseTimes()];

  const vr = visionRoute(method, path);
  if (vr) return vr;
  const rv = rovRoute(method, path, q, body, u);
  if (rv) return rv;

  if (method === 'POST' && path === '/sms/test') {
    need(u, ['admin']);
    if (!mockSms.configured) throw new HttpError(503, 'sms_not_configured', 'SMS intake is not configured');
    return [200, smsIntake(String(body.from ?? ''), String(body.text ?? ''))];
  }

  if (method === 'GET' && path === '/audit') {
    need(u, ['admin']);
    return [200, auditLog.slice(0, Math.max(1, Math.min(1000, Number(q.get('limit') ?? 200))))];
  }

  if (path === '/users' && method === 'GET') { need(u, ['admin']); return [200, { items: users.map(({ password: _p, ...x }) => x), next_cursor: null }]; }
  if (path === '/users' && method === 'POST') {
    need(u, ['admin']);
    if (users.some((x) => x.username === body.username)) throw new HttpError(409, 'exists', 'Username taken');
    const nu = { id: users.length + 1, username: String(body.username), display_name: String(body.display_name || body.username), role: body.role as User['role'], team_id: (body.team_id as number) ?? null, is_active: true, password: String(body.password) };
    users.push(nu);
    audit(u.username, 'user.create', nu.username, { role: nu.role });
    const { password: _p, ...out } = nu; void _p;
    return [201, out];
  }
  if (method === 'PATCH' && (g = m(/^\/users\/([^/]+)$/))) {
    need(u, ['admin']);
    const x = users.find((y) => String(y.id) === g![1]);
    if (!x) throw new HttpError(404, 'not_found', 'No such user');
    Object.assign(x, body);
    audit(u.username, 'user.update', x.username, Object.fromEntries(Object.entries(body).filter(([k]) => k !== 'password')));
    const { password: _p, ...out } = x; void _p;
    return [200, out];
  }

  throw new HttpError(404, 'not_found', `Mock has no route for ${method} ${path}`);
}

// ─── Install ─────────────────────────────────────────────────────────────────

const realFetch = window.fetch.bind(window);
// ─── SMS intake (mirrors /sms/inbound; /sms/test is the admin dry run that still creates the request) ───

const mockSms = { configured: true };
const SMS_RE = /^\s*SOS\s+(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)(?:\s+P(\d+))?(?:\s+I(\d+))?(?:\s+T([a-z-]+))?\s*(.*)$/i;

function smsIntake(from: string, text: string) {
  const mt = text.match(SMS_RE);
  if (!mt) {
    return { reference_id: null, priority: null, parsed: null, reply: 'TRIDENT: could not read your message. Send: SOS <lat>,<lng> P<people> I<injured> T<type> <note>' };
  }
  const type = (mt[5] ?? 'other').toLowerCase();
  const note = mt[6].trim();
  const parsed = {
    latitude: Number(mt[1]), longitude: Number(mt[2]),
    people_to_rescue: mt[3] ? Number(mt[3]) : 1, people_injured: mt[4] ? Number(mt[4]) : 0,
    emergency_type: (EMERGENCY_TYPES as readonly string[]).includes(type) ? type as EmergencyType : 'other' as EmergencyType,
    note: note || null,
  };
  const lc = note.toLowerCase();
  const vulnerabilities = {
    pregnant: lc.includes('pregnan'), elderly: /elder|old/.test(lc), children: /child|baby|kid/.test(lc),
    disabled: /disab|wheelchair/.test(lc), medical: /medic|insulin|dialysis|oxygen/.test(lc),
  };
  const fields = {
    name: 'SMS sender', age: null, phone: from, email: undefined, address: `${parsed.latitude.toFixed(4)}, ${parsed.longitude.toFixed(4)} (from SMS)`,
    city: '', pincode: '', people_to_rescue: parsed.people_to_rescue, people_injured: parsed.people_injured,
    food_availability: 'limited' as const, water_availability: 'limited' as const, vulnerabilities, emergency_type: parsed.emergency_type,
    additional_info: text, latitude: parsed.latitude, longitude: parsed.longitude, device_id: undefined,
  };
  const dup = sosRows.find((a) => isOpen(a) && a.phone === from);
  const r = makeSos(0, 'pending', 0);
  Object.assign(r, fields, scoreSos(fields), { reference_id: newRef(), created_at: iso(), updated_at: iso(), notes: [], assignments: [], history: [{ status: 'pending', at: iso(), by: 'SMS intake' }], version: 1, assigned_team: null, source: 'sms', duplicate_of: dup?.reference_id ?? null, queued_at: undefined });
  sosRows.unshift(r);
  emit('sos', { event: 'created', sos: publicSos(r) });
  return {
    reference_id: r.reference_id, priority: r.priority, parsed,
    reply: `TRIDENT: request ${r.reference_id} received, priority P${r.priority}. Stay where you are if safe; a team will be assigned. Reply with updates quoting ${r.reference_id}.`,
  };
}

/** Network faults for testing the offline SOS path without DevTools (see __tridentMock below). */
const mockNet = { down: false, latencyMs: 0 };

window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.origin);
  if (!url.pathname.startsWith('/api/v1/')) return realFetch(input, init);
  // DevTools "Offline" (or a forced outage) must look like one to the app, as a real fetch would.
  if (!navigator.onLine || mockNet.down) throw new TypeError('Failed to fetch');
  const method = (init?.method ?? 'GET').toUpperCase();
  const headers = new Headers(init?.headers);
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  const rid = `mock-${(++reqN).toString(36)}-${Date.now().toString(36).slice(-4)}`;
  await new Promise((r, reject) => {
    const t = setTimeout(r, 120 + Math.random() * 260 + mockNet.latencyMs);
    init?.signal?.addEventListener('abort', () => { clearTimeout(t); reject(new DOMException('Aborted', 'AbortError')); });
  });
  try {
    const [status, data] = await route(method, url.pathname.slice('/api/v1'.length), url.searchParams, body, headers);
    return new Response(status === 204 ? null : JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json', 'X-Request-ID': rid } });
  } catch (e) {
    const err = e instanceof HttpError ? e : new HttpError(500, 'internal', (e as Error).message);
    return new Response(JSON.stringify({ error: { code: err.code, message: err.message, details: err.details }, request_id: rid }), { status: err.status, headers: { 'Content-Type': 'application/json', 'X-Request-ID': rid } });
  }
};

setSocketFactory((url) => {
  const token = new URL(url).searchParams.get('token') ?? '';
  const s = new MockSocket();
  if (!tokens.has(token)) setTimeout(() => s.close(), 300);
  return s;
});

// A few audit rows so the admin panel is not empty on first load (oldest first; the log is newest first).
audit('admin', 'auth.login', 'admin', null, Date.now() - 95 * MIN);
audit('admin', 'device.register', 'TRD-W08', null, Date.now() - 80 * MIN);
audit('dispatcher', 'team.update', teams[0].name, { capacity: 3 }, Date.now() - 52 * MIN);
audit('auto-dispatch', 'sos.reallocate_extreme', sosRows[4].reference_id, { team_id: sosRows[4].assigned_team?.id ?? null, from: sosRows[12].reference_id }, Date.now() - 31 * MIN);
audit('dispatcher', 'rov.deploy', 'Neerkuthi 1', { reference_id: sosRows[5].reference_id }, Date.now() - 12 * MIN);

// Test/demo hook: bump a record's version without broadcasting, as if an event were missed,
// so the next write from the UI gets a 409 and the conflict banner can be exercised.
(window as unknown as { __tridentMock: unknown }).__tridentMock = {
  bumpVersion(ref: string) {
    const r = sosRows.find((x) => x.reference_id === ref);
    if (r) { r.version++; r.updated_at = iso(); r.notes.push({ id: Date.now(), text: 'Called the family back', author: 'A. Bose (dispatcher)', at: r.updated_at }); }
    return r?.version;
  },
  /** Plug (true) or unplug (false) the vision camera of a unit, e.g. setVisionCamera('ROV-2', true). */
  setVisionCamera,
  /** false makes POST /sms/test answer 503 (SMS intake not configured). */
  setSmsConfigured(on: boolean) { mockSms.configured = on; return on; },
  /** Fail every API call as a network error (true) or restore (false). */
  setNetworkDown(down: boolean) { mockNet.down = down; return down; },
  /** Extra delay per API call; above 20 s the public SOS POST times out and is queued. */
  setLatency(ms: number) { mockNet.latencyMs = Math.max(0, ms); return mockNet.latencyMs; },
  /** Leave n available teams with room (0 = exhausted, 1 = strained); the rest are full. */
  setTeamsFree(n: number) {
    teams.filter((t) => t.is_available).forEach((t, i) => { t.current_load = i < n ? Math.max(0, t.capacity - 1) : t.capacity; });
    emitCapacityIfChanged();
    return freeTeams().length;
  },
};

setInterval(stepSim, 1500);
setInterval(rovStep, 1000);
setInterval(visionStep, 500);
// eslint-disable-next-line no-console
console.info('[TRIDENT] mock backend active: sign in as admin / dispatcher / responder / viewer, password "trident"');
