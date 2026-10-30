import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Link2, Link2Off, Phone, Send } from 'lucide-react';
import { api, ApiError } from '../../api/client';
import { upsertSos, useLive } from '../../api/live';
import { teamLatLng, type SosDetail, type SosStatus, type StatusHistoryEntry, type Team } from '../../api/types';
import { ago, dayHhmm, hhmm, num, pct, titleCase } from '../../lib/format';
import { useAsync, useNow } from '../../lib/hooks';
import { allowedTransitions, FINAL, levelTone, SOS_FLOW, SOS_LABEL, stateLabel } from '../../lib/states';
import { ConfirmDialog } from '../../ui/Dialog';
import { ScrambleText } from '../../ui/effects';
import { MapView, type MapMarker } from '../../ui/MapView';
import { Battery, Button, Chip, Empty, ErrorState, Panel, Priority, Skeleton, StateChip, StatusChip } from '../../ui/primitives';
import { useErrorToast, useToast } from '../../ui/Toast';
import { useAuth } from '../auth/auth';
import { SosFlags } from './SosFlags';

type PendingAction = { kind: 'status'; status: SosStatus; note?: string } | { kind: 'assign'; team: Team };

/** "who · what" for a timeline event; the server sends the same text as `text` and `note`. */
function eventLine(e: StatusHistoryEntry): string {
  return [e.by ?? e.actor, e.text ?? e.note].filter(Boolean).join(' · ');
}

function describe(a: PendingAction) {
  return a.kind === 'status' ? `move to ${SOS_LABEL[a.status]}` : `assign ${a.team.name}`;
}

