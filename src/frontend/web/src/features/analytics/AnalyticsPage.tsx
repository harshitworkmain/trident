import { useMemo, useState, type KeyboardEvent } from 'react';
import type { AlignedData } from 'uplot';
import { api } from '../../api/client';
import type { Bucket, Metric, ResponseTimes } from '../../api/types';
import { num, titleCase } from '../../lib/format';
import { useAsync } from '../../lib/hooks';
import { SOS_LABEL } from '../../lib/states';
import { token, UPlot, useSeriesOptions } from '../../ui/charts';
import { Empty, ErrorState, Panel, Skeleton, Stat } from '../../ui/primitives';
import { HBars, Provenance, useInterval } from './common';
import { GeoTab, ModelsTab, SensorsTab } from './AnalyticsTabs';

const TABS = ['Overview', 'Sensors', 'Trends', 'Geographic', 'Performance', 'AI predictions'] as const;
type Tab = (typeof TABS)[number];

const METRICS: { key: Metric; label: string }[] = [
  { key: 'sos_created', label: 'SOS created' },
  { key: 'sos_resolved', label: 'SOS resolved' },
  { key: 'alerts', label: 'Alerts opened' },
  { key: 'telemetry_frames', label: 'Telemetry frames' },
  { key: 'state_changes', label: 'Wearable state changes' },
];

const sinceFor = (b: Bucket) => new Date(Date.now() - (b === 'minute' ? 60 * 60e3 : b === 'hour' ? 24 * 3600e3 : 14 * 86400e3)).toISOString();

function SeriesChart({ metrics, bucket, height = 180, bars }: { metrics: Metric[]; bucket: Bucket; height?: number; bars?: boolean }) {
  const q = useAsync(() => Promise.all(metrics.map((m) => api.timeseries(m, bucket, sinceFor(bucket)))), [metrics.join(','), bucket]);
  useInterval(q.reload, bucket === 'minute' ? 30_000 : 120_000);
  const colors = useMemo(() => metrics.map((_, i) => token(`--series-${(i % 5) + 1}`)), [metrics]);
  const opts = useSeriesOptions(metrics.map((m) => METRICS.find((x) => x.key === m)?.label ?? m), colors, bars, bucket === 'day');
  const data = useMemo<AlignedData | null>(() => {
    if (!q.data?.length) return null;
    const xs = q.data[0].points.map((p) => Date.parse(p.t) / 1000);
    return [xs, ...q.data.map((s) => xs.map((x) => s.points.find((p) => Date.parse(p.t) / 1000 === x)?.value ?? 0))] as AlignedData;
  }, [q.data]);
  if (q.loading && !data) return <Skeleton rows={4} />;
  if (q.error && !data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!data || data[0].length === 0) return <Empty title="No data in this window" />;
  const total = q.data!.map((s) => s.points.reduce((a, p) => a + p.value, 0));
  return (
    <div>
      <p className="chart-legend">
        {metrics.map((m, i) => (
          <span key={m}><span className="lg-swatch" style={{ background: colors[i] }} />{METRICS.find((x) => x.key === m)?.label} <span className="mono muted">{total[i]}</span></span>
        ))}
      </p>
      <UPlot options={opts} data={data} height={height} label={`${metrics.join(', ')} per ${bucket}`} />
    </div>
  );
}

