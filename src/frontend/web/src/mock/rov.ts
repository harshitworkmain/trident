// Mock ROV fleet: a 1 Hz kinematic simulation plus the control endpoints (takeover/release/control/stop...).
import type { Rov, RovCommand, User } from '../api/types';
import { devices, iso, jitter, missionVictims, rovs, sosRows, teams } from './data';
import { audit, emit, HttpError } from './http';

const ACTIVE = ['deploying', 'on_mission', 'returning'];
const lastCmd = new Map<string, number>(); // for the 120 s dead-man
const M_PER_DEG = 111_000;
const tracks = new Map<string, { t: string; lat: number; lng: number; depth_m: number | null; heading_deg: number | null; battery_pct: number | null; water_temp_c: number | null }[]>();
const motion = new Map<string, RovCommand | null>(); // current manual command per ROV

// Seed 20 min of track behind each active unit so the map has history immediately.
for (const r of rovs) {
  if (!ACTIVE.includes(r.status) || r.latitude == null || r.longitude == null) continue;
  const pts = [];
  for (let i = 1200; i > 0; i -= 10) {
    const k = i / 1200;
    const lat = r.latitude + ((r.home?.lat ?? r.latitude) - r.latitude) * k * 0.6 + Math.sin(i / 90) * 0.0004;
    const lng = r.longitude + ((r.home?.lng ?? r.longitude) - r.longitude) * k * 0.6 + Math.cos(i / 110) * 0.0004;
    pts.push({ t: iso(i * 1000), lat, lng, depth_m: +(1 + Math.sin(i / 60) * 0.4).toFixed(2), heading_deg: (r.heading_deg ?? 0) + Math.sin(i / 200) * 30, battery_pct: (r.battery_pct ?? 50) + k * 12, water_temp_c: 27.9 });
  }
  tracks.set(r.id, pts);
}

function dist(a: { lat: number; lng: number }, b: { lat: number; lng: number }) {
  const dx = (a.lng - b.lng) * Math.cos((a.lat * Math.PI) / 180) * M_PER_DEG;
  const dy = (a.lat - b.lat) * M_PER_DEG;
  return Math.hypot(dx, dy);
}

function moveAlong(r: Rov, headingDeg: number, metres: number) {
  const h = (headingDeg * Math.PI) / 180;
  r.latitude = (r.latitude ?? 0) + (Math.cos(h) * metres) / M_PER_DEG;
  r.longitude = (r.longitude ?? 0) + (Math.sin(h) * metres) / (M_PER_DEG * Math.cos(((r.latitude ?? 0) * Math.PI) / 180));
}

