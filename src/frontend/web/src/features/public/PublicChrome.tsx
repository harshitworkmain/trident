import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useOutbox } from './offline';

/** Online / offline / queued requests, for people on weak connections. */
export function NetStatus() {
  const { online, items, sending } = useOutbox();
  const waiting = items.filter((i) => !i.rejected).length;
  const [tone, label] = sending ? ['warning', 'Sending saved request…']
    : waiting ? ['warning', `${waiting} request${waiting === 1 ? '' : 's'} waiting to send`]
      : online ? ['ok', 'Online'] : ['critical', 'Offline'];
  return (
    <span className={`net net--${tone} ${sending ? 'net--busy' : ''}`} role="status" aria-live="polite" title={online ? 'Connected' : 'No connection: requests are saved on this phone'}>
      <span className="dot" aria-hidden="true" />
      <span>{!online && waiting ? `Offline · ${label.toLowerCase()}` : label}</span>
    </span>
  );
}

export function PublicHeader({ right }: { right?: ReactNode }) {
  return (
    <header className="pub-header">
      <Link to="/" className="brand" aria-label="TRIDENT home">
        <img src="/logo.png" alt="" width={28} height={28} />
        <span>TRIDENT</span>
      </Link>
      <NetStatus />
      <nav className="pub-nav" aria-label="Site">
        {right ?? (
          <>
            <Link to="/sos" className="link-sweep">Request help</Link>
            <Link to="/login" className="link-sweep">Staff sign-in</Link>
          </>
        )}
      </nav>
    </header>
  );
}

export function EmergencyNumbers({ compact }: { compact?: boolean }) {
  return (
    <aside className={`emergency ${compact ? 'emergency--compact' : ''}`} aria-label="Emergency phone numbers">
      <h2>If you can call</h2>
      <ul>
        <li><a href="tel:112" className="mono">112</a><span>National emergency number</span></li>
        <li><a href="tel:1070" className="mono">1070</a><span>Tamil Nadu State Emergency Operation Centre</span></li>
        <li><a href="tel:1913" className="mono">1913</a><span>Greater Chennai Corporation helpline</span></li>
      </ul>
    </aside>
  );
}

export function PublicFooter() {
  return (
    <footer className="pub-footer">
      <span>TRIDENT · flood and water-rescue coordination, Chennai</span>
      <span className="muted">Requests are seen by the control room and assigned rescue teams only.</span>
    </footer>
  );
}
