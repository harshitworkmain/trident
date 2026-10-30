import { useSyncExternalStore } from 'react';
import { api, freshAccessToken, clearSession } from './client';
import type {
  Alert, AlertEventData, AlertLevel, Capacity, DeviceEventData, DeviceSummary, Hazard, Rov, RovEventData, RovVision,
  SosEventData, SosRecord, StateTransition, SystemEventData, Team, Topic, WeatherCurrent, WeatherEventData, WsEvent, WsHello,
} from './types';
import { alertLevelOf, isUnassigned, stateLabel } from '../lib/states';

// The WebSocket is never the source of truth (contract §1): on every (re)connect we load REST
// snapshots, then apply per-topic deltas. A seq gap on a topic reloads that topic's snapshot.

export type ConnState = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'offline';
export type LoadState = 'loading' | 'ok' | 'error';
type SnapKey = 'sos' | 'alerts' | 'devices' | 'teams' | 'rov' | 'weather' | 'capacity';

export interface TelemetryPoint {
  t: number; // epoch seconds
  bpm: number | null;
  spo2: number | null;
  temp: number | null;
  eda: number | null;
  acc: number | null;
}

export interface Announcement {
  id: number;
  text: string;
  level: 'assertive' | 'polite';
}

export interface LiveState {
  conn: ConnState;
  retryInMs: number | null;
  lastMessageAt: number | null;
  load: Record<SnapKey, LoadState>;
  sos: Record<string, SosRecord>;
  alerts: Record<string, Alert>;
  devices: Record<string, DeviceSummary>;
  teams: Team[];
  rov: Record<string, Rov>;
  weather: WeatherCurrent | null;
  hazards: Hazard[];
  /** GET /dispatch/capacity, replaced by `system` capacity events. Null until loaded or if unsupported. */
  capacity: Capacity | null;
  /** bumps whenever any telemetry buffer changes; buffers themselves are mutable for speed. */
  telemetryTick: number;
  transitions: Record<string, StateTransition[]>;
  announcement: Announcement | null;
}

const TELEMETRY_KEEP = 400; // ~10 min at 1.5 s
export const telemetry = new Map<string, TelemetryPoint[]>();

const initial = (): LiveState => ({
  conn: 'idle',
  retryInMs: null,
  lastMessageAt: null,
  load: { sos: 'loading', alerts: 'loading', devices: 'loading', teams: 'loading', rov: 'loading', weather: 'loading', capacity: 'loading' },
  sos: {}, alerts: {}, devices: {}, teams: [], rov: {}, weather: null, hazards: [], capacity: null,
  telemetryTick: 0, transitions: {}, announcement: null,
});

let state: LiveState = initial();
const listeners = new Set<() => void>();

function set(patch: Partial<LiveState> | ((s: LiveState) => Partial<LiveState>)) {
  const p = typeof patch === 'function' ? patch(state) : patch;
  state = { ...state, ...p };
  listeners.forEach((l) => l());
}

export const liveStore = {
  get: () => state,
  subscribe(l: () => void) {
    listeners.add(l);
    return () => { listeners.delete(l); };
  },
};

export function useLive<T>(selector: (s: LiveState) => T): T {
  return useSyncExternalStore(liveStore.subscribe, () => selector(state), () => selector(state));
}

// ─── Merges (idempotent: snapshots and buffered deltas may overlap) ─────────

// `waiting_min` is true when the server produced the record; we note when that was so the
// queue can keep counting without a refetch. Keyed by object identity: every merge is a new object.
const receivedAt = new WeakMap<SosRecord, number>();
function stamp(rec: SosRecord) { receivedAt.set(rec, Date.now()); return rec; }

/** Minutes this request has waited without a team, extrapolated from the server's `waiting_min`. */
export function waitingMinutes(r: SosRecord, now = Date.now()): number | null {
  if (r.waiting_min == null || !isUnassigned(r)) return null;
  const at = receivedAt.get(r) ?? now;
  return Math.max(0, Math.floor(r.waiting_min + (now - at) / 60_000));
}

