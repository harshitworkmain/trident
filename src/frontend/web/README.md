# TRIDENT web console

React 18 + TypeScript (strict) + Vite. It holds the public request-help site and the staff operations console, and is built to static files that FastAPI serves at `/`, with an SPA fallback.

## Run

```bash
cd src/frontend/web
npm install
npm run dev          # http://localhost:5173 — proxies /api, /ws, /healthz to http://localhost:8000
npm run dev:mock     # same, with the in-app mock backend (no API needed)
npm run typecheck    # tsc --noEmit
npm run build        # typecheck + production build → dist/
```

- To point the dev proxy at another API, set `TRIDENT_API=http://host:port npm run dev`.
- `npm run build:mock` builds a demo bundle with the mock compiled in. It writes to `dist/` too, so rebuild with `npm run build` before you deploy.

### Environment

| Variable | Effect |
|---|---|
| `VITE_MOCK=1` | Enables the mock backend. It is set by `--mode mock`, from `.env.mock`. |
| `VITE_MAP_TILE_URL` | Overrides the Leaflet tile template. CARTO `dark_all` needs an API key (keyless requests return "API KEY REQUIRED" watermark tiles): `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?api_key=…`. |
| `VITE_MAP_TILE_ATTRIBUTION` | Attribution for a custom tile source. |
| `VITE_MAP_TILE_DARKEN=1` | Applies the dark CSS filter to a light custom source. |

With no tile URL set, the map uses Stadia Maps `alidade_smooth_dark` (already dark, no CSS filter; keyless on localhost, a deployed domain must be registered with Stadia). After 3 tile errors in a row it falls back to OpenStreetMap standard tiles darkened with a CSS filter, and after 3 more it shows "Map tiles unavailable".

## Mock mode

`src/mock/` is loaded only when `VITE_MOCK=1`, through a dynamic import in `main.tsx` that is dead code in a real build, so the real `dist/` contains none of it. It provides:

- **Fake REST.** A `fetch` wrapper scoped to `/api/v1/*` implements every endpoint in `docs/PLATFORM_DESIGN.md` §2. It includes JWT-shaped login/refresh, RBAC, 409 version conflicts, `Idempotency-Key`, ROV takeover and control, and the analytics reports.
- **A fake WebSocket.** It follows the same event contract:
  - `devices` frames every 1.5 s
  - `rov` telemetry at 1 Hz
  - new SOS and state changes that open alerts
  - "another dispatcher" status moves
  - alert escalation after 2 min
- **Analytics computed from the mock's own state** (the frames it emitted, its SOS rows and its alerts), not constants. The model metrics are copied from `docs/reports/WEARABLE_FINAL_MODELS.md` and `docs/reports/WEARABLE_FUSION_REPLAY.md`.
- **Users** `admin`, `dispatcher`, `responder` (team 1) and `viewer`. The password for all of them is `trident`.
- **Dispatch capacity.** Teams start "strained" (one free team). `GET /dispatch/capacity`, `system` capacity events, `POST /sos/{ref}/reallocate`, `source` / `duplicate_of` / `waiting_min` / `awaiting_resources` on SOS rows, and a `LOST_CONTACT` alert every ~90 s.
- **Wearable SOS button and SMS intake.** An `SOS_BUTTON` alert opens every ~2 min. `POST /sms/test` (admin) parses the compact SMS format and creates a `source: "sms"` request.
- **ROV vision.** Neerkuthi 1 (ROV-1) has a camera with the vision worker: `vision` events on the `rov` topic twice a second (persons, faces, objects with distances), and `POST /rov/{id}/vision/ticket` returns a blob URL of an animated SVG with drawn boxes in place of the real MJPEG stream. ROV-2 has no camera, so its panel shows the "No camera feed" placeholder.
- **Wearable link.** `POST /sos/{ref}/link-device` confirms (`{"device_id": "TRD-W05"}`) or removes (`{"device_id": null}`) the band on a request; the band-raised request is `device_verified`, the others are claims.
- **Offline.** With DevTools set to Offline, every `/api/v1` call fails like a real network error.
- **Test hooks** on `window.__tridentMock`:
  - `bumpVersion('SOS-…')` changes a record silently, so the next write gets a 409.
  - `setTeamsFree(n)`: `0` makes capacity exhausted, `1` strained.
  - `setVisionCamera('ROV-1', false)` unplugs a unit's vision camera (`true` plugs it in; it streams while the unit is on a mission).
  - `setSmsConfigured(false)` makes `POST /sms/test` return 503.
  - `setNetworkDown(true)` fails every API call; `setLatency(25000)` makes the SOS POST time out and queue.

