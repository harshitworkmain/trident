import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Anchor, Home, KeyRound, OctagonX, RotateCcw } from 'lucide-react';
import { KeyReveal } from '../../ui/KeyReveal';
import { api } from '../../api/client';
import { reloadSnapshot, upsertRov, useLive } from '../../api/live';
import type { Rov } from '../../api/types';
import { ago, num } from '../../lib/format';
import { useNow } from '../../lib/hooks';
import { isOpenSos } from '../../lib/states';
import { DataTable, type Column } from '../../ui/DataTable';
import { ConfirmDialog, Dialog } from '../../ui/Dialog';
import { Button, Empty, Meter, Panel } from '../../ui/primitives';
import { useErrorToast, useToast } from '../../ui/Toast';
import { useAuth } from '../auth/auth';
import { Compass, isOnMission, LinkChip, RovStatusChip } from './rovUi';
import { Distance, PersonsBadge, VisionStream, visionActive } from './VisionFeed';

type Act = 'recall' | 'stop' | 'reset';

const COPY: Record<Act, { title: (r: Rov) => string; body: string; label: string; danger?: boolean }> = {
  recall: { title: (r) => `Recall ${r.name}?`, body: 'The unit abandons its mission and drives home on autopilot. Manual control, if held, is released.', label: 'Recall' },
  stop: { title: (r) => `Stop ${r.name}?`, body: 'Thrusters stop immediately and the unit holds position. It stays stopped until someone resets it.', label: 'Stop now', danger: true },
  reset: { title: (r) => `Clear the stop on ${r.name}?`, body: 'Clears the emergency stop and the unit returns home on autopilot. It does not resume its mission; deploy it again to send it back out.', label: 'Clear stop · return home' },
};

