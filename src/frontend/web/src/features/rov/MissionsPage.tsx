import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, ChevronsDown, ChevronsUp, Gamepad2, Home, Lightbulb, LightbulbOff, OctagonX, RotateCcw, VideoOff } from 'lucide-react';
import { api, ApiError } from '../../api/client';
import { rovTracks, seedRovTrack, telemetry, upsertRov, useLive } from '../../api/live';
import { type Mission, type MissionVictim, type Rov, type RovCommand } from '../../api/types';
import { ago, num, pct } from '../../lib/format';
import { useAsync, useNow } from '../../lib/hooks';
import { levelTone, priorityTone } from '../../lib/states';
import { Sparkline, token } from '../../ui/charts';
import { ConfirmDialog } from '../../ui/Dialog';
import { MapView, type MapMarker, type MapTrack } from '../../ui/MapView';
import { Button, Chip, Empty, ErrorState, Kbd, Meter, Panel, Priority, Skeleton, StateChip, StatusChip } from '../../ui/primitives';
import { useErrorToast, useToast } from '../../ui/Toast';
import { useAuth } from '../auth/auth';
import { Compass, isOnMission, LinkChip, RovStatusChip } from './rovUi';
import { PersonsBadge, VisionDetections, VisionStream, visionActive } from './VisionFeed';
import { ErrorBoundary } from '../../ui/ErrorBoundary';

const KEYMAP: Record<string, RovCommand> = { w: 'forward', s: 'backward', a: 'left', d: 'right', r: 'up', f: 'down' };

// ─── Live readouts ───────────────────────────────────────────────────────────

function Readout({ label, children }: { label: string; children: ReactNode }) {
  return <div className="readout"><dt>{label}</dt><dd>{children}</dd></div>;
}

function RovTelemetry({ rov, now }: { rov: Rov; now: number }) {
  // A simulated unit has no bridge, so no last_seen; its simulation tick bumps updated_at instead.
  const seen = rov.last_seen ?? (rov.link === 'simulated' || rov.simulated ? rov.updated_at : null);
  const stale = seen ? now - Date.parse(seen) > 5000 : true;
  return (
    <dl className={`readouts ${stale ? 'is-stale' : ''}`} aria-label={`${rov.name} telemetry`}>
      <Readout label="Depth"><span className="mono big">{num(rov.depth_m, 1)}</span><small>m</small></Readout>
      <Readout label="Heading"><Compass deg={rov.heading_deg} /></Readout>
      <Readout label="Water"><span className="mono big">{num(rov.water_temp_c, 1)}</span><small>°C</small></Readout>
      <Readout label="Speed"><span className="mono big">{num(rov.speed_pct, 0)}</span><small>%</small></Readout>
      <Readout label="Battery">
        <span className={`mono big ${(rov.battery_pct ?? 100) < 20 ? 'text-critical' : ''}`}>{num(rov.battery_pct, 0)}</span><small>%</small>
        <Meter value={rov.battery_pct} max={100} tone={(rov.battery_pct ?? 0) < 20 ? 'critical' : 'ok'} label="Battery" />
      </Readout>
      <Readout label="Lights">{rov.lights_on ? <Chip tone="accent">on</Chip> : <Chip tone="muted">off</Chip>}</Readout>
      <Readout label="Link"><LinkChip link={rov.link} /><small className="mono">{stale ? `stale ${ago(seen, now)}` : 'live'}</small></Readout>
      <Readout label="Mode">{rov.mode === 'manual' ? <Chip tone="accent">manual · {rov.pilot ?? '?'}</Chip> : <Chip tone="info">auto</Chip>}</Readout>
    </dl>
  );
}

