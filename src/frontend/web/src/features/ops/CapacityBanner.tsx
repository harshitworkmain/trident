import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowRight } from 'lucide-react';
import { api, ApiError } from '../../api/client';
import { reloadSnapshot, upsertSos, useLive } from '../../api/live';
import type { CapacitySuggestion } from '../../api/types';
import { hhmm } from '../../lib/format';
import { SOS_LABEL } from '../../lib/states';
import { ConfirmDialog } from '../../ui/Dialog';
import { Button } from '../../ui/primitives';
import { useErrorToast, useToast } from '../../ui/Toast';
import { useAuth } from '../auth/auth';

const SHOW_WAITING = 3;

/**
 * Shown above the queue when dispatch capacity is strained (one team free or none). Each server
 * suggestion is an explicit, confirmed action: a team is never moved automatically.
 */
export function CapacityBanner() {
  const cap = useLive((s) => s.capacity);
  const sos = useLive((s) => s.sos);
  const { can } = useAuth();
  const toast = useToast();
  const fail = useErrorToast();
  const [pending, setPending] = useState<CapacitySuggestion | null>(null);
  const [busy, setBusy] = useState(false);

  if (!cap || cap.status === 'ok') return null;

  const waiting = [...cap.waiting].sort((a, b) => a.priority - b.priority || b.waiting_min - a.waiting_min);
  const prioOf = (ref: string) => cap.waiting.find((w) => w.reference_id === ref)?.priority ?? sos[ref]?.priority;
  const exhausted = cap.status === 'exhausted';
  const allowed = can('sos.reallocate');

  const move = async (s: CapacitySuggestion) => {
    const target = sos[s.for_reference_id];
    const from = sos[s.from_reference_id];
    setBusy(true);
    try {
      if (!target || !from) throw new ApiError(409, 'conflict', 'One of the requests is no longer in the queue.', null);
      const rec = await api.reallocateSos(s.for_reference_id, {
        team_id: s.team_id, from_reference_id: s.from_reference_id, version: target.version, from_version: from.version,
      });
      upsertSos(rec);
      setPending(null);
      toast({ tone: 'ok', title: `${s.team_name} moved to ${s.for_reference_id}`, message: `${s.from_reference_id} is back in the queue without a team.` });
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setPending(null);
        toast({ tone: 'warning', title: 'Not moved: changed by someone else', message: `${s.from_reference_id} or ${s.for_reference_id} changed since this suggestion was made. The suggestions have been refreshed.` });
      } else fail(e, `Could not move ${s.team_name}`);
    } finally {
      setBusy(false);
      // Both records, the team loads and the suggestions all changed (or were stale).
      void reloadSnapshot('sos');
      void reloadSnapshot('teams');
      void reloadSnapshot('capacity');
    }
  };

  const fromRec = pending ? sos[pending.from_reference_id] : undefined;

  return (
    <section className={`capacity ${exhausted ? 'capacity--exhausted' : ''}`} aria-labelledby="capacity-title">
      <div className="capacity-head">
        <AlertTriangle aria-hidden="true" />
        <p id="capacity-title">
          <strong>{exhausted ? 'No free teams' : `Only ${cap.teams_free} of ${cap.teams_total} teams free`}</strong>
          {' — '}
          {waiting.length === 0 ? 'no urgent request is waiting yet.' : (
            <span className="capacity-waiting">
              {waiting.length} urgent request{waiting.length === 1 ? '' : 's'} waiting (
              {waiting.slice(0, SHOW_WAITING).map((w, i) => (
                <span key={w.reference_id}>
                  {i > 0 && ', '}
                  <Link to={`/sos/${encodeURIComponent(w.reference_id)}`}><span className="mono">P{w.priority} {w.reference_id}</span></Link>{' '}
                  <span className="mono">{Math.round(w.waiting_min)} min</span>
                </span>
              ))}
              {waiting.length > SHOW_WAITING && ', …'})
            </span>
          )}
        </p>
        <span className="muted mono" title={cap.updated_at}>updated {hhmm(cap.updated_at)}</span>
      </div>

      {cap.suggestions.length > 0 && (
        <ul className="capacity-moves" aria-label="Suggested team moves">
          {cap.suggestions.map((s) => (
            <li key={`${s.for_reference_id}-${s.team_id}-${s.from_reference_id}`}>
              <Button size="sm" onClick={() => setPending(s)} disabled={!allowed || busy}
                title={allowed ? s.reason : 'Only a dispatcher can move teams'}>
                Move {s.team_name} from <span className="mono">{s.from_reference_id}</span> (P{s.from_priority})
                <ArrowRight aria-label="to" />
                <span className="mono">{s.for_reference_id}</span> (P{prioOf(s.for_reference_id) ?? '?'})
              </Button>
              <span className="field-hint">{s.reason}</span>
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog open={!!pending} busy={busy} confirmLabel="Move team"
        title={pending ? `Move ${pending.team_name} to ${pending.for_reference_id}?` : ''}
        onClose={() => setPending(null)}
        onConfirm={() => { if (pending) void move(pending); }}
        body={pending && (
          <>
            <p>
              <strong>{pending.team_name}</strong> is assigned to <span className="mono">{pending.from_reference_id}</span> (P{pending.from_priority}) and has not left yet.
              It will be assigned to <span className="mono">{pending.for_reference_id}</span> (P{prioOf(pending.for_reference_id) ?? '?'}) instead.
            </p>
            <p>
              <span className="mono">{pending.from_reference_id}</span> goes back to the queue without a team and keeps its place by priority and waiting time.
              Tell the team about the change by radio or phone.
            </p>
            {pending.reason && <p className="muted">Why suggested: {pending.reason}</p>}
            {fromRec && fromRec.status !== 'assigned' && (
              <p className="banner banner--warning" role="status">
                <span><span className="mono">{pending.from_reference_id}</span> is now {SOS_LABEL[fromRec.status].toLowerCase()}, so the server will probably refuse this move.</span>
              </p>
            )}
          </>
        )} />
    </section>
  );
}
