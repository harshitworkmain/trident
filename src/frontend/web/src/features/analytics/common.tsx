import { useEffect, type ReactNode } from 'react';
import { hhmm } from '../../lib/format';
import type { Tone } from '../../lib/states';

/** Where a panel's numbers come from and when; shown on every analytics panel. */
export function Provenance({ source, at }: { source: ReactNode; at?: string | null }) {
  return <span className="prov mono">{source}{at ? ` · ${hhmm(at)}` : ''}</span>;
}

export function HBars({ items, tone = 'accent', format = (n: number) => String(n), max }: {
  items: { key: string; label: ReactNode; value: number; tone?: Tone }[]; tone?: Tone; format?: (n: number) => string; max?: number;
}) {
  const top = max ?? Math.max(1, ...items.map((i) => i.value));
  return (
    <ul className="hbars">
      {items.map((i) => (
        <li key={i.key}>
          <span className="hbar-label">{i.label}</span>
          <span className={`hbar meter--${i.tone ?? tone}`} aria-hidden="true"><span style={{ width: `${Math.min(100, (i.value / top) * 100)}%` }} /></span>
          <span className="hbar-val mono">{format(i.value)}</span>
        </li>
      ))}
    </ul>
  );
}

/** Refresh a REST report periodically; the report itself is server-computed, nothing is synthesised here. */
export function useInterval(fn: () => void, ms: number) {
  useEffect(() => {
    const id = window.setInterval(fn, ms);
    return () => window.clearInterval(id);
  }, [fn, ms]);
}