/** Vision feed when the worker runs; otherwise a plain bridge camera if the unit has one; otherwise the placeholder. */
function Camera({ rov, now }: { rov: Rov; now: number }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [rov.video_url]);
  if (visionActive(rov.vision)) {
    return (
      <div className="vision">
        <VisionStream rov={rov} now={now} />
        <VisionDetections vision={rov.vision} />
      </div>
    );
  }
  if (!rov.video_url) return <VisionStream rov={rov} now={now} />;
  if (failed) {
    return <div className="camera camera--none" role="img" aria-label="Camera stream unavailable"><VideoOff aria-hidden="true" /><span>Camera stream unavailable</span></div>;
  }
  // MJPEG streams render natively in <img>.
  return <div className="camera"><img src={rov.video_url} alt={`Live camera, ${rov.name}`} onError={() => setFailed(true)} /></div>;
}

// ─── Victims (live wearables) ────────────────────────────────────────────────

function VictimRow({ v, tick, now }: { v: MissionVictim; tick: number; now: number }) {
  const live = useLive((s) => (v.device_id ? s.devices[v.device_id] : undefined));
  const dev = live ?? v.device;
  const colors = useMemo(() => [token('--series-1'), token('--series-2'), token('--series-3'), token('--series-4')], []);
  void tick;
  const tail = v.device_id ? (telemetry.get(v.device_id) ?? []).slice(-60) : [];
  const last = tail[tail.length - 1];
  const vitals: [string, (number | null)[], number | null | undefined, string, number][] = [
    ['HR', tail.map((p) => p.bpm), last?.bpm, 'bpm', 0],
    ['SpO₂', tail.map((p) => p.spo2), last?.spo2, '%', 0],
    ['Skin', tail.map((p) => p.temp), last?.temp, '°C', 1],
    ['EDA', tail.map((p) => p.eda), last?.eda, 'µS', 1],
  ];
  return (
    <li className={`victim ${dev?.state.alert_level === 'critical' ? 'is-critical' : ''}`}>
      <div className="victim-head">
        <Priority p={v.priority} />
        <Link to={`/sos/${v.reference_id}`} className="mono">{v.reference_id}</Link>
        <span>{v.name}</span>
        <StatusChip status={v.status} />
      </div>
      {!v.device_id ? <p className="muted">No wearable linked to this person.</p> : !dev ? <p className="muted mono">{v.device_id}: not registered</p> : (
        <>
          <div className="victim-state">
            <Link to={`/wearables/${dev.device_id}`} className="mono">{dev.device_id}</Link>
            <StateChip state={dev.state.ml_health_state} level={dev.state.alert_level} />
            <span className="mono muted">risk {pct(dev.state.risk)}</span>
            <span className={`dot ${dev.online ? 'dot--ok' : 'dot--off'}`} aria-hidden="true" />
            <span className="muted">{dev.online ? 'online' : `offline ${ago(dev.last_seen, now)}`}</span>
          </div>
          <div className="dev-vitals">
            {vitals.map(([name, series, val, unit, dg], i) => (
              <div key={name} className="vital">
                <span className="vital-name">{name}</span>
                <span className="vital-val mono">{dev.online ? num(val, dg) : '—'}<small>{unit}</small></span>
                <Sparkline values={series} color={colors[i]} label={`${name} trend`} />
              </div>
            ))}
          </div>
          {dev.state.alert_level !== 'none' && dev.state.evidence?.length > 0 && <p className="alert-evidence">{dev.state.evidence.slice(0, 3).join(' · ')}</p>}
        </>
      )}
    </li>
  );
}

// ─── Controls ────────────────────────────────────────────────────────────────

function useRovCommands(rov: Rov) {
  const toast = useToast();
  const fail = useErrorToast();
  const report = (e: unknown, what: string) => {
    if (e instanceof ApiError && e.status === 409) {
      const pilot = (e.details as { pilot?: string } | undefined)?.pilot;
      toast({ tone: 'warning', title: `${rov.name}: ${what} refused`, message: pilot ? `${pilot} has control of this unit.` : e.message, requestId: e.requestId });
    } else fail(e, `${rov.name}: ${what} failed`);
  };
  return {
    control: async (cmd: RovCommand, speed: number) => {
      try { upsertRov(await api.rovControl(rov.id, cmd, speed)); return true; } catch (e) { report(e, cmd.replace('_', ' ')); return false; }
    },
    action: async (act: 'takeover' | 'release' | 'stop' | 'recall' | 'reset') => {
      try { upsertRov(await api.rovAction(rov.id, act)); return true; } catch (e) { report(e, act); return false; }
    },
  };
}