export default function SosDetailPage() {
  const { ref = '' } = useParams();
  const q = useAsync(() => api.getSos(ref), [ref]);
  const liveRec = useLive((s) => s.sos[ref]);
  const teams = useLive((s) => s.teams);
  const devices = useLive((s) => s.devices);
  const { can } = useAuth();
  const toast = useToast();
  const fail = useErrorToast();
  const now = useNow(10_000);

  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState<{ action: PendingAction; fresh: SosDetail } | null>(null);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [cancelNote, setCancelNote] = useState('');
  const [teamId, setTeamId] = useState('');
  const [noteText, setNoteText] = useState('');
  const [noteBusy, setNoteBusy] = useState(false);
  const [linkBusy, setLinkBusy] = useState<'confirm' | 'remove' | null>(null);

  const d = q.data;

  // Live: when the WebSocket reports a newer version, refetch the full record (history/notes are not in the delta).
  const lastVersion = useRef(0);
  useEffect(() => {
    if (!d || !liveRec) return;
    if (liveRec.version > d.version && liveRec.version !== lastVersion.current) {
      lastVersion.current = liveRec.version;
      q.reload();
    }
  }, [liveRec, d, q]);

  const perform = async (action: PendingAction, version: number) => {
    setBusy(true);
    try {
      const rec = action.kind === 'status'
        ? await api.setSosStatus(ref, action.status, version, action.note)
        : await api.assignSos(ref, action.team.id, version);
      upsertSos(rec);
      setConflict(null);
      toast({ tone: 'ok', title: `${ref}: ${action.kind === 'status' ? SOS_LABEL[action.status] : `assigned to ${action.team.name}`}` });
      q.reload();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.code === 'conflict') {
        try {
          const fresh = await api.getSos(ref);
          q.setData(fresh);
          upsertSos(fresh);
          setConflict({ action, fresh });
        } catch (e2) { fail(e2, 'Could not reload the record'); }
      } else fail(e, `Could not ${describe(action)}`);
    } finally {
      setBusy(false);
    }
  };

  const linkDevice = async (deviceId: string | null) => {
    setLinkBusy(deviceId ? 'confirm' : 'remove');
    try {
      const rec = await api.linkSosDevice(ref, deviceId);
      if (rec && typeof rec === 'object' && 'reference_id' in rec && 'version' in rec) upsertSos(rec);
      toast({ tone: 'ok', title: deviceId ? `${ref}: wearable ${deviceId} confirmed` : `${ref}: wearable link removed` });
      q.reload();
    } catch (e) { fail(e, deviceId ? 'Could not confirm the wearable link' : 'Could not remove the wearable link'); } finally { setLinkBusy(null); }
  };

  const addNote = async () => {
    if (!noteText.trim()) return;
    setNoteBusy(true);
    try {
      await api.addSosNote(ref, noteText.trim());
      setNoteText('');
      q.reload();
    } catch (e) { fail(e, 'Could not add note'); } finally { setNoteBusy(false); }
  };

  const markers = useMemo<MapMarker[]>(() => {
    if (!d) return [];
    const m: MapMarker[] = [];
    if (d.latitude != null && d.longitude != null) m.push({ id: d.reference_id, kind: 'sos', lat: d.latitude, lng: d.longitude, tone: 'critical', emphasis: true, label: d.reference_id });
    const dev = d.device_id ? devices[d.device_id] ?? d.linked_device ?? null : null;
    if (dev?.location) m.push({ id: dev.device_id, kind: 'device', lat: dev.location.lat, lng: dev.location.lng, tone: levelTone(dev.state.alert_level), label: dev.device_id });
    const team = teams.find((t) => String(t.id) === String(d.assigned_team?.id));
    const base = team ? teamLatLng(team) : null;
    if (team && base) m.push({ id: String(team.id), kind: 'team', lat: base.lat, lng: base.lng, tone: 'info', label: team.name });
    return m;
  }, [d, devices, teams]);

  if (q.loading && !d) return <div className="page"><Skeleton rows={10} /></div>;
  if (q.error && !d) {
    return (
      <div className="page">
        <Link to="/ops" className="back"><ArrowLeft aria-hidden="true" />Operations</Link>
        <ErrorState error={q.error} onRetry={q.reload} title={q.error.status === 404 ? `No SOS ${ref}` : undefined} />
      </div>
    );
  }
  if (!d) return null;

  const transitions = allowedTransitions(d.status);
  const canStatus = can('sos.status', d);
  const canAssign = can('sos.assign') && ['pending', 'triaged', 'assigned'].includes(d.status);
  // The live store's copy is fresher; linked_device (same shape as GET /devices) fills the gap until it loads.
  const dev = (d.device_id ? devices[d.device_id] : undefined) ?? d.linked_device ?? null;
  const verified = d.device_verified === true;
  const canLink = can('sos.link_device') && !!d.device_id && !verified;
  const vul = Object.entries(d.vulnerabilities ?? {}).filter(([, v]) => v).map(([k]) => k);
  // Every event that set a status (status changes and assignments), oldest first, grouped by step.
  const byStep = new Map<SosStatus, StatusHistoryEntry[]>();
  for (const h of [...(d.history ?? [])].sort((a, b) => Date.parse(a.at) - Date.parse(b.at))) {
    if (!h.status) continue;
    byStep.set(h.status, [...(byStep.get(h.status) ?? []), h]);
  }
  const reached = new Map([...byStep].map(([st, hs]) => [st, hs[hs.length - 1]]));
  const assignments = [...(d.assignments ?? [])].sort((a, b) => Date.parse(b.assigned_at ?? b.at ?? '') - Date.parse(a.assigned_at ?? a.at ?? ''));
  const flow = d.status === 'cancelled' ? [...SOS_FLOW.filter((s) => reached.has(s)), 'cancelled' as SosStatus] : SOS_FLOW;
  const notes = [...(d.notes ?? [])].sort((a, b) => Date.parse(b.at ?? b.created_at ?? '') - Date.parse(a.at ?? a.created_at ?? ''));

  return (
    <div className="page page--detail">
      <Link to="/ops" className="back"><ArrowLeft aria-hidden="true" />Operations</Link>
      <div className="detail-head">
        <Priority p={d.priority} />
        <h1><ScrambleText text={d.reference_id} /></h1>
        <StatusChip status={d.status} />
        <span className="muted">{titleCase(d.emergency_type)} · score <span className="mono">{d.priority_score}</span> · created {ago(d.created_at, now)} ago · v{d.version}</span>
        {/* The live record carries the receive time used to keep the waiting count current. */}
        <SosFlags r={liveRec && liveRec.version === d.version ? liveRec : d} now={now} size="lg" />
      </div>

      {conflict && (
        <div className="banner banner--warning" role="alert">
          <div>
            <strong>Changed by someone else.</strong> Someone updated this SOS while you were looking. It is now <strong>{SOS_LABEL[conflict.fresh.status]}</strong>
            {conflict.fresh.assigned_team && <> with <strong>{conflict.fresh.assigned_team.name}</strong></>} (version {conflict.fresh.version}).
            The page now shows the current record. Your change was to {describe(conflict.action)}.
          </div>
          <Button size="sm" variant="primary" busy={busy}
            disabled={conflict.action.kind === 'status' && !allowedTransitions(conflict.fresh.status).includes(conflict.action.status)}
            onClick={() => void perform(conflict.action, conflict.fresh.version)}>Re-apply my change</Button>
          <Button size="sm" variant="ghost" onClick={() => setConflict(null)}>Discard</Button>
        </div>
      )}

      <div className="detail-grid">
        <div className="detail-main">
          <Panel title="Request">
            <dl className="kv">
              <dt>Caller</dt><dd>{d.name}{d.age ? `, ${d.age}` : ''} · <a href={`tel:${d.phone}`} className="mono"><Phone className="inline-icon" aria-hidden="true" />{d.phone}</a>{d.email && <> · {d.email}</>}</dd>
              <dt>Address</dt><dd>{d.address}, {d.city} {d.pincode}</dd>
              <dt>Coordinates</dt><dd className="mono">{d.latitude != null ? `${num(d.latitude, 5)}, ${num(d.longitude, 5)}` : 'not shared'}</dd>
              <dt>People</dt><dd><span className="mono">{d.people_to_rescue}</span> to rescue{d.people_injured > 0 && <>, <strong className="injured mono">{d.people_injured}</strong> injured</>}</dd>
              <dt>Vulnerable</dt><dd>{vul.length ? vul.map((v) => <Chip key={v} tone="warning">{v}</Chip>) : <span className="muted">none reported</span>}</dd>
              <dt>Water / food</dt><dd><Chip tone={['none', 'critical'].includes(d.water_availability) ? 'critical' : 'muted'}>water {d.water_availability}</Chip> <Chip tone={d.food_availability === 'none' ? 'warning' : 'muted'}>food {d.food_availability}</Chip></dd>
              {d.additional_info && <><dt>Notes from caller</dt><dd className="quote">{d.additional_info}</dd></>}
              <dt>Priority reasons</dt><dd className="reasons">{d.priority_reasons.map((r) => <span key={r} className="reason">{r}</span>)}</dd>
            </dl>
          </Panel>

          <Panel title="Location" bodyClass="panel-body--flush map-body map-body--sm">
            {markers.length ? <MapView markers={markers} fitKey={d.reference_id} label={`Location of ${d.reference_id}`} /> : <Empty title="No coordinates">The caller did not share a location. Use the address.</Empty>}
          </Panel>

          <Panel title="Notes" count={notes.length}>
            {can('sos.note') && (
              <form className="note-form" onSubmit={(e) => { e.preventDefault(); void addNote(); }}>
                <label className="sr-only" htmlFor="note">Add note</label>
                <textarea id="note" className="textarea" rows={2} value={noteText} onChange={(e) => setNoteText(e.target.value)} placeholder="Add a note for the control room and the team"
                  onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) void addNote(); }} />
                <Button type="submit" icon={<Send />} busy={noteBusy} disabled={!noteText.trim()}>Add</Button>
              </form>
            )}
            {notes.length === 0 ? <p className="muted">No notes yet.</p> : (
              <ul className="notes">
                {notes.map((n, i) => (
                  <li key={n.id ?? i}><p>{n.text}</p><span className="muted mono">{n.author ?? 'staff'} · {dayHhmm(n.at ?? n.created_at)}</span></li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <aside className="detail-side">
          <Panel title="Actions">
            {FINAL.includes(d.status) ? <p className="muted">This request is closed ({SOS_LABEL[d.status].toLowerCase()}).</p> : (
              <div className="stack">
                <div className="action-row">
                  {transitions.filter((s) => s !== 'cancelled').map((s) => (
                    <Button key={s} variant="primary" disabled={!canStatus} busy={busy} onClick={() => void perform({ kind: 'status', status: s }, d.version)}
                      title={canStatus ? undefined : 'Your role cannot change this SOS'}>
                      Mark {SOS_LABEL[s].toLowerCase()}
                    </Button>
                  ))}
                  {transitions.includes('cancelled') && (
                    <Button variant="danger" disabled={!canStatus || busy} onClick={() => setConfirmCancel(true)}>Cancel request</Button>
                  )}
                </div>
                {!canStatus && <p className="field-hint">You can view this request. Status changes need a dispatcher{d.assigned_team ? ' or the assigned team' : ''}.</p>}

                {canAssign && (
                  <form className="assign" onSubmit={(e) => {
                    e.preventDefault();
                    const team = teams.find((t) => String(t.id) === teamId);
                    if (team) void perform({ kind: 'assign', team }, d.version);
                  }}>
                    <label className="field">
                      <span className="field-label">{d.assigned_team ? 'Reassign team' : 'Assign team'}</span>
                      <select className="select" value={teamId} onChange={(e) => setTeamId(e.target.value)}>
                        <option value="">Choose a team…</option>
                        {teams.map((t) => {
                          const full = t.current_load >= t.capacity || !t.is_available;
                          return (
                            <option key={t.id} value={String(t.id)} disabled={full || String(t.id) === String(d.assigned_team?.id)}>
                              {t.name} · {t.current_load}/{t.capacity}{!t.is_available ? ' · unavailable' : full ? ' · full' : ''}
                            </option>
                          );
                        })}
                      </select>
                    </label>
                    <Button type="submit" disabled={!teamId} busy={busy}>Assign</Button>
                  </form>
                )}
                {d.assigned_team && <p className="muted">Assigned: <strong>{d.assigned_team.name}</strong></p>}
                {d.awaiting_resources && !d.assigned_team && (
                  <p className="field-hint">No team has free capacity. The banner on <Link to="/ops">Operations</Link> suggests teams that could be moved from lower-priority requests.</p>
                )}
              </div>
            )}
          </Panel>

          <Panel title="Timeline">
            <ol className="timeline">
              {flow.map((s) => {
                const h = reached.get(s);
                const cur = s === d.status;
                return (
                  <li key={s} className={`${cur ? 'is-current' : ''} ${!h ? 'is-future' : ''} ${s === 'cancelled' ? 'is-critical' : ''}`}>
                    <span className="t-time" title={h?.at}>{h ? hhmm(h.at) : ''}</span>
                    <span className="t-rail"><span className="t-node" /></span>
                    <span className="t-body">
                      {SOS_LABEL[s]}
                      {(byStep.get(s) ?? []).map((e, i) => {
                        const line = eventLine(e);
                        return line && <small key={e.id ?? i} title={e.at}>{(byStep.get(s)?.length ?? 0) > 1 ? `${hhmm(e.at)} · ` : ''}{line}</small>;
                      })}
                    </span>
                  </li>
                );
              })}
            </ol>
          </Panel>

          <Panel title="Linked wearable">
            {!dev ? <p className="muted">{d.device_id ? `${d.device_id} is not registered.` : 'No band linked to this request.'}</p> : (
              <div className="stack">
                <div className="row">
                  <Link to={`/wearables/${dev.device_id}`} className="mono">{dev.device_id}</Link><span className="muted">{dev.label}</span>
                  {d.device_id && (verified
                    ? <Chip tone="ok" title="Staff confirmed this band belongs to the caller">verified</Chip>
                    : <Chip tone="warning" title="The band ID was given with the request and has not been confirmed by staff">claimed (not verified)</Chip>)}
                </div>
                <div className="row"><StateChip state={dev.state.ml_health_state} level={dev.state.alert_level} /><span className="mono muted">risk {pct(dev.state.risk)}</span></div>
                <div className="row muted"><span className={`dot ${dev.online ? 'dot--ok' : 'dot--off'}`} />{dev.online ? 'online' : 'offline'} · seen {ago(dev.last_seen, now)} ago · <Battery volts={dev.battery_v} /></div>
                {dev.state.evidence?.length > 0 && <ul className="evidence">{dev.state.evidence.map((e) => <li key={e}>{e}</li>)}</ul>}
                <span className="sr-only">State: {stateLabel(dev.state.ml_health_state)}</span>
              </div>
            )}
            {canLink && d.device_id && (
              <div className="action-row link-actions">
                <Button size="sm" icon={<Link2 />} busy={linkBusy === 'confirm'} disabled={!!linkBusy} onClick={() => void linkDevice(d.device_id!)}
                  title="Confirm that this band belongs to the caller (e.g. after a call back)">Confirm wearable link</Button>
                <Button size="sm" variant="ghost" icon={<Link2Off />} busy={linkBusy === 'remove'} disabled={!!linkBusy} onClick={() => void linkDevice(null)}
                  title="Unlink the band from this request">Remove link</Button>
              </div>
            )}
          </Panel>

          {assignments.length > 0 && (
            <Panel title="Assignment history" count={assignments.length}>
              <ul className="notes">
                {assignments.map((a, i) => (
                  <li key={a.id ?? i}>
                    <p>{a.team_name ?? teams.find((t) => String(t.id) === String(a.team_id))?.name ?? `Team ${a.team_id}`}</p>
                    {a.text && <p className="muted">{a.text}</p>}
                    <span className="muted mono" title={a.assigned_at ?? a.at ?? undefined}>
                      {a.assigned_by ?? a.by ?? a.actor ?? 'unknown'} · {dayHhmm(a.assigned_at ?? a.at)}
                    </span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </aside>
      </div>

      <ConfirmDialog open={confirmCancel} title={`Cancel ${d.reference_id}?`} confirmLabel="Cancel request" danger busy={busy}
        onClose={() => setConfirmCancel(false)}
        onConfirm={() => { setConfirmCancel(false); void perform({ kind: 'status', status: 'cancelled', note: cancelNote.trim() || undefined }, d.version); }}
        body={(
          <>
            <p>The caller will see this request as closed on their tracking page. Use this for duplicates or when the people are already safe.</p>
            <label className="field">
              <span className="field-label">Reason</span>
              <input className="input" value={cancelNote} onChange={(e) => setCancelNote(e.target.value)} placeholder="e.g. Duplicate of SOS-…" />
            </label>
          </>
        )} />
    </div>
  );
}