export function upsertSos(rec: SosRecord) {
  set((s) => {
    const cur = s.sos[rec.reference_id];
    if (cur && cur.version > rec.version) return {};
    return { sos: { ...s.sos, [rec.reference_id]: stamp(rec) } };
  });
}

export function setCapacity(c: Capacity) {
  set((s) => ({ capacity: c, load: { ...s.load, capacity: 'ok' } }));
}

export function upsertAlert(a: Alert, escalated = false) {
  set((s) => ({ alerts: { ...s.alerts, [String(a.id)]: { ...s.alerts[String(a.id)], ...a, ...(escalated ? { escalated: true } : {}) } } }));
}

export function upsertRov(r: Rov) {
  set((s) => ({ rov: { ...s.rov, [r.id]: { ...s.rov[r.id], ...r } } }));
}

/** Merges a `vision` event into a known unit (unknown ids wait for the next snapshot). */
export function setRovVision(id: string, vision: RovVision) {
  set((s) => (s.rov[id] ? { rov: { ...s.rov, [id]: { ...s.rov[id], vision } } } : {}));
}

function pushTelemetry(id: string, p: TelemetryPoint) {
  let buf = telemetry.get(id);
  if (!buf) telemetry.set(id, (buf = []));
  const last = buf[buf.length - 1];
  if (last && p.t <= last.t) return;
  buf.push(p);
  if (buf.length > TELEMETRY_KEEP) buf.splice(0, buf.length - TELEMETRY_KEEP);
}

/** Lets a detail page seed the live buffer from GET /frames so charts have history immediately. */
export function seedTelemetry(id: string, points: TelemetryPoint[]) {
  const live = telemetry.get(id) ?? [];
  const firstLive = live[0]?.t ?? Infinity;
  const merged = [...points.filter((p) => p.t < firstLive), ...live].slice(-TELEMETRY_KEEP);
  telemetry.set(id, merged);
  set((s) => ({ telemetryTick: s.telemetryTick + 1 }));
}

export interface RovTrackSample { t: number; lat: number; lng: number; depth: number | null }
/** ROV positions from `rov` events, for mission map tracks (seeded from GET /rov/{id}/track). */
export const rovTracks = new Map<string, RovTrackSample[]>();
function pushRovTrack(r: Rov, ts: string) {
  let buf = rovTracks.get(r.id);
  if (!buf) rovTracks.set(r.id, (buf = []));
  const t = Date.parse(r.updated_at || ts) / 1000;
  if (buf.length && t <= buf[buf.length - 1].t) return;
  buf.push({ t, lat: r.latitude!, lng: r.longitude!, depth: r.depth_m });
  if (buf.length > 1800) buf.splice(0, buf.length - 1800);
}
export function seedRovTrack(id: string, pts: RovTrackSample[]) {
  const live = rovTracks.get(id) ?? [];
  const first = live[0]?.t ?? Infinity;
  rovTracks.set(id, [...pts.filter((p) => p.t < first), ...live]);
  set((s) => ({ telemetryTick: s.telemetryTick + 1 }));
}

let announceId = 0;
function announce(text: string, level: Announcement['level']) {
  set({ announcement: { id: ++announceId, text, level } });
}

