// Plausible demo data for VITE_MOCK=1. Never imported in real mode.
import type {
  Alert, DeviceSummary, Forecast, ForecastStep, Hazard, ModelCard, Rov, SosNote, SosRecord, SosStatus,
  StateTransition, Team, User, WeatherCurrent, Assignment,
} from '../api/types';
import { alertLevelOf } from '../lib/states';

export const iso = (msAgo = 0) => new Date(Date.now() - msAgo).toISOString().replace(/\.\d{3}Z$/, 'Z');
const MIN = 60_000;
const HOUR = 60 * MIN;

let seed = 7;
export function rand() {
  seed = (seed * 16807) % 2147483647;
  return (seed - 1) / 2147483646;
}
export const pick = <T,>(xs: readonly T[]) => xs[Math.floor(rand() * xs.length)];
export const jitter = (v: number, s: number) => v + (rand() - 0.5) * 2 * s;

export const PLACES = [
  { area: 'Velachery', pin: '600042', lat: 12.9815, lng: 80.218 },
  { area: 'Mudichur', pin: '600048', lat: 12.912, lng: 80.07 },
  { area: 'Pallikaranai', pin: '600100', lat: 12.935, lng: 80.213 },
  { area: 'Tambaram West', pin: '600045', lat: 12.9249, lng: 80.1 },
  { area: 'Adyar', pin: '600020', lat: 13.0012, lng: 80.2565 },
  { area: 'Saidapet', pin: '600015', lat: 13.0213, lng: 80.2231 },
  { area: 'Kotturpuram', pin: '600085', lat: 13.018, lng: 80.24 },
  { area: 'Ennore', pin: '600057', lat: 13.2146, lng: 80.3203 },
  { area: 'Tiruvottiyur', pin: '600019', lat: 13.1586, lng: 80.3018 },
  { area: 'Perumbakkam', pin: '600100', lat: 12.899, lng: 80.2 },
  { area: 'Manali', pin: '600068', lat: 13.1667, lng: 80.2667 },
  { area: 'Korattur', pin: '600080', lat: 13.11, lng: 80.183 },
  { area: 'Royapuram', pin: '600013', lat: 13.1137, lng: 80.2954 },
  { area: 'Ashok Nagar', pin: '600083', lat: 13.0359, lng: 80.212 },
];

const NAMES = ['R. Lakshmi', 'S. Karthik', 'M. Fathima', 'P. Venkatesan', 'A. Priya', 'K. Murugan', 'J. Thomas', 'N. Revathi',
  'G. Senthil', 'D. Anitha', 'V. Ramesh', 'B. Kavitha', 'H. Abdul Rahman', 'T. Sangeetha', 'E. Joseph', 'C. Meena'];
const STREETS = ['2nd Cross St', 'Main Rd', 'Lake View Rd', 'Gandhi St', 'Bharathi Nagar 4th St', 'Church Rd', 'Canal Bank Rd', 'Temple St'];

export const users: (User & { password: string })[] = [
  { id: 1, username: 'admin', display_name: 'Control Room Admin', role: 'admin', team_id: null, is_active: true, password: 'trident' },
  { id: 2, username: 'dispatcher', display_name: 'S. Raghavan', role: 'dispatcher', team_id: null, is_active: true, password: 'trident' },
  { id: 3, username: 'responder', display_name: 'Insp. K. Durai', role: 'responder', team_id: 1, is_active: true, password: 'trident' },
  { id: 4, username: 'viewer', display_name: 'GCC Liaison', role: 'viewer', team_id: null, is_active: true, password: 'trident' },
];

