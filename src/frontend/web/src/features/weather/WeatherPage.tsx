import { useMemo, useState } from 'react';
import type { AlignedData } from 'uplot';
import { api } from '../../api/client';
import { useLive } from '../../api/live';
import { FORECAST_VARS, type Forecast, type ForecastVar, type ModelCard } from '../../api/types';
import { ago, dayHhmm, hhmm, num, siteName, titleCase } from '../../lib/format';
import { useAsync } from '../../lib/hooks';
import { token, UPlot, useBandOptions } from '../../ui/charts';
import { Chip, Empty, ErrorState, Panel, Skeleton, Stat } from '../../ui/primitives';

const VAR_META: Record<ForecastVar, { name: string; unit: string; color: string; digits: number; bars?: boolean }> = {
  temp_c: { name: 'Temperature', unit: '°C', color: '--series-1', digits: 1 },
  rain_mm: { name: 'Rain', unit: 'mm/h', color: '--series-2', digits: 1, bars: true },
  wind_ms: { name: 'Wind', unit: 'm/s', color: '--series-4', digits: 1 },
  pressure_hpa: { name: 'Pressure', unit: 'hPa', color: '--series-3', digits: 1 },
  rh: { name: 'Humidity', unit: '%', color: '--series-5', digits: 0 },
};

function BandChart({ v, fc }: { v: ForecastVar; fc: Forecast }) {
  const m = VAR_META[v];
  const opts = useBandOptions(m.name, m.unit, token(m.color), m.bars);
  const data = useMemo<AlignedData>(() => {
    const h = fc.horizon;
    return [h.map((s) => Date.parse(s.time) / 1000), h.map((s) => s[v]?.p10 ?? null), h.map((s) => s[v]?.p50 ?? null), h.map((s) => s[v]?.p90 ?? null)];
  }, [fc, v]);
  const peak = fc.horizon.reduce((best, s) => (s[v] && s[v].p50 > (best?.[v]?.p50 ?? -Infinity) ? s : best), fc.horizon[0]);
  const total = v === 'rain_mm' ? fc.horizon.reduce((a, s) => a + (s.rain_mm?.p50 ?? 0), 0) : null;
  return (
    <section className="fchart" aria-label={`${m.name} forecast`}>
      <header>
        <h3>{m.name} <span className="muted">{m.unit}</span></h3>
        <span className="muted mono">
          {total !== null ? `${num(total, 0)} mm total (p50)` : `peak ${num(peak?.[v]?.p50, m.digits)} at ${hhmm(peak?.time)}`}
        </span>
      </header>
      <UPlot options={opts} data={data} height={150} label={`${m.name} forecast, median with 10th to 90th percentile band`} />
    </section>
  );
}

