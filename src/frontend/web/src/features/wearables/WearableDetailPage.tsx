import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, BellRing, Crosshair, MapPinned, RotateCcw } from 'lucide-react';
import type { AlignedData } from 'uplot';
import { api } from '../../api/client';
import { seedTelemetry, telemetry, useLive, type TelemetryPoint } from '../../api/live';
import type { DeviceAction, FlatFrame, Heads, StateTransition } from '../../api/types';
import { ago, hhmmss, num, pct } from '../../lib/format';
import { useAsync, useNow } from '../../lib/hooks';
import { alertLevelOf, levelTone, stateLabel } from '../../lib/states';
import { token, UPlot, useLineOptions } from '../../ui/charts';
import { Dialog } from '../../ui/Dialog';
import { Battery, Button, Chip, Empty, ErrorState, Meter, Panel, Skeleton, StateChip } from '../../ui/primitives';
import { useErrorToast, useToast } from '../../ui/Toast';
import { useAuth } from '../auth/auth';

function frameTime(f: FlatFrame) {
  const s = f.ts ?? f.received_at ?? f.at;
  return s ? Date.parse(String(s)) / 1000 : NaN;
}
const n = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : null);

function toPoints(frames: FlatFrame[]): TelemetryPoint[] {
  return frames
    .map((f) => ({ t: frameTime(f), bpm: n(f.ppg_bpm), spo2: n(f.ppg_spo2), temp: n(f.temp_skin_c), eda: n(f.eda_us), acc: n(f.imu_acc_std_g) }))
    .filter((p) => Number.isFinite(p.t))
    .sort((a, b) => a.t - b.t);
}

const WINDOWS = [[120, '2 min'], [300, '5 min'], [600, '10 min']] as const;

type ChartKey = 'bpm' | 'spo2' | 'temp' | 'eda' | 'acc';
const CHARTS: { key: ChartKey; name: string; unit: string; color: string; range?: [number, number] }[] = [
  { key: 'bpm', name: 'Heart rate', unit: 'bpm', color: '--series-1' },
  { key: 'spo2', name: 'SpO₂', unit: '%', color: '--series-2', range: [80, 100] },
  { key: 'temp', name: 'Skin temperature', unit: '°C', color: '--series-3' },
  { key: 'eda', name: 'Electrodermal activity', unit: 'µS', color: '--series-4' },
  { key: 'acc', name: 'Motion (acc. std)', unit: 'g', color: '--series-5' },
];

function VitalChart({ name, unit, color, range, data, latest }: { name: string; unit: string; color: string; range?: [number, number]; data: AlignedData; latest: number | null }) {
  const opts = useLineOptions(name, unit, token(color), range);
  return (
    <section className="vchart" aria-label={name}>
      <header><h3>{name}</h3><span className="mono vchart-val">{num(latest, unit === 'g' ? 3 : unit === '°C' || unit === 'µS' ? 1 : 0)}<small>{unit}</small></span></header>
      <UPlot options={opts} data={data} height={120} label={`${name} over time, latest ${num(latest, 1)} ${unit}`} />
    </section>
  );
}

const HEAD_INFO: Record<string, string> = {
  fall: 'Probability that the last impact window was a fall',
  stress: 'Advisory only: does not transfer reliably beyond the lab dataset',
  hr_trust: 'How far the optical heart rate can be trusted right now',
  rhythm: 'Probability of an irregular rhythm from beat intervals',
};

function HeadsPanel({ heads }: { heads: Heads }) {
  const entries = Object.entries(heads ?? {}).filter(([k]) => k !== 'activity');
  return (
    <Panel title="Tier-1 heads">
      {entries.length === 0 && heads?.activity == null ? <p className="muted">No head outputs yet.</p> : (
        <dl className="heads">
          {entries.map(([k, v]) => {
            const p = typeof v === 'number' ? v : null;
            const tone = k === 'hr_trust' ? (p !== null && p < 0.5 ? 'warning' : 'ok') : p !== null && p >= 0.8 ? 'critical' : p !== null && p >= 0.5 ? 'warning' : 'info';
            return (
              <div key={k} className="head-row" title={HEAD_INFO[k]}>
                <dt>{k === 'hr_trust' ? 'HR trust' : k}</dt>
                <dd><Meter value={p} tone={tone} label={`${k} probability`} /><span className="mono">{p === null ? 'n/a' : p.toFixed(2)}</span></dd>
              </div>
            );
          })}
          {heads?.activity != null && (
            <div className="head-row"><dt>activity</dt><dd><Chip tone="info">{String(heads.activity)}</Chip></dd></div>
          )}
        </dl>
      )}
    </Panel>
  );
}