// Loads are set so capacity starts "strained" (one team with room: SDRF Adyar). Assigning it makes
// capacity "exhausted"; window.__tridentMock.setTeamsFree(n) changes this at runtime.
export const teams: Team[] = [
  { id: 1, name: 'NDRF 4th Bn · Alpha', type: 'boat', team_type: 'ndrf', location: { lat: 12.975, lng: 80.205 }, capacity: 4, current_load: 4, is_available: true, deployment_mode: 'boat' },
  { id: 2, name: 'TNFRS Tambaram', type: 'fire_rescue', team_type: 'fire_rescue', location: { lat: 12.925, lng: 80.118 }, capacity: 3, current_load: 3, is_available: true, deployment_mode: 'road' },
  { id: 3, name: 'Coast Guard Ennore', type: 'coast_guard', team_type: 'coast_guard', location: { lat: 13.205, lng: 80.315 }, capacity: 3, current_load: 3, is_available: true, deployment_mode: 'boat' },
  { id: 4, name: 'SDRF Adyar', type: 'sdrf', team_type: 'sdrf', location: { lat: 13.006, lng: 80.25 }, capacity: 4, current_load: 3, is_available: true, deployment_mode: 'boat' },
  { id: 5, name: 'GCC Medical Unit 7', type: 'medical', team_type: 'medical', location: { lat: 13.03, lng: 80.225 }, capacity: 2, current_load: 2, is_available: false, deployment_mode: 'ambulance' },
  { id: 6, name: 'Fishermen Volunteers Kasimedu', type: 'volunteer', team_type: 'volunteer', location: { lat: 13.125, lng: 80.293 }, capacity: 5, current_load: 5, is_available: true, deployment_mode: 'boat' },
];

const DEVICE_LABELS = ['Rescuer · Insp. Durai', 'Rescuer · HC Selvam', 'Evacuee · Velachery camp #12', 'Rescuer · Diver Arun',
  'Evacuee · Mudichur #3', 'Volunteer · Kasimedu boat 2', 'Evacuee · Pallikaranai #7', 'Rescuer · CG Sailor Imran'];

export interface DeviceSim {
  id: string;
  base: { bpm: number; spo2: number; temp: number; eda: number };
  t: number; // phase
}

export const devices: DeviceSummary[] = DEVICE_LABELS.map((label, i) => {
  const p = PLACES[i % PLACES.length];
  const state = i === 2 ? 'CONCUSSIVE_STASIS' : i === 4 ? 'ELEVATED_STRESS' : 'STABLE';
  return {
    device_id: `TRD-W${String(i + 1).padStart(2, '0')}`,
    label,
    online: i !== 6,
    last_seen: iso(i === 6 ? 7 * MIN : 1000),
    battery_v: i === 5 ? 3.42 : jitter(3.95, 0.12),
    location: { lat: jitter(p.lat, 0.004), lng: jitter(p.lng, 0.004) },
    boot_id: `b${(1000 + i * 37).toString(16)}`,
    state: {
      ml_health_state: state,
      alert_level: alertLevelOf(state),
      risk: state === 'CONCUSSIVE_STASIS' ? 0.9 : state === 'ELEVATED_STRESS' ? 0.35 : 0.05,
      evidence: state === 'CONCUSSIVE_STASIS'
        ? ['fall p=0.94 @ 5.8 g', 'immobile 74 s', 'HR 58 trusted']
        : state === 'ELEVATED_STRESS' ? ['stress p=0.91, activity rest', 'HR 104 trusted'] : ['HR 78 trusted'],
    },
    heads: { stress: state === 'ELEVATED_STRESS' ? 0.91 : 0.12, fall: state === 'CONCUSSIVE_STASIS' ? 0.94 : 0.02, activity: i % 3 === 0 ? 'active' : 'rest', hr_trust: 0.88, rhythm: 0.04 },
  };
});

export const deviceSims: DeviceSim[] = devices.map((d, i) => ({
  id: d.device_id,
  base: {
    bpm: d.state.ml_health_state === 'CONCUSSIVE_STASIS' ? 58 : d.state.ml_health_state === 'ELEVATED_STRESS' ? 104 : 72 + i * 3,
    spo2: d.state.ml_health_state === 'CONCUSSIVE_STASIS' ? 93 : 97,
    temp: 33.6 - (i % 3) * 0.4,
    eda: d.state.ml_health_state === 'ELEVATED_STRESS' ? 9.5 : 3 + i * 0.3,
  },
  t: i * 13,
}));

