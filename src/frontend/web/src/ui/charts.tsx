import { useEffect, useMemo, useRef } from 'react';
import uPlot, { type AlignedData, type Options } from 'uplot';
import 'uplot/dist/uPlot.min.css';

/** Reads design tokens at runtime so charts follow the theme without duplicating hex values. */
export function token(name: string, fallback = '#888') {
  if (typeof window === 'undefined') return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

export function alpha(hex: string, a: number) {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

function axis(extra: Partial<uPlot.Axis> = {}): uPlot.Axis {
  return {
    stroke: token('--fg-3'),
    grid: { stroke: token('--line'), width: 1 },
    ticks: { stroke: token('--line'), width: 1, size: 4 },
    font: `11px ${token('--font-mono', 'monospace')}`,
    gap: 4,
    size: 40,
    ...extra,
  };
}

/** Thin React wrapper: creates the plot once per `options` identity, pushes data updates via setData. */
export function UPlot({ options, data, height = 160, label }: {
  options: Omit<Options, 'width' | 'height'>; data: AlignedData; height?: number; label: string;
}) {
  const el = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);
  const dataRef = useRef(data);
  dataRef.current = data;

  useEffect(() => {
    const node = el.current;
    if (!node) return;
    const p = new uPlot({ ...options, width: Math.max(200, node.clientWidth), height }, dataRef.current, node);
    plot.current = p;
    const ro = new ResizeObserver(() => p.setSize({ width: Math.max(200, node.clientWidth), height }));
    ro.observe(node);
    return () => { ro.disconnect(); p.destroy(); plot.current = null; };
  }, [options, height]);

  useEffect(() => { plot.current?.setData(data); }, [data]);

  return <div ref={el} className="uplot-host" role="img" aria-label={label} />;
}

const timeFmt = (_u: uPlot, splits: number[]) => splits.map((s) => {
  const d = new Date(s * 1000);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
});

/** Live single-series line (wearable vitals). */
export function useLineOptions(name: string, unit: string, color: string, range?: [number, number]) {
  return useMemo<Omit<Options, 'width' | 'height'>>(() => ({
    legend: { show: false },
    cursor: { y: false, points: { size: 6 } },
    scales: { x: { time: true }, y: range ? { range } : { auto: true } },
    axes: [axis({ values: timeFmt, size: 28 }), axis({ size: 44, values: (_u, s) => s.map((v) => `${v}`) })],
    series: [{}, { label: `${name} (${unit})`, stroke: color, width: 1.5, points: { show: false }, spanGaps: false }],
  }), [name, unit, color, range?.[0], range?.[1]]); // eslint-disable-line react-hooks/exhaustive-deps
}

/** p10–p90 band + p50 line (weather forecast). Data order: x, p10, p50, p90. */
export function useBandOptions(name: string, unit: string, color: string, bars = false) {
  return useMemo<Omit<Options, 'width' | 'height'>>(() => ({
    legend: { show: false },
    cursor: { y: false },
    scales: { x: { time: true }, y: { auto: true } },
    axes: [
      axis({ values: (_u, splits) => splits.map((s) => { const d = new Date(s * 1000); return d.getHours() === 0 ? d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : `${String(d.getHours()).padStart(2, '0')}h`; }), size: 28 }),
      axis({ size: 44 }),
    ],
    series: [
      {},
      { label: 'p10', stroke: alpha(color, 0.35), width: 1, points: { show: false } },
      bars
        ? { label: `p50 ${unit}`, stroke: color, fill: alpha(color, 0.55), width: 0, paths: uPlot.paths.bars!({ size: [0.7, 12] }), points: { show: false } }
        : { label: `p50 ${unit}`, stroke: color, width: 2, points: { show: false } },
      { label: 'p90', stroke: alpha(color, 0.35), width: 1, points: { show: false } },
    ],
    bands: [{ series: [3, 1], fill: alpha(color, 0.16) }],
  }), [name, unit, color, bars]);
}

const dateFmt = (_u: uPlot, splits: number[]) => splits.map((s) => new Date(s * 1000).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }));

/** Generic multi-series line for analytics. */
export function useSeriesOptions(names: string[], colors: string[], bars = false, byDay = false) {
  return useMemo<Omit<Options, 'width' | 'height'>>(() => ({
    legend: { show: false },
    cursor: { y: false },
    scales: { x: { time: true }, y: { auto: true, range: (_u, _min, max) => [0, Math.max(1, max * 1.1)] } },
    axes: [axis({ size: 28, values: byDay ? dateFmt : timeFmt }), axis({ size: 36 })],
    series: [{}, ...names.map((n, i) => ({
      label: n, stroke: colors[i], width: bars ? 0 : 1.75, points: { show: false },
      ...(bars ? { fill: alpha(colors[i] ?? '#888', 0.7), paths: uPlot.paths.bars!({ size: [0.6, 18] }) } : {}),
    }))],
  }), [names.join('|'), colors.join('|'), bars, byDay]); // eslint-disable-line react-hooks/exhaustive-deps
}

/** SVG sparkline for the dense device grid: much cheaper than a uPlot instance per cell. */
export function Sparkline({ values, color, label, min, max }: { values: (number | null)[]; color: string; label: string; min?: number; max?: number }) {
  const pts = values.map((v, i) => [i, v] as const).filter((p): p is readonly [number, number] => p[1] !== null && Number.isFinite(p[1]));
  if (pts.length < 2) return <svg className="spark" role="img" aria-label={`${label}: no data`} />;
  const ys = pts.map((p) => p[1]);
  const lo = min ?? Math.min(...ys);
  const hi = max ?? Math.max(...ys);
  const span = hi - lo || 1;
  const n = Math.max(values.length - 1, 1);
  const d = pts.map(([i, v], k) => `${k ? 'L' : 'M'}${((i / n) * 100).toFixed(2)},${(26 - ((v - lo) / span) * 24).toFixed(2)}`).join('');
  return (
    <svg className="spark" viewBox="0 0 100 28" preserveAspectRatio="none" role="img" aria-label={`${label}: latest ${ys[ys.length - 1].toFixed(1)}`}>
      <path d={d} stroke={color} />
    </svg>
  );
}