export default function WearableDetailPage() {
  const { id = '' } = useParams();
  const dev = useLive((s) => s.devices[id]);
  const loadState = useLive((s) => s.load.devices);
  const tick = useLive((s) => s.telemetryTick);
  const liveTransitions = useLive((s) => s.transitions[id]);
  const { can } = useAuth();
  const toast = useToast();
  const fail = useErrorToast();
  const now = useNow(1000);
  const [win, setWin] = useState<number>(300);
  const [geoOpen, setGeoOpen] = useState(false);
  const [geo, setGeoForm] = useState({ lat: '', lng: '', radius_m: '500' });
  const [cmdBusy, setCmdBusy] = useState<DeviceAction | null>(null);
  const [log, setLog] = useState<{ id: string; action: string; status: string; at: string }[]>([]);

  const frames = useAsync(() => api.frames(id, undefined, 400), [id]);
  const states = useAsync(() => api.states(id), [id]);

  useEffect(() => { if (frames.data) seedTelemetry(id, toPoints(frames.data)); }, [frames.data, id]);

  const data = useMemo(() => {
    void tick;
    const buf = telemetry.get(id) ?? [];
    const cutoff = now / 1000 - win;
    const pts = buf.filter((p) => p.t >= cutoff);
    const xs = pts.map((p) => p.t);
    const out = {} as Record<ChartKey, AlignedData>;
    for (const c of CHARTS) out[c.key] = [xs, pts.map((p) => p[c.key])] as AlignedData;
    return { out, last: pts[pts.length - 1] };
  }, [tick, id, win, now]);

  const timeline = useMemo<StateTransition[]>(() => {
    const merged = [...(states.data ?? []), ...(liveTransitions ?? [])];
    const seen = new Set<string>();
    return merged.filter((t) => { const k = `${t.state}@${t.at}`; if (seen.has(k)) return false; seen.add(k); return true; })
      .sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
  }, [states.data, liveTransitions]);

  // The form takes metres; the command contract is {lat, lng, radius_km}.
  const geoLat = Number(geo.lat.trim() || NaN);
  const geoLng = Number(geo.lng.trim() || NaN);
  const geoRadiusM = Number(geo.radius_m.trim() || NaN);
  const geoProblem = !Number.isFinite(geoLat) || geoLat < -90 || geoLat > 90 ? 'Latitude: a number from -90 to 90.'
    : !Number.isFinite(geoLng) || geoLng < -180 || geoLng > 180 ? 'Longitude: a number from -180 to 180.'
      : !Number.isFinite(geoRadiusM) || geoRadiusM < 10 || geoRadiusM > 50_000 ? 'Radius: 10 m to 50 km (50000 m).' : null;

  const send = async (action: DeviceAction, params: Record<string, unknown> = {}) => {
    setCmdBusy(action);
    try {
      const cmd = await api.sendCommand(id, action, params);
      setLog((l) => [{ id: cmd.id, action, status: cmd.status ?? 'queued', at: cmd.created_at ?? new Date().toISOString() }, ...l].slice(0, 10));
      toast({ tone: 'ok', title: `${action} queued for ${id}`, message: 'Delivered with the device’s next telemetry upload.' });
      return true;
    } catch (e) { fail(e, `Could not send ${action}`); return false; } finally { setCmdBusy(null); }
  };

  if (!dev) {
    if (loadState === 'loading') return <div className="page"><Skeleton rows={10} /></div>;
    return (
      <div className="page">
        <Link to="/wearables" className="back"><ArrowLeft aria-hidden="true" />Wearables</Link>
        <ErrorState error={loadState === 'error' ? 'Device list unavailable.' : `No device ${id} is registered.`} title={`Device ${id}`} />
      </div>
    );
  }

  const canCmd = can('device.command');
  const level = dev.state.alert_level;

  return (
    <div className="page page--detail">
      <Link to="/wearables" className="back"><ArrowLeft aria-hidden="true" />Wearables</Link>
      <div className="detail-head">
        <h1 className="mono">{dev.device_id}</h1>
        <span className="dev-label-lg">{dev.label}</span>
        <StateChip state={dev.state.ml_health_state} level={level} size="lg" />
        <span className={`dot ${dev.online ? 'dot--ok' : 'dot--off'}`} aria-hidden="true" />
        <span className="muted">{dev.online ? 'online' : 'offline'} · last frame <span className="mono">{ago(dev.last_seen, now)}</span> ago</span>
        <Battery volts={dev.battery_v} />
        {dev.boot_id && <span className="muted mono" title="Boot id: changes when the band restarts">boot {dev.boot_id}</span>}
      </div>

      {!dev.online && <div className="banner banner--warning" role="status">This band has not sent a frame for over 30 s. Charts show the last data received; commands queue until it reconnects.</div>}

      <div className="wd-grid">
        <Panel title="Vitals" className="wd-charts" actions={(
          <div className="segmented" role="group" aria-label="Time window">
            {WINDOWS.map(([s, l]) => <button key={s} type="button" aria-pressed={win === s} onClick={() => setWin(s)}>{l}</button>)}
          </div>
        )}>
          {frames.loading && !data.last ? <Skeleton rows={8} /> : frames.error && !data.last ? <ErrorState error={frames.error} onRetry={frames.reload} /> : !data.last ? (
            <Empty title="No frames in this window">Frames arrive every 1.5 s while the band is online.</Empty>
          ) : (
            <div className="vcharts">
              {CHARTS.map((c) => <VitalChart key={c.key} name={c.name} unit={c.unit} color={c.color} range={c.range} data={data.out[c.key]} latest={data.last?.[c.key] ?? null} />)}
            </div>
          )}
        </Panel>

        <div className="wd-side">
          <Panel title="Fusion state">
            <div className="stack">
              <div className="row"><StateChip state={dev.state.ml_health_state} level={level} /><span className="mono">risk {pct(dev.state.risk)}</span></div>
              <Meter value={dev.state.risk} tone={levelTone(level)} label="Risk score" />
              <h3 className="sub-h">Evidence</h3>
              {dev.state.evidence?.length ? <ul className="evidence">{dev.state.evidence.map((e) => <li key={e}>{e}</li>)}</ul> : <p className="muted">No evidence recorded for this state.</p>}
            </div>
          </Panel>

          <HeadsPanel heads={dev.heads} />

          <Panel title="Commands">
            {!canCmd ? <p className="muted">Sending commands needs a dispatcher or admin.</p> : (
              <div className="cmd-grid">
                <Button icon={<RotateCcw />} busy={cmdBusy === 'reset_fall'} onClick={() => void send('reset_fall')} title="Clear a latched fall on the band">Reset fall</Button>
                <Button icon={<Crosshair />} busy={cmdBusy === 'calibrate_gsr'} onClick={() => void send('calibrate_gsr')} title="Re-baseline the skin conductance sensor">Calibrate GSR</Button>
                <Button icon={<MapPinned />} onClick={() => { setGeoForm({ lat: String(dev.location?.lat ?? ''), lng: String(dev.location?.lng ?? ''), radius_m: '500' }); setGeoOpen(true); }}>Set geofence</Button>
                <Button icon={<BellRing />} busy={cmdBusy === 'buzz'} onClick={() => void send('buzz', { ms: 1500 })} title="Vibrate the band to get the wearer’s attention">Buzz</Button>
              </div>
            )}
            {log.length > 0 && (
              <ul className="cmd-log">
                {log.map((c) => <li key={c.id}><span className="mono">{hhmmss(c.at)}</span> {c.action} <Chip tone="muted">{c.status}</Chip></li>)}
              </ul>
            )}
          </Panel>

          <Panel title="State history" count={timeline.length} bodyClass="panel-body--scroll state-hist">
            {states.loading && !timeline.length ? <Skeleton rows={4} /> : states.error && !timeline.length ? <ErrorState error={states.error} onRetry={states.reload} /> : timeline.length === 0 ? <p className="muted">No transitions recorded.</p> : (
              <ol className="timeline">
                {timeline.map((t, i) => {
                  const lv = t.alert_level ?? alertLevelOf(t.state);
                  return (
                    <li key={`${t.state}${t.at}`} className={`${i === 0 ? 'is-current' : ''} ${lv === 'critical' ? 'is-critical' : ''}`}>
                      <span className="t-time" title={t.at}>{hhmmss(t.at).slice(0, 5)}</span>
                      <span className="t-rail"><span className="t-node" /></span>
                      <span className="t-body">{stateLabel(t.state)} <span className="mono muted">{pct(t.risk)}</span>{t.evidence?.length > 0 && <small>{t.evidence.slice(0, 2).join(' · ')}</small>}</span>
                    </li>
                  );
                })}
              </ol>
            )}
          </Panel>
        </div>
      </div>

      <Dialog open={geoOpen} onClose={() => setGeoOpen(false)} title={`Geofence · ${dev.device_id}`} labelledBy="geo-title"
        footer={(
          <>
            <Button onClick={() => setGeoOpen(false)}>Back</Button>
            <Button variant="primary" busy={cmdBusy === 'set_geofence'} disabled={!!geoProblem}
              onClick={() => void send('set_geofence', { lat: geoLat, lng: geoLng, radius_km: geoRadiusM / 1000 }).then((ok) => ok && setGeoOpen(false))}>
              Send geofence
            </Button>
          </>
        )}>
        <p className="muted">The band alerts when it leaves this circle. Defaults to the band’s current position.</p>
        <div className="row-3">
          <label className="field"><span className="field-label">Latitude</span><input className="input mono" inputMode="decimal" value={geo.lat} onChange={(e) => setGeoForm({ ...geo, lat: e.target.value })} /></label>
          <label className="field"><span className="field-label">Longitude</span><input className="input mono" inputMode="decimal" value={geo.lng} onChange={(e) => setGeoForm({ ...geo, lng: e.target.value })} /></label>
          <label className="field"><span className="field-label">Radius (m)</span><input className="input mono" inputMode="numeric" value={geo.radius_m} onChange={(e) => setGeoForm({ ...geo, radius_m: e.target.value })} /></label>
        </div>
        {geoProblem ? <p className="field-hint" role="status">{geoProblem}</p>
          : <p className="field-hint">Sent as <span className="mono">radius_km {+(geoRadiusM / 1000).toFixed(3)}</span>.</p>}
      </Dialog>
    </div>
  );
}