export function sampleVitals(sim: DeviceSim, t: number) {
  const { base } = sim;
  return {
    bpm: Math.round(base.bpm + 4 * Math.sin((t + sim.t) / 9) + jitter(0, 2)),
    spo2: Math.min(100, Math.round(base.spo2 + jitter(0, 1))),
    temp: +(base.temp + 0.2 * Math.sin((t + sim.t) / 40) + jitter(0, 0.05)).toFixed(2),
    eda: +(Math.max(0.2, base.eda + 0.8 * Math.sin((t + sim.t) / 15) + jitter(0, 0.3))).toFixed(2),
    acc: +(Math.max(0.005, (sim.id === 'TRD-W03' ? 0.01 : 0.08) + jitter(0, 0.04))).toFixed(3),
  };
}

// ─── SOS ─────────────────────────────────────────────────────────────────────

export interface SosRow extends SosRecord {
  /** Same shape as the server's event_out: `by`/`actor` and `text`/`note` carry the same values. */
  history: { kind?: 'status' | 'assign'; status: SosStatus; at: string; by?: string; actor?: string; team_id?: number | string; text?: string; note?: string }[];
  notes: SosNote[];
  assignments: Assignment[];
  tracking_token: string;
  /** When it last became unassigned (creation, or a team moved away); waiting_min counts from here. */
  queued_at?: string;
}

let refCounter = 0;
export function newRef() {
  const chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
  refCounter++;
  let s = '';
  for (let i = 0; i < 6; i++) s += chars[Math.floor(rand() * chars.length)];
  return `SOS-${s}`;
}

export function scoreSos(r: Pick<SosRecord, 'people_injured' | 'people_to_rescue' | 'vulnerabilities' | 'food_availability' | 'water_availability' | 'emergency_type' | 'device_id'>) {
  const reasons: string[] = [];
  let score = 20;
  if (r.people_injured > 0) { score += 12 + 6 * Math.min(r.people_injured, 4); reasons.push(`${r.people_injured} injured`); }
  if (r.people_to_rescue >= 5) { score += 10; reasons.push(`${r.people_to_rescue} people`); }
  const v = r.vulnerabilities;
  if (v.medical) { score += 12; reasons.push('medical need'); }
  if (v.elderly) { score += 6; reasons.push('elderly'); }
  if (v.children) { score += 5; reasons.push('children'); }
  if (v.pregnant) { score += 8; reasons.push('pregnant'); }
  if (v.disabled) { score += 6; reasons.push('mobility impaired'); }
  if (r.water_availability === 'none' || r.water_availability === 'critical') { score += 8; reasons.push(`water ${r.water_availability}`); }
  if (r.food_availability === 'none') { score += 4; reasons.push('no food'); }
  if (r.emergency_type === 'dam-breach' || r.emergency_type === 'tsunami') { score += 15; reasons.push(r.emergency_type.replace('-', ' ')); }
  if (r.device_id === 'TRD-W03') { score += 20; reasons.push('wearable: CONCUSSIVE_STASIS'); }
  score = Math.min(100, score);
  const priority = score >= 70 ? 1 : score >= 55 ? 2 : score >= 40 ? 3 : score >= 28 ? 4 : 5;
  return { priority_score: score, priority, priority_reasons: reasons.length ? reasons : ['no risk factors reported'] };
}

/** An assignment as the server records it: a kind "assign" history event plus the matching assignments[] item. */
export function assignEvent(team: { id: number | string; name: string }, by: string, at: string, text: string) {
  return {
    history: { kind: 'assign' as const, status: 'assigned' as SosStatus, at, by, actor: by, team_id: team.id, text, note: text },
    assignment: { team_id: team.id, team_name: team.name, assigned_at: at, assigned_by: by, at, by, actor: by, text } satisfies Assignment,
  };
}

const FLOW: SosStatus[] = ['pending', 'triaged', 'assigned', 'en_route', 'on_scene', 'resolved'];