let t = 0;
export function rovStep() {
  t++;
  const now = iso();
  for (const r of rovs) {
    if (!ACTIVE.includes(r.status) || r.latitude == null || r.longitude == null) continue;
    const pos = { lat: r.latitude, lng: r.longitude };
    if (r.mode === 'manual') {
      if (motion.get(r.id) && Date.now() - (lastCmd.get(r.id) ?? 0) > 120_000) { motion.set(r.id, null); r.speed_pct = 0; }
      const cmd = motion.get(r.id);
      const v = ((r.speed_pct ?? 0) / 100) * 2.5; // up to 2.5 m/s
      if (cmd === 'forward') moveAlong(r, r.heading_deg ?? 0, v);
      if (cmd === 'backward') moveAlong(r, (r.heading_deg ?? 0) + 180, v * 0.6);
      if (cmd === 'left') r.heading_deg = ((r.heading_deg ?? 0) - 12 + 360) % 360;
      if (cmd === 'right') r.heading_deg = ((r.heading_deg ?? 0) + 12) % 360;
      if (cmd === 'up') r.depth_m = Math.max(0, +((r.depth_m ?? 0) - 0.15).toFixed(2));
      if (cmd === 'down') r.depth_m = Math.min(6, +((r.depth_m ?? 0) + 0.15).toFixed(2));
    } else {
      const target = r.status === 'returning' ? r.home : r.target;
      if (target) {
        const d = dist(pos, target);
        if (d > 25) {
          const want = (Math.atan2((target.lng - pos.lng) * Math.cos((pos.lat * Math.PI) / 180), target.lat - pos.lat) * 180) / Math.PI;
          r.heading_deg = Math.round(((want + 360) % 360) * 10) / 10;
          r.speed_pct = r.status === 'returning' ? 70 : 60;
          moveAlong(r, r.heading_deg, Math.min(d, 1.8 * (r.speed_pct / 60)));
          r.depth_m = +Math.max(0.3, jitter(r.depth_m ?? 0.8, 0.05)).toFixed(2);
        } else if (r.status === 'returning') {
          Object.assign(r, { status: 'idle', speed_pct: 0, depth_m: 0, target: null, mission_reference_id: null, team_id: null, lights_on: false });
          emit('rov', { event: 'recalled', rov: r });
          continue;
        } else {
          // On station: slow search circle around the SOS location.
          if (r.status === 'deploying') { r.status = 'on_mission'; emit('rov', { event: 'deployed', rov: r }); }
          r.speed_pct = 25;
          r.heading_deg = ((r.heading_deg ?? 0) + 9) % 360;
          moveAlong(r, r.heading_deg, 0.9);
          r.depth_m = +Math.min(4, Math.max(0.6, jitter(r.depth_m ?? 1.2, 0.08))).toFixed(2);
        }
      }
    }
    r.battery_pct = Math.max(0, +((r.battery_pct ?? 50) - 0.01 - ((r.speed_pct ?? 0) / 100) * 0.03).toFixed(2));
    r.water_temp_c = +(27.8 - (r.depth_m ?? 0) * 0.15 + jitter(0, 0.03)).toFixed(2);
    r.last_seen = now;
    r.updated_at = now;
    const tr = tracks.get(r.id) ?? [];
    tr.push({ t: now, lat: r.latitude!, lng: r.longitude!, depth_m: r.depth_m, heading_deg: r.heading_deg, battery_pct: r.battery_pct, water_temp_c: r.water_temp_c });
    if (tr.length > 3600) tr.splice(0, tr.length - 3600);
    tracks.set(r.id, tr);
    emit('rov', { event: 'telemetry', rov: r });
  }
}

function findRov(id: string) {
  const r = rovs.find((x) => x.id === id);
  if (!r) throw new HttpError(404, 'not_found', `No ROV ${id}`);
  return r;
}

function role(u: User, roles: User['role'][]) {
  if (!roles.includes(u.role)) throw new HttpError(403, 'forbidden', `Your role (${u.role}) cannot do this`);
}

export function missions() {
  return rovs.filter((r) => ACTIVE.includes(r.status) || (r.status === 'stopped' && r.mission_reference_id)).map((rov) => {
    const sos = sosRows.find((s) => s.reference_id === rov.mission_reference_id) ?? null;
    const team = teams.find((x) => String(x.id) === String(rov.team_id));
    const refs = (rov.mission_reference_id && missionVictims[rov.mission_reference_id]) || (sos ? [sos.reference_id] : []);
    const victims = refs.map((ref) => sosRows.find((s) => s.reference_id === ref)).filter(Boolean).map((s) => ({
      reference_id: s!.reference_id, name: s!.name, status: s!.status, priority: s!.priority, device_id: s!.device_id ?? null,
      device: s!.device_id ? devices.find((d) => d.device_id === s!.device_id) ?? null : null,
    }));
    const { history: _h, notes: _n, assignments: _a, tracking_token: _t, ...sosRec } = sos ?? ({} as never);
    void _h; void _n; void _a; void _t;
    return { rov, sos: sos ? sosRec : null, team: team ? { id: team.id, name: team.name } : null, victims };
  });
}

