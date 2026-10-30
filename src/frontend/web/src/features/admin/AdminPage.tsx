import { Fragment, useMemo, useState } from 'react';
import { Check, Copy, Eye, KeyRound, MessageSquare, Plus } from 'lucide-react';
import { Link } from 'react-router-dom';
import { KeyReveal } from '../../ui/KeyReveal';
import { api, ApiError } from '../../api/client';
import { reloadSnapshot, useLive } from '../../api/live';
import type { AuditEntry, DeviceSummary, Role, Rov, SmsTestResponse, User } from '../../api/types';
import { ago, dayHhmm } from '../../lib/format';
import { useAsync, useNow } from '../../lib/hooks';
import { DataTable, type Column } from '../../ui/DataTable';
import { ConfirmDialog, Dialog } from '../../ui/Dialog';
import { Button, Chip, Empty, Panel, Priority } from '../../ui/primitives';
import { useErrorToast, useToast } from '../../ui/Toast';
import { TeamsPanel } from '../ops/TeamsPanel';
import { LinkChip } from '../rov/rovUi';

const ROLES: Role[] = ['admin', 'dispatcher', 'responder', 'viewer'];

/** The server's message plus the per-field reasons of a 422 (`details: [{loc, msg}]`). */
function errorText(e: ApiError): string {
  const list = Array.isArray(e.details) ? (e.details as { loc?: unknown[]; msg?: string }[]) : [];
  const parts = list.map((d) => `${String(d.loc?.[d.loc.length - 1] ?? '').replace(/_/g, ' ')}: ${d.msg ?? ''}`.trim()).filter((x) => x !== ':');
  return parts.length ? `${e.message}: ${parts.join('; ')}` : e.message;
}

function Users() {
  const q = useAsync(() => api.users(), []);
  const teams = useLive((s) => s.teams);
  const toast = useToast();
  const fail = useErrorToast();
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ username: '', display_name: '', password: '', role: 'responder' as Role, team_id: '' });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const patch = async (u: User, body: Parameters<typeof api.patchUser>[1]) => {
    try {
      const nu = await api.patchUser(u.id, body);
      q.setData((q.data ?? []).map((x) => (x.id === u.id ? { ...x, ...nu } : x)));
      toast({ tone: 'ok', title: `Updated ${u.username}` });
    } catch (e) { fail(e, `Could not update ${u.username}`); }
  };

  const create = async () => {
    setBusy(true);
    setErr(null);
    try {
      const u = await api.createUser({ ...form, team_id: form.team_id ? (Number.isNaN(Number(form.team_id)) ? form.team_id : Number(form.team_id)) : null });
      q.setData([...(q.data ?? []), u]);
      setCreating(false);
      setForm({ username: '', display_name: '', password: '', role: 'responder', team_id: '' });
      toast({ tone: 'ok', title: `Created ${u.username}` });
    } catch (e) {
      setErr(e instanceof ApiError ? errorText(e) : 'Could not create user');
    } finally { setBusy(false); }
  };

  // Mirrors the server's UserIn rules so Create is only enabled for a request it will accept.
  const userProblem = !/^[a-zA-Z0-9_.-]{3,64}$/.test(form.username) ? 'Username: 3 to 64 letters, digits, dots, dashes or underscores.'
    : !form.display_name.trim() ? 'Enter a display name.'
      : form.password.length < 10 ? 'Password: at least 10 characters.' : null;

  const cols: Column<User>[] = [
    { key: 'u', header: 'User', render: (u) => <><span className="mono">{u.username}</span><span className="cell-sub">{u.display_name}</span></> },
    {
      key: 'role', header: 'Role', render: (u) => (
        <select className="select input--sm" aria-label={`Role for ${u.username}`} value={u.role} onChange={(e) => void patch(u, { role: e.target.value })} style={{ width: 130 }}>
          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      ),
    },
    {
      key: 'team', header: 'Team', render: (u) => (
        <select className="select input--sm" aria-label={`Team for ${u.username}`} value={u.team_id == null ? '' : String(u.team_id)}
          onChange={(e) => void patch(u, { team_id: e.target.value ? (teams.find((t) => String(t.id) === e.target.value)?.id ?? e.target.value) : null })} style={{ width: 200 }}>
          <option value="">—</option>
          {teams.map((t) => <option key={t.id} value={String(t.id)}>{t.name}</option>)}
        </select>
      ),
    },
    {
      key: 'act', header: 'Status', render: (u) => (
        <label className="check-inline">
          <input type="checkbox" checked={u.is_active !== false} onChange={(e) => void patch(u, { is_active: e.target.checked })} /> active
        </label>
      ),
    },
  ];

  return (
    <Panel title="Users" count={q.data?.length} bodyClass="panel-body--flush" actions={<Button size="sm" icon={<Plus />} onClick={() => setCreating(true)}>Add user</Button>}>
      <DataTable rows={q.data ?? []} columns={cols} rowKey={(u) => String(u.id)} loading={q.loading} error={q.error} onRetry={q.reload} caption="Staff users" />
      <Dialog open={creating} onClose={() => setCreating(false)} title="Add user" labelledBy="user-title"
        footer={<><Button onClick={() => setCreating(false)}>Back</Button><Button variant="primary" busy={busy} disabled={!!userProblem} onClick={() => void create()}>Create</Button></>}>
        <div className="row-2">
          <label className="field"><span className="field-label">Username</span><input className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value.trim() })} autoComplete="off" /></label>
          <label className="field"><span className="field-label">Display name</span><input className="input" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></label>
        </div>
        <label className="field"><span className="field-label">Initial password</span><input className="input" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete="new-password" /><span className="field-hint">At least 10 characters. Share it privately.</span></label>
        <div className="row-2">
          <label className="field"><span className="field-label">Role</span>
            <select className="select" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select>
          </label>
          <label className="field"><span className="field-label">Team (responders)</span>
            <select className="select" value={form.team_id} onChange={(e) => setForm({ ...form, team_id: e.target.value })}>
              <option value="">—</option>{teams.map((t) => <option key={t.id} value={String(t.id)}>{t.name}</option>)}
            </select>
          </label>
        </div>
        {userProblem && (form.username || form.display_name || form.password) && <p className="field-hint" role="status">{userProblem}</p>}
        {err && <p className="field-error" role="alert">{err}</p>}
      </Dialog>
    </Panel>
  );
}