export function makeSos(i: number, status: SosStatus, ageMin: number): SosRow {
  const p = PLACES[i % PLACES.length];
  const injured = i % 4 === 0 ? 1 + (i % 3) : 0;
  const vul = { pregnant: i % 7 === 3, elderly: i % 3 === 0, children: i % 2 === 1, disabled: i % 9 === 4, medical: i % 5 === 0 };
  const base = {
    name: NAMES[i % NAMES.length],
    age: 24 + ((i * 13) % 50),
    phone: `98${String(40000000 + i * 1234567).slice(0, 8)}`,
    email: undefined,
    address: `${1 + ((i * 7) % 40)}, ${STREETS[i % STREETS.length]}, ${p.area}`,
    city: 'Chennai',
    pincode: p.pin,
    people_to_rescue: 1 + ((i * 5) % 9),
    people_injured: injured,
    food_availability: (['adequate', 'limited', 'critical', 'none'] as const)[i % 4],
    water_availability: (['limited', 'critical', 'adequate', 'none'] as const)[i % 4],
    vulnerabilities: vul,
    emergency_type: (['flood', 'water-level-rising', 'flood', 'medical', 'storm', 'flood', 'dam-breach', 'other'] as const)[i % 8],
    additional_info: i % 3 === 0 ? 'Ground floor fully submerged, we are on the terrace. Power cut since morning.' : undefined,
    latitude: jitter(p.lat, 0.006),
    longitude: jitter(p.lng, 0.006),
    device_id: i === 2 ? 'TRD-W03' : undefined,
  };
  const created = ageMin * MIN;
  const idx = status === 'cancelled' ? 1 : FLOW.indexOf(status);
  const history: SosRow['history'] = [];
  const team = idx >= 2 && status !== 'cancelled' ? teams[i % teams.length] : null;
  let assigned: ReturnType<typeof assignEvent> | null = null;
  for (let k = 0; k <= idx; k++) {
    const at = iso(created - (k * created) / (idx + 1.5));
    if (FLOW[k] === 'assigned' && team) {
      assigned = assignEvent(team, 'S. Raghavan', at, `Assigned ${team.name}`);
      history.push(assigned.history);
    } else {
      const by = k === 0 ? 'public form' : k === 1 ? 'auto-triage' : 'S. Raghavan';
      history.push({ kind: 'status', status: FLOW[k], at, by, actor: by });
    }
  }
  if (status === 'cancelled') history.push({ kind: 'status', status: 'cancelled', at: iso(created / 3), by: 'S. Raghavan', actor: 'S. Raghavan', text: 'Duplicate of an earlier request', note: 'Duplicate of an earlier request' });
  return {
    reference_id: newRef(),
    ...base,
    ...scoreSos(base),
    status,
    version: history.length,
    assigned_team: team ? { id: team.id, name: team.name } : null,
    created_at: iso(created),
    updated_at: history[history.length - 1].at,
    history,
    notes: idx >= 2 ? [{ id: i * 10, text: 'Called back, family confirmed on terrace. 2 elderly, 1 child.', author: 'S. Raghavan', at: iso(created * 0.6) }] : [],
    assignments: assigned ? [assigned.assignment] : [],
    tracking_token: `trk_${Math.floor(rand() * 1e9).toString(36)}`,
  };
}

const SEED_STATUS: [SosStatus, number][] = [
  ['pending', 3], ['pending', 9], ['triaged', 14], ['pending', 22], ['assigned', 31], ['en_route', 44], ['triaged', 52],
  ['on_scene', 70], ['assigned', 85], ['resolved', 140], ['resolved', 210], ['cancelled', 260], ['resolved', 320],
  ['en_route', 38], ['pending', 1], ['resolved', 600], ['resolved', 900],
];
export const sosRows: SosRow[] = SEED_STATUS.map(([s, m], i) => makeSos(i, s, m));

