import { useEffect } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { api } from '../../api/client';
import type { SosStatus } from '../../api/types';
import { useAsync } from '../../lib/hooks';
import { dayHhmm, hhmm } from '../../lib/format';
import { SOS_FLOW, SOS_LABEL } from '../../lib/states';
import { ScrambleText } from '../../ui/effects';
import { Skeleton } from '../../ui/primitives';
import { EmergencyNumbers, PublicFooter, PublicHeader } from './PublicChrome';

const PUBLIC_TEXT: Record<SosStatus, string> = {
  pending: 'Received by the control room. Waiting for a dispatcher to check it.',
  triaged: 'Checked by a dispatcher. Finding a team with space.',
  assigned: 'A rescue team has been assigned to you.',
  en_route: 'The team is on the way.',
  on_scene: 'The team has reached your location.',
  resolved: 'Closed: rescue completed.',
  cancelled: 'Closed by the control room.',
};

export function TrackPage() {
  const { ref = '' } = useParams();
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const q = useAsync(() => api.trackSos(ref, token), [ref, token]);

  // Poll gently; the public page has no WebSocket.
  useEffect(() => {
    if (q.data && (q.data.status === 'resolved' || q.data.status === 'cancelled')) return;
    const id = window.setInterval(q.reload, 30_000);
    return () => window.clearInterval(id);
  }, [q.data, q.reload]);

  const d = q.data;
  const reached = new Map(d?.history.map((h) => [h.status, h.at]) ?? []);
  const cancelled = d?.status === 'cancelled';
  const steps: SosStatus[] = cancelled ? [...SOS_FLOW.filter((s) => reached.has(s)), 'cancelled'] : SOS_FLOW;
  const currentIdx = d ? steps.indexOf(d.status) : -1;

  return (
    <div className="public public--form">
      <PublicHeader />
      <main id="main" className="track">
        <p className="eyebrow mono">Request status</p>
        <h1><ScrambleText text={ref.toUpperCase()} className="ref-id" /></h1>

        {!token && <div className="banner banner--warning" role="alert">This link is missing its tracking code. Use the full link from your confirmation screen.</div>}

        {q.loading && !d && <Skeleton rows={6} />}

        {q.error && !d && (
          <div className="banner banner--critical" role="alert">
            <div>
              {q.error.status === 404 || q.error.status === 403
                ? <><strong>Not found.</strong> The reference or tracking code is not recognised. Check the link, or call 1070 with your reference.</>
                : q.error.status === 0
                  ? <><strong>No connection.</strong> Your request is still with the control room; this page just cannot reach it right now.</>
                  : <><strong>Could not load status.</strong> {q.error.message}</>}
              {q.error.requestId && <span className="mono muted"> · {q.error.requestId}</span>}
            </div>
            <button className="btn" onClick={q.reload}><RefreshCw aria-hidden="true" />Try again</button>
          </div>
        )}

        {d && (
          <>
            <section className="track-now" aria-live="polite">
              <p className="track-status">{PUBLIC_TEXT[d.status]}</p>
              <dl className="kv">
                {d.team_name && <><dt>Team</dt><dd>{d.team_name}</dd></>}
                {d.eta_min != null && <><dt>Estimated arrival</dt><dd className="mono">about {d.eta_min} min</dd></>}
                <dt>Sent</dt><dd className="mono">{dayHhmm(d.created_at)}</dd>
                <dt>Last update</dt><dd className="mono">{dayHhmm(d.updated_at)}</dd>
              </dl>
            </section>
            <ol className="timeline timeline--lg" aria-label="Status history">
              {steps.map((s, i) => {
                const at = reached.get(s);
                const cls = i === currentIdx ? 'is-current' : i > currentIdx ? 'is-future' : '';
                return (
                  <li key={s} className={cls} aria-current={i === currentIdx ? 'step' : undefined}>
                    <span className="t-time">{at ? hhmm(at) : ''}</span>
                    <span className="t-rail"><span className="t-node" /></span>
                    <span className="t-body">{SOS_LABEL[s]}{i === currentIdx && <small>{PUBLIC_TEXT[s]}</small>}</span>
                  </li>
                );
              })}
            </ol>
            <p className="field-hint">This page refreshes every 30 seconds. <button className="linklike" onClick={q.reload}>Refresh now</button></p>
          </>
        )}
        <p><Link to="/sos" className="link-sweep">Send another request</Link></p>
        <EmergencyNumbers compact />
      </main>
      <PublicFooter />
    </div>
  );
}