export default function RovPage() {
  const rov = useLive((s) => s.rov);
  const load = useLive((s) => s.load.rov);
  const sos = useLive((s) => s.sos);
  const { can } = useAuth();
  const now = useNow(1000);
  const toast = useToast();
  const fail = useErrorToast();
  const [confirm, setConfirm] = useState<{ rov: Rov; act: Act } | null>(null);
  const [deploying, setDeploying] = useState<Rov | null>(null);
  const [ref, setRef] = useState('');
  const [busy, setBusy] = useState(false);
  const [bridge, setBridge] = useState<Rov | null>(null);
  const [videoUrl, setVideoUrl] = useState('');
  const [bridgeKey, setBridgeKey] = useState<{ name: string; key: string } | null>(null);
  const isAdmin = can('users.admin');

  const issueBridgeKey = async () => {
    if (!bridge) return;
    setBusy(true);
    try {
      const r = await api.rovBridgeKey(bridge.id, videoUrl.trim() || undefined);
      setBridgeKey({ name: bridge.name, key: r.api_key });
      setBridge(null);
      void reloadSnapshot('rov');
    } catch (e) { fail(e, 'Could not issue a bridge key'); } finally { setBusy(false); }
  };

  const list = useMemo(() => Object.values(rov).sort((a, b) => a.name.localeCompare(b.name)), [rov]);
  const cams = list.filter((r) => visionActive(r.vision));
  const targets = useMemo(() => Object.values(sos).filter((s) => isOpenSos(s.status) && s.latitude != null).sort((a, b) => a.priority - b.priority), [sos]);
  const canControl = can('rov.control');
  const canStop = can('rov.stop');

  const run = async (r: Rov, act: Act | 'deploy', reference?: string) => {
    setBusy(true);
    try {
      upsertRov(await api.rovAction(r.id, act, reference));
      toast({ tone: 'ok', title: `${r.name}: ${act === 'deploy' ? `deploying to ${reference}` : act}` });
      setConfirm(null);
      setDeploying(null);
    } catch (e) { fail(e, `Could not ${act} ${r.name}`); } finally { setBusy(false); }
  };

  const cols: Column<Rov>[] = [
    { key: 'name', header: 'Unit', render: (r) => <><strong>{r.name}</strong><span className="cell-sub mono">{r.id}{r.simulated ? ' · simulated' : ''}</span></> },
    { key: 'st', header: 'Status', render: (r) => <><RovStatusChip status={r.status} />{r.mode === 'manual' && <span className="cell-sub">manual · {r.pilot ?? 'unknown pilot'}</span>}</> },
    { key: 'link', header: 'Link', render: (r) => <><LinkChip link={r.link} /><span className="cell-sub mono">{ago(r.last_seen, now)} ago</span></> },
    { key: 'bat', header: 'Battery', render: (r) => <div style={{ width: 90 }}><span className="mono">{num(r.battery_pct, 0)}%</span><Meter value={r.battery_pct} max={100} tone={(r.battery_pct ?? 0) < 20 ? 'critical' : 'ok'} label="Battery" /></div> },
    { key: 'nav', header: 'Depth / heading', render: (r) => <span className="row"><span className="mono">{num(r.depth_m, 1)} m</span><Compass deg={r.heading_deg} /></span> },
    { key: 'mission', header: 'Mission', render: (r) => r.mission_reference_id ? <Link to={`/sos/${r.mission_reference_id}`} className="mono">{r.mission_reference_id}</Link> : <span className="muted">—</span> },
    {
      key: 'act', header: <span className="sr-only">Actions</span>, className: 'r nowrap', render: (r) => (
        <span className="action-row" onClick={(e) => e.stopPropagation()}>
          {isOnMission(r) && <Link to="/missions" className="btn btn--sm">Open mission</Link>}
          {canControl && (r.status === 'idle') && <Button size="sm" icon={<Anchor />} onClick={() => { setRef(''); setDeploying(r); }} disabled={r.link === 'offline'}>Deploy</Button>}
          {canControl && ['deploying', 'on_mission', 'manual', 'stopped'].includes(r.status) && r.mission_reference_id && <Button size="sm" icon={<Home />} onClick={() => setConfirm({ rov: r, act: 'recall' })}>Recall</Button>}
          {canControl && r.status === 'stopped' && <Button size="sm" icon={<RotateCcw />} onClick={() => setConfirm({ rov: r, act: 'reset' })}
            title="Clears the emergency stop; the unit returns home on autopilot">Reset</Button>}
          {isAdmin && <Button size="sm" variant="ghost" icon={<KeyRound />} onClick={() => { setVideoUrl(r.video_url ?? ''); setBridge(r); }} title="Connect real hardware through the serial bridge">Bridge key</Button>}
          {canStop && r.status !== 'stopped' && r.status !== 'idle' && <Button size="sm" variant="danger" icon={<OctagonX />} onClick={() => setConfirm({ rov: r, act: 'stop' })}>Stop</Button>}
        </span>
      ),
    },
  ];

  return (
    <div className="page">
      <div className="page-head">
        <h1>ROV units</h1>
        <span className="muted">Underwater search units. Live missions and manual driving are on <Link to="/missions">ROV missions</Link>.</span>
      </div>
      <Panel title="Fleet" count={list.length} bodyClass="panel-body--flush">
        <DataTable rows={list} columns={cols} rowKey={(r) => r.id} caption="ROV fleet" loading={load === 'loading'}
          error={load === 'error' ? new Error('ROV list could not be loaded.') : null} onRetry={() => void reloadSnapshot('rov')}
          empty={<Empty title="No ROV units registered" />} />
      </Panel>
      {cams.length > 0 && (
        <Panel title="Live cameras" count={cams.length}>
          <div className="cam-tiles">
            {cams.map((r) => {
              const near = [...(r.vision?.faces ?? [])].filter((f) => f.distance_m != null).sort((a, b) => a.distance_m! - b.distance_m!)[0];
              return (
                <figure key={r.id} className="cam-tile">
                  <VisionStream rov={r} now={now} compact />
                  <figcaption>
                    <strong>{r.name}</strong>
                    <PersonsBadge rov={r} />
                    {near && <span className="muted">nearest face <Distance m={near.distance_m} /></span>}
                    {isOnMission(r) && <Link to="/missions" className="cam-tile-link">Open mission</Link>}
                  </figcaption>
                </figure>
              );
            })}
          </div>
        </Panel>
      )}
      {!canControl && <p className="field-hint">Deploying and recalling needs a dispatcher. {canStop ? 'You can still stop a unit in an emergency.' : ''}</p>}

      {confirm && (
        <ConfirmDialog open title={COPY[confirm.act].title(confirm.rov)} confirmLabel={COPY[confirm.act].label} danger={COPY[confirm.act].danger} busy={busy}
          body={<p>{COPY[confirm.act].body}</p>} onClose={() => setConfirm(null)} onConfirm={() => void run(confirm.rov, confirm.act)} />
      )}

      <Dialog open={!!bridge} onClose={() => setBridge(null)} title={`Bridge key · ${bridge?.name ?? ''}`} labelledBy="bridge-title"
        footer={<><Button onClick={() => setBridge(null)}>Back</Button><Button variant="primary" busy={busy} onClick={() => void issueBridgeKey()}>Issue key</Button></>}>
        <p className="muted">Issuing a key marks this unit as real hardware: it stops being simulated and shows offline until the serial bridge (<code className="mono">src/rov/bridge.py</code>) connects with this key. Any previous key stops working.</p>
        <label className="field">
          <span className="field-label">Camera stream URL (optional, MJPEG)</span>
          <input className="input mono" value={videoUrl} onChange={(e) => setVideoUrl(e.target.value)} placeholder="http://10.0.0.20:8080/stream.mjpg" />
          <span className="field-hint">Leave empty if the unit has no camera; the missions page will say so rather than show anything.</span>
        </label>
      </Dialog>
      {bridgeKey && <KeyReveal title={`Bridge key for ${bridgeKey.name}`} apiKey={bridgeKey.key} onClose={() => setBridgeKey(null)}
        hint={<>Start the bridge with this value as <code className="mono">X-ROV-Key</code>.</>} />}

      <Dialog open={!!deploying} onClose={() => setDeploying(null)} title={`Deploy ${deploying?.name ?? ''}`} labelledBy="deploy-title"
        footer={<><Button onClick={() => setDeploying(null)}>Back</Button><Button variant="primary" disabled={!ref} busy={busy} onClick={() => deploying && void run(deploying, 'deploy', ref)}>Deploy to {ref || '…'}</Button></>}>
        <p className="muted">The unit drives to the SOS location on autopilot and starts a search pattern. Only open requests with coordinates are listed.</p>
        <label className="field">
          <span className="field-label">SOS request</span>
          <select className="select" value={ref} onChange={(e) => setRef(e.target.value)} autoFocus>
            <option value="">Choose…</option>
            {targets.map((s) => <option key={s.reference_id} value={s.reference_id}>P{s.priority} · {s.reference_id} · {s.address.split(',').slice(-1)[0].trim()} · {s.people_to_rescue} people</option>)}
          </select>
        </label>
      </Dialog>
    </div>
  );
}
