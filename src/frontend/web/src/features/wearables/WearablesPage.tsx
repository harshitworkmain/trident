import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { reloadSnapshot, telemetry, useLive } from '../../api/live';
import type { DeviceSummary } from '../../api/types';
import { ago, num, pct } from '../../lib/format';
import { useNow } from '../../lib/hooks';
import { levelTone, stateLabel } from '../../lib/states';
import { Sparkline, token } from '../../ui/charts';
import { Battery, Empty, ErrorState, Meter, Skeleton, StateChip } from '../../ui/primitives';

type Filter = 'all' | 'attention' | 'online' | 'offline';
const RANK = { critical: 0, advisory: 1, none: 2 } as const;
const SPARK_N = 80; // ~2 min at 1.5 s

function DeviceTile({ d, now, tick }: { d: DeviceSummary; now: number; tick: number }) {
  const buf = telemetry.get(d.device_id) ?? [];
  const tail = buf.slice(-SPARK_N);
  const last = tail[tail.length - 1];
  const colors = useMemo(() => [token('--series-1'), token('--series-2'), token('--series-3'), token('--series-4')], []);
  void tick;
  const vit: [string, (number | null)[], number | null | undefined, string, number][] = [
    ['HR', tail.map((p) => p.bpm), last?.bpm, 'bpm', 0],
    ['SpO₂', tail.map((p) => p.spo2), last?.spo2, '%', 0],
    ['Skin', tail.map((p) => p.temp), last?.temp, '°C', 1],
    ['EDA', tail.map((p) => p.eda), last?.eda, 'µS', 1],
  ];
  const tone = levelTone(d.state.alert_level);
  return (
    <li className={`dev-tile dev-tile--${d.online ? tone : 'off'}`}>
      <Link to={`/wearables/${encodeURIComponent(d.device_id)}`} className="dev-link" aria-label={`${d.device_id}, ${d.label}, ${stateLabel(d.state.ml_health_state)}, ${d.online ? 'online' : 'offline'}`}>
        <div className="dev-head">
          <span className={`dot ${d.online ? 'dot--ok' : 'dot--off'}`} aria-hidden="true" />
          <span className="mono dev-id">{d.device_id}</span>
          <span className="dev-label">{d.label}</span>
        </div>
        <div className="dev-state">
          <StateChip state={d.state.ml_health_state} level={d.state.alert_level} />
          <span className="mono muted">risk {pct(d.state.risk)}</span>
        </div>
        <Meter value={d.state.risk} tone={tone === 'ok' ? 'ok' : tone} label="Risk" />
        <div className="dev-vitals">
          {vit.map(([name, series, v, unit, dg], i) => (
            <div key={name} className="vital">
              <span className="vital-name">{name}</span>
              <span className="vital-val mono">{d.online ? num(v, dg) : '—'}<small>{unit}</small></span>
              <Sparkline values={series} color={colors[i]} label={`${name} trend`} />
            </div>
          ))}
        </div>
        <div className="dev-foot">
          <Battery volts={d.battery_v} />
          <span className="mono muted" title={d.last_seen ?? ''}>{d.online ? `${ago(d.last_seen, now)} ago` : `offline ${ago(d.last_seen, now)}`}</span>
        </div>
      </Link>
    </li>
  );
}

export default function WearablesPage() {
  const devices = useLive((s) => s.devices);
  const tick = useLive((s) => s.telemetryTick);
  const load = useLive((s) => s.load.devices);
  const now = useNow(2000);
  const [filter, setFilter] = useState<Filter>('all');

  const list = useMemo(() => Object.values(devices)
    .filter((d) => filter === 'all' || (filter === 'attention' ? d.state.alert_level !== 'none' : filter === 'online' ? d.online : !d.online))
    .sort((a, b) => Number(b.online) - Number(a.online) || RANK[a.state.alert_level] - RANK[b.state.alert_level] || a.device_id.localeCompare(b.device_id)), [devices, filter]);
  const all = Object.values(devices);
  const counts = { online: all.filter((d) => d.online).length, critical: all.filter((d) => d.online && d.state.alert_level === 'critical').length };

  return (
    <div className="page">
      <div className="page-head">
        <h1>Wearables</h1>
        <span className="muted"><span className="mono">{counts.online}</span> of <span className="mono">{all.length}</span> online{counts.critical > 0 && <> · <span className="text-critical mono">{counts.critical}</span> critical</>}</span>
        <div className="segmented page-head-right" role="group" aria-label="Filter devices">
          {(['all', 'attention', 'online', 'offline'] as Filter[]).map((f) => (
            <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}>{f === 'attention' ? 'Needs attention' : f[0].toUpperCase() + f.slice(1)}</button>
          ))}
        </div>
      </div>
      {load === 'loading' && !all.length ? <Skeleton rows={8} /> : load === 'error' && !all.length ? (
        <ErrorState error="The device list could not be loaded." onRetry={() => void reloadSnapshot('devices')} />
      ) : list.length === 0 ? (
        <Empty title={all.length ? 'No devices match this filter' : 'No wearables registered'}>{all.length ? null : 'An admin can register bands on the Admin page.'}</Empty>
      ) : (
        <ul className="dev-grid" aria-label="Wearable devices">
          {list.map((d) => <DeviceTile key={d.device_id} d={d} now={now} tick={tick} />)}
        </ul>
      )}
    </div>
  );
}
