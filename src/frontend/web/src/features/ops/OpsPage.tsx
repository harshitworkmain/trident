import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users } from 'lucide-react';
import { api } from '../../api/client';
import { useLive } from '../../api/live';
import { ACTIVE_ROV, teamLatLng } from '../../api/types';
import { useAsync, useHotkeys } from '../../lib/hooks';
import { isOpenSos, levelTone, priorityTone, stateLabel } from '../../lib/states';
import { Dialog } from '../../ui/Dialog';
import { CountUp } from '../../ui/effects';
import { MapLegend, MapView, type MapMarker } from '../../ui/MapView';
import { Button, Panel, Stat } from '../../ui/primitives';
import { AlertsPanel } from '../alerts/AlertsPanel';
import { SosQueue } from '../sos/SosQueue';
import { WeatherStrip } from '../weather/WeatherStrip';
import { useAuth } from '../auth/auth';
import { CapacityBanner } from './CapacityBanner';
import { TeamsTable } from './TeamsPanel';

function Kpis() {
  const sos = useLive((s) => s.sos);
  const alerts = useLive((s) => s.alerts);
  const teams = useLive((s) => s.teams);
  const devices = useLive((s) => s.devices);
  const capacity = useLive((s) => s.capacity);
  // avg response time is server-computed; everything else is derived live from the store.
  const summary = useAsync(() => api.summary(), []);
  useEffect(() => {
    const id = window.setInterval(summary.reload, 60_000);
    return () => window.clearInterval(id);
  }, [summary.reload]);

  const k = useMemo(() => {
    const open = Object.values(sos).filter((r) => isOpenSos(r.status));
    const devs = Object.values(devices);
    return {
      open: open.length,
      p1: open.filter((r) => r.priority === 1).length,
      pending: open.filter((r) => r.status === 'pending').length,
      alerts: Object.values(alerts).filter((a) => a.status === 'open').length,
      teamsFree: teams.filter((t) => t.is_available && t.current_load < t.capacity).length,
      teamsTotal: teams.length,
      online: devs.filter((d) => d.online).length,
      devTotal: devs.length,
      critical: devs.filter((d) => d.online && d.state.alert_level === 'critical').length,
    };
  }, [sos, alerts, teams, devices]);
  // Server status when available (it also knows about suspended teams); else ≤1 free team is strained.
  const strained = capacity ? capacity.status !== 'ok' : k.teamsTotal > 0 && k.teamsFree <= 1;

  return (
    <div className="kpi-strip" role="group" aria-label="Key figures">
      <Stat label="Open SOS" value={<CountUp value={k.open} />} sub={`${k.pending} awaiting triage`} />
      <Stat label="Priority 1" value={<CountUp value={k.p1} />} tone={k.p1 ? 'critical' : undefined} sub="open, most urgent" />
      <Stat label="Open alerts" value={<CountUp value={k.alerts} />} tone={k.alerts ? 'critical' : undefined} sub="not acknowledged" />
      <Stat label="Teams free" value={<CountUp value={k.teamsFree} />} unit={`/ ${k.teamsTotal}`} sub={capacity?.status === 'exhausted' ? 'no team free' : strained ? 'capacity strained' : 'available with capacity'} tone={strained ? 'warning' : undefined} />
      <Stat label="Wearables online" value={<CountUp value={k.online} />} unit={`/ ${k.devTotal}`} sub={k.critical ? `${k.critical} in critical state` : 'none critical'} />
      <Stat label="Avg response" value={<CountUp value={summary.data?.avg_response_min ?? null} digits={1} />} unit="min" sub="created → on scene" />
    </div>
  );
}