## Structure

```
src/
  api/        types.ts (contract types), client.ts (fetch, tokens, single-flight refresh), live.ts (WebSocket store)
  lib/        format, permissions (role matrix), states (SOS state machine, fusion state labels), hooks, motion
  ui/         primitives (Button, Chip, StateChip, Panel, Stat, Meter…), DataTable, Dialog, Toast, charts (uPlot, Sparkline), MapView (Leaflet), KeyReveal, effects
  features/   public (landing, SOS form, tracking), auth, shell, ops, sos, alerts, wearables, rov (fleet + missions), weather, analytics, admin
  mock/       mock backend (VITE_MOCK only)
  styles/     tokens.css (all design tokens), base.css, components.css, layout.css
```

### Data flow

- **Auth.** The access token is held in memory and the refresh token in `localStorage`; `client.ts` explains the trade-off. A 401 triggers one refresh, shared by all concurrent requests, and is then retried once. Every 5xx is toasted with its `request_id`.
- **Real time** (`api/live.ts`):
  1. After login the app opens `/ws?token=`.
  2. On every connect it loads the REST snapshots for all topics. Events that arrive during a load are buffered and replayed after it.
  3. Each topic tracks its own `seq`. A gap reloads that topic.
  4. Reconnects use exponential backoff with jitter (1 s to 30 s). A watchdog closes a socket that has been silent for 70 s, and the browser's online/offline events are honoured.
  5. Wearable vitals for the charts come only from `devices` frame events, seeded from `GET /devices/{id}/frames`.
- **ROV camera.** When a unit's `vision.active` is true, the mission panel asks `POST /rov/{id}/vision/ticket` for a single-use ticket and puts the returned `url` (annotated MJPEG) in an `<img>`. On an image error, on `active` going false→true, or when frames resume after a gap longer than the server's 30 s idle cut-off, it fetches a new ticket (backoff 1 s to 15 s); a ticket is never reused. Detections come from `rov` events (`event: "vision"`), merged into the unit.
- **Error boundaries.** The routed page and each mission panel sit in an error boundary: a render crash shows "This panel failed to render" with "Reload panel" and the error details, the shell keeps working, and a route change clears it.
- **Optimistic concurrency.** SOS writes send `version`. On a 409 with code `conflict`, the detail page reloads the record, shows "Changed by someone else" and offers "Re-apply my change".

## Offline and weak connections

- **App shell.** `public/sw.js` is a hand-written service worker, registered from `main.tsx` in real production builds only. At build time the `swPrecache` plugin in `vite.config.ts` writes the precache list into `dist/sw.js`: `index.html`, the JS and CSS it references, their woff2 fonts, the logo and the manifest. `/assets/*` is cache-first. Navigations are network-first (4 s) and fall back to the cached `index.html`. `/api`, `/ws` and `/healthz` never touch the cache.
- **SOS outbox** (`features/public/offline.ts`). If the phone is offline, or the POST fails with a network error, a timeout (20 s), a 408, a 429 or a 5xx, the request is saved in `localStorage` under `trident.sos.outbox`. It keeps the same `Idempotency-Key`. The outbox is retried on `online` events and every 30 s, and through Background Sync where supported. For that, the page mirrors the outbox into Cache Storage, which the worker can read. Any other 4xx stops the retries and shows the server's reason.
- **SMS fallback.** `GET /public/summary` returns `sms_number`, which is cached in `trident.public.sms`. The fallback composes `SOS <lat>,<lng> P<people> I<injured> T<type> <note>`, at most 160 characters.
- **Test it.** Run `npm run dev:mock`, fill in the form, set DevTools → Network to Offline and press Send. Then go back online. To test the service worker, run `npm run build && npx vite preview` and use DevTools → Application → Service workers → Offline.

