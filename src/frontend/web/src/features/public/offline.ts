// Offline support for the public SOS form: a local outbox that keeps retrying, the compact SMS
// fallback, and a small connectivity store. Everything here must work with no network at all.
import { useEffect, useSyncExternalStore } from 'react';
import { api, ApiError } from '../../api/client';
import type { SosSubmit, SosSubmitResponse } from '../../api/types';

// ─── Outbox ──────────────────────────────────────────────────────────────────
// Each item keeps the Idempotency-Key it was first sent with; the server de-duplicates on it,
// so retries (from any tab, or from the service worker) can never create a second request.

export const OUTBOX_KEY = 'trident.sos.outbox';
const LAST_KEY = 'trident.sos.last';
const RETRY_MS = 30_000;
/** Background Sync tag; public/sw.js listens for it. */
export const SYNC_TAG = 'trident-sos-outbox';
/** Cache the service worker reads the outbox from (it cannot read localStorage). */
const MIRROR_CACHE = 'trident-outbox';
const MIRROR_URL = '/__trident/outbox';

export interface OutboxItem {
  key: string;
  payload: SosSubmit;
  queued_at: string;
  attempts: number;
  last_try?: string;
  /** Set when the server refused it (4xx other than 408/429): retrying will not help. */
  rejected?: { status: number; message: string; request_id: string | null };
}

interface OutboxState {
  items: OutboxItem[];
  sending: boolean;
  /** Responses for items sent during this page's life, by key. */
  sent: Record<string, SosSubmitResponse>;
  online: boolean;
}

function readItems(): OutboxItem[] {
  try {
    const raw = localStorage.getItem(OUTBOX_KEY);
    const v = raw ? (JSON.parse(raw) as OutboxItem[]) : [];
    return Array.isArray(v) ? v.filter((x) => x && typeof x.key === 'string' && x.payload) : [];
  } catch {
    return [];
  }
}

let state: OutboxState = {
  items: readItems(),
  sending: false,
  sent: {},
  online: typeof navigator === 'undefined' ? true : navigator.onLine,
};
const listeners = new Set<() => void>();
function setState(p: Partial<OutboxState>) {
  state = { ...state, ...p };
  listeners.forEach((l) => l());
}
const subscribe = (l: () => void) => { listeners.add(l); return () => { listeners.delete(l); }; };

function writeItems(items: OutboxItem[]) {
  try {
    if (items.length) localStorage.setItem(OUTBOX_KEY, JSON.stringify(items));
    else localStorage.removeItem(OUTBOX_KEY);
  } catch { /* storage blocked: the in-memory copy still retries while the page is open */ }
  setState({ items });
  void mirror(items);
}

/** Copies the retryable items into Cache Storage so a Background Sync can send them with the page closed. */
async function mirror(items: OutboxItem[]) {
  try {
    if (!('caches' in window)) return;
    const c = await caches.open(MIRROR_CACHE);
    const live = items.filter((i) => !i.rejected).map(({ key, payload }) => ({ key, payload }));
    if (live.length) await c.put(MIRROR_URL, new Response(JSON.stringify(live), { headers: { 'Content-Type': 'application/json' } }));
    else await c.delete(MIRROR_URL);
  } catch { /* best effort */ }
}

function rememberLast(res: SosSubmitResponse) {
  try { localStorage.setItem(LAST_KEY, JSON.stringify({ ref: res.reference_id, token: res.tracking_token })); } catch { /* ignore */ }
}

function markSent(key: string, res: SosSubmitResponse) {
  rememberLast(res);
  setState({ sent: { ...state.sent, [key]: res } });
  writeItems(readItems().filter((i) => i.key !== key));
}

export function enqueue(key: string, payload: SosSubmit) {
  const items = readItems().filter((i) => i.key !== key);
  items.push({ key, payload, queued_at: new Date().toISOString(), attempts: 0 });
  writeItems(items);
  void requestBackgroundSync();
}

export function discard(key: string) {
  writeItems(readItems().filter((i) => i.key !== key));
}

/** A network failure or timeout (status 0), a 408/429 or a 5xx: worth retrying later. */
export function isRetryable(e: unknown) {
  if (!(e instanceof ApiError)) return true;
  return e.status === 0 || e.status === 408 || e.status === 429 || e.status >= 500;
}

let flushing: Promise<void> | null = null;

/** Sends every queued item once. Safe to call often: concurrent calls share one pass. */
export function flushOutbox(): Promise<void> {
  if (flushing) return flushing;
  flushing = (async () => {
    const pending = readItems().filter((i) => !i.rejected);
    if (!pending.length) return;
    setState({ sending: true });
    try {
      for (const item of pending) {
        try {
          const res = await api.submitSos(item.payload, item.key, 25_000);
          markSent(item.key, res);
        } catch (e) {
          const items = readItems();
          const cur = items.find((i) => i.key === item.key);
          if (!cur) continue; // sent by another tab or the service worker meanwhile
          cur.attempts += 1;
          cur.last_try = new Date().toISOString();
          if (!isRetryable(e)) {
            const err = e as ApiError;
            cur.rejected = { status: err.status, message: err.message, request_id: err.requestId };
          }
          writeItems(items);
          if (isRetryable(e) && e instanceof ApiError && e.status === 0) break; // still offline: stop this pass
        }
      }
    } finally {
      setState({ sending: false });
    }
  })().finally(() => { flushing = null; });
  return flushing;
}

