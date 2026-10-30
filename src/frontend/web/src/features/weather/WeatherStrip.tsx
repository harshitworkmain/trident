import { Link } from 'react-router-dom';
import { CloudRain } from 'lucide-react';
import { useLive } from '../../api/live';
import { ago, hhmm, num, titleCase } from '../../lib/format';
import { Chip } from '../../ui/primitives';

export function WeatherStrip() {
  const w = useLive((s) => s.weather);
  const hazards = useLive((s) => s.hazards);
  const load = useLive((s) => s.load.weather);
  return (
    <section className="wx-strip" aria-label="Weather now">
      <Link to="/weather" className="wx-strip-title"><CloudRain aria-hidden="true" />Weather</Link>
      {load === 'loading' && !w ? <span className="skeleton" style={{ width: 280 }} /> : !w ? (
        <span className="muted">Weather service unavailable</span>
      ) : (
        <dl className="wx-vals">
          <div><dt>Temp</dt><dd className="mono">{num(w.temp_c, 1)}<small>°C</small></dd></div>
          <div><dt>Rain</dt><dd className="mono">{num(w.rain_mm, 1)}<small>mm/h</small></dd></div>
          <div><dt>Wind</dt><dd className="mono">{num(w.wind_ms, 1)}{w.gust_ms != null && <small>g{num(w.gust_ms, 0)}</small>}<small>m/s</small></dd></div>
          <div><dt>RH</dt><dd className="mono">{num(w.rh)}<small>%</small></dd></div>
          <div><dt>Pressure</dt><dd className="mono">{num(w.pressure_hpa, 1)}<small>hPa</small></dd></div>
          <div className="wx-obs"><dt className="sr-only">Observed</dt><dd className="muted mono" title={w.observed_at}>{w.source === 'offline-csv' ? 'offline data' : 'obs'} {ago(w.observed_at)} ago</dd></div>
        </dl>
      )}
      <div className="wx-hazards">
        {hazards.length === 0 && w && <span className="muted">No active hazards</span>}
        {hazards.map((h) => (
          <Chip key={`${h.type}${h.from}`} tone={h.level === 'warning' ? 'warning' : 'info'} title={h.reason}>
            {titleCase(h.type)} {h.level} · {hhmm(h.from)}–{hhmm(h.to)}
          </Chip>
        ))}
      </div>
    </section>
  );
}
