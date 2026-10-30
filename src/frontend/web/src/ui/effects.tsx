import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { prefersReducedMotion } from '../lib/motion';

const GLYPHS = 'ABCDEFGHJKLMNPQRSTUVWXYZ0123456789';

/**
 * "Decode" settle: when `text` changes, characters resolve left to right from random glyphs
 * over ~360 ms. Used on reference ids and device state names. Screen readers get the final
 * text only (a visually hidden copy while it animates), never the noise.
 */
export function ScrambleText({ text, className, duration = 360, onMount = false }: {
  text: string; className?: string; duration?: number; onMount?: boolean;
}) {
  const [shown, setShown] = useState(text);
  const [active, setActive] = useState(false);
  const prev = useRef<string | null>(onMount ? '' : text);
  useEffect(() => {
    if (prev.current === text) return;
    prev.current = text;
    if (prefersReducedMotion()) { setShown(text); return; }
    let raf = 0;
    const start = performance.now();
    setActive(true);
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / duration);
      const settled = Math.floor(p * text.length);
      let out = '';
      for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        out += i < settled || ch === ' ' || ch === '-' || ch === '_' ? ch : GLYPHS[(Math.random() * GLYPHS.length) | 0];
      }
      setShown(out);
      if (p < 1) raf = requestAnimationFrame(tick);
      else { setShown(text); setActive(false); }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [text, duration]);
  return (
    <span className={`scramble ${className ?? ''}`} data-active={active}>
      {/* aria-label is not allowed on a role-less span: settled text is plain; mid-animation the noise is hidden. */}
      {active ? <><span aria-hidden="true">{shown}</span><span className="sr-only">{text}</span></> : shown}
    </span>
  );
}

/** Count-up for KPI changes: eases from the previous value over 350 ms and flashes the accent once. */
export function CountUp({ value, digits = 0, className }: { value: number | null | undefined; digits?: number; className?: string }) {
  const [display, setDisplay] = useState(value ?? null);
  const [flash, setFlash] = useState(0);
  const from = useRef(value ?? null);
  useEffect(() => {
    if (value === null || value === undefined) { setDisplay(null); from.current = null; return; }
    const start = from.current;
    from.current = value;
    if (start === null || start === value || prefersReducedMotion()) { setDisplay(value); return; }
    setFlash((f) => f + 1);
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / 350);
      const e = 1 - (1 - p) ** 3;
      setDisplay(start + (value - start) * e);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return (
    <span key={flash} className={`num ${flash ? 'count-flash' : ''} ${className ?? ''}`}>
      {display === null ? '—' : display.toFixed(digits)}
    </span>
  );
}

/** Line-by-line masked reveal for the landing headline (pure CSS; disabled under reduced motion). */
export function RevealLines({ lines, as: Tag = 'h1', className }: { lines: string[]; as?: 'h1' | 'h2'; className?: string }) {
  return (
    <Tag className={`reveal ${className ?? ''}`} aria-label={lines.join(' ')}>
      {lines.map((l, i) => (
        <span key={i} className="reveal-line" aria-hidden="true">
          <span style={{ '--i': i } as CSSProperties}>{l}</span>
        </span>
      ))}
    </Tag>
  );
}