function applyDevice(d: DeviceEventData, ts: string) {
  const sm = d.summary ?? {};
  set((s) => {
    const cur = s.devices[d.device_id];
    const base: DeviceSummary = cur ?? {
      device_id: d.device_id, label: d.device_id, online: true, last_seen: ts, battery_v: null, location: null,
      state: { ml_health_state: 'STABLE', alert_level: 'none', risk: 0, evidence: [] }, heads: {},
    };
    const next: DeviceSummary = { ...base, last_seen: ts };
    if (d.event === 'offline') next.online = false;
    if (d.event === 'online' || d.event === 'frame' || d.event === 'state') next.online = true;
    if (sm.battery_v != null) next.battery_v = sm.battery_v;
    if (sm.lat != null && sm.lng != null) next.location = { lat: sm.lat, lng: sm.lng };
    if (sm.label) next.label = sm.label;
    if (sm.heads) next.heads = sm.heads;
    const raw = sm.state;
    if (raw && typeof raw === 'object') {
      next.state = { ...base.state, ...raw };
    } else if (typeof raw === 'string') {
      const level: AlertLevel = sm.alert_level ?? alertLevelOf(raw);
      next.state = {
        ml_health_state: raw, alert_level: level, risk: sm.risk ?? base.state.risk,
        evidence: sm.evidence ?? (raw === base.state.ml_health_state ? base.state.evidence : []),
      };
    }
    const patch: Partial<LiveState> = { devices: { ...s.devices, [d.device_id]: next } };
    if (next.state.ml_health_state !== base.state.ml_health_state || d.event === 'state') {
      const tr: StateTransition = { state: next.state.ml_health_state, alert_level: next.state.alert_level, risk: next.state.risk, evidence: next.state.evidence, at: ts };
      const prev = s.transitions[d.device_id] ?? [];
      if (prev[prev.length - 1]?.state !== tr.state) patch.transitions = { ...s.transitions, [d.device_id]: [...prev, tr].slice(-200) };
    }
    if (d.event === 'frame') {
      pushTelemetry(d.device_id, {
        t: Date.parse(ts) / 1000, bpm: sm.bpm ?? null, spo2: sm.spo2 ?? null, temp: sm.temp_skin_c ?? null,
        eda: sm.eda_us ?? null, acc: sm.acc_std_g ?? null,
      });
      patch.telemetryTick = s.telemetryTick + 1;
    }
    return patch;
  });
}

function applyEvent(ev: WsEvent) {
  switch (ev.topic) {
    case 'sos': {
      const d = ev.data as SosEventData;
      if (!d?.sos) return;
      upsertSos(d.sos);
      if (d.event === 'created' && d.sos.priority <= 2) announce(`New priority ${d.sos.priority} SOS ${d.sos.reference_id}, ${d.sos.city || d.sos.address}`, 'polite');
      if (d.event === 'assigned') scheduleTeamsReload();
      return;
    }
    case 'alerts': {
      const d = ev.data as AlertEventData;
      if (!d?.alert) return;
      upsertAlert(d.alert, d.event === 'escalated');
      if (d.event === 'opened') {
        announce(d.alert.state === 'SOS_BUTTON'
          ? `Critical alert: SOS button pressed on ${d.alert.device_id}`
          : `Critical alert: ${d.alert.device_id} ${stateLabel(d.alert.state).toLowerCase()}`, 'assertive');
      }
      if (d.event === 'escalated') announce(`Alert escalated, not acknowledged: ${d.alert.device_id}`, 'assertive');
      return;
    }
    case 'devices':
      applyDevice(ev.data as DeviceEventData, ev.ts);
      return;
    case 'weather': {
      const d = ev.data as WeatherEventData;
      set({ weather: d.current ?? state.weather, ...(d.forecast_summary?.hazards ? { hazards: d.forecast_summary.hazards } : {}) });
      return;
    }
    case 'rov': {
      const d = ev.data as RovEventData;
      if (d?.event === 'vision') { if (d.rov_id != null && d.vision) setRovVision(String(d.rov_id), d.vision); return; }
      if (d?.rov?.id) upsertRov(d.rov);
      if (d?.rov?.latitude != null && d.rov.longitude != null) pushRovTrack(d.rov, ev.ts);
      return;
    }
    case 'system': {
      const d = ev.data as SystemEventData;
      if (d?.event !== 'capacity') return;
      const { event: _e, ...cap } = d as { event: 'capacity' } & Capacity;
      void _e;
      const prev = state.capacity?.status;
      setCapacity(cap);
      if (cap.status === 'exhausted' && prev !== 'exhausted' && cap.waiting.length) {
        announce(`No free teams. ${cap.waiting.length} urgent request${cap.waiting.length === 1 ? '' : 's'} waiting.`, 'polite');
      }
      return;
    }
    default:
  }
}