## Design tokens (`src/styles/tokens.css`)

- **Surfaces**, from the background up: `--bg-0 #0d0e10`, `--bg-1 #141619`, `--bg-2 #1b1e22`, `--bg-3 #24282e`. Hairlines are `--line #2a2e35`.
- **Text**: `--fg #ece8e1`, `--fg-2 #aaa59c` and `--fg-3 #8b867e`. All three are at least 4.5:1 on `--bg-1`.
- **The one accent**: `--accent #e8a33d`. It marks focus rings, primary actions and the selected state.
- **Semantic colours**, used only for meaning:
  - `--critical #ef5b5b`
  - `--warning #ee8a3a`
  - `--ok #3fb8a1`
  - `--info #8fa3b8`
- **Type**: IBM Plex Sans for the UI and IBM Plex Mono for numbers, IDs and times (tabular, slashed zero). Both are self-hosted through `@fontsource`, latin subset only.
- **Spacing**: an 8 px grid (`--s-1` … `--s-8`).
- **Motion**: `--t-fast` is 120 ms, `--t-ui` 200 ms and `--t-reveal` 400 ms. All three drop to 0 under `prefers-reduced-motion`.
- **Dim variant**: an optional slightly lighter theme, `:root[data-theme="dim"]`.

### Text effects

- **Landing headline**: a masked line-by-line reveal (CSS).
- **Decode/scramble settle**: SOS reference IDs (new rows, detail and confirmation) and wearable state names each settle in when they change. It lasts about 360 ms, and screen readers get only the final text.
- **Critical chips**: a thin light sweep crosses the chip every 3.2 s.
- **KPIs**: values count up over 350 ms with a one-off accent flash.

Every effect is disabled under `prefers-reduced-motion`.

### Keyboard

| Keys | Action |
|---|---|
| `?` | Help |
| `1`–`7` | Pages |
| `/` | Search the SOS queue |
| `j` / `k` | Move in the queue |
| `Enter` | Open the selected SOS |
| `a` | Acknowledge the oldest open alert |
| `m` | Toggle the map |
| `W` `A` `S` `D`, `R` / `F`, `L`, `Space` | Drive a ROV: move, up/down, lights, stop. Only works with a mission panel focused and while you hold manual control. Hold a key to move; releasing it sends `stop`. |

## What the UI relies on beyond the written contract

The UI reads all of the following defensively; anything missing simply isn't shown.

- **`GET /devices/{id}/frames`**: each frame has a timestamp in `ts`, `received_at` or `at`. Fusion output may be nested under `fusion` or be flat (`ml_health_state`, `ml_risk_score`, `alert_level`).
- **List responses**: both `{items, next_cursor}` and bare arrays are accepted. That applies to `/teams`, `/devices`, `/alerts`, `/users`, `/rov`, `/missions` and `/rov/{id}/track`.
- **Analytics reports**: the timeseries, breakdown and response-times payloads are expected as:

  ```
  timeseries     → {metric, bucket, points:[{t, value}]}
  breakdown      → {by, items:[{key, count}]}
  response-times → {items:[{priority, n, p50, p90, p95}]}   (minutes)
  ```
- **409 bodies**: a refusal because someone else holds ROV control should carry `error.code: "control_held"` and `details.pilot`. A version conflict should use `error.code: "conflict"`.
- **Capacity contract** (all optional, read defensively): SOS `source`, `duplicate_of`, `waiting_min` and `awaiting_resources`; `GET /dispatch/capacity` (the banner is hidden if it fails); `system` events `{event: "capacity", …}`; `POST /sos/{ref}/reallocate`, where a 409 reloads the queue and the suggestions. The queue extrapolates `waiting_min` from the time the record arrived.
- **Optional fields**:
  - SOS history entries: `by` and `note`
  - notes: `author` and `at` (or `created_at`)
  - users: `is_active`
  - models report: `generated_at`