function Devices() {
  const devices = useLive((s) => s.devices);
  const load = useLive((s) => s.load.devices);
  const now = useNow(5000);
  const fail = useErrorToast();
  const [reg, setReg] = useState(false);
  const [form, setForm] = useState({ device_id: '', label: '' });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reveal, setReveal] = useState<{ id: string; key: string } | null>(null);
  const [rotate, setRotate] = useState<DeviceSummary | null>(null);
  const rows = useMemo(() => Object.values(devices).sort((a, b) => a.device_id.localeCompare(b.device_id)), [devices]);

  const register = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.registerDevice(form.device_id.trim(), form.label.trim());
      setReg(false);
      setForm({ device_id: '', label: '' });
      setReveal({ id: r.device_id, key: r.api_key });
      void reloadSnapshot('devices');
    } catch (e) { setErr(e instanceof ApiError ? errorText(e) : 'Could not register'); } finally { setBusy(false); }
  };
  const doRotate = async () => {
    if (!rotate) return;
    setBusy(true);
    try {
      const r = await api.rotateKey(rotate.device_id);
      setReveal({ id: rotate.device_id, key: r.api_key });
      setRotate(null);
    } catch (e) { fail(e, 'Could not rotate key'); } finally { setBusy(false); }
  };

  const cols: Column<DeviceSummary>[] = [
    { key: 'id', header: 'Device', render: (d) => <><span className="mono">{d.device_id}</span><span className="cell-sub">{d.label}</span></> },
    { key: 'on', header: 'Status', render: (d) => <><span className={`dot ${d.online ? 'dot--ok' : 'dot--off'}`} /> {d.online ? 'online' : 'offline'}</> },
    { key: 'seen', header: 'Last seen', render: (d) => <span className="mono muted">{d.last_seen ? `${ago(d.last_seen, now)} ago` : 'never'}</span> },
    { key: 'boot', header: 'Boot', render: (d) => <span className="mono muted">{d.boot_id ?? '—'}</span> },
    { key: 'k', header: <span className="sr-only">Actions</span>, className: 'r', render: (d) => <Button size="sm" icon={<KeyRound />} onClick={() => setRotate(d)}>Rotate key</Button> },
  ];

  return (
    <Panel title="Devices" count={rows.length} bodyClass="panel-body--flush" actions={<Button size="sm" icon={<Plus />} onClick={() => setReg(true)}>Register device</Button>}>
      <DataTable rows={rows} columns={cols} rowKey={(d) => d.device_id} loading={load === 'loading'} caption="Registered wearables" />
      <Dialog open={reg} onClose={() => setReg(false)} title="Register a wearable" labelledBy="reg-title"
        footer={<><Button onClick={() => setReg(false)}>Back</Button><Button variant="primary" busy={busy} disabled={!/^[A-Za-z0-9_-]{3,32}$/.test(form.device_id)} onClick={() => void register()}>Register</Button></>}>
        <label className="field"><span className="field-label">Device ID</span><input className="input mono" value={form.device_id} placeholder="TRD-W09" onChange={(e) => setForm({ ...form, device_id: e.target.value.toUpperCase() })} /><span className="field-hint">Must match DEVICE_ID in the firmware. 3–32 letters, digits, - or _.</span></label>
        <label className="field"><span className="field-label">Label</span><input className="input" value={form.label} placeholder="Rescuer · name, or Evacuee · camp #" onChange={(e) => setForm({ ...form, label: e.target.value })} /></label>
        {err && <p className="field-error" role="alert">{err}</p>}
      </Dialog>
      <ConfirmDialog open={!!rotate} title={`Rotate key for ${rotate?.device_id ?? ''}?`} confirmLabel="Rotate key" danger busy={busy}
        body={<p>The current key stops working immediately. The band will be rejected until its firmware has the new key.</p>}
        onClose={() => setRotate(null)} onConfirm={() => void doRotate()} />
      {reveal && <KeyReveal title={`API key for ${reveal.id}`} apiKey={reveal.key} onClose={() => setReveal(null)}
        hint={<>Put it in the band firmware as the <code className="mono">X-Device-Key</code> value (secrets.h, never in git).</>} />}
    </Panel>
  );
}