// Capacity demo: row 3 is an urgent P1 waiting 22 min, row 8 a P5 whose team has not left yet (a
// candidate to move), row 14 a possible duplicate of row 3, row 1 came in by SMS, row 2 from a band.
function rescore(r: SosRow) { Object.assign(r, scoreSos(r)); }
sosRows[3].people_injured = 2;
rescore(sosRows[3]);
Object.assign(sosRows[8], { people_to_rescue: 2, people_injured: 0, vulnerabilities: { pregnant: false, elderly: false, children: false, disabled: false, medical: false }, water_availability: 'adequate', food_availability: 'adequate', emergency_type: 'water-level-rising' });
rescore(sosRows[8]);
Object.assign(sosRows[14], { phone: sosRows[3].phone, latitude: (sosRows[3].latitude ?? 13) + 0.0004, longitude: sosRows[3].longitude, duplicate_of: sosRows[3].reference_id, address: sosRows[3].address });
Object.assign(sosRows[1], { source: 'sms', name: 'SMS sender', email: undefined, additional_info: 'SOS P4 I0 Tflood ground floor gone, on terrace' });
// Row 4 got its team from the server's extreme-case auto-reallocation (evidence in the event text).
{
  const r = sosRows[4];
  const ev = r.history.find((h) => h.kind === 'assign');
  const a = r.assignments[0];
  if (ev && a && r.assigned_team) {
    const text = `Auto-reallocated (extreme case) from ${sosRows[12].reference_id} to ${r.assigned_team.name}: P1 ${r.priority_score}/100; wearable CONCUSSIVE_STASIS risk 0.91 for 95 s; Adyar river rising`;
    Object.assign(ev, { by: 'auto-dispatch', actor: 'auto-dispatch', text, note: text });
    Object.assign(a, { assigned_by: 'auto-dispatch', by: 'auto-dispatch', actor: 'auto-dispatch', text });
  }
}
sosRows[2].source = 'wearable';
sosRows[2].device_verified = true; // the band itself raised it

// ─── Alerts ──────────────────────────────────────────────────────────────────

let alertId = 100;
export const nextAlertId = () => ++alertId;
export const alerts: Alert[] = [
  { id: nextAlertId(), device_id: 'TRD-W03', state: 'CONCUSSIVE_STASIS', risk: 0.9, evidence: ['fall p=0.94 @ 5.8 g', 'immobile 74 s'], status: 'open', opened_at: iso(95_000), sos_reference_id: sosRows[2].reference_id },
  { id: nextAlertId(), device_id: 'TRD-W08', state: 'HYPOTHERMIA_RISK', risk: 0.7, evidence: ['skin temp 30.9 °C falling', 'wet 22 min'], status: 'acked', opened_at: iso(18 * MIN), acked_by: 'S. Raghavan', acked_at: iso(16 * MIN) },
  { id: nextAlertId(), device_id: 'TRD-W07', state: 'LOST_CONTACT', risk: 0.7, evidence: ['last seen 7 min ago in HYPOTHERMIA_RISK', 'battery 3.61 V at last frame'], status: 'open', opened_at: iso(6 * MIN) },
  { id: nextAlertId(), device_id: 'TRD-W04', state: 'ASPIRATION_HYPOXIA', risk: 0.85, evidence: ['SpO2 86 %', 'submerged (wet, pressure rising)'], status: 'resolved', opened_at: iso(2.2 * HOUR), acked_by: 'Insp. K. Durai', acked_at: iso(2.15 * HOUR), resolved_at: iso(1.9 * HOUR) },
];

export const transitions: Record<string, StateTransition[]> = Object.fromEntries(devices.map((d) => {
  const list: StateTransition[] = [{ state: 'STABLE', alert_level: 'none', risk: 0.05, evidence: [], at: iso(45 * MIN) }];
  if (d.state.ml_health_state !== 'STABLE') list.push({ ...d.state, state: d.state.ml_health_state, at: iso(d.device_id === 'TRD-W03' ? 95_000 : 6 * MIN) });
  if (d.device_id === 'TRD-W03') list.splice(1, 0, { state: 'ELEVATED_STRESS', alert_level: 'advisory', risk: 0.3, evidence: ['stress p=0.88'], at: iso(12 * MIN) }, { state: 'STABLE', alert_level: 'none', risk: 0.05, evidence: [], at: iso(8 * MIN) });
  return [d.device_id, list];
}));