function HoldButton({ cmd, label, icon, disabled, onStart, onEnd, active }: {
  cmd: RovCommand; label: string; icon: ReactNode; disabled: boolean; active: boolean;
  onStart: (c: RovCommand) => void; onEnd: () => void;
}) {
  const down = (e: PointerEvent<HTMLButtonElement>) => {
    if (disabled || e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    onStart(cmd);
  };
  const keyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if ((e.key === 'Enter' || e.key === ' ') && !e.repeat) { e.preventDefault(); e.stopPropagation(); onStart(cmd); }
  };
  const keyUp = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); onEnd(); }
  };
  return (
    <button type="button" className={`btn dpad-btn ${active ? 'is-active' : ''}`} aria-label={`${label} (hold)`} disabled={disabled}
      onPointerDown={down} onPointerUp={onEnd} onPointerCancel={onEnd} onLostPointerCapture={onEnd} onKeyDown={keyDown} onKeyUp={keyUp}
      onContextMenu={(e) => e.preventDefault()}>
      {icon}
    </button>
  );
}

function RovControls({ rov, panelRef }: { rov: Rov; panelRef: React.RefObject<HTMLElement> }) {
  const { user, can } = useAuth();
  const cmds = useRovCommands(rov);
  const [speed, setSpeed] = useState(40);
  const [active, setActive] = useState<RovCommand | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmHome, setConfirmHome] = useState(false);
  const activeRef = useRef<RovCommand | null>(null);

  const isPilot = rov.mode === 'manual' && rov.pilot === user?.username;
  const heldByOther = rov.mode === 'manual' && !!rov.pilot && rov.pilot !== user?.username;
  const canDrive = can('rov.control');
  const canStop = can('rov.stop');

  const start = (c: RovCommand) => {
    if (!isPilot || activeRef.current === c) return;
    activeRef.current = c;
    setActive(c);
    void cmds.control(c, speed);
  };
  const end = () => {
    if (!activeRef.current) return;
    activeRef.current = null;
    setActive(null);
    void cmds.control('stop', 0);
  };
  const stop = async () => {
    activeRef.current = null;
    setActive(null);
    setBusy('stop');
    await cmds.action('stop');
    setBusy(null);
  };
  const lights = () => { if (isPilot) void cmds.control(rov.lights_on ? 'lights_off' : 'lights_on', speed); };
  const act = async (a: 'takeover' | 'release' | 'recall' | 'reset') => {
    setBusy(a);
    await cmds.action(a);
    setBusy(null);
  };

  // Keyboard driving: only while this mission panel has focus and we hold manual control.
  useEffect(() => {
    const el = panelRef.current;
    if (!el) return;
    const typing = (t: EventTarget | null) => t instanceof HTMLElement && (t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || (t.tagName === 'INPUT' && (t as HTMLInputElement).type !== 'range'));
    const kd = (e: globalThis.KeyboardEvent) => {
      if (!isPilot || typing(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === ' ') { if (e.target instanceof HTMLButtonElement) return; e.preventDefault(); void stop(); return; }
      if (k === 'l') { e.preventDefault(); if (!e.repeat) lights(); return; }
      const c = KEYMAP[k];
      if (c) { e.preventDefault(); e.stopPropagation(); if (!e.repeat) start(c); }
    };
    const ku = (e: globalThis.KeyboardEvent) => {
      const c = KEYMAP[e.key.toLowerCase()];
      if (c && activeRef.current === c) { e.preventDefault(); end(); }
    };
    const blur = (e: FocusEvent) => { if (!el.contains(e.relatedTarget as Node | null)) end(); };
    el.addEventListener('keydown', kd);
    el.addEventListener('keyup', ku);
    el.addEventListener('focusout', blur);
    return () => { el.removeEventListener('keydown', kd); el.removeEventListener('keyup', ku); el.removeEventListener('focusout', blur); };
  });

  // Safety: if we lose manual control (released elsewhere, or link drop), forget any held command.
  useEffect(() => { if (!isPilot) { activeRef.current = null; setActive(null); } }, [isPilot]);

  const driveDisabled = !isPilot || rov.status === 'stopped' || rov.link === 'offline';

  return (
    <div className="rov-controls">
      <div className="ctl-mode">
        {isPilot ? (
          <>
            <Chip tone="accent" dot>You are driving</Chip>
            <Button size="sm" onClick={() => void act('release')} busy={busy === 'release'}>Release to auto</Button>
          </>
        ) : heldByOther ? (
          <>
            <Chip tone="warning" dot>{rov.pilot} is driving</Chip>
            {user?.role === 'admin' && <Button size="sm" icon={<Gamepad2 />} onClick={() => void act('takeover')} busy={busy === 'takeover'}>Take over (admin)</Button>}
          </>
        ) : canDrive ? (
          <Button size="sm" variant="primary" icon={<Gamepad2 />} onClick={() => void act('takeover')} busy={busy === 'takeover'} disabled={rov.link === 'offline'}>Take manual control</Button>
        ) : <span className="muted">Driving needs a dispatcher.</span>}
      </div>

      <div className={`dpad-wrap ${driveDisabled ? 'is-disabled' : ''}`} aria-label="Movement controls" role="group">
        <div className="dpad">
          <span />
          <HoldButton cmd="forward" label="Forward" icon={<ArrowUp />} disabled={driveDisabled} active={active === 'forward'} onStart={start} onEnd={end} />
          <span />
          <HoldButton cmd="left" label="Turn left" icon={<ArrowLeft />} disabled={driveDisabled} active={active === 'left'} onStart={start} onEnd={end} />
          <span className="dpad-center" aria-hidden="true" />
          <HoldButton cmd="right" label="Turn right" icon={<ArrowRight />} disabled={driveDisabled} active={active === 'right'} onStart={start} onEnd={end} />
          <span />
          <HoldButton cmd="backward" label="Backward" icon={<ArrowDown />} disabled={driveDisabled} active={active === 'backward'} onStart={start} onEnd={end} />
          <span />
        </div>
        <div className="dpad-vert">
          <HoldButton cmd="up" label="Ascend" icon={<ChevronsUp />} disabled={driveDisabled} active={active === 'up'} onStart={start} onEnd={end} />
          <HoldButton cmd="down" label="Descend" icon={<ChevronsDown />} disabled={driveDisabled} active={active === 'down'} onStart={start} onEnd={end} />
        </div>
      </div>

      <label className="field speed">
        <span className="field-label">Speed <span className="mono">{speed}%</span></span>
        <input type="range" min={0} max={100} step={5} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} disabled={!isPilot} aria-valuetext={`${speed} percent`} />
      </label>

      <div className="ctl-row">
        <Button size="sm" icon={rov.lights_on ? <LightbulbOff /> : <Lightbulb />} onClick={lights} disabled={driveDisabled}>{rov.lights_on ? 'Lights off' : 'Lights on'}</Button>
        {canDrive && <Button size="sm" icon={<Home />} onClick={() => setConfirmHome(true)} disabled={heldByOther || rov.status === 'returning'}>Return home</Button>}
        {canDrive && rov.status === 'stopped' && <Button size="sm" icon={<RotateCcw />} onClick={() => void act('reset')} busy={busy === 'reset'}
          title="Clears the emergency stop; the unit returns home on autopilot">Clear stop · return home</Button>}
      </div>

      <Button variant="danger" className="btn-stop" icon={<OctagonX />} onClick={() => void stop()} busy={busy === 'stop'} disabled={!canStop}
        title={canStop ? 'Stop all thrusters now (Space while driving)' : 'Your role cannot stop units'}>STOP</Button>

      {isPilot && (
        <p className="ctl-keys" aria-label="Keyboard controls">
          <Kbd>W</Kbd><Kbd>A</Kbd><Kbd>S</Kbd><Kbd>D</Kbd> move · <Kbd>R</Kbd>/<Kbd>F</Kbd> up/down · <Kbd>L</Kbd> lights · <Kbd>Space</Kbd> stop. Hold to move; release stops. Thrust cuts out after 120 s without a command.
        </p>
      )}

      <ConfirmDialog open={confirmHome} title={`Return ${rov.name} home?`} confirmLabel="Return home" busy={busy === 'recall'}
        body={<p>The unit leaves the search area and drives home on autopilot. Manual control is released.</p>}
        onClose={() => setConfirmHome(false)} onConfirm={() => { setConfirmHome(false); void act('recall'); }} />
    </div>
  );
}