/** A shell command with a copy button, shown next to a newly issued key. */
function CommandLine({ cmd, label }: { cmd: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(cmd); setCopied(true); } catch { /* the user can select the text */ }
  };
  return (
    <div className="key-box">
      <code className="mono" aria-label={label}>{cmd}</code>
      <Button size="sm" icon={copied ? <Check /> : <Copy />} onClick={copy}>{copied ? 'Copied' : 'Copy'}</Button>
    </div>
  );
}

type RovKeyKind = 'bridge' | 'vision';

/** Keys for real ROV hardware: the serial bridge (telemetry and commands) and the vision worker (camera). */
function RovUnits() {
  const rov = useLive((s) => s.rov);
  const load = useLive((s) => s.load.rov);
  const now = useNow(5000);
  const fail = useErrorToast();
  const [bridge, setBridge] = useState<Rov | null>(null);
  const [vision, setVision] = useState<Rov | null>(null);
  const [videoUrl, setVideoUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [reveal, setReveal] = useState<{ kind: RovKeyKind; name: string; key: string } | null>(null);
  const rows = useMemo(() => Object.values(rov).sort((a, b) => a.name.localeCompare(b.name)), [rov]);

  const issue = async (kind: RovKeyKind, r: Rov) => {
    setBusy(true);
    try {
      const k = kind === 'bridge' ? await api.rovBridgeKey(r.id, videoUrl.trim() || undefined) : await api.rovVisionKey(r.id);
      setReveal({ kind, name: r.name, key: k.api_key });
      setBridge(null);
      setVision(null);
      // A bridge key turns the unit into real hardware (simulated: false, offline until the bridge connects).
      if (kind === 'bridge') void reloadSnapshot('rov');
    } catch (e) { fail(e, `Could not issue a ${kind} key for ${r.name}`); } finally { setBusy(false); }
  };

  const cols: Column<Rov>[] = [
    { key: 'n', header: 'Unit', render: (r) => <><strong>{r.name}</strong><span className="cell-sub mono">{r.id}</span></> },
    { key: 'h', header: 'Hardware', render: (r) => (r.simulated ? <Chip tone="info">simulated</Chip> : <Chip tone="ok">real unit</Chip>) },
    { key: 'l', header: 'Link', render: (r) => <><LinkChip link={r.link} /><span className="cell-sub mono">{r.last_seen ? `${ago(r.last_seen, now)} ago` : 'never'}</span></> },
    {
      key: 'a', header: <span className="sr-only">Actions</span>, className: 'r', render: (r) => (
        <span className="action-row">
          <Button size="sm" icon={<KeyRound />} onClick={() => { setVideoUrl(r.video_url ?? ''); setBridge(r); }}>Issue bridge key</Button>
          <Button size="sm" icon={<Eye />} onClick={() => setVision(r)}>Issue vision key</Button>
        </span>
      ),
    },
  ];

  const command = reveal?.kind === 'bridge'
    ? `python -m src.rov.bridge --port COMx --key ${reveal.key}`
    : `python -m src.cv.vision --key ${reveal?.key ?? ''} --source <camera>`;

  return (
    <Panel title="ROV units" count={rows.length} bodyClass="panel-body--flush"
      footer={<>A bridge key connects real hardware through <code className="mono">src/rov/bridge.py</code>; a vision key connects the camera worker in <code className="mono">src/cv/vision</code>.</>}>
      <DataTable rows={rows} columns={cols} rowKey={(r) => r.id} loading={load === 'loading'} caption="ROV units"
        error={load === 'error' ? new Error('ROV list could not be loaded.') : null} onRetry={() => void reloadSnapshot('rov')} />
      <Dialog open={!!bridge} onClose={() => setBridge(null)} title={`Bridge key · ${bridge?.name ?? ''}`} labelledBy="admin-bridge-title"
        footer={<><Button onClick={() => setBridge(null)}>Back</Button><Button variant="primary" busy={busy} onClick={() => { if (bridge) void issue('bridge', bridge); }}>Issue key</Button></>}>
        <div className="banner banner--warning" role="status">
          This marks {bridge?.name ?? 'the unit'} as a real unit and ends its simulation. It shows offline until the serial bridge connects with the new key. Any previous bridge key stops working.
        </div>
        <label className="field">
          <span className="field-label">Camera stream URL (optional, MJPEG)</span>
          <input className="input mono" value={videoUrl} onChange={(e) => setVideoUrl(e.target.value)} placeholder="http://10.0.0.20:8080/stream.mjpg" />
          <span className="field-hint">Leave empty to keep the current URL (or none).</span>
        </label>
      </Dialog>
      <ConfirmDialog open={!!vision} title={`Issue a vision key for ${vision?.name ?? ''}?`} confirmLabel="Issue key" busy={busy}
        body={<p>The camera worker next to the unit uses this key to post annotated frames and detections. Any previous vision key for this unit stops working. The unit stays {vision?.simulated ? 'simulated' : 'a real unit'}.</p>}
        onClose={() => setVision(null)} onConfirm={() => { if (vision) void issue('vision', vision); }} />
      {reveal && (
        <KeyReveal title={`${reveal.kind === 'bridge' ? 'Bridge' : 'Vision'} key for ${reveal.name}`} apiKey={reveal.key} onClose={() => setReveal(null)}
          hint={(
            <>
              Run this on the computer {reveal.kind === 'bridge' ? 'wired to the unit' : 'with the camera'}:
              <CommandLine cmd={command} label={`${reveal.kind} command`} />
              {reveal.kind === 'bridge'
                ? <>Replace <code className="mono">COMx</code> with the serial port (e.g. <code className="mono">COM3</code> or <code className="mono">/dev/ttyUSB0</code>).</>
                : <>Replace <code className="mono">&lt;camera&gt;</code> with a webcam index (<code className="mono">0</code>), a camera URL, a video file or <code className="mono">demo</code>.</>}
              {' '}Add <code className="mono">--api {window.location.origin}</code> when the server is not on <code className="mono">localhost:8000</code>.
            </>
          )} />
      )}
    </Panel>
  );
}

const fmtDetails = (d: AuditEntry['details']) => (d == null ? '' : typeof d === 'string' ? d : Object.keys(d).length ? JSON.stringify(d) : '');

/** GET /audit: who did what, newest first, filtered in the browser. */
function AuditLog() {
  const q = useAsync(() => api.audit(200), []);
  const [filter, setFilter] = useState('');
  const f = filter.trim().toLowerCase();
  const rows = useMemo(() => {
    const all = q.data ?? [];
    if (!f) return all;
    return all.filter((a) => [a.actor, a.action, a.target, fmtDetails(a.details), a.request_id].some((v) => v && v.toLowerCase().includes(f)));
  }, [q.data, f]);

  const cols: Column<AuditEntry>[] = [
    { key: 't', header: 'Time', render: (a) => <span className="mono muted" title={a.at}>{dayHhmm(a.at)}</span> },
    { key: 'u', header: 'Actor', render: (a) => <span className="mono">{a.actor ?? '—'}</span> },
    { key: 'a', header: 'Action', render: (a) => <span className="mono">{a.action}</span> },
    { key: 'g', header: 'Target', render: (a) => a.target ?? '—' },
    { key: 'd', header: 'Details', render: (a) => <span className="mono muted">{fmtDetails(a.details) || '—'}</span> },
    { key: 'r', header: 'Request', render: (a) => <span className="mono muted">{a.request_id ?? '—'}</span> },
  ];

  return (
    <Panel title="Audit log" count={q.data ? (f ? `${rows.length} / ${q.data.length}` : q.data.length) : undefined} bodyClass="panel-body--flush"
      actions={(
        <>
          <input className="input input--sm" type="search" placeholder="Filter" aria-label="Filter the audit log" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ width: 200 }} />
          <Button size="sm" variant="ghost" onClick={q.reload} busy={q.loading}>Refresh</Button>
        </>
      )}
      footer={<>The latest 200 entries, newest first.</>}>
      <DataTable rows={rows} columns={cols} rowKey={(a) => String(a.id)} loading={q.loading} error={q.error} onRetry={q.reload} caption="Audit log"
        empty={<Empty title={f ? 'No entries match the filter' : 'No audit entries'} />} />
    </Panel>
  );
}