// ─── ROV ─────────────────────────────────────────────────────────────────────

// Victim bands for the mission demo: SOS 5 and 13 carry wearables (W07 is offline on purpose).
sosRows[5].device_id = 'TRD-W05';
sosRows[13].device_id = 'TRD-W07';

/** Mission SOS -> the SOS references whose people the ROV is searching for. */
export const missionVictims: Record<string, string[]> = {
  [sosRows[2].reference_id]: [sosRows[2].reference_id],
  [sosRows[5].reference_id]: [sosRows[5].reference_id, sosRows[13].reference_id],
};

function rovBase(id: string, name: string, home: { lat: number; lng: number }): Rov {
  return {
    id, name, status: 'idle', mode: 'auto', pilot: null, battery_pct: 98, latitude: home.lat, longitude: home.lng, depth_m: 0,
    heading_deg: 0, water_temp_c: 27.8, speed_pct: 0, lights_on: false, link: 'simulated', last_seen: iso(2000), target: null, home,
    mission_reference_id: null, team_id: null, video_url: null, simulated: true, updated_at: iso(2000), vision: { active: false },
  };
}

const s2 = sosRows[2];
const s5 = sosRows[5];
export const rovs: Rov[] = [
  { ...rovBase('ROV-1', 'Neerkuthi 1', { lat: 12.975, lng: 80.205 }), status: 'on_mission', battery_pct: 64, depth_m: 1.4, heading_deg: 72, speed_pct: 35, lights_on: true,
    latitude: (s2.latitude ?? 12.98) - 0.004, longitude: (s2.longitude ?? 80.21) - 0.006, target: { lat: s2.latitude ?? 12.98, lng: s2.longitude ?? 80.21 },
    mission_reference_id: s2.reference_id, team_id: 1 },
  { ...rovBase('ROV-2', 'Neerkuthi 2', { lat: 13.006, lng: 80.25 }), status: 'deploying', battery_pct: 91, depth_m: 0.4, heading_deg: 250, speed_pct: 60,
    latitude: 13.01, longitude: 80.243, target: { lat: s5.latitude ?? 13.02, lng: s5.longitude ?? 80.22 }, mission_reference_id: s5.reference_id, team_id: 4 },
  { ...rovBase('ROV-3', 'Neerkuthi 3', { lat: 13.205, lng: 80.315 }), status: 'stopped', battery_pct: 12, link: 'offline', last_seen: iso(5 * HOUR), updated_at: iso(5 * HOUR) },
];

// Real-world river gauges are fetched by the backend (Open-Meteo Flood API / GloFAS). These are demo values only.
export const rivers = [
  { name: 'Adyar', lat: 13.0105, lng: 80.2337, base: 142, p50: 38 },
  { name: 'Cooum', lat: 13.0732, lng: 80.2609, base: 61, p50: 19 },
  { name: 'Kosasthalaiyar', lat: 13.2257, lng: 80.3043, base: 210, p50: 74 },
];

// ─── Weather ─────────────────────────────────────────────────────────────────

export function weatherCurrent(): WeatherCurrent {
  return { site: { name: 'Chennai (Nungambakkam)', lat: 13.0674, lon: 80.2376 }, observed_at: iso(12 * MIN), temp_c: 27.4, rh: 91, rain_mm: 6.2, wind_ms: 7.8, gust_ms: 13.1, pressure_hpa: 1003.6, source: 'open-meteo' };
}

