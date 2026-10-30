/* TRIDENT service worker (hand-written, no dependencies).
 *
 * - Precaches the app shell: index.html plus the hashed assets it references. The list below is
 *   rewritten at build time by the `swPrecache` plugin in vite.config.ts; in dev it stays empty and
 *   the worker is never registered (see main.tsx).
 * - /assets/* is cache-first (file names are content-hashed), navigations are network-first and
 *   fall back to the cached index.html, so the public SOS form opens with no connection.
 * - /api, /ws and /healthz are never touched: live data always goes to the network.
 * - Background Sync: sends the SOS outbox that the page mirrors into Cache Storage, with the same
 *   Idempotency-Key per request, so the server counts each request once.
 */
const BUILD = { version: 'dev', precache: [] }; // replaced at build time by vite.config.ts (swPrecache)

const SHELL = `trident-shell-${BUILD.version}`;
const ASSETS = `trident-assets-${BUILD.version}`;
const OUTBOX_CACHE = 'trident-outbox';
const OUTBOX_URL = '/__trident/outbox';
const SYNC_TAG = 'trident-sos-outbox';
const NAV_TIMEOUT_MS = 4000;
const LIVE = /^\/(api|ws|healthz)(\/|$)/;

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL);
    // cache: 'reload' skips the HTTP cache so the shell always matches this build.
    await cache.addAll(BUILD.precache.map((url) => new Request(url, { cache: 'reload' })));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keep = new Set([SHELL, ASSETS, OUTBOX_CACHE]);
    for (const key of await caches.keys()) {
      if (key.startsWith('trident-') && !keep.has(key)) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // map tiles and other third parties: untouched
  if (LIVE.test(url.pathname)) return; // API and WebSocket: never from cache
  if (req.mode === 'navigate') {
    event.respondWith(navigate(req));
  } else if (url.pathname.startsWith('/assets/')) {
    event.respondWith(cacheFirst(req));
  } else if (BUILD.precache.includes(url.pathname)) {
    event.respondWith(networkFirst(req));
  }
});

async function navigate(req) {
  try {
    return await withTimeout(fetch(req), NAV_TIMEOUT_MS);
  } catch {
    const shell = await caches.match('/index.html', { cacheName: SHELL });
    return shell || Response.error();
  }
}

async function cacheFirst(req) {
  const hit = await caches.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) {
    const cache = await caches.open(ASSETS);
    await cache.put(req, res.clone());
  }
  return res;
}

async function networkFirst(req) {
  try {
    const res = await fetch(req);
    if (res.ok) {
      const cache = await caches.open(SHELL);
      await cache.put(req, res.clone());
    }
    return res;
  } catch {
    return (await caches.match(req)) || Response.error();
  }
}

function withTimeout(promise, ms) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('timeout')), ms);
    promise.then((v) => { clearTimeout(t); resolve(v); }, (e) => { clearTimeout(t); reject(e); });
  });
}

// ─── Background Sync: the SOS outbox ────────────────────────────────────────

self.addEventListener('sync', (event) => {
  if (event.tag === SYNC_TAG) event.waitUntil(flushOutbox());
});

async function flushOutbox() {
  const cache = await caches.open(OUTBOX_CACHE);
  const hit = await cache.match(OUTBOX_URL);
  if (!hit) return;
  let items;
  try { items = await hit.json(); } catch { items = []; }
  const left = [];
  let offline = false;
  for (const item of items) {
    if (offline) { left.push(item); continue; }
    try {
      const res = await fetch('/api/v1/sos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'Idempotency-Key': item.key },
        body: JSON.stringify(item.payload),
      });
      if (res.ok) {
        const body = await res.json();
        await notify({ type: 'outbox-sent', key: item.key, res: body });
      } else if (res.status === 408 || res.status === 429 || res.status >= 500) {
        left.push(item);
      }
      // Any other 4xx: drop it here; the page retries it itself and shows the server's reason.
    } catch {
      offline = true;
      left.push(item);
    }
  }
  if (left.length) await cache.put(OUTBOX_URL, new Response(JSON.stringify(left), { headers: { 'Content-Type': 'application/json' } }));
  else await cache.delete(OUTBOX_URL);
  // Rejecting asks the browser to fire the sync again later.
  if (offline) throw new Error('offline');
}

async function notify(msg) {
  const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  clients.forEach((c) => c.postMessage(msg));
}
