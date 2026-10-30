import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, MapPin } from 'lucide-react';
import { api } from '../../api/client';
import type { PublicSummary } from '../../api/types';
import { hhmm, titleCase } from '../../lib/format';
import { CountUp, RevealLines } from '../../ui/effects';
import { Chip } from '../../ui/primitives';
import { rememberSmsNumber } from './offline';
import { EmergencyNumbers, PublicFooter, PublicHeader } from './PublicChrome';

function usePublicSummary() {
  const [data, setData] = useState<PublicSummary | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let alive = true;
    const load = () => api.publicSummary()
      .then((d) => { rememberSmsNumber(d.sms_number); if (alive) { setData(d); setFailed(false); } })
      .catch(() => { if (alive) setFailed(true); });
    void load();
    const id = window.setInterval(load, 30_000);
    return () => { alive = false; window.clearInterval(id); };
  }, []);
  return { data, failed };
}

function LiveStrip() {
  const { data, failed } = usePublicSummary();
  // The strip is informative, not essential: if the summary is unavailable it simply disappears.
  if (failed && !data) return null;
  const cells: [string, number | null | undefined, string?][] = [
    ['Rescue teams available', data?.teams_available, data ? `of ${data.teams_total}` : undefined],
    ['Open requests', data?.sos_open],
    ['Resolved, last 24 h', data?.sos_resolved_24h],
    ['Wearables online', data?.devices_online],
  ];
  return (
    <section className="live-strip" aria-label="Live status">
      <div className="live-strip-head">
        <span className="live-dot" aria-hidden="true" />
        <span>Live</span>
        {data && <span className="muted mono">updated {hhmm(data.updated_at)}</span>}
      </div>
      <dl className="live-cells">
        {cells.map(([label, v, sub]) => (
          <div key={label} className="live-cell">
            <dt>{label}</dt>
            <dd>{data ? <CountUp value={v ?? null} /> : <span className="skeleton" style={{ width: 40, height: 22 }} />}{sub && <small> {sub}</small>}</dd>
          </div>
        ))}
        <div className="live-cell live-cell--wx">
          <dt>Weather now</dt>
          <dd>
            {data ? <><CountUp value={data.weather.temp_c} digits={1} /><small> °C</small></> : <span className="skeleton" style={{ width: 40, height: 22 }} />}
            {data?.weather.hazards.map((h) => (
              <Chip key={h.type + h.level} tone={h.level === 'warning' ? 'warning' : 'info'}>{titleCase(h.type)} {h.level}</Chip>
            ))}
          </dd>
        </div>
      </dl>
    </section>
  );
}

function lastRequest(): { ref: string; token: string } | null {
  try { return JSON.parse(localStorage.getItem('trident.sos.last') ?? 'null'); } catch { return null; }
}

export function LandingPage() {
  const last = lastRequest();
  return (
    <div className="public">
      <PublicHeader />
      <main id="main" className="landing">
        <section className="hero">
          <div className="hero-text">
            <p className="eyebrow mono">Chennai · flood and water rescue</p>
            <RevealLines lines={['Trapped by floodwater?', 'Send your location', 'to the rescue teams.']} className="hero-title" />
            <p className="hero-lede">
              One short form reaches the control room that dispatches NDRF, SDRF, fire and rescue, coast guard and volunteer boat teams.
              It works on a weak mobile connection and saves as you type.
            </p>
            <div className="hero-actions">
              <Link to="/sos" className="btn btn--primary btn--lg"><MapPin aria-hidden="true" />Request help</Link>
              {last ? (
                <Link to={`/track/${encodeURIComponent(last.ref)}?token=${encodeURIComponent(last.token)}`} className="btn btn--lg">
                  Track <span className="mono">{last.ref}</span>
                </Link>
              ) : (
                <a href="#track" className="btn btn--lg btn--ghost">Track a request</a>
              )}
            </div>
          </div>
          <EmergencyNumbers />
        </section>

        <LiveStrip />

        <section className="steps" aria-labelledby="steps-title">
          <h2 id="steps-title">What happens after you send a request</h2>
          <ol>
            <li><span className="step-n mono">01</span><div><h3>You get a reference number</h3><p>Keep it. The tracking link shows every status change, from received to rescued.</p></div></li>
            <li><span className="step-n mono">02</span><div><h3>It is ranked within seconds</h3><p>Injuries, medical needs, elderly people, children and running out of water raise the priority. Nobody is dropped from the queue.</p></div></li>
            <li><span className="step-n mono">03</span><div><h3>A dispatcher assigns the nearest team</h3><p>Only a team with free capacity is assigned, so two boats are not sent to one house while another waits.</p></div></li>
            <li><span className="step-n mono">04</span><div><h3>The team comes to you</h3><p>Stay where you said you are, keep your phone charged and on, and signal from a terrace or window.</p></div></li>
          </ol>
        </section>

        <section className="about" aria-labelledby="about-title">
          <h2 id="about-title">What TRIDENT is</h2>
          <div className="about-grid">
            <div><h3>Public requests</h3><p>The form on this site, with location from your phone and an automatic priority score the dispatcher can see the reasons for.</p></div>
            <div><h3>Dispatch console</h3><p>A live queue, a map of requests, teams and underwater ROVs, and team capacity, shared by everyone in the control room.</p></div>
            <div><h3>Wearable bands</h3><p>Worn by rescuers and evacuees. They stream heart rate, SpO₂, skin temperature and motion, and flag falls, hypothermia or a stopped heart.</p></div>
            <div><h3>48-hour forecast</h3><p>Rain, wind and pressure for Chennai with an uncertainty range, so teams are staged before the heavy rain arrives.</p></div>
          </div>
        </section>

        <section id="track" className="track-cta" aria-labelledby="track-title">
          <h2 id="track-title">Track a request</h2>
          <p className="muted">Open the tracking link from your confirmation screen, or enter your reference number and the tracking code shown with it.</p>
          <TrackForm />
        </section>
      </main>
      <PublicFooter />
    </div>
  );
}

function TrackForm() {
  const [ref, setRef] = useState('');
  const [token, setToken] = useState('');
  const nav = useNavigate();
  return (
    <form className="track-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (ref.trim() && token.trim()) nav(`/track/${encodeURIComponent(ref.trim().toUpperCase())}?token=${encodeURIComponent(token.trim())}`);
      }}>
      <label className="field">
        <span className="field-label">Reference number</span>
        <input className="input input--lg mono" placeholder="SOS-7K2Q9X" value={ref} onChange={(e) => setRef(e.target.value)} autoCapitalize="characters" />
      </label>
      <label className="field">
        <span className="field-label">Tracking code</span>
        <input className="input input--lg mono" name="token" value={token} onChange={(e) => setToken(e.target.value)} />
      </label>
      <button className="btn btn--lg" type="submit" disabled={!ref.trim() || !token.trim()}>Show status <ArrowRight aria-hidden="true" /></button>
    </form>
  );
}