export function rovRoute(method: string, path: string, q: URLSearchParams, body: Record<string, unknown>, u: User): [number, unknown] | null {
  if (method === 'GET' && path === '/rov') return [200, rovs];
  if (method === 'GET' && path === '/missions') return [200, missions()];
  let g = path.match(/^\/rov\/([^/]+)\/track$/);
  if (method === 'GET' && g) {
    findRov(g[1]);
    const since = Date.now() - Number(q.get('minutes') ?? 30) * 60_000;
    return [200, (tracks.get(g[1]) ?? []).filter((p) => Date.parse(p.t) >= since)];
  }
  g = path.match(/^\/rov\/([^/]+)\/bridge-key$/);
  if (method === 'POST' && g) {
    role(u, ['admin']);
    const r = findRov(g[1]);
    Object.assign(r, { simulated: false, link: 'offline', video_url: (body.video_url as string) || r.video_url }); // like the server: empty keeps the old URL
    audit(u.username, 'rov.bridge_key', r.name, { video_url: r.video_url });
    return [200, { rov_id: r.id, api_key: `rbk_${crypto.getRandomValues(new Uint32Array(4)).join('').slice(0, 32)}` }];
  }
  g = path.match(/^\/rov\/([^/]+)\/vision-key$/);
  if (method === 'POST' && g) {
    role(u, ['admin']);
    const r = findRov(g[1]);
    audit(u.username, 'rov.vision_key', r.name);
    return [200, { rov_id: r.id, api_key: `rvk_${crypto.getRandomValues(new Uint32Array(4)).join('').slice(0, 32)}` }];
  }
  g = path.match(/^\/rov\/([^/]+)\/(deploy|recall|stop|reset|takeover|release|control)$/);
  if (method !== 'POST' || !g) return null;
  const r = findRov(g[1]);
  const action = g[2];
  const heldByOther = r.mode === 'manual' && r.pilot && r.pilot !== u.username;
  if (r.link === 'offline' && action !== 'stop') throw new HttpError(409, 'link_offline', `${r.name} has no link`);

  switch (action) {
    case 'stop':
      role(u, ['admin', 'dispatcher', 'responder']);
      motion.set(r.id, null);
      Object.assign(r, { status: 'stopped', speed_pct: 0 });
      emit('rov', { event: 'stopped', rov: r });
      break;
    case 'takeover':
      role(u, ['admin', 'dispatcher']);
      if (heldByOther && u.role !== 'admin') throw new HttpError(409, 'control_held', `${r.pilot} is driving ${r.name}`, { pilot: r.pilot });
      if (!ACTIVE.includes(r.status) && r.status !== 'stopped') throw new HttpError(409, 'not_on_mission', `${r.name} is not on a mission`);
      motion.set(r.id, null);
      lastCmd.set(r.id, Date.now());
      Object.assign(r, { mode: 'manual', pilot: u.username, status: r.status === 'stopped' ? (r.target ? 'on_mission' : 'idle') : r.status, speed_pct: 0 });
      emit('rov', { event: 'mode', rov: r });
      break;
    case 'release':
      role(u, ['admin', 'dispatcher']);
      if (heldByOther && u.role !== 'admin') throw new HttpError(409, 'control_held', `${r.pilot} is driving ${r.name}`, { pilot: r.pilot });
      motion.set(r.id, null);
      Object.assign(r, { mode: 'auto', pilot: null, status: r.target ? (r.status === 'on_mission' ? 'on_mission' : 'deploying') : 'idle' });
      emit('rov', { event: 'mode', rov: r });
      break;
    case 'control': {
      if (r.mode !== 'manual') throw new HttpError(409, 'not_manual', 'Take manual control first');
      if (r.pilot !== u.username) throw new HttpError(409, 'control_held', `${r.pilot} is driving ${r.name}`, { pilot: r.pilot });
      const cmd = String(body.command) as RovCommand;
      const sp = Math.max(0, Math.min(100, Number(body.speed_pct ?? r.speed_pct ?? 0)));
      if (cmd === 'lights_on' || cmd === 'lights_off') r.lights_on = cmd === 'lights_on';
      else if (cmd === 'stop') { motion.set(r.id, null); r.speed_pct = 0; }
      else { motion.set(r.id, cmd); r.speed_pct = sp; }
      lastCmd.set(r.id, Date.now());
      emit('rov', { event: 'control', rov: r });
      break;
    }
    case 'recall':
      role(u, ['admin', 'dispatcher']);
      if (heldByOther) throw new HttpError(409, 'control_held', `${r.pilot} is driving ${r.name}`, { pilot: r.pilot });
      motion.set(r.id, null);
      Object.assign(r, { status: 'returning', mode: 'auto', pilot: null });
      emit('rov', { event: 'recalled', rov: r });
      break;
    case 'reset':
      role(u, ['admin', 'dispatcher']);
      if (r.status !== 'stopped') throw new HttpError(409, 'conflict', `${r.name} is not stopped`);
      // Like the server: clearing a stop sends the unit home on autopilot; the mission is not resumed.
      motion.set(r.id, null);
      Object.assign(r, { status: 'returning', mode: 'auto', pilot: null });
      emit('rov', { event: 'recalled', rov: r });
      break;
    case 'deploy': {
      role(u, ['admin', 'dispatcher']);
      const ref = String(body.reference_id ?? '');
      const s = sosRows.find((x) => x.reference_id === ref);
      if (!s) throw new HttpError(422, 'validation_error', `Unknown SOS ${ref || '(empty)'}`);
      if (ACTIVE.includes(r.status)) throw new HttpError(409, 'busy', `${r.name} is already on a mission`);
      if (s.latitude == null || s.longitude == null) throw new HttpError(422, 'no_location', `${ref} has no coordinates`);
      Object.assign(r, { status: 'deploying', mode: 'auto', pilot: null, target: { lat: s.latitude, lng: s.longitude }, mission_reference_id: ref, team_id: s.assigned_team?.id ?? null, depth_m: 0.4 });
      emit('rov', { event: 'deployed', rov: r });
      break;
    }
  }
  r.updated_at = iso();
  return [200, r];
}

