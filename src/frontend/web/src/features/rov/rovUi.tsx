import { ACTIVE_ROV, type Rov } from '../../api/types';
import type { Tone } from '../../lib/states';
import { num } from '../../lib/format';
import { Chip } from '../../ui/primitives';

/** A unit belongs on the missions board while it has a mission, including when it is stopped mid-mission. */
export function isOnMission(r: Pick<Rov, 'status' | 'mission_reference_id'>) {
  return ACTIVE_ROV.includes(r.status) || (r.status === 'stopped' && !!r.mission_reference_id);
}

const STATUS_TONE: Record<string, Tone> = {
  idle: 'muted', deploying: 'info', on_mission: 'accent', returning: 'info', stopped: 'warning', manual: 'accent',
};
const STATUS_LABEL: Record<string, string> = {
  idle: 'Idle', deploying: 'Deploying', on_mission: 'On mission', returning: 'Returning', stopped: 'Stopped', manual: 'Manual',
};

export function RovStatusChip({ status }: { status: Rov['status'] }) {
  return <Chip tone={STATUS_TONE[status] ?? 'muted'}>{STATUS_LABEL[status] ?? status}</Chip>;
}

export function LinkChip({ link }: { link: Rov['link'] }) {
  return <Chip tone={link === 'online' ? 'ok' : link === 'simulated' ? 'info' : 'critical'} dot>{link}</Chip>;
}

/** Compass rose with the heading needle; the number is the accessible value. */
export function Compass({ deg }: { deg: number | null }) {
  const d = deg ?? 0;
  return (
    <span className="compass" role="img" aria-label={deg == null ? 'Heading unknown' : `Heading ${Math.round(d)} degrees`}>
      <svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">
        <circle cx="20" cy="20" r="18" fill="none" stroke="var(--line-strong)" />
        <text x="20" y="8" textAnchor="middle" fontSize="6" fill="var(--fg-3)" fontFamily="var(--font-mono)">N</text>
        <g transform={`rotate(${d} 20 20)`} style={{ transition: 'transform var(--t-ui) var(--ease)' }}>
          <path d="M20 7 L23.5 21 L20 19 L16.5 21 Z" fill="var(--accent)" />
          <path d="M20 33 L22 21 L20 22 L18 21 Z" fill="var(--fg-3)" />
        </g>
      </svg>
      <span className="mono">{deg == null ? '—' : `${num(d, 0).padStart(3, '0')}°`}</span>
    </span>
  );
}