// ─── Mission panel ───────────────────────────────────────────────────────────

function MissionPanel({ m, now, tick }: { m: Mission; now: number; tick: number }) {
  const live = useLive((s) => s.rov[m.rov.id]);
  const devices = useLive((s) => s.devices);
  const rov = live ?? m.rov;
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let alive = true;
    api.rovTrack(rov.id, 30)
      .then((pts) => { if (alive) seedRovTrack(rov.id, pts.map((p) => ({ t: Date.parse(p.t) / 1000, lat: p.lat, lng: p.lng, depth: p.depth_m }))); })
      .catch(() => { /* live track still builds from events */ });
    return () => { alive = false; };
  }, [rov.id]);

  const { markers, tracks } = useMemo(() => {
    void tick;
    const mk: MapMarker[] = [];
    const tr: MapTrack[] = [];
    if (rov.latitude != null && rov.longitude != null) {
      mk.push({ id: rov.id, kind: 'rov', lat: rov.latitude, lng: rov.longitude, tone: 'accent', emphasis: true, label: `${rov.name} · ${num(rov.depth_m, 1)} m` });
      const pts = (rovTracks.get(rov.id) ?? []).map((p) => [p.lat, p.lng] as [number, number]);
      if (pts.length > 1) tr.push({ id: `${rov.id}-track`, points: [...pts, [rov.latitude, rov.longitude]], tone: 'accent' });
      const goal = rov.status === 'returning' ? rov.home : rov.target;
      if (goal) tr.push({ id: `${rov.id}-goal`, points: [[rov.latitude, rov.longitude], [goal.lat, goal.lng]], tone: 'muted', dashed: true });
    }
    if (m.sos?.latitude != null && m.sos.longitude != null) {
      const t = priorityTone(m.sos.priority);
      mk.push({ id: m.sos.reference_id, kind: 'sos', lat: m.sos.latitude, lng: m.sos.longitude, tone: t === 'muted' ? 'info' : t, label: `${m.sos.reference_id} · P${m.sos.priority}`, href: `/sos/${m.sos.reference_id}` });
    }
    if (rov.home) mk.push({ id: `${rov.id}-home`, kind: 'team', lat: rov.home.lat, lng: rov.home.lng, tone: 'muted', label: `${rov.name} home` });
    for (const v of m.victims) {
      const d = v.device_id ? devices[v.device_id] ?? v.device : null;
      if (d?.location) mk.push({ id: d.device_id, kind: 'device', lat: d.location.lat, lng: d.location.lng, tone: d.online ? levelTone(d.state.alert_level) : 'muted', emphasis: d.state.alert_level === 'critical', label: `${d.device_id} · ${v.name}` });
    }
    return { markers: mk, tracks: tr };
  }, [rov, m, devices, tick]);

  const critical = m.victims.some((v) => v.device_id && devices[v.device_id]?.state.alert_level === 'critical');

  return (
    <section ref={panelRef} className={`panel mission ${rov.mode === 'manual' ? 'is-manual' : ''}`} tabIndex={0}
      aria-labelledby={`m-${rov.id}`} aria-describedby={`m-${rov.id}-hint`}>
      <header className="panel-head mission-head">
        <h2 className="panel-title" id={`m-${rov.id}`}>{rov.name} <span className="count">{rov.id}</span></h2>
        <RovStatusChip status={rov.status} />
        {rov.simulated && <Chip tone="muted">simulated unit</Chip>}
        {critical && <Chip tone="critical" sweep>victim critical</Chip>}
        <PersonsBadge rov={rov} />
        <span className="panel-actions muted" id={`m-${rov.id}-hint`}>
          {m.team ? <>Team <strong>{m.team.name}</strong></> : 'No team assigned'}
        </span>
      </header>
      <div className="mission-grid">
        <div className="mission-feed">
          <div className="mission-map"><MapView markers={markers} tracks={tracks} follow={`rov:${rov.id}`} fitKey={rov.id} label={`${rov.name} position and track`} /></div>
          <RovTelemetry rov={rov} now={now} />
          <Camera rov={rov} now={now} />
        </div>
        <div className="mission-people">
          <h3 className="sub-h">Mission SOS</h3>
          {m.sos ? (
            <div className="mission-sos">
              <Priority p={m.sos.priority} />
              <Link to={`/sos/${m.sos.reference_id}`} className="mono">{m.sos.reference_id}</Link>
              <StatusChip status={m.sos.status} />
              <span className="muted">{m.sos.address}</span>
              <span className="mono muted">{num(m.sos.latitude, 5)}, {num(m.sos.longitude, 5)} · {m.sos.people_to_rescue} people{m.sos.people_injured ? `, ${m.sos.people_injured} injured` : ''}</span>
            </div>
          ) : <p className="muted">Not linked to an SOS.</p>}
          <h3 className="sub-h">Victim wearables <span className="muted mono">live</span></h3>
          {m.victims.length === 0 ? <p className="muted">No people linked to this mission.</p> : (
            <ul className="victims">{m.victims.map((v) => <VictimRow key={v.reference_id} v={v} tick={tick} now={now} />)}</ul>
          )}
        </div>
        <RovControls rov={rov} panelRef={panelRef} />
      </div>
    </section>
  );
}