function SkillTable({ card }: { card: ModelCard }) {
  const skill = card.skill ?? [];
  if (!skill.length) return <p className="muted">No backtest results in the model card.</p>;
  const horizons = [...new Set(skill.map((s) => s.horizon_h))].sort((a, b) => a - b);
  const vars = [...new Set(skill.map((s) => s.variable))];
  return (
    <div className="table-wrap" tabIndex={0} role="region" aria-label="Backtest skill">
      <table className="table skill-table">
        <caption className="sr-only">Backtest skill versus persistence, by variable and horizon. Positive means better than persistence.</caption>
        <thead><tr><th scope="col">Variable</th><th scope="col">Model</th>{horizons.map((h) => <th key={h} scope="col" className="r">+{h} h</th>)}</tr></thead>
        <tbody>
          {vars.map((v) => (
            <tr key={v}>
              <th scope="row">{VAR_META[v as ForecastVar]?.name ?? v}</th>
              <td className="mono muted nowrap skill-model">{card.chosen?.[v] ?? '—'}</td>
              {horizons.map((h) => {
                const c = skill.find((s) => s.variable === v && s.horizon_h === h);
                const tone = !c ? '' : c.skill > 0.05 ? 'text-ok' : c.skill < 0 ? 'text-critical' : 'muted';
                return (
                  <td key={h} className={`r mono ${tone}`} title={c ? `MAE ${c.model_mae} vs persistence ${c.persistence_mae}` : undefined}>
                    {c ? `${c.skill >= 0 ? '+' : ''}${(c.skill * 100).toFixed(0)}%` : '—'}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ModelCardPanel({ card, loading, error, onRetry }: { card?: ModelCard; loading: boolean; error: Error | null; onRetry: () => void }) {
  const range = card?.training_data ?? card?.training_range;
  return (
    <Panel title="Forecast model" actions={card?.model_version ? <span className="mono muted">{card.model_version}</span> : undefined}>
      {loading && !card ? <Skeleton rows={5} /> : error && !card ? <ErrorState error={error} onRetry={onRetry} /> : !card ? null : (
        <div className="stack">
          <dl className="kv">
            {range && <><dt>Training data</dt><dd className="mono">{range.from} → {range.to}{'rows' in range && range.rows ? ` · ${Number(range.rows).toLocaleString('en-IN')} rows` : ''}</dd></>}
            {card.training_data?.source && <><dt>Source</dt><dd>{card.training_data.source}</dd></>}
            {card.candidates && <><dt>Candidates</dt><dd className="mono">{card.candidates.map((c) => (typeof c === 'string' ? c : c.name)).join(', ')}</dd></>}
          </dl>
          <h3 className="sub-h">Backtest skill vs persistence <span className="muted">(1 − MAE / MAE persistence)</span></h3>
          <SkillTable card={card} />
        </div>
      )}
    </Panel>
  );
}

export default function WeatherPage() {
  const [hours, setHours] = useState(48);
  const liveWx = useLive((s) => s.weather);
  const cur = useAsync(() => api.weatherCurrent(), []);
  const fc = useAsync(() => api.forecast(hours), [hours]);
  const card = useAsync(() => api.modelCard(), []);
  const w = liveWx ?? cur.data;

  return (
    <div className="page">
      <div className="page-head">
        <h1>Weather</h1>
        <span className="muted">{siteName(w?.site ?? fc.data?.site)}</span>
        <div className="segmented page-head-right" role="group" aria-label="Forecast horizon">
          {[24, 48].map((h) => <button key={h} type="button" aria-pressed={hours === h} onClick={() => setHours(h)}>{h} h</button>)}
        </div>
      </div>

      {cur.loading && !w ? <Skeleton rows={2} /> : !w ? <ErrorState error={cur.error} onRetry={cur.reload} title="Current conditions unavailable" /> : (
        <div className="kpi-strip" role="group" aria-label="Current conditions">
          <Stat label="Temperature" value={num(w.temp_c, 1)} unit="°C" />
          <Stat label="Humidity" value={num(w.rh)} unit="%" />
          <Stat label="Rain" value={num(w.rain_mm, 1)} unit="mm/h" />
          <Stat label="Wind" value={num(w.wind_ms, 1)} unit="m/s" sub={w.gust_ms != null ? `gusts ${num(w.gust_ms, 1)} m/s` : undefined} />
          <Stat label="Pressure" value={num(w.pressure_hpa, 1)} unit="hPa" />
          <Stat label="Observed" value={<span className="mono">{hhmm(w.observed_at)}</span>} sub={`${ago(w.observed_at)} ago · ${w.source === 'offline-csv' ? 'offline CSV fallback' : 'Open-Meteo'}`} />
        </div>
      )}

      <div className="wx-grid">
        <Panel title={`Forecast, next ${hours} h`} className="wx-charts"
          actions={fc.data ? <span className="muted mono">model {fc.data.model_version} · run {dayHhmm(fc.data.generated_at)}</span> : undefined}>
          {fc.loading && !fc.data ? <Skeleton rows={10} /> : fc.error && !fc.data ? <ErrorState error={fc.error} onRetry={fc.reload} /> : !fc.data?.horizon.length ? (
            <Empty title="No forecast available">The forecast job runs every 30 minutes.</Empty>
          ) : (
            <>
              <p className="chart-legend"><span className="lg-line" />median (p50) <span className="lg-band" />10th–90th percentile</p>
              <div className="fcharts">{FORECAST_VARS.map((v) => <BandChart key={v} v={v} fc={fc.data!} />)}</div>
            </>
          )}
        </Panel>

        <div className="wx-side">
          <Panel title="Hazards" count={fc.data?.hazards.length ?? 0}>
            {!fc.data ? <Skeleton rows={3} /> : fc.data.hazards.length === 0 ? <Empty title="No hazards in this horizon" /> : (
              <ul className="hazards">
                {fc.data.hazards.map((h) => (
                  <li key={`${h.type}${h.from}`}>
                    <div className="row"><Chip tone={h.level === 'warning' ? 'warning' : 'info'}>{h.level}</Chip><strong>{titleCase(h.type)}</strong></div>
                    <span className="mono muted">{dayHhmm(h.from)} → {dayHhmm(h.to)}</span>
                    <p>{h.reason}</p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <ModelCardPanel card={card.data} loading={card.loading} error={card.error} onRetry={card.reload} />
        </div>
      </div>
    </div>
  );
}
