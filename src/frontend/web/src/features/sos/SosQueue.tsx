import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { reloadSnapshot, useLive } from '../../api/live';
import type { SosRecord } from '../../api/types';
import { ago, titleCase } from '../../lib/format';
import { useHotkeys, useNow } from '../../lib/hooks';
import { isOpenSos } from '../../lib/states';
import { DataTable, type Column } from '../../ui/DataTable';
import { ScrambleText } from '../../ui/effects';
import { Empty, Kbd, Panel, Priority, StatusChip } from '../../ui/primitives';
import { isWaitingReason, SosFlags } from './SosFlags';

type Filter = 'open' | 'pending' | 'all';

export function sortQueue(a: SosRecord, b: SosRecord) {
  return a.priority - b.priority || b.priority_score - a.priority_score || Date.parse(a.created_at) - Date.parse(b.created_at);
}

export function SosQueue({ className, selected, onSelect }: { className?: string; selected: string | null; onSelect: (ref: string | null) => void }) {
  const sos = useLive((s) => s.sos);
  const load = useLive((s) => s.load.sos);
  const nav = useNavigate();
  const now = useNow(5000);
  const [filter, setFilter] = useState<Filter>('open');
  const [q, setQ] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);
  const seenRefs = useRef<Set<string> | null>(null);

  const rows = useMemo(() => {
    const term = q.trim().toLowerCase();
    return Object.values(sos)
      .filter((r) => (filter === 'all' ? true : filter === 'pending' ? r.status === 'pending' : isOpenSos(r.status)))
      .filter((r) => !term || `${r.reference_id} ${r.source ?? ''} ${r.name} ${r.address} ${r.city} ${r.emergency_type} ${r.assigned_team?.name ?? ''}`.toLowerCase().includes(term))
      .sort(sortQueue);
  }, [sos, filter, q]);

  // Rows that arrived after the first render get a one-off highlight.
  const fresh = useMemo(() => {
    if (load !== 'ok') return new Set<string>();
    if (!seenRefs.current) { seenRefs.current = new Set(Object.keys(sos)); return new Set<string>(); }
    const out = new Set<string>();
    for (const k of Object.keys(sos)) if (!seenRefs.current.has(k)) out.add(k);
    return out;
  }, [sos, load]);
  useEffect(() => {
    if (!fresh.size) return;
    const t = window.setTimeout(() => fresh.forEach((k) => seenRefs.current?.add(k)), 4000);
    return () => window.clearTimeout(t);
  }, [fresh]);

  const move = (d: 1 | -1) => {
    if (!rows.length) return;
    const i = rows.findIndex((r) => r.reference_id === selected);
    const n = rows[Math.max(0, Math.min(rows.length - 1, i === -1 ? 0 : i + d))];
    onSelect(n.reference_id);
    document.querySelector(`tr[data-key="${n.reference_id}"]`)?.scrollIntoView({ block: 'nearest' });
  };

  useHotkeys({
    '/': () => searchRef.current?.focus(),
    j: () => move(1),
    k: () => move(-1),
    Enter: () => { if (selected) nav(`/sos/${selected}`); },
  });

  const cols: Column<SosRecord>[] = [
    { key: 'p', header: <span title="Priority">P</span>, width: 36, render: (r) => <Priority p={r.priority} /> },
    {
      key: 'ref', header: 'Request', render: (r) => (
        <>
          <ScrambleText text={r.reference_id} onMount={fresh.has(r.reference_id)} />
          <span className="cell-sub">{titleCase(r.emergency_type)} · {r.address.split(',').slice(-2).join(',').trim() || r.city}</span>
          <SosFlags r={r} now={now} />
        </>
      ),
    },
    {
      key: 'ppl', header: 'People', className: 'nowrap', render: (r) => (
        <span className="mono">{r.people_to_rescue}{r.people_injured > 0 && <span className="injured"> · {r.people_injured} inj</span>}</span>
      ),
    },
    {
      key: 'why', header: 'Why this priority', render: (r) => {
        // Priority ageing ("waiting 25 min") is already shown as the live waiting chip.
        const reasons = r.waiting_min != null ? r.priority_reasons.filter((x) => !isWaitingReason(x)) : r.priority_reasons;
        return (
          <span className="reasons">
            <span className="mono score" title="Priority score 0-100">{r.priority_score}</span>
            {reasons.slice(0, 3).map((x) => <span key={x} className="reason">{x}</span>)}
            {reasons.length > 3 && <span className="reason">+{reasons.length - 3}</span>}
          </span>
        );
      },
    },
    { key: 'st', header: 'Status', render: (r) => <><StatusChip status={r.status} />{r.assigned_team && <span className="cell-sub">{r.assigned_team.name}</span>}</> },
    { key: 'age', header: 'Age', className: 'r nowrap', render: (r) => <span className="mono muted" title={r.created_at}>{ago(r.created_at, now)}</span> },
  ];

  return (
    <Panel title="SOS queue" count={rows.length} className={className} bodyClass="panel-body--flush queue-body"
      actions={(
        <>
          <div className="segmented" role="group" aria-label="Filter">
            {(['open', 'pending', 'all'] as Filter[]).map((f) => (
              <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}>{titleCase(f)}</button>
            ))}
          </div>
          <div className="search">
            <Search aria-hidden="true" />
            <input ref={searchRef} className="input input--sm" type="search" placeholder="Search" aria-label="Search SOS queue" value={q}
              onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === 'Escape') { setQ(''); e.currentTarget.blur(); } }} />
            {!q && <Kbd>/</Kbd>}
          </div>
        </>
      )}>
      <DataTable rows={rows} columns={cols} rowKey={(r) => r.reference_id} caption="SOS requests sorted by priority"
        selectedKey={selected} onRowClick={(r) => { onSelect(r.reference_id); nav(`/sos/${r.reference_id}`); }}
        loading={load === 'loading'} error={load === 'error' ? new Error('The SOS list could not be loaded.') : null}
        onRetry={() => void reloadSnapshot('sos')}
        rowClass={(r) => `${fresh.has(r.reference_id) ? 'is-fresh' : ''} ${r.priority === 1 ? 'is-p1' : ''}`}
        empty={<Empty title={q ? 'No match' : filter === 'pending' ? 'Nothing waiting for triage' : 'No open requests'}>{q ? 'Try a reference, name or area.' : 'New public requests appear here within a second.'}</Empty>} />
    </Panel>
  );
}
