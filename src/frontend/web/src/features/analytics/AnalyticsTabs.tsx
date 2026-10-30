import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import { useLive } from '../../api/live';
import type { River, SensorKey } from '../../api/types';
import { dayHhmm, num, pct } from '../../lib/format';
import { useAsync } from '../../lib/hooks';
import { alertLevelOf, levelTone, priorityTone, stateLabel } from '../../lib/states';
import { Sparkline, token } from '../../ui/charts';
import { MapView, type MapMarker } from '../../ui/MapView';
import { Battery, Chip, Empty, ErrorState, Panel, Skeleton, Stat, StateChip } from '../../ui/primitives';
import { ModelCardPanel } from '../weather/WeatherPage';
import { HBars, Provenance, useInterval } from './common';

const SENSORS: SensorKey[] = ['ppg', 'spo2', 'eda', 'temp', 'imu', 'gps'];
const STATE_COLOR: Record<string, string> = { STABLE: 'var(--ok)', ELEVATED_STRESS: 'var(--warning)' };

// ─── Sensors ─────────────────────────────────────────────────────────────────

export function SensorsTab() {
  const q = useAsync(() => api.sensors(), []);
  useInterval(q.reload, 15_000);
  const live = useLive((s) => s.devices);
  const r = q.data;
  if (q.loading && !r) return <Skeleton rows={8} />;
  if (!r) return <ErrorState error={q.error} onRetry={q.reload} />;
  return (
    <div className="stack-lg">
      <div className="kpi-strip">
        <Stat label="Frames / min" value={r.totals.frames_per_min} sub="all devices, last minute" />
        <Stat label="Devices online" value={r.totals.devices_online} unit={`/ ${r.totals.devices_total}`} />
        <Stat label="Expected rate" value="0.67" unit="Hz" sub="one frame per 1.5 s" />
      </div>
      <Panel title="Per-device sensor health" bodyClass="panel-body--flush" actions={<Provenance source={`ingest · ${r.devices.length} devices`} at={r.generated_at} />}>
        {r.devices.length === 0 ? <Empty title="No devices registered" /> : (
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Per-device sensor health">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Device</th><th scope="col">Now</th><th scope="col" className="r">Frames 5 min</th><th scope="col" className="r">Rate</th><th scope="col">Battery</th>
                  {SENSORS.map((s) => <th key={s} scope="col" className="r">{s.toUpperCase()}</th>)}
                  <th scope="col" style={{ minWidth: 160 }}>State share 24 h</th><th scope="col" className="r">Sensor fault</th>
                </tr>
              </thead>
              <tbody>
                {r.devices.map((d) => {
                  const ld = live[d.device_id];
                  const shares = Object.entries(d.state_share_24h ?? {}).sort((a, b) => b[1] - a[1]);
                  return (
                    <tr key={d.device_id}>
                      <th scope="row"><Link to={`/wearables/${d.device_id}`} className="mono">{d.device_id}</Link></th>
                      <td>{ld ? <StateChip state={ld.state.ml_health_state} level={ld.state.alert_level} /> : <span className={`dot ${d.online ? 'dot--ok' : 'dot--off'}`} />}</td>
                      <td className="r mono">{d.frames_5min}</td>
                      <td className={`r mono ${d.frame_rate_hz != null && d.frame_rate_hz < 0.5 ? 'text-warning' : ''}`}>{num(d.frame_rate_hz, 2)}</td>
                      <td><Battery volts={ld?.battery_v ?? d.battery_v} /></td>
                      {SENSORS.map((s) => {
                        const v = d.signal_availability?.[s];
                        return <td key={s} className={`r mono ${v != null && v < 0.8 ? 'text-warning' : v === 0 ? 'muted' : ''}`}>{v == null ? '—' : pct(v)}</td>;
                      })}
                      <td>
                        {shares.length ? (
                          <span className="stack-bar" title={shares.map(([k, v]) => `${stateLabel(k)} ${pct(v)}`).join(', ')}>
                            {shares.map(([k, v]) => <span key={k} style={{ width: `${v * 100}%`, background: STATE_COLOR[k] ?? 'var(--critical)' }} />)}
                          </span>
                        ) : <span className="muted">—</span>}
                      </td>
                      <td className="r mono">{d.sensor_fault_share == null ? '—' : pct(d.sensor_fault_share, 1)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      <p className="field-hint">State share colours: <span className="text-ok">stable</span>, <span className="text-warning">elevated stress (advisory)</span>, <span className="text-critical">any critical state</span>.</p>
    </div>
  );
}

// ─── Geographic ──────────────────────────────────────────────────────────────

/** "last 30 days + 14-day forecast", from the lengths of the arrays the API actually returned. */
function riverSpan(r: Pick<River, 'history' | 'forecast'>): string {
  const h = r.history?.length ?? 0;
  const f = r.forecast?.length ?? 0;
  const parts = [h ? `last ${h} day${h === 1 ? '' : 's'}` : '', f ? `${f}-day forecast` : ''].filter(Boolean);
  return parts.length ? parts.join(' + ') : 'no data';
}

function RiverRow({ r }: { r: River }) {
  const hist = r.history ?? [];
  const fc = r.forecast ?? [];
  const ratio = r.discharge_m3s != null && r.discharge_p50_30d ? r.discharge_m3s / r.discharge_p50_30d : null;
  return (
    <tr>
      <th scope="row">{r.name}</th>
      <td className="r mono">{num(r.discharge_m3s, 1)}</td>
      <td className="r mono muted">{num(r.discharge_p50_30d, 1)}</td>
      <td className={`r mono ${ratio != null && ratio > 2 ? 'text-critical' : ratio != null && ratio > 1.3 ? 'text-warning' : ''}`}>{ratio == null ? '—' : `${ratio.toFixed(1)}×`}</td>
      <td><Chip tone={r.trend === 'rising' ? 'warning' : r.trend === 'falling' ? 'ok' : 'muted'}>{r.trend}</Chip></td>
      <td style={{ width: 120 }}><Sparkline values={[...hist, ...fc].map((f) => f.discharge_m3s)} color={token('--series-2')} label={`${r.name} discharge, ${riverSpan(r)}`} /></td>
    </tr>
  );
}

export function GeoTab() {
  const q = useAsync(() => api.geo(), []);
  useInterval(q.reload, 60_000);
  const g = q.data;
  const markers = useMemo<MapMarker[]>(() => {
    if (!g) return [];
    const maxCount = Math.max(1, ...g.grid.map((c) => c.count));
    return [
      ...g.grid.map((c) => ({ id: `${c.lat},${c.lng}`, kind: 'cell' as const, lat: c.lat, lng: c.lng, tone: 'warning' as const, size: 16 + (c.count / maxCount) * 44, label: `${c.count} SOS in this cell` })),
      ...g.sos.filter((s) => !['resolved', 'cancelled'].includes(s.status)).map((s) => {
        const t = priorityTone(s.priority);
        return { id: s.reference_id, kind: 'sos' as const, lat: s.lat, lng: s.lng, tone: t === 'muted' ? ('info' as const) : t, label: `${s.reference_id} · P${s.priority} · ${s.status}`, href: `/sos/${s.reference_id}` };
      }),
      ...g.devices.map((d) => ({ id: d.device_id, kind: 'device' as const, lat: d.lat, lng: d.lng, tone: levelTone(d.alert_level ?? alertLevelOf(d.state)), label: `${d.device_id} · ${stateLabel(d.state)}` })),
      ...g.teams.map((t) => ({ id: String(t.id), kind: 'team' as const, lat: t.lat, lng: t.lng, tone: 'info' as const, label: t.name })),
      ...g.rovs.map((r) => ({ id: r.id, kind: 'rov' as const, lat: r.lat, lng: r.lng, tone: 'accent' as const, label: `${r.name} · ${r.status}` })),
      ...g.rivers.map((r) => ({ id: r.name, kind: 'river' as const, lat: r.lat, lng: r.lng, tone: r.trend === 'rising' ? ('warning' as const) : ('info' as const), label: `${r.name}: ${num(r.discharge_m3s, 0)} m³/s, ${r.trend}` })),
    ];
  }, [g]);

  if (q.loading && !g) return <Skeleton rows={8} />;
  if (!g) return <ErrorState error={q.error} onRetry={q.reload} />;
  const src = g.rivers[0]?.source;
  return (
    <div className="geo-grid">
      <Panel title="SOS density and assets" bodyClass="panel-body--flush map-body map-body--lg"
        actions={<Provenance source={`database · ${g.sos.length} SOS, ${g.grid.length} cells (0.02°)`} at={g.generated_at} />}>
        <MapView markers={markers} label="SOS density grid with live assets and river gauges" fitKey="geo" />
        <ul className="map-legend" aria-label="Legend">
          <li><svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="5" fill="var(--warning)" fillOpacity="0.3" stroke="var(--warning)" /></svg>SOS density</li>
          <li><svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true"><path d="M6 1 L11 10 L1 10 Z" fill="var(--info)" /></svg>River gauge</li>
        </ul>
      </Panel>
      <Panel title="Rivers" bodyClass="panel-body--flush"
        actions={<Provenance source={src ?? 'no river source'} at={g.rivers[0]?.updated_at} />}>
        {g.rivers.length === 0 ? <Empty title="No river data">The backend pulls GloFAS discharge from the Open-Meteo Flood API.</Empty> : (
          <div className="table-wrap" tabIndex={0} role="region" aria-label="River gauges">
            <table className="table">
              <thead><tr><th scope="col">River</th><th scope="col" className="r">Now m³/s</th><th scope="col" className="r">30-day median</th><th scope="col" className="r">Ratio</th><th scope="col">Trend</th><th scope="col">{g.rivers[0] ? `Discharge (${riverSpan(g.rivers[0])})` : 'Discharge'}</th></tr></thead>
              <tbody>{g.rivers.map((r) => <RiverRow key={r.name} r={r} />)}</tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}

// ─── AI predictions ──────────────────────────────────────────────────────────

function kv(obj: Record<string, unknown> | null | undefined) {
  if (!obj) return null;
  return Object.entries(obj).map(([k, v]) => `${k.replace(/_/g, ' ')} ${typeof v === 'number' ? (v < 1 && v > 0 ? v.toFixed(3) : v) : String(v)}`).join(' · ');
}

export function ModelsTab() {
  const q = useAsync(() => api.models(), []);
  const m = q.data;
  if (q.loading && !m) return <Skeleton rows={8} />;
  if (!m) return <ErrorState error={q.error} onRetry={q.reload} />;
  const fa = Object.entries(m.fusion?.false_alarms_per_8h ?? {});
  const falls = m.fusion?.falls_caught as Record<string, unknown> | string | null | undefined;
  return (
    <div className="stack-lg">
      <Panel title="Wearable Tier-1 heads" bodyClass="panel-body--flush" actions={<Provenance source="model registry · out-of-fold, subject-bootstrap CI" at={m.generated_at} />}>
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Wearable model heads">
          <table className="table">
            <thead><tr><th scope="col">Head</th><th scope="col">Model</th><th scope="col" className="r">Macro-F1</th><th scope="col" className="r">95 % CI</th><th scope="col" className="r">AUROC</th><th scope="col" className="r">Threshold</th><th scope="col">External test</th></tr></thead>
            <tbody>
              {m.wearable.map((h) => (
                <tr key={h.head}>
                  <th scope="row">{h.head.replace('_', ' ')}{h.head === 'stress' && <Chip tone="warning">advisory</Chip>}</th>
                  <td className="mono muted">{h.model}</td>
                  <td className="r mono">{num(h.macro_f1, 3)}</td>
                  <td className="r mono muted">{h.ci95?.length === 2 ? `${h.ci95[0].toFixed(3)}–${h.ci95[1].toFixed(3)}` : '—'}</td>
                  <td className="r mono">{num(h.auroc, 3)}</td>
                  <td className="r mono">{h.threshold == null ? 'argmax' : h.threshold.toFixed(2)}</td>
                  <td className="muted">{kv(h.external) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <div className="grid-2">
        <Panel title={`Fusion ${m.fusion?.version ?? ''}: critical false alarms per 8 h`} actions={<Provenance source="replay on real daily-life recordings" />}>
          {fa.length === 0 ? <Empty title="No replay results" /> : (
            <HBars format={(n) => n.toFixed(2)} items={fa.map(([k, v]) => ({ key: k, label: <span className="mono">{k}</span>, value: v, tone: v > 1.5 ? 'warning' : 'ok' }))} />
          )}
          {falls && (
            <p className="field-hint" style={{ marginTop: 12 }}>
              Falls → stasis: {typeof falls === 'string' ? falls : kv(falls as Record<string, unknown>)}
            </p>
          )}
        </Panel>
        <Panel title="Rhythm head on PPG atrial fibrillation" actions={<Provenance source="external test" />}>
          {m.rhythm_ppg_af ? <p className="mono">{kv(m.rhythm_ppg_af)}</p> : <Empty title="Not evaluated yet">An external PPG AF test set has not been run for the rhythm head.</Empty>}
        </Panel>
      </div>
      <ModelCardPanel card={m.weather} loading={false} error={null} onRetry={q.reload} />
      <p className="field-hint">Weather model card generated {dayHhmm(m.generated_at)}.</p>
    </div>
  );
}
