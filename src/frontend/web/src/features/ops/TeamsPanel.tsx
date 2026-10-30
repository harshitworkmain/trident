import { api } from '../../api/client';
import { reloadSnapshot, useLive } from '../../api/live';
import type { Team } from '../../api/types';
import { DataTable, type Column } from '../../ui/DataTable';
import { Chip, Panel } from '../../ui/primitives';
import { useErrorToast } from '../../ui/Toast';

/** Availability and capacity of the response teams (PATCH /teams/{id}, permission `team.edit`: admin and dispatcher). */
export function TeamsTable() {
  const teams = useLive((s) => s.teams);
  const load = useLive((s) => s.load.teams);
  const fail = useErrorToast();
  const set = async (t: Team, body: { is_available?: boolean; capacity?: number }) => {
    try { await api.patchTeam(t.id, body); } catch (e) { fail(e, `Could not update ${t.name}`); }
    // Reload either way: on success to show the change, on failure to put the input back.
    void reloadSnapshot('teams');
    void reloadSnapshot('capacity');
  };
  const cols: Column<Team>[] = [
    { key: 'n', header: 'Team', render: (t) => <><strong>{t.name}</strong><span className="cell-sub">{t.team_type ?? t.type} · {t.deployment_mode}</span></> },
    { key: 'l', header: 'Load', render: (t) => <span className="mono">{t.current_load}</span> },
    {
      key: 'c', header: 'Capacity', render: (t) => (
        // Keyed by the server value so a change made elsewhere replaces the uncontrolled input.
        <input key={t.capacity} className="input input--sm mono" type="number" min={0} max={100} defaultValue={t.capacity} aria-label={`Capacity of ${t.name}`} style={{ width: 70 }}
          onBlur={(e) => { const v = Number(e.target.value); if (Number.isInteger(v) && v !== t.capacity && v >= 0 && v <= 100) void set(t, { capacity: v }); else e.target.value = String(t.capacity); }} />
      ),
    },
    {
      key: 'a', header: 'Available', render: (t) => (
        <label className="check-inline">
          <input type="checkbox" checked={t.is_available} onChange={(e) => void set(t, { is_available: e.target.checked })} aria-label={`${t.name} available`} />
          {' '}{t.is_available ? <Chip tone="ok">available</Chip> : <Chip tone="muted">stood down</Chip>}
        </label>
      ),
    },
  ];
  return <DataTable rows={teams} columns={cols} rowKey={(t) => String(t.id)} loading={load === 'loading'} caption="Response teams" />;
}

export function TeamsPanel() {
  const count = useLive((s) => s.teams.length);
  return (
    <Panel title="Teams" count={count} bodyClass="panel-body--flush"
      footer={<>Dispatchers can also change these from <strong>Teams</strong> on Operations.</>}>
      <TeamsTable />
    </Panel>
  );
}
