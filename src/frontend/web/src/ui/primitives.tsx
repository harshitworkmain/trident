import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { AlertTriangle, Inbox, RefreshCw, WifiOff } from 'lucide-react';
import type { AlertLevel, HealthState, SosStatus } from '../api/types';
import { ApiError } from '../api/client';
import { levelTone, priorityTone, SOS_LABEL, sosTone, stateLabel, type Tone } from '../lib/states';
import { batteryPct, num } from '../lib/format';
import { ScrambleText } from './effects';

// ─── Button ──────────────────────────────────────────────────────────────────

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'default' | 'primary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  icon?: ReactNode;
  block?: boolean;
  iconOnly?: boolean;
  busy?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, BtnProps>(function Button(
  { variant = 'default', size = 'md', icon, block, iconOnly, busy, className, children, type = 'button', disabled, ...rest },
  ref,
) {
  const cls = ['btn', variant !== 'default' && `btn--${variant}`, size !== 'md' && `btn--${size}`, block && 'btn--block', iconOnly && 'btn--icon', className]
    .filter(Boolean).join(' ');
  return (
    <button ref={ref} type={type} className={cls} disabled={disabled || busy} aria-busy={busy || undefined} {...rest}>
      {icon}
      {children}
    </button>
  );
});

// ─── Chips ───────────────────────────────────────────────────────────────────

export function Chip({ tone = 'muted', children, dot, size, sweep, title }: {
  tone?: Tone; children: ReactNode; dot?: boolean; size?: 'lg'; sweep?: boolean; title?: string;
}) {
  return (
    <span className={`chip chip--${tone} ${size ? 'chip--lg' : ''} ${sweep ? 'chip--sweep' : ''}`} title={title}>
      {dot && <span className="chip-dot" aria-hidden="true" />}
      {children}
    </span>
  );
}

/** Wearable fusion state; critical states get the sweep, every change decodes in. */
export function StateChip({ state, level, size }: { state: HealthState; level: AlertLevel; size?: 'lg' }) {
  return (
    <Chip tone={levelTone(level)} dot sweep={level === 'critical'} size={size} title={`Alert level: ${level}`}>
      <ScrambleText text={stateLabel(state).toUpperCase()} className="chip-text" />
    </Chip>
  );
}

export function StatusChip({ status }: { status: SosStatus }) {
  return <Chip tone={sosTone(status)}>{SOS_LABEL[status] ?? status}</Chip>;
}

export function Priority({ p }: { p: number }) {
  return (
    <span className={`prio prio--${p}`} title={`Priority ${p} of 5 (1 is most urgent)`} aria-label={`Priority ${p}`} data-tone={priorityTone(p)}>
      {p}
    </span>
  );
}

// ─── Panel ───────────────────────────────────────────────────────────────────

export function Panel({ title, count, actions, children, className, bodyClass = '', id, footer, as: Tag = 'section' }: {
  title?: ReactNode; count?: number | string; actions?: ReactNode; children: ReactNode; className?: string;
  bodyClass?: string; id?: string; footer?: ReactNode; as?: 'section' | 'div' | 'aside';
}) {
  const headingId = id ? `${id}-title` : undefined;
  return (
    <Tag className={`panel ${className ?? ''}`} aria-labelledby={headingId} id={id}>
      {(title || actions) && (
        <header className="panel-head">
          {title && (
            <h2 className="panel-title" id={headingId}>
              {title}
              {count !== undefined && <span className="count">{count}</span>}
            </h2>
          )}
          {actions && <div className="panel-actions">{actions}</div>}
        </header>
      )}
      <div className={`panel-body ${bodyClass}`}>{children}</div>
      {footer && <footer className="panel-foot">{footer}</footer>}
    </Tag>
  );
}

// ─── Stat ────────────────────────────────────────────────────────────────────

export function Stat({ label, value, unit, sub, tone }: {
  label: string; value: ReactNode; unit?: string; sub?: ReactNode; tone?: 'critical' | 'warning';
}) {
  return (
    <div className={`stat ${tone ? `stat--${tone}` : ''}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}
        {unit && <span className="stat-unit">{unit}</span>}
      </div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

// ─── Loading / empty / error ─────────────────────────────────────────────────

export function Skeleton({ rows = 4, widths }: { rows?: number; widths?: string[] }) {
  return (
    <div className="skeleton-rows" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <span key={i} className="skeleton" style={{ width: widths?.[i % widths.length] ?? `${90 - ((i * 17) % 40)}%` }} />
      ))}
    </div>
  );
}

export function Empty({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="state-block" role="status">
      {icon ?? <Inbox aria-hidden="true" />}
      <strong>{title}</strong>
      {children}
    </div>
  );
}

export function ErrorState({ error, onRetry, title }: { error: ApiError | Error | null | string; onRetry?: () => void; title?: string }) {
  const e = typeof error === 'string' ? null : error;
  const isNetwork = e instanceof ApiError && e.status === 0;
  const msg = typeof error === 'string' ? error : error?.message ?? 'Something went wrong.';
  return (
    <div className="state-block state-block--error" role="alert">
      {isNetwork ? <WifiOff aria-hidden="true" /> : <AlertTriangle aria-hidden="true" />}
      <strong>{title ?? (isNetwork ? 'Server unreachable' : 'Could not load')}</strong>
      <span>{msg}</span>
      {e instanceof ApiError && e.requestId && <span className="mono">request {e.requestId}</span>}
      {onRetry && <Button size="sm" icon={<RefreshCw />} onClick={onRetry}>Retry</Button>}
    </div>
  );
}

// ─── Small indicators ────────────────────────────────────────────────────────

export function Battery({ volts }: { volts: number | null | undefined }) {
  const p = batteryPct(volts);
  if (p === null) return <span className="battery muted">—</span>;
  return (
    <span className={`battery ${p < 20 ? 'battery--low' : ''}`} title={`${num(volts, 2)} V`}>
      <span className="battery-cell" aria-hidden="true"><span style={{ width: `${p}%` }} /></span>
      {p}%
    </span>
  );
}

export function Meter({ value, max = 1, tone = 'accent', label }: { value: number | null | undefined; max?: number; tone?: Tone; label: string }) {
  const v = value === null || value === undefined || !Number.isFinite(value) ? 0 : Math.max(0, Math.min(1, value / max));
  return (
    <div className={`meter meter--${tone}`} role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value ?? undefined}>
      <span style={{ width: `${v * 100}%` }} />
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="kbd">{children}</kbd>;
}