function OpsMap() {
  const sos = useLive((s) => s.sos);
  const devices = useLive((s) => s.devices);
  const teams = useLive((s) => s.teams);
  const rov = useLive((s) => s.rov);
  const nav = useNavigate();
  const [layers, setLayers] = useState({ sos: true, device: true, team: true, rov: true });

  const markers = useMemo(() => {
    const out: MapMarker[] = [];
    if (layers.sos) for (const r of Object.values(sos)) {
      if (!isOpenSos(r.status) || r.latitude == null || r.longitude == null) continue;
      const t = priorityTone(r.priority);
      out.push({ id: r.reference_id, kind: 'sos', lat: r.latitude, lng: r.longitude, tone: t === 'muted' ? 'info' : t, emphasis: r.priority === 1, label: `${r.reference_id} · P${r.priority} · ${r.people_to_rescue} people · ${r.status}`, href: `/sos/${r.reference_id}` });
    }
    if (layers.device) for (const d of Object.values(devices)) {
      if (!d.location) continue;
      out.push({ id: d.device_id, kind: 'device', lat: d.location.lat, lng: d.location.lng, tone: d.online ? levelTone(d.state.alert_level) : 'muted', emphasis: d.state.alert_level === 'critical', label: `${d.device_id} · ${stateLabel(d.state.ml_health_state)}${d.online ? '' : ' · offline'}`, href: `/wearables/${d.device_id}` });
    }
    if (layers.team) for (const t of teams) {
      const at = teamLatLng(t);
      if (!at) continue;
      out.push({ id: String(t.id), kind: 'team', lat: at.lat, lng: at.lng, tone: t.is_available && t.current_load < t.capacity ? 'info' : 'muted', label: `${t.name} · ${t.current_load}/${t.capacity}` });
    }
    if (layers.rov) for (const r of Object.values(rov)) {
      if (r.latitude == null || r.longitude == null) continue;
      out.push({ id: r.id, kind: 'rov', lat: r.latitude, lng: r.longitude, tone: ACTIVE_ROV.includes(r.status) ? 'accent' : 'muted', emphasis: r.mode === 'manual', label: `${r.name} · ${r.status}${r.pilot ? ` · ${r.pilot}` : ''}`, href: ACTIVE_ROV.includes(r.status) ? '/missions' : '/rov' });
    }
    return out;
  }, [sos, devices, teams, rov, layers]);

  return (
    <Panel title="Map" className="ops-map" bodyClass="panel-body--flush map-body"
      actions={(
        <div className="segmented" role="group" aria-label="Map layers">
          {(['sos', 'device', 'team', 'rov'] as const).map((k) => (
            <button key={k} type="button" aria-pressed={layers[k]} onClick={() => setLayers((l) => ({ ...l, [k]: !l[k] }))}>
              {k === 'sos' ? 'SOS' : k === 'device' ? 'Wearables' : k === 'team' ? 'Teams' : 'ROV'}
            </button>
          ))}
        </div>
      )}>
      <MapView markers={markers} label="Operations map: SOS, wearables, teams and ROVs" onSelect={(m) => m.href && nav(m.href)} />
      <MapLegend />
    </Panel>
  );
}

export default function OpsPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const [showMap, setShowMap] = useState(true);
  const [teamsOpen, setTeamsOpen] = useState(false);
  const { can } = useAuth();
  useHotkeys({ m: () => setShowMap((v) => !v) });

  return (
    <div className="page page--ops">
      <div className="page-head">
        <h1>Operations</h1>
        <WeatherStrip />
        {can('team.edit') && <Button size="sm" variant="ghost" icon={<Users />} onClick={() => setTeamsOpen(true)} title="Team availability and capacity">Teams</Button>}
        <Button size="sm" variant="ghost" onClick={() => setShowMap((v) => !v)} aria-pressed={showMap} title="Toggle map (m)">{showMap ? 'Hide map' : 'Show map'}</Button>
      </div>
      <Kpis />
      <CapacityBanner />
      <div className={`ops-grid ${showMap ? '' : 'ops-grid--nomap'}`}>
        <SosQueue className="ops-queue" selected={selected} onSelect={setSelected} />
        <div className="ops-side">
          <AlertsPanel className="ops-alerts" />
          {showMap && <OpsMap />}
        </div>
      </div>
      <Dialog open={teamsOpen} onClose={() => setTeamsOpen(false)} title="Teams" labelledBy="teams-title" wide
        footer={<Button onClick={() => setTeamsOpen(false)}>Done</Button>}>
        <p className="muted">Stand a team down or change how many requests it can take at once. Capacity changes apply when you leave the field.</p>
        <TeamsTable />
      </Dialog>
    </div>
  );
}