export function forecast(hours = 48): Forecast {
  const start = new Date();
  start.setMinutes(0, 0, 0);
  const horizon: ForecastStep[] = [];
  for (let h = 1; h <= hours; h++) {
    const t = new Date(start.getTime() + h * HOUR);
    const hod = t.getHours();
    const spread = 0.4 + h * 0.03;
    const temp = 27 + 3 * Math.sin(((hod - 9) / 24) * 2 * Math.PI) - (h > 6 && h < 20 ? 1.2 : 0);
    const rainPeak = Math.exp(-((h - 12) ** 2) / 30) * 14 + Math.exp(-((h - 33) ** 2) / 20) * 6;
    const wind = 6 + Math.exp(-((h - 13) ** 2) / 40) * 6 + Math.sin(h / 5);
    const pres = 1004 - Math.exp(-((h - 12) ** 2) / 60) * 4 + h * 0.03;
    const rh = Math.min(99, 82 + rainPeak * 1.2 - (hod > 11 && hod < 16 ? 6 : 0));
    const q = (p50: number, w: number, lo = -Infinity) => ({ p10: Math.max(lo, +(p50 - w).toFixed(2)), p50: Math.max(lo, +p50.toFixed(2)), p90: +(p50 + w).toFixed(2) });
    horizon.push({
      time: t.toISOString().replace(/\.\d{3}Z$/, 'Z'),
      temp_c: q(temp, spread),
      rain_mm: { p10: +Math.max(0, rainPeak * 0.3).toFixed(2), p50: +rainPeak.toFixed(2), p90: +(rainPeak * 1.9 + 0.3 * spread).toFixed(2) },
      wind_ms: q(wind, 1 + spread, 0),
      pressure_hpa: q(pres, 0.6 + spread * 0.8),
      rh: { p10: +Math.max(50, rh - 4 - spread * 2).toFixed(1), p50: +rh.toFixed(1), p90: +Math.min(100, rh + 3 + spread).toFixed(1) },
    });
  }
  const at = (h: number) => new Date(start.getTime() + h * HOUR).toISOString().replace(/\.\d{3}Z$/, 'Z');
  const hazards: Hazard[] = [
    { type: 'heavy_rain', level: 'warning', from: at(8), to: at(17), reason: 'p50 rain peaks at 14 mm/h; p90 above 25 mm/h for 5 h' },
    { type: 'flood_risk', level: 'watch', from: at(10), to: at(30), reason: '48 h accumulated p50 rain 128 mm on saturated ground' },
    { type: 'high_wind', level: 'watch', from: at(10), to: at(16), reason: 'p90 wind above 13 m/s' },
  ];
  return { site: { name: 'Chennai (Nungambakkam)' }, generated_at: iso(14 * MIN), model_version: 'wx-2026.10.3', horizon, hazards: hours >= 30 ? hazards : hazards.slice(0, 1) };
}

export function modelCard(): ModelCard {
  const vars = ['temp_c', 'rain_mm', 'wind_ms', 'pressure_hpa', 'rh'];
  const skill: NonNullable<ModelCard['skill']> = [];
  for (const v of vars) for (const h of [1, 6, 12, 24, 48]) {
    const pers = { temp_c: 0.6, rain_mm: 1.6, wind_ms: 1.1, pressure_hpa: 0.4, rh: 4.2 }[v as 'rh']! * (1 + Math.log2(h) * 0.45);
    const s = Math.max(-0.05, 0.42 - h * 0.004 - (v === 'rain_mm' ? 0.2 : 0) + (v === 'pressure_hpa' ? 0.1 : 0));
    skill.push({ variable: v, horizon_h: h, model_mae: +(pers * (1 - s)).toFixed(3), persistence_mae: +pers.toFixed(3), skill: +s.toFixed(3) });
  }
  return {
    model_version: 'wx-2026.10.3',
    training_data: { from: '2015-01-01', to: '2026-09-30', rows: 102_216, source: 'Open-Meteo archive, Nungambakkam' },
    candidates: ['persistence', 'climatology', 'ridge-lags', 'lightgbm-quantile', 'lstm-quantile'],
    chosen: { temp_c: 'lightgbm-quantile', rain_mm: 'lightgbm-quantile', wind_ms: 'ridge-lags', pressure_hpa: 'lightgbm-quantile', rh: 'lightgbm-quantile' },
    skill,
  };
}

export const frameHistoryFor = (id: string) => deviceSims.find((s) => s.id === id);
export { HOUR, MIN };
