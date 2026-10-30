import { useMemo, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Activity, BarChart3, CloudRain, HelpCircle, LayoutDashboard, LogOut, Radar, Shield, Ship, Watch } from 'lucide-react';
import { reconnectNow, useLive, type ConnState } from '../../api/live';
import { useHotkeys, useNow } from '../../lib/hooks';
import { Button, Kbd } from '../../ui/primitives';
import { Dialog } from '../../ui/Dialog';
import { ErrorBoundary } from '../../ui/ErrorBoundary';
import { useAuth } from '../auth/auth';

const NAV = [
  { to: '/ops', label: 'Operations', icon: LayoutDashboard, key: '1' },
  { to: '/wearables', label: 'Wearables', icon: Watch, key: '2' },
  { to: '/missions', label: 'ROV missions', icon: Radar, key: '3' },
  { to: '/weather', label: 'Weather', icon: CloudRain, key: '4' },
  { to: '/analytics', label: 'Analytics', icon: BarChart3, key: '5' },
  { to: '/rov', label: 'ROV units', icon: Ship, key: '6' },
  { to: '/admin', label: 'Admin', icon: Shield, key: '7', admin: true },
];

const CONN_LABEL: Record<ConnState, string> = {
  idle: 'Not connected', connecting: 'Connecting', open: 'Live', reconnecting: 'Reconnecting', offline: 'Offline',
};

export function ConnectionIndicator() {
  const conn = useLive((s) => s.conn);
  const retry = useLive((s) => s.retryInMs);
  const clickable = conn === 'reconnecting' || conn === 'offline';
  const label = `${CONN_LABEL[conn]}${retry ? `, retry in ${Math.ceil(retry / 1000)} s` : ''}`;
  return (
    <button type="button" className={`conn conn--${conn}`} onClick={clickable ? reconnectNow : undefined}
      title={clickable ? 'Real-time feed interrupted. Click to retry now.' : 'Real-time feed status'} aria-label={`Real-time feed: ${label}`}
      aria-disabled={!clickable}>
      <span className="dot" aria-hidden="true" />
      <span>{CONN_LABEL[conn]}</span>
    </button>
  );
}

function Clock() {
  const now = useNow(1000);
  const t = new Date(now);
  const s = t.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  return <time className="clock mono" dateTime={t.toISOString()} aria-label="Local time">{s}</time>;
}

function LiveRegions() {
  const a = useLive((s) => s.announcement);
  return (
    <>
      <div className="sr-only" aria-live="assertive" aria-atomic="true">{a?.level === 'assertive' ? a.text : ''}</div>
      <div className="sr-only" aria-live="polite" aria-atomic="true">{a?.level === 'polite' ? a.text : ''}</div>
    </>
  );
}

export function ShortcutHelp({ open, onClose }: { open: boolean; onClose: () => void }) {
  const rows: [string[], string][] = [
    [['?'], 'Show this help'],
    [['1'], 'Operations'], [['2'], 'Wearables'], [['3'], 'ROV missions'], [['4'], 'Weather'], [['5'], 'Analytics'], [['6'], 'ROV units'], [['7'], 'Admin'],
    [['/'], 'Search the SOS queue (Operations)'],
    [['j'], 'Next SOS in queue'], [['k'], 'Previous SOS in queue'],
    [['Enter'], 'Open the selected SOS'],
    [['a'], 'Acknowledge the oldest open alert'],
    [['m'], 'Show or hide the map (Operations)'],
    [['W', 'A', 'S', 'D'], 'Drive the ROV (mission panel focused, manual control)'],
    [['R', 'F'], 'ROV up / down'],
    [['L'], 'ROV lights'],
    [['Space'], 'ROV stop'],
    [['Esc'], 'Close a dialog'],
  ];
  return (
    <Dialog open={open} onClose={onClose} title="Keyboard shortcuts" labelledBy="help-title">
      <dl className="help-grid">
        {rows.map(([keys, desc]) => (
          <div key={desc} style={{ display: 'contents' }}>
            <dt>{keys.map((k) => <Kbd key={k}>{k}</Kbd>)}</dt>
            <dd>{desc}</dd>
          </div>
        ))}
      </dl>
    </Dialog>
  );
}

export function StaffLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const { pathname } = useLocation();
  const [help, setHelp] = useState(false);
  const alerts = useLive((s) => s.alerts);
  const openAlerts = useMemo(() => Object.values(alerts).filter((a) => a.status === 'open').length, [alerts]);
  const items = NAV.filter((n) => !n.admin || user?.role === 'admin');

  useHotkeys({
    '?': () => setHelp(true),
    ...Object.fromEntries(items.map((n) => [n.key, () => nav(n.to)])),
  });

  return (
    <div className="shell">
      <a href="#main" className="skip-link">Skip to content</a>
      <header className="topbar">
        <NavLink to="/ops" className="brand" aria-label="TRIDENT operations home">
          <img src="/logo.png" alt="" width={24} height={24} />
          <span>TRIDENT</span>
        </NavLink>
        <span className="topbar-site">Chennai control room</span>
        <div className="topbar-right">
          {openAlerts > 0 && (
            <NavLink to="/ops#alerts" className="alert-pill" aria-label={`${openAlerts} open alert${openAlerts > 1 ? 's' : ''}`}>
              <Activity aria-hidden="true" /> <span className="num">{openAlerts}</span> open alert{openAlerts > 1 ? 's' : ''}
            </NavLink>
          )}
          <ConnectionIndicator />
          <Clock />
          <Button variant="ghost" iconOnly size="sm" aria-label="Keyboard shortcuts" title="Keyboard shortcuts (?)" onClick={() => setHelp(true)} icon={<HelpCircle />} />
          <div className="user-chip" title={`${user?.username} · ${user?.role}`}>
            <span className="user-name">{user?.display_name}</span>
            <span className="user-role">{user?.role}</span>
          </div>
          <Button variant="ghost" iconOnly size="sm" aria-label="Sign out" title="Sign out" onClick={() => void logout().then(() => nav('/login'))} icon={<LogOut />} />
        </div>
      </header>
      <nav className="sidenav" aria-label="Primary">
        <ul>
          {items.map((n) => (
            <li key={n.to}>
              <NavLink to={n.to} className={({ isActive }) => `navlink ${isActive ? 'is-active' : ''}`} title={`${n.label} (${n.key})`}>
                <n.icon aria-hidden="true" />
                <span className="navlink-label">{n.label}</span>
                <kbd className="navlink-key" aria-hidden="true">{n.key}</kbd>
              </NavLink>
            </li>
          ))}
        </ul>
        {import.meta.env.VITE_MOCK === '1' && <p className="mock-flag mono">MOCK DATA</p>}
      </nav>
      <main id="main" className="main" tabIndex={-1}>
        {/* A crash in one page stays inside <main>; navigating away clears it. */}
        <ErrorBoundary resetKey={pathname} className="page"><Outlet /></ErrorBoundary>
      </main>
      <LiveRegions />
      <ShortcutHelp open={help} onClose={() => setHelp(false)} />
    </div>
  );
}
