import { Link } from 'react-router-dom';
import { waitingMinutes } from '../../api/live';
import type { SosRecord } from '../../api/types';
import { isUnassigned, SOURCE_LABEL, WAIT_WARN_MIN, waitingTone } from '../../lib/states';
import { Chip } from '../../ui/primitives';

/** "waiting 25 min" in priority_reasons duplicates the waiting chip; callers may hide it. */
export const isWaitingReason = (reason: string) => /^waiting \d+(\.\d+)? ?min/i.test(reason);

/** Capacity-related flags: source (non-web), possible duplicate, waiting time, awaiting resources. */
export function SosFlags({ r, now, size }: { r: SosRecord; now: number; size?: 'lg' }) {
  const wait = waitingMinutes(r, now);
  const source = r.source && r.source !== 'web' ? r.source : null;
  const awaiting = !!r.awaiting_resources && isUnassigned(r);
  if (!source && !r.duplicate_of && (wait === null || wait < 1) && !awaiting) return null;
  return (
    <span className="sos-flags">
      {source && <Chip tone="info" size={size} title={source === 'wearable' ? 'Raised from a wearable band (SOS button or health alert)' : `Received by ${SOURCE_LABEL[source] ?? source}`}>{SOURCE_LABEL[source] ?? source}</Chip>}
      {awaiting && <Chip tone="warning" size={size} title="Urgent and unassigned because no team has free capacity">Awaiting resources</Chip>}
      {wait !== null && wait >= 1 && (
        <Chip tone={waitingTone(r.priority, wait)} size={size}
          title={`Unassigned for ${wait} min${r.priority <= 2 ? ` (warning after ${WAIT_WARN_MIN} min for P1/P2)` : ''}`}>
          waiting <span className="mono">{wait}</span> min
        </Chip>
      )}
      {r.duplicate_of && (
        <Link to={`/sos/${encodeURIComponent(r.duplicate_of)}`} onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}
          title="Same phone, or within about 100 m of an earlier open request">
          <Chip tone="muted" size={size}>possible duplicate of <span className="mono">{r.duplicate_of}</span></Chip>
        </Link>
      )}
    </span>
  );
}
