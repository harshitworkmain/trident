import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, CheckCheck } from 'lucide-react';
import { api } from '../../api/client';
import { upsertAlert, useLive } from '../../api/live';
import type { Alert } from '../../api/types';
import { ago, pct } from '../../lib/format';
import { useHotkeys, useNow } from '../../lib/hooks';
import { alertLevelOf } from '../../lib/states';
import { Dialog } from '../../ui/Dialog';
import { Button, Chip, Empty, ErrorState, Kbd, Panel, Skeleton, StateChip } from '../../ui/primitives';
import { useErrorToast, useToast } from '../../ui/Toast';
import { useAuth } from '../auth/auth';

export function AlertsPanel({ className }: { className?: string }) {
  const alerts = useLive((s) => s.alerts);
  const devices = useLive((s) => s.devices);
  const load = useLive((s) => s.load.alerts);
  const { can } = useAuth();
  const now = useNow(5000);
  const toast = useToast();
  const fail = useErrorToast();
  const [busy, setBusy] = useState<string | null>(null);
  const [resolving, setResolving] = useState<Alert | null>(null);
  const [note, setNote] = useState('');

  const list = useMemo(() => Object.values(alerts)
    .filter((a) => a.status !== 'resolved')
    .sort((a, b) => (a.status === b.status ? Date.parse(a.opened_at) - Date.parse(b.opened_at) : a.status === 'open' ? -1 : 1)), [alerts]);
  const openCount = list.filter((a) => a.status === 'open').length;

  const ack = async (a: Alert) => {
    setBusy(String(a.id));
    try {
      upsertAlert(await api.ackAlert(a.id));
      toast({ tone: 'ok', title: `Acknowledged ${a.device_id}` });
    } catch (e) { fail(e, 'Could not acknowledge'); } finally { setBusy(null); }
  };
  const resolve = async () => {
    if (!resolving) return;
    setBusy(String(resolving.id));
    try {
      upsertAlert(await api.resolveAlert(resolving.id, note.trim() || undefined));
      setResolving(null);
      setNote('');
    } catch (e) { fail(e, 'Could not resolve'); } finally { setBusy(null); }
  };

  useHotkeys({
    a: () => {
      const first = list.find((x) => x.status === 'open');
      if (first && can('alert.ack')) void ack(first);
    },
  });

  return (
    <Panel id="alerts" title="Alerts" count={openCount ? `${openCount} open` : list.length} className={className}
      bodyClass="panel-body--flush panel-body--scroll"
      actions={can('alert.ack') && openCount > 0 ? <span className="hint"><Kbd>a</Kbd> ack oldest</span> : undefined}>
      {load === 'loading' && !list.length ? <Skeleton rows={3} /> : load === 'error' && !list.length ? <ErrorState error="Alerts could not be loaded." /> : list.length === 0 ? (
        <Empty title="No unresolved alerts" icon={<CheckCheck aria-hidden="true" />}>Critical wearable states open an alert here automatically.</Empty>
      ) : (
        <ul className="alert-list">
          {list.map((a) => {
            const dev = devices[a.device_id];
            return (
              <li key={a.id} className={`alert-row ${a.status === 'open' ? 'is-open' : ''} ${a.escalated ? 'is-escalated' : ''}`}>
                <div className="alert-main">
                  <div className="alert-line">
                    <StateChip state={a.state} level={alertLevelOf(a.state)} />
                    {a.escalated && a.status === 'open' && <Chip tone="critical">Escalated</Chip>}
                    {a.status === 'acked' && <Chip tone="muted">Acked{a.acked_by ? ` · ${a.acked_by}` : ''}</Chip>}
                    <span className="alert-age mono" title={a.opened_at}>{ago(a.opened_at, now)}</span>
                  </div>
                  <div className="alert-line">
                    <Link to={`/wearables/${encodeURIComponent(a.device_id)}`} className="mono">{a.device_id}</Link>
                    {dev?.label && <span className="muted">{dev.label}</span>}
                    <span className="muted mono">risk {pct(a.risk)}</span>
                    {a.sos_reference_id && <Link to={`/sos/${a.sos_reference_id}`} className="mono">{a.sos_reference_id}</Link>}
                  </div>
                  {a.evidence?.length > 0 && <p className="alert-evidence">{a.evidence.slice(0, 3).join(' · ')}</p>}
                </div>
                <div className="alert-actions">
                  {a.status === 'open' && can('alert.ack') && (
                    <Button size="sm" variant="primary" icon={<Check />} busy={busy === String(a.id)} onClick={() => void ack(a)}>Ack</Button>
                  )}
                  {can('alert.resolve') && (
                    <Button size="sm" onClick={() => setResolving(a)} disabled={busy === String(a.id)}>Resolve</Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      <Dialog open={!!resolving} onClose={() => setResolving(null)} title={`Resolve alert · ${resolving?.device_id ?? ''}`} labelledBy="resolve-title"
        footer={<><Button onClick={() => setResolving(null)}>Back</Button><Button variant="primary" onClick={() => void resolve()} busy={!!busy}>Resolve alert</Button></>}>
        <p className="muted">Resolve when the person has been reached or the reading is confirmed false. This closes the alert for everyone.</p>
        <label className="field">
          <span className="field-label">Note (optional)</span>
          <textarea className="textarea" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Reached by NDRF Alpha, conscious, moved to camp" />
        </label>
      </Dialog>
    </Panel>
  );
}
