import { useCallback, useEffect, useRef, useState } from 'react';
import { ScanFace, UserRound, VideoOff } from 'lucide-react';
import { api } from '../../api/client';
import type { Rov, RovVision, VisionObject } from '../../api/types';
import { ago, num, pct } from '../../lib/format';
import { Chip } from '../../ui/primitives';

const APPROX = 'pinhole estimate, ±30 %';
/** No new frame for this long and the feed is shown as stalled. */
const STALL_MS = 5_000;
/** The server ends a stream after 30 s without frames; a longer gap means ours was closed. */
const GAP_RECONNECT_MS = 25_000;

export function visionActive(v: RovVision | undefined): v is RovVision & { active: true } {
  return v?.active === true;
}

export function personsSeen(rov: Rov) {
  return visionActive(rov.vision) ? rov.vision.persons ?? 0 : 0;
}

/** "~2.1 m" with the estimate caveat as a tooltip; "—" when the worker could not range it. */
export function Distance({ m }: { m: number | null | undefined }) {
  if (m == null || !Number.isFinite(m)) return <span className="muted" title="No distance estimate">—</span>;
  return <span className="mono" title={APPROX}>~{num(m, m < 10 ? 1 : 0)} m</span>;
}

/**
 * The annotated MJPEG stream from the vision worker. Every connection uses a fresh single-use ticket
 * (POST /rov/{id}/vision/ticket); on an <img> error, a resumed feed or active going false→true it
 * fetches a new one, with backoff. A ticket URL is never reused.
 */
export function VisionStream({ rov, now, compact }: { rov: Rov; now: number; compact?: boolean }) {
  const v = rov.vision;
  const active = visionActive(v);
  const [src, setSrc] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [epoch, setEpoch] = useState(0);
  const attempts = useRef(0);
  const timer = useRef<number>();
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; window.clearTimeout(timer.current); };
  }, []);

  const reconnect = useCallback((immediate = false) => {
    window.clearTimeout(timer.current);
    setSrc(null);
    setRetrying(true);
    const delay = immediate ? 0 : Math.min(15_000, 1000 * 2 ** attempts.current) + Math.random() * 400;
    attempts.current = immediate ? 0 : attempts.current + 1;
    timer.current = window.setTimeout(() => { if (alive.current) setEpoch((e) => e + 1); }, delay);
  }, []);

  useEffect(() => {
    if (!active) {
      window.clearTimeout(timer.current);
      setSrc(null);
      setRetrying(false);
      attempts.current = 0;
      return;
    }
    let cancelled = false;
    api.rovVisionTicket(rov.id)
      .then((t) => { if (!cancelled) setSrc(t.url); })
      .catch(() => { if (!cancelled) reconnect(); });
    return () => { cancelled = true; };
  }, [rov.id, active, epoch, reconnect]);

  // Frames resumed after a pause long enough for the server to have closed our stream: reconnect.
  const lastFrame = active ? Date.parse(v.last_frame_at ?? '') : NaN;
  const prevFrame = useRef<number>(NaN);
  useEffect(() => {
    if (!Number.isFinite(lastFrame)) return;
    if (Number.isFinite(prevFrame.current) && lastFrame - prevFrame.current > GAP_RECONNECT_MS) reconnect(true);
    prevFrame.current = lastFrame;
  }, [lastFrame, reconnect]);

  if (!active) return <NoFeed rov={rov} compact={compact} />;

  const stalled = Number.isFinite(lastFrame) && now - lastFrame > STALL_MS;
  return (
    <div className={`camera vision-cam ${compact ? 'vision-cam--sm' : ''}`}>
      {src ? (
        <img key={src} src={src} alt={`Live camera with detections, ${rov.name}`}
          onLoad={() => { attempts.current = 0; setRetrying(false); }}
          onError={() => reconnect()} />
      ) : <span className="vision-wait mono">{retrying ? 'Reconnecting…' : 'Connecting…'}</span>}
      <div className="vision-strip mono" aria-label="Feed status">
        <span className={`vision-live ${stalled ? 'is-stalled' : ''}`}><span className="dot" aria-hidden="true" />{stalled ? 'STALLED' : 'LIVE'}</span>
        <span>{v.model ?? 'vision'}</span>
        <span>{num(v.fps, 1)} fps</span>
        {stalled && <span>last frame {ago(v.last_frame_at, now)} ago</span>}
      </div>
    </div>
  );
}

function NoFeed({ rov, compact }: { rov: Rov; compact?: boolean }) {
  return (
    <div className={`camera camera--none ${compact ? 'vision-cam--sm' : ''}`} role="img" aria-label={`No camera feed, ${rov.name}`}>
      <VideoOff aria-hidden="true" />
      <span>No camera feed</span>
      {!compact && <small className="mono camera-hint">Start the vision worker: python -m src.cv.vision --key … --source &lt;camera&gt;</small>}
    </div>
  );
}

const byDistance = (a: VisionObject, b: VisionObject) => (a.distance_m ?? Infinity) - (b.distance_m ?? Infinity);

/** Persons count (the number that matters in a rescue), recognised faces and the nearest objects. */
export function VisionDetections({ vision }: { vision: RovVision }) {
  const persons = vision.persons ?? 0;
  const faces = vision.faces ?? [];
  const objects = [...(vision.objects ?? [])].sort(byDistance).slice(0, 6);
  return (
    <div className="vision-det" aria-label="Detections">
      <div className={`vision-persons ${persons > 0 ? 'is-on' : ''}`}>
        <UserRound aria-hidden="true" />
        <span className="vision-persons-n mono">{persons}</span>
        <span>{persons === 1 ? 'person in view' : 'persons in view'}</span>
      </div>

      <div>
        <h4 className="sub-h">Faces</h4>
        {faces.length === 0 ? <p className="muted vision-empty">No faces in view.</p> : (
          <ul className="vision-list">
            {faces.map((f, i) => {
              const known = f.name && f.name !== 'Unknown';
              return (
                <li key={`${f.name}-${i}`}>
                  <ScanFace aria-hidden="true" className={known ? 'text-ok' : 'muted'} />
                  <span className={known ? '' : 'muted'}>{known ? f.name : 'Unknown person'}</span>
                  <span className="mono muted" title="LBPH match confidence">{f.match == null ? '' : pct(f.match)}</span>
                  <Distance m={f.distance_m} />
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div>
        <h4 className="sub-h">Objects <span className="muted">nearest first</span></h4>
        {objects.length === 0 ? <p className="muted vision-empty">Nothing detected.</p> : (
          <ul className="vision-list">
            {objects.map((o, i) => (
              <li key={`${o.label}-${i}`}>
                <span className={o.label === 'person' ? 'vision-label is-person' : 'vision-label'}>{o.label}</span>
                <span className="mono muted" title="Detector confidence">{pct(o.confidence)}</span>
                <Distance m={o.distance_m} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/** Header badge on a mission / unit when the detector sees people. */
export function PersonsBadge({ rov }: { rov: Rov }) {
  const n = personsSeen(rov);
  if (n <= 0) return null;
  return <Chip tone="warning" dot title="People detected by the ROV camera">Persons seen · {n}</Chip>;
}