// ─── Snapshots ───────────────────────────────────────────────────────────────

const topicSnaps: Record<Topic, SnapKey[]> = {
  sos: ['sos', 'teams'], alerts: ['alerts'], devices: ['devices'], weather: ['weather'], rov: ['rov'], system: ['capacity'],
};

async function loadSnap(key: SnapKey) {
  set((s) => ({ load: { ...s.load, [key]: s.load[key] === 'ok' ? 'ok' : 'loading' } }));
  try {
    switch (key) {
      case 'sos': {
        const page = await api.listSos({ limit: 200 });
        set({ sos: Object.fromEntries(page.items.map((r) => [r.reference_id, stamp(r)])) });
        break;
      }
      case 'alerts': {
        const items = await api.alerts();
        set({ alerts: Object.fromEntries(items.map((a) => [String(a.id), a])) });
        break;
      }
      case 'devices': {
        const items = await api.devices();
        set({ devices: Object.fromEntries(items.map((d) => [d.device_id, d])) });
        break;
      }
      case 'teams':
        set({ teams: await api.teams() });
        break;
      case 'capacity':
        set({ capacity: await api.capacity() });
        break;
      case 'rov': {
        const items = await api.rovs();
        set({ rov: Object.fromEntries(items.map((r) => [r.id, r])) });
        break;
      }
      case 'weather': {
        const [cur, fc] = await Promise.allSettled([api.weatherCurrent(), api.forecast(48)]);
        if (cur.status === 'rejected' && fc.status === 'rejected') throw cur.reason;
        set({
          weather: cur.status === 'fulfilled' ? cur.value : state.weather,
          hazards: fc.status === 'fulfilled' ? fc.value.hazards : state.hazards,
        });
        break;
      }
    }
    set((s) => ({ load: { ...s.load, [key]: 'ok' } }));
  } catch {
    set((s) => ({ load: { ...s.load, [key]: 'error' } }));
  }
}

export function reloadSnapshot(key: SnapKey) {
  return loadSnap(key);
}

let teamsTimer: number | undefined;
function scheduleTeamsReload() {
  window.clearTimeout(teamsTimer);
  teamsTimer = window.setTimeout(() => void loadSnap('teams'), 800);
}

// Per-topic sequencing. While a topic's snapshot loads, its events are buffered and replayed after.
const lastSeq = new Map<Topic, number>();
const buffering = new Map<Topic, WsEvent[]>();

async function resyncTopic(topic: Topic) {
  if (buffering.has(topic)) return;
  buffering.set(topic, []);
  lastSeq.delete(topic);
  await Promise.all(topicSnaps[topic].map(loadSnap));
  const buf = buffering.get(topic) ?? [];
  buffering.delete(topic);
  buf.sort((a, b) => a.seq - b.seq).forEach((ev) => handleEvent(ev));
}

function handleEvent(ev: WsEvent) {
  const buf = buffering.get(ev.topic);
  if (buf) { buf.push(ev); return; }
  const last = lastSeq.get(ev.topic);
  if (last !== undefined) {
    if (ev.seq <= last) return; // duplicate or stale
    if (ev.seq > last + 1) {
      buffering.delete(ev.topic);
      void resyncTopic(ev.topic).then(() => handleEvent(ev));
      return;
    }
  }
  lastSeq.set(ev.topic, ev.seq);
  applyEvent(ev);
}

// ─── Socket lifecycle ────────────────────────────────────────────────────────