function Overview() {
  const sum = useAsync(() => api.summary(), []);
  const by = useAsync(() => Promise.all([api.breakdown('type'), api.breakdown('status'), api.breakdown('priority')]), []);
  useInterval(sum.reload, 30_000);
  const s = sum.data;
  return (
    <div className="stack-lg">
      {sum.loading && !s ? <Skeleton rows={2} /> : !s ? <ErrorState error={sum.error} onRetry={sum.reload} /> : (
        <div className="kpi-strip">
          <Stat label="Open SOS" value={s.sos_open} />
          <Stat label="Critical open" value={s.sos_critical} tone={s.sos_critical ? 'critical' : undefined} />
          <Stat label="Avg response" value={num(s.avg_response_min, 1)} unit="min" />
          <Stat label="Teams available" value={s.teams_available} />
          <Stat label="Wearables online" value={s.devices_online} />
          <Stat label="Open alerts" value={s.alerts_open} tone={s.alerts_open ? 'critical' : undefined} />
        </div>
      )}
      <Panel title="SOS created vs resolved, last 24 h" actions={<Provenance source="database · hourly" />}>
        <SeriesChart metrics={['sos_created', 'sos_resolved']} bucket="hour" />
      </Panel>
      <div className="grid-3">
        {(['type', 'status', 'priority'] as const).map((k, i) => {
          const d = by.data?.[i];
          return (
            <Panel key={k} title={`By ${k}`} actions={<Provenance source="database · all SOS" />}>
              {by.loading && !d ? <Skeleton rows={4} /> : by.error && !d ? <ErrorState error={by.error} onRetry={by.reload} /> : !d?.items.length ? <Empty title="No SOS yet" /> : (
                <HBars items={d.items.map((x) => ({
                  key: x.key, value: x.count,
                  label: k === 'status' ? SOS_LABEL[x.key as keyof typeof SOS_LABEL] ?? x.key : k === 'priority' ? (x.key.startsWith('P') ? x.key : `P${x.key}`) : titleCase(x.key),
                  tone: k === 'priority' && /1$/.test(x.key) ? 'critical' : undefined,
                }))} />
              )}
            </Panel>
          );
        })}
      </div>
    </div>
  );
}