export default function MissionsPage() {
  const rovMap = useLive((s) => s.rov);
  const tick = useLive((s) => s.telemetryTick);
  const conn = useLive((s) => s.conn);
  const now = useNow(1000);
  const activeKey = useMemo(() => Object.values(rovMap).filter(isOnMission).map((r) => `${r.id}:${r.mission_reference_id}`).sort().join('|'), [rovMap]);
  // Mission composition (SOS, team, victims) changes only when a unit starts or ends a mission.
  const q = useAsync(() => api.missions(), [activeKey]);
  const missions = (q.data ?? []).filter((m) => isOnMission(rovMap[m.rov.id] ?? m.rov));

  return (
    <div className="page">
      <div className="page-head">
        <h1>ROV missions</h1>
        <span className="muted">Live position, victims’ wearables and semi-autonomous control. Focus a mission panel to drive with the keyboard.</span>
        {conn !== 'open' && <Chip tone="warning" dot>feed {conn}</Chip>}
      </div>
      {q.loading && !q.data ? <Skeleton rows={10} /> : q.error && !q.data ? <ErrorState error={q.error} onRetry={q.reload} /> : missions.length === 0 ? (
        <Panel><Empty title="No ROV is on a mission">Deploy a unit to an SOS from <Link to="/rov">ROV units</Link>.</Empty></Panel>
      ) : (
        <div className="missions">
          {missions.map((m) => (
            <ErrorBoundary key={m.rov.id} className="panel">
              <MissionPanel m={m} now={now} tick={tick} />
            </ErrorBoundary>
          ))}
        </div>
      )}
    </div>
  );
}