// ─── Vision (YOLOv8n + LBPH worker) ──────────────────────────────────────────
// ROV-1 carries a camera with the vision worker; ROV-2 has none, so its panel shows the placeholder.
// The real stream is MJPEG; the mock hands out a blob URL of an animated SVG with drawn boxes instead.

const cameras = new Set<string>(['ROV-1']);
const tickets = new Set<string>();
const streamBlobs = new Map<string, string>();
let vt = 0;

function frameSvg(r: Rov) {
  const victim = sosRows.find((s) => s.reference_id === r.mission_reference_id)?.name ?? 'Unknown';
  const box = (x: number, y: number, w: number, h: number, color: string, label: string, dx = 0, dur = 6) => `
    <g><animateTransform attributeName="transform" type="translate" values="0 0; ${dx} ${dx / 4}; 0 0" dur="${dur}s" repeatCount="indefinite"/>
      <rect x="${x}" y="${y}" width="${w}" height="${h}" fill="none" stroke="${color}" stroke-width="2"/>
      <rect x="${x}" y="${y - 16}" width="${label.length * 6.6 + 8}" height="16" fill="${color}"/>
      <text x="${x + 4}" y="${y - 4}" font-family="monospace" font-size="11" fill="#0d0e10">${label}</text></g>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" width="640" height="360">
  <defs><linearGradient id="w" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#21414a"/><stop offset="1" stop-color="#0b1a1f"/></linearGradient></defs>
  <rect width="640" height="360" fill="url(#w)"/>
  <g stroke="#3d6470" stroke-opacity="0.35">${Array.from({ length: 9 }, (_, i) => `<path d="M0 ${40 + i * 36} Q160 ${30 + i * 36} 320 ${44 + i * 36} T640 ${38 + i * 36}" fill="none"><animate attributeName="d" dur="${4 + (i % 3)}s" repeatCount="indefinite" values="M0 ${40 + i * 36} Q160 ${30 + i * 36} 320 ${44 + i * 36} T640 ${38 + i * 36};M0 ${44 + i * 36} Q160 ${48 + i * 36} 320 ${36 + i * 36} T640 ${44 + i * 36};M0 ${40 + i * 36} Q160 ${30 + i * 36} 320 ${44 + i * 36} T640 ${38 + i * 36}"/></path>`).join('')}</g>
  <rect x="300" y="250" width="300" height="70" fill="#2b2b2b" opacity="0.8"/>
  <ellipse cx="200" cy="200" rx="34" ry="60" fill="#5a4a3e" opacity="0.85"/><circle cx="200" cy="128" r="18" fill="#7a6250"/>
  <ellipse cx="455" cy="175" rx="24" ry="44" fill="#4a4038" opacity="0.8"/><circle cx="455" cy="122" r="13" fill="#6b5545"/>
  ${box(160, 108, 84, 160, '#e8a33d', 'person 0.88 ~2.4 m', 6)}
  ${box(180, 108, 40, 40, '#3fb8a1', `${victim.split(' ')[0]} 64%`, 6)}
  ${box(428, 106, 56, 118, '#e8a33d', 'person 0.71 ~4.9 m', -4, 7)}
  ${box(300, 250, 300, 70, '#8fa3b8', 'boat 0.63 ~6.8 m', 0, 9)}
  <text x="10" y="350" font-family="monospace" font-size="11" fill="#ece8e1" opacity="0.8">${r.name} · MOCK FEED</text>
</svg>`;
}

