// Mock analytics computed from the mock's own state (frames it emitted, SOS rows, alerts, teams),
// so the analytics pages are exercised with numbers that move with the simulation.
import { alerts, devices, forecast, iso, modelCard, rivers, rovs, sosRows, teams, transitions } from './data';
import { missions } from './rov';

const frameTimes = new Map<string, number[]>(); // device -> epoch ms of frames emitted
export function recordFrame(id: string) {
  let a = frameTimes.get(id);
  if (!a) frameTimes.set(id, (a = []));
  a.push(Date.now());
  if (a.length > 2400) a.splice(0, a.length - 2400);
}

const MIN = 60_000;

export function sensors() {
  const now = Date.now();
  const out = devices.map((d, i) => {
    const f = (frameTimes.get(d.device_id) ?? []).filter((t) => t > now - 5 * MIN);
    const span = f.length > 1 ? (f[f.length - 1] - f[0]) / 1000 : 0;
    const tr = transitions[d.device_id] ?? [];
    const share: Record<string, number> = {};
    // Share of the last 24 h spent in each state, from the transition log.
    const start = now - 24 * 60 * MIN;
    for (let k = 0; k < tr.length; k++) {
      const a = Math.max(start, Date.parse(tr[k].at));
      const b = k + 1 < tr.length ? Date.parse(tr[k + 1].at) : now;
      if (b > a) share[tr[k].state] = (share[tr[k].state] ?? 0) + (b - a);
    }
    const tot = Object.values(share).reduce((x, y) => x + y, 0) || 1;
    for (const k of Object.keys(share)) share[k] = +(share[k] / tot).toFixed(3);
    return {
      device_id: d.device_id, online: d.online, frames_5min: f.length,
      frame_rate_hz: span > 0 ? +((f.length - 1) / span).toFixed(2) : null,
      battery_v: d.battery_v,
      signal_availability: { ppg: d.online ? 0.93 - (i % 3) * 0.05 : 0, spo2: d.online ? 0.71 - (i % 3) * 0.06 : 0, eda: d.online ? 0.99 : 0, temp: d.online ? 1 : 0, imu: d.online ? 1 : 0, gps: d.online ? 0.78 + (i % 2) * 0.15 : 0 },
      state_share_24h: share,
      sensor_fault_share: d.online ? +(0.01 + (i % 4) * 0.012).toFixed(3) : null,
    };
  });
  const perMin = [...frameTimes.values()].reduce((n, a) => n + a.filter((t) => t > now - MIN).length, 0);
  return { devices: out, totals: { frames_per_min: perMin, devices_online: devices.filter((d) => d.online).length, devices_total: devices.length }, generated_at: iso() };
}

function bucketStart(t: number, bucket: string) {
  const d = new Date(t);
  if (bucket === 'minute') d.setSeconds(0, 0);
  else if (bucket === 'hour') d.setMinutes(0, 0, 0);
  else d.setHours(0, 0, 0, 0);
  return d.getTime();
}

export function timeseries(metric: string, bucket: string, since?: string | null) {
  const step = bucket === 'minute' ? MIN : bucket === 'hour' ? 60 * MIN : 24 * 60 * MIN;
  const n = bucket === 'minute' ? 60 : bucket === 'hour' ? 24 : 14;
  const from = since ? Date.parse(since) : Date.now() - n * step;
  let times: number[] = [];
  if (metric === 'sos_created') times = sosRows.map((r) => Date.parse(r.created_at));
  else if (metric === 'sos_resolved') times = sosRows.flatMap((r) => r.history.filter((h) => h.status === 'resolved').map((h) => Date.parse(h.at)));
  else if (metric === 'alerts') times = alerts.map((a) => Date.parse(a.opened_at));
  else if (metric === 'telemetry_frames') times = [...frameTimes.values()].flat();
  else if (metric === 'state_changes') times = Object.values(transitions).flat().map((t) => Date.parse(t.at));
  const counts = new Map<number, number>();
  for (let b = bucketStart(from, bucket); b <= Date.now(); b += step) counts.set(b, 0);
  for (const t of times) if (t >= from) { const b = bucketStart(t, bucket); counts.set(b, (counts.get(b) ?? 0) + 1); }
  return { metric, bucket, points: [...counts].sort((a, b) => a[0] - b[0]).map(([t, value]) => ({ t: new Date(t).toISOString().replace(/\.\d{3}Z$/, 'Z'), value })) };
}

function quantile(xs: number[], q: number) {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const i = (s.length - 1) * q;
  const lo = Math.floor(i);
  return +(s[lo] + (s[Math.ceil(i)] - s[lo]) * (i - lo)).toFixed(1);
}

export function responseTimes() {
  const by = new Map<number, number[]>();
  for (const r of sosRows) {
    const on = r.history.find((h) => h.status === 'on_scene');
    if (!on) continue;
    const m = (Date.parse(on.at) - Date.parse(r.created_at)) / MIN;
    by.set(r.priority, [...(by.get(r.priority) ?? []), m]);
  }
  return { items: [1, 2, 3, 4, 5].map((p) => { const xs = by.get(p) ?? []; return { priority: p, n: xs.length, p50: quantile(xs, 0.5), p90: quantile(xs, 0.9), p95: quantile(xs, 0.95) }; }) };
}

export function avgResponseMin() {
  const xs = sosRows.flatMap((r) => r.history.filter((h) => h.status === 'on_scene').map((h) => (Date.parse(h.at) - Date.parse(r.created_at)) / MIN));
  return xs.length ? +(xs.reduce((a, b) => a + b, 0) / xs.length).toFixed(1) : null;
}