function Trends() {
  const [metric, setMetric] = useState<Metric>('sos_created');
  const [bucket, setBucket] = useState<Bucket>('hour');
  return (
    <div className="stack-lg">
      <Panel title={METRICS.find((m) => m.key === metric)?.label} actions={(
        <>
          <select className="select input--sm" aria-label="Metric" value={metric} onChange={(e) => setMetric(e.target.value as Metric)} style={{ width: 200 }}>
            {METRICS.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
          </select>
          <div className="segmented" role="group" aria-label="Bucket">
            {(['minute', 'hour', 'day'] as Bucket[]).map((b) => <button key={b} type="button" aria-pressed={bucket === b} onClick={() => setBucket(b)}>{b === 'minute' ? 'Last hour' : b === 'hour' ? 'Last 24 h' : 'Last 14 d'}</button>)}
          </div>
          <Provenance source={`database · per ${bucket}`} />
        </>
      )}>
        <SeriesChart metrics={[metric]} bucket={bucket} height={240} bars={bucket !== 'minute'} />
      </Panel>
      <div className="grid-2">
        <Panel title="Telemetry ingest, last hour" actions={<Provenance source="live ingest · per minute" />}><SeriesChart metrics={['telemetry_frames']} bucket="minute" height={140} /></Panel>
        <Panel title="Alerts and state changes, last 24 h" actions={<Provenance source="database · hourly" />}><SeriesChart metrics={['alerts', 'state_changes']} bucket="hour" height={140} bars /></Panel>
      </div>
    </div>
  );
}

export function ResponseTable({ rt }: { rt: ResponseTimes }) {
  const max = Math.max(1, ...rt.items.map((i) => i.p95 ?? i.p90 ?? 0));
  return (
    <div className="table-wrap" tabIndex={0} role="region" aria-label="Response time percentiles">
      <table className="table">
        <caption className="sr-only">Response time percentiles by priority, minutes from creation to on scene</caption>
        <thead><tr><th scope="col">Priority</th><th scope="col" className="r">n</th><th scope="col" className="r">p50</th><th scope="col" className="r">p90</th><th scope="col" className="r">p95</th><th scope="col" style={{ width: '40%' }}>Distribution (min)</th></tr></thead>
        <tbody>
          {rt.items.map((r) => (
            <tr key={r.priority}>
              <th scope="row"><span className={`prio prio--${r.priority}`}>{r.priority}</span></th>
              <td className="r mono">{r.n}</td>
              <td className="r mono">{num(r.p50, 1)}</td>
              <td className="r mono">{num(r.p90, 1)}</td>
              <td className="r mono">{num(r.p95, 1)}</td>
              <td>
                {r.p50 != null ? (
                  <span className="pbar" aria-hidden="true">
                    <span className="pbar-range" style={{ left: `${((r.p50 ?? 0) / max) * 100}%`, width: `${(((r.p95 ?? r.p90 ?? r.p50) - r.p50) / max) * 100}%` }} />
                    <span className="pbar-mid" style={{ left: `${(r.p50 / max) * 100}%` }} />
                  </span>
                ) : <span className="muted">no completed rescues</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Performance() {
  const q = useAsync(() => api.performance(), []);
  useInterval(q.reload, 60_000);
  const p = q.data;
  if (q.loading && !p) return <Skeleton rows={8} />;
  if (!p) return <ErrorState error={q.error} onRetry={q.reload} />;
  return (
    <div className="stack-lg">
      <div className="kpi-strip">
        <Stat label="Alert ack p50" value={num(p.alert_ack.p50_s, 0)} unit="s" sub={`${p.alert_ack.n} acknowledged`} />
        <Stat label="Alert ack p90" value={num(p.alert_ack.p90_s, 0)} unit="s" tone={(p.alert_ack.p90_s ?? 0) > 120 ? 'warning' : undefined} sub="escalates after 120 s" />
        <Stat label="ROV missions" value={p.missions.n} />
        <Stat label="Median ROV transit" value={num(p.missions.median_transit_min, 1)} unit="min" />
      </div>
      <div className="grid-2">
        <Panel title="Response time by priority" actions={<Provenance source="database · created → on scene" at={p.generated_at} />}>
          <ResponseTable rt={p.response_times} />
        </Panel>
        <Panel title="Team utilisation" actions={<Provenance source="live · teams" at={p.generated_at} />}>
          {p.team_utilization.length === 0 ? <Empty title="No teams" /> : (
            <HBars max={1} format={(n) => `${Math.round(n * 100)}%`}
              items={p.team_utilization.map((t) => ({ key: String(t.team_id), value: t.utilization, label: <>{t.name} <span className="mono muted">{t.load}/{t.capacity}</span></>, tone: t.utilization >= 1 ? 'critical' : t.utilization >= 0.75 ? 'warning' : 'ok' }))} />
          )}
        </Panel>
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const [tab, setTab] = useState<Tab>(() => {
    try { return (sessionStorage.getItem('trident.analytics.tab') as Tab) || 'Overview'; } catch { return 'Overview'; }
  });
  const choose = (t: Tab) => {
    setTab(t);
    try { sessionStorage.setItem('trident.analytics.tab', t); } catch { /* ignore */ }
  };
  const onKey = (e: KeyboardEvent) => {
    const i = TABS.indexOf(tab);
    if (e.key === 'ArrowRight') { e.preventDefault(); choose(TABS[(i + 1) % TABS.length]); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); choose(TABS[(i - 1 + TABS.length) % TABS.length]); }
  };
  return (
    <div className="page">
      <div className="page-head"><h1>Analytics</h1></div>
      <div className="tabs" role="tablist" aria-label="Analytics sections" onKeyDown={onKey}>
        {TABS.map((t) => (
          <button key={t} role="tab" id={`tab-${t}`} aria-selected={tab === t} aria-controls="tabpanel" tabIndex={tab === t ? 0 : -1} onClick={() => choose(t)}>{t}</button>
        ))}
      </div>
      <div id="tabpanel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="tabpanel">
        {tab === 'Overview' && <Overview />}
        {tab === 'Sensors' && <SensorsTab />}
        {tab === 'Trends' && <Trends />}
        {tab === 'Geographic' && <GeoTab />}
        {tab === 'Performance' && <Performance />}
        {tab === 'AI predictions' && <ModelsTab />}
      </div>
    </div>
  );
}