export interface SocketLike {
  readyState: number;
  onopen: ((ev: Event) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  onerror: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  send(data: string): void;
  close(code?: number, reason?: string): void;
}

type SocketFactory = (url: string) => SocketLike;
let socketFactory: SocketFactory = (url) => new WebSocket(url);
/** Mock mode swaps the transport; real mode never imports the mock. */
export function setSocketFactory(f: SocketFactory) { socketFactory = f; }

let socket: SocketLike | null = null;
let running = false;
let attempt = 0;
let retryTimer: number | undefined;
let pingTimer: number | undefined;
let watchdog: number | undefined;

const ALL_TOPICS: Topic[] = ['sos', 'alerts', 'devices', 'weather', 'rov', 'system'];

function wsUrl(token: string) {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${location.host}/ws?token=${encodeURIComponent(token)}`;
}

async function connect() {
  if (!running) return;
  if (!navigator.onLine) { set({ conn: 'offline', retryInMs: null }); return; }
  set({ conn: attempt === 0 ? 'connecting' : 'reconnecting', retryInMs: null });
  const token = await freshAccessToken();
  if (!running) return;
  if (!token) { stopLive(); clearSession(); return; }

  const ws = socketFactory(wsUrl(token));
  socket = ws;
  ws.onopen = () => {
    attempt = 0;
    set({ conn: 'open', lastMessageAt: Date.now() });
    ws.send(JSON.stringify({ type: 'subscribe', topics: ALL_TOPICS }));
    // Fresh snapshots for every topic: events missed while disconnected are unrecoverable otherwise.
    lastSeq.clear();
    ALL_TOPICS.forEach((t) => void resyncTopic(t));
    window.clearInterval(pingTimer);
    pingTimer = window.setInterval(() => { try { ws.send(JSON.stringify({ type: 'ping' })); } catch { /* closing */ } }, 25_000);
    armWatchdog(ws);
  };
  ws.onmessage = (m) => {
    armWatchdog(ws);
    set({ lastMessageAt: Date.now() });
    let msg: WsEvent | WsHello | { type: string };
    try { msg = JSON.parse(String(m.data)); } catch { return; }
    if (msg.type === 'event') handleEvent(msg as WsEvent);
  };
  ws.onerror = () => { /* onclose follows */ };
  ws.onclose = () => {
    if (socket !== ws) return;
    socket = null;
    window.clearInterval(pingTimer);
    window.clearTimeout(watchdog);
    if (running) scheduleReconnect();
  };
}

function armWatchdog(ws: SocketLike) {
  window.clearTimeout(watchdog);
  // Pings every 25 s should earn a pong or event; 70 s of silence means a dead half-open socket.
  watchdog = window.setTimeout(() => { try { ws.close(4000, 'watchdog'); } catch { /* ignore */ } }, 70_000);
}

function scheduleReconnect() {
  if (!navigator.onLine) { set({ conn: 'offline', retryInMs: null }); return; }
  const base = Math.min(30_000, 1000 * 2 ** attempt);
  const delay = Math.round(base * (0.75 + Math.random() * 0.5));
  attempt += 1;
  set({ conn: 'reconnecting', retryInMs: delay });
  window.clearTimeout(retryTimer);
  retryTimer = window.setTimeout(() => void connect(), delay);
}

function onOnline() {
  if (!running || socket) return;
  attempt = 0;
  window.clearTimeout(retryTimer);
  void connect();
}
function onOffline() {
  if (!running) return;
  set({ conn: 'offline', retryInMs: null });
}

export function startLive() {
  if (running) return;
  running = true;
  attempt = 0;
  window.addEventListener('online', onOnline);
  window.addEventListener('offline', onOffline);
  void connect();
}

export function stopLive() {
  running = false;
  window.removeEventListener('online', onOnline);
  window.removeEventListener('offline', onOffline);
  window.clearTimeout(retryTimer);
  window.clearInterval(pingTimer);
  window.clearTimeout(watchdog);
  const s = socket;
  socket = null;
  try { s?.close(1000, 'logout'); } catch { /* ignore */ }
  lastSeq.clear();
  buffering.clear();
  telemetry.clear();
  rovTracks.clear();
  state = initial();
  listeners.forEach((l) => l());
}

/** Manual "retry now" from the connection indicator. */
export function reconnectNow() {
  if (!running) return;
  window.clearTimeout(retryTimer);
  attempt = 0;
  if (socket) { try { socket.close(4001, 'manual'); } catch { /* ignore */ } } else void connect();
}