export function performance() {
  const acks = alerts.filter((a) => a.acked_at).map((a) => (Date.parse(a.acked_at!) - Date.parse(a.opened_at)) / 1000);
  const ms = missions();
  return {
    response_times: responseTimes(),
    alert_ack: { n: acks.length, p50_s: quantile(acks, 0.5), p90_s: quantile(acks, 0.9) },
    team_utilization: teams.map((t) => ({ team_id: t.id, name: t.name, load: t.current_load, capacity: t.capacity, utilization: +(t.current_load / Math.max(1, t.capacity)).toFixed(2) })),
    missions: { n: ms.length, median_transit_min: ms.length ? 14.5 : null },
    generated_at: iso(),
  };
}

export function geo() {
  const grid = new Map<string, { lat: number; lng: number; count: number }>();
  for (const r of sosRows) {
    if (r.latitude == null || r.longitude == null) continue;
    const lat = Math.round(r.latitude / 0.02) * 0.02;
    const lng = Math.round(r.longitude / 0.02) * 0.02;
    const k = `${lat.toFixed(2)},${lng.toFixed(2)}`;
    const c = grid.get(k) ?? { lat: +lat.toFixed(2), lng: +lng.toFixed(2), count: 0 };
    c.count++;
    grid.set(k, c);
  }
  const today = new Date();
  return {
    sos: sosRows.filter((r) => r.latitude != null).map((r) => ({ reference_id: r.reference_id, lat: r.latitude!, lng: r.longitude!, priority: r.priority, status: r.status, emergency_type: r.emergency_type })),
    devices: devices.filter((d) => d.location).map((d) => ({ device_id: d.device_id, lat: d.location!.lat, lng: d.location!.lng, state: d.state.ml_health_state, alert_level: d.state.alert_level })),
    teams: teams.filter((t) => t.location && typeof t.location !== 'string').map((t) => ({ id: t.id, name: t.name, lat: (t.location as { lat: number }).lat, lng: (t.location as { lng: number }).lng, current_load: t.current_load, capacity: t.capacity })),
    rovs: rovs.filter((r) => r.latitude != null).map((r) => ({ id: r.id, name: r.name, lat: r.latitude!, lng: r.longitude!, status: r.status })),
    rivers: rivers.map((rv, i) => ({
      name: rv.name, lat: rv.lat, lng: rv.lng, discharge_m3s: rv.base, discharge_p50_30d: rv.p50, trend: i === 1 ? 'steady' : 'rising',
      // Same span as the server's Open-Meteo request: past_days 30 (through today) + forecast_days 14.
      history: Array.from({ length: 30 }, (_, k) => ({ date: new Date(today.getTime() - (29 - k) * 864e5).toISOString().slice(0, 10), discharge_m3s: +(rv.p50 * (0.8 + 0.25 * Math.sin(k / 3.1)) + (rv.base - rv.p50) * Math.max(0, (k - 22) / 7)).toFixed(1) })),
      forecast: Array.from({ length: 14 }, (_, k) => ({ date: new Date(today.getTime() + (k + 1) * 864e5).toISOString().slice(0, 10), discharge_m3s: +(rv.base * (1 + 0.35 * Math.sin((k + 1) / 2.2)) * (k < 3 ? 1 + k * 0.1 : Math.max(0.5, 1.3 - k * 0.07))).toFixed(1) })),
      source: 'Open-Meteo Flood API (GloFAS)', updated_at: iso(42 * MIN),
    })),
    grid: [...grid.values()],
    generated_at: iso(),
  };
}

export function models() {
  return {
    wearable: [
      { head: 'stress', model: 'minirocket', macro_f1: 0.935, ci95: [0.889, 0.97], auroc: 0.985, threshold: 0.33, external: { dataset: 'stress_predict', macro_f1: 0.521, note: 'advisory only' } },
      { head: 'hr_trust', model: 'vote(cnn1d+extratrees)', macro_f1: 0.768, ci95: [0.742, 0.792], auroc: 0.872, threshold: 0.59, external: null },
      { head: 'rhythm', model: 'cnn1d', macro_f1: 0.932, ci95: [0.915, 0.949], auroc: 0.977, threshold: 0.61, external: null },
      { head: 'activity', model: 'extratrees', macro_f1: 0.801, ci95: [0.778, 0.82], auroc: 0.953, threshold: null, external: { dataset: 'pamap2', macro_f1: 0.59 } },
      { head: 'fall', model: 'vote(extratrees+cnn1d)', macro_f1: 0.867, ci95: [0.843, 0.886], auroc: 0.994, threshold: 0.72, external: { dataset: 'hifd', macro_f1: 0.716, false_alarms_per_8h: 2.14 } },
    ],
    // Values copied from docs/reports/WEARABLE_FUSION_REPLAY.md (P5 replay) so the mock matches the real report.
    fusion: {
      version: '1.2.0',
      false_alarms_per_8h: { ppg_dalia: 0.667, wesad: 0.332, pamap2: 2.244, stress_predict: 0.511, capture24: 1.197 },
      falls_caught: { dataset: 'hifd', fall_trials: 104, stasis_after_fall: 0.846, adl_trials: 245, stasis_after_adl: 0.069, median_latency_s: 32.25 },
    },
    weather: modelCard(),
    rhythm_ppg_af: null,
    generated_at: iso(),
  };
}

void forecast;