function visionFor(r: Rov): NonNullable<Rov['vision']> {
  vt++;
  const victim = sosRows.find((s) => s.reference_id === r.mission_reference_id)?.name ?? 'Unknown';
  const w = (v: number, a: number) => +(v + Math.sin(vt / 7 + a) * v * 0.08).toFixed(1);
  const second = Math.floor(vt / 20) % 3 !== 2; // the farther person drifts in and out of view
  const objects = [
    { label: 'person', confidence: +(0.86 + Math.sin(vt / 5) * 0.04).toFixed(2), distance_m: w(2.4, 0), box: [160, 108, 244, 268] as [number, number, number, number] },
    ...(second ? [{ label: 'person', confidence: +(0.7 + Math.sin(vt / 4) * 0.05).toFixed(2), distance_m: w(4.9, 1), box: [428, 106, 484, 224] as [number, number, number, number] }] : []),
    { label: 'boat', confidence: 0.63, distance_m: w(6.8, 2), box: [300, 250, 600, 320] as [number, number, number, number] },
    ...(vt % 10 < 4 ? [{ label: 'dog', confidence: 0.41, distance_m: null, box: null }] : []),
  ];
  return {
    active: true, fps: +(3.6 + Math.sin(vt / 9) * 0.3).toFixed(1), last_frame_at: iso(), persons: second ? 2 : 1, model: 'yolov8n + lbph',
    faces: [
      { name: victim, match: +(0.62 + Math.sin(vt / 6) * 0.03).toFixed(2), distance_m: w(2.3, 0) },
      ...(second && vt % 6 < 3 ? [{ name: 'Unknown', match: null, distance_m: w(5.1, 1) }] : []),
    ],
    objects,
  };
}

export function visionStep() {
  for (const r of rovs) {
    const on = cameras.has(r.id) && r.status === 'on_mission' && r.link !== 'offline';
    if (on) r.vision = visionFor(r);
    else if (r.vision?.active !== false) r.vision = { active: false };
    else continue;
    emit('rov', { event: 'vision', rov_id: String(r.id), vision: r.vision });
  }
}

/** Test hook: give a unit a camera (true) or unplug it (false). */
export function setVisionCamera(id: string, on: boolean) {
  if (on) cameras.add(id); else cameras.delete(id);
  return on;
}

export function visionRoute(method: string, path: string): [number, unknown] | null {
  const g = path.match(/^\/rov\/([^/]+)\/vision\/ticket$/);
  if (method !== 'POST' || !g) return null;
  const r = findRov(g[1]);
  if (!r.vision?.active) throw new HttpError(409, 'no_feed', `${r.name} has no vision feed`);
  const ticket = `vt_${crypto.getRandomValues(new Uint32Array(3)).join('')}`;
  tickets.add(ticket);
  let blob = streamBlobs.get(r.id);
  if (!blob) streamBlobs.set(r.id, (blob = URL.createObjectURL(new Blob([frameSvg(r)], { type: 'image/svg+xml' }))));
  // A real url is /api/v1/rov/{id}/vision/stream?ticket=…; the fragment keeps each mock ticket's URL unique.
  return [200, { ticket, expires_in: 60, url: `${blob}#${ticket}` }];
}