async function requestBackgroundSync() {
  try {
    if (!('serviceWorker' in navigator)) return;
    const reg = await navigator.serviceWorker.getRegistration();
    const sync = (reg as (ServiceWorkerRegistration & { sync?: { register(tag: string): Promise<void> } }) | undefined)?.sync;
    if (sync) await sync.register(SYNC_TAG);
  } catch { /* unsupported or refused: the page keeps retrying itself */ }
}

let started = false;

/** Starts the retry loop for the life of the page (called once from main.tsx). */
export function startOutbox() {
  if (started) return;
  started = true;
  const onOnline = () => { setState({ online: true }); void flushOutbox(); };
  const onOffline = () => setState({ online: false });
  window.addEventListener('online', onOnline);
  window.addEventListener('offline', onOffline);
  // Another tab changed the outbox.
  window.addEventListener('storage', (e) => { if (e.key === OUTBOX_KEY) setState({ items: readItems() }); });
  // The service worker sent an item through Background Sync.
  navigator.serviceWorker?.addEventListener('message', (e: MessageEvent) => {
    const m = e.data as { type?: string; key?: string; res?: SosSubmitResponse } | null;
    if (m?.type === 'outbox-sent' && m.key && m.res) markSent(m.key, m.res);
  });
  window.setInterval(() => { if (readItems().some((i) => !i.rejected)) void flushOutbox(); }, RETRY_MS);
  if (state.items.length) {
    void mirror(state.items);
    void flushOutbox();
  }
}

export function useOutbox() {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

// ─── SMS fallback ────────────────────────────────────────────────────────────

const SMS_KEY = 'trident.public.sms';
const SMS_MAX = 160;

export function cachedSmsNumber(): string | null {
  try { return localStorage.getItem(SMS_KEY); } catch { return null; }
}

const smsListeners = new Set<() => void>();
const smsSubscribe = (l: () => void) => { smsListeners.add(l); return () => { smsListeners.delete(l); }; };

/** Remembers the SMS number from GET /public/summary so it is there when the network is not. */
export function rememberSmsNumber(n: string | null | undefined) {
  if (n === undefined) return; // older server: keep what we had
  try {
    if (n) localStorage.setItem(SMS_KEY, n);
    else localStorage.removeItem(SMS_KEY);
  } catch { /* ignore */ }
  smsListeners.forEach((l) => l());
}

let smsFetchedAt = 0;
/** Refreshes the cached number at most every 5 minutes; failures (offline) keep the cached value. */
export function refreshSmsNumber() {
  if (Date.now() - smsFetchedAt < 5 * 60_000) return;
  smsFetchedAt = Date.now();
  api.publicSummary().then((s) => rememberSmsNumber(s.sms_number)).catch(() => { smsFetchedAt = 0; });
}

/** Cached SMS number, refreshed from the public summary when the network allows. */
export function useSmsNumber(): string | null {
  const n = useSyncExternalStore(smsSubscribe, cachedSmsNumber, cachedSmsNumber);
  useEffect(() => { refreshSmsNumber(); }, []);
  return n;
}

const VUL_WORD: Record<keyof SosSubmit['vulnerabilities'], string> = {
  elderly: 'elderly', children: 'children', pregnant: 'pregnant', disabled: 'cannot walk', medical: 'needs medicine',
};

const clean = (s: string) => s.replace(/\s+/g, ' ').trim();

/**
 * The compact format the server parses from an SMS:
 *   SOS <lat>,<lng> P<people> I<injured> T<type> <short note>
 * e.g. `SOS 13.0120,80.2410 P3 I1 Tflood elderly, water critical`. Coordinates are left out when
 * unknown (the address then leads the note). Never longer than one 160-character SMS.
 */
export function composeSms(p: Pick<SosSubmit, 'latitude' | 'longitude' | 'people_to_rescue' | 'people_injured' | 'emergency_type' | 'vulnerabilities' | 'water_availability' | 'food_availability' | 'address' | 'additional_info'>): string {
  const hasGps = p.latitude != null && p.longitude != null && Number.isFinite(p.latitude) && Number.isFinite(p.longitude);
  const head = ['SOS'];
  if (hasGps) head.push(`${p.latitude!.toFixed(4)},${p.longitude!.toFixed(4)}`);
  head.push(`P${p.people_to_rescue}`, `I${p.people_injured}`, `T${p.emergency_type || 'other'}`);
  const notes: string[] = [];
  // Without GPS the address is the only way to be found, so it goes first.
  const address = clean(p.address ?? '').replace(/^GPS [\d., -]+$/, '');
  if (!hasGps && address) notes.push(address);
  notes.push(...(Object.keys(VUL_WORD) as (keyof typeof VUL_WORD)[]).filter((k) => p.vulnerabilities?.[k]).map((k) => VUL_WORD[k]));
  if (p.water_availability === 'critical' || p.water_availability === 'none') notes.push(`water ${p.water_availability}`);
  if (p.food_availability === 'none') notes.push('no food');
  if (p.additional_info) notes.push(clean(p.additional_info));
  const base = head.join(' ');
  const note = notes.join(', ');
  if (!note) return base;
  const room = SMS_MAX - base.length - 1;
  return room > 0 ? `${base} ${note.length > room ? note.slice(0, room).trimEnd() : note}` : base.slice(0, SMS_MAX);
}

export function smsHref(number: string, body: string) {
  return `sms:${number.replace(/[^\d+]/g, '')}?body=${encodeURIComponent(body)}`;
}