const SMS_FROM = '+91 98400 00000';
const SMS_TEXT = 'SOS 13.0120,80.2410 P2 I1 Tflood elderly, ground floor flooded';

const fmtParsed = (v: unknown) => (v == null || v === '' ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v));

/** Runs a message through the SMS intake parser (POST /sms/test) without a gateway or provider. */
function SmsTest() {
  const [from, setFrom] = useState(SMS_FROM);
  const [text, setText] = useState(SMS_TEXT);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [res, setRes] = useState<SmsTestResponse | null>(null);

  const send = async () => {
    setBusy(true);
    setErr(null);
    setRes(null);
    try {
      setRes(await api.smsTest({ from: from.trim(), text }));
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 503 ? 'SMS intake is not configured on the server'
        : e instanceof ApiError ? errorText(e) : 'Could not send the test message');
    } finally { setBusy(false); }
  };

  const parsed = res?.parsed ? Object.entries(res.parsed) : [];
  return (
    <Panel title="SMS intake test"
      footer={<>In production an SMS gateway (a provider, or an Android phone) posts incoming messages to <code className="mono">/api/v1/sms/inbound</code>.</>}>
      <form className="sms-test" onSubmit={(e) => { e.preventDefault(); void send(); }}>
        <label className="field"><span className="field-label">From (phone number)</span>
          <input className="input mono" value={from} onChange={(e) => setFrom(e.target.value)} autoComplete="off" inputMode="tel" />
        </label>
        <label className="field"><span className="field-label">Message</span>
          <textarea className="textarea mono" rows={3} maxLength={160} value={text} onChange={(e) => setText(e.target.value)} />
          <span className="field-hint">Format: <span className="mono">SOS &lt;lat&gt;,&lt;lng&gt; P&lt;people&gt; I&lt;injured&gt; T&lt;type&gt; &lt;note&gt;</span> · <span className="mono">{text.length}</span>/160</span>
        </label>
        <div><Button type="submit" variant="primary" icon={<MessageSquare />} busy={busy} disabled={!from.trim() || !text.trim()}>Send test SMS</Button></div>
      </form>
      {err && <p className="field-error" role="alert">{err}</p>}
      {res && (
        <div className="sms-result" role="status">
          <dl className="kv">
            <dt>Reference</dt>
            <dd>{res.reference_id
              ? <Link to={`/sos/${encodeURIComponent(res.reference_id)}`} className="mono">{res.reference_id}</Link>
              : <span className="muted">no request created</span>}</dd>
            <dt>Priority</dt>
            <dd>{res.priority != null ? <Priority p={res.priority} /> : '—'}</dd>
            <dt>Reply to sender</dt>
            <dd><span className="mono">{res.reply || '—'}</span></dd>
          </dl>
          {parsed.length > 0 && (
            <>
              <h3 className="sms-sub">Parsed</h3>
              <dl className="kv">
                {parsed.map(([k, v]) => <Fragment key={k}><dt className="mono">{k}</dt><dd className="mono">{fmtParsed(v)}</dd></Fragment>)}
              </dl>
            </>
          )}
        </div>
      )}
    </Panel>
  );
}

export default function AdminPage() {
  return (
    <div className="page">
      <div className="page-head"><h1>Admin</h1></div>
      <div className="admin-grid">
        <Users />
        <Devices />
        <RovUnits />
        <SmsTest />
        <TeamsPanel />
        <AuditLog />
      </div>
    </div>
  );
}
