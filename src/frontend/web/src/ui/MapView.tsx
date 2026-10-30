import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export type MarkerKind = 'sos' | 'device' | 'team' | 'rov' | 'river' | 'cell';

export interface MapMarker {
  id: string;
  kind: MarkerKind;
  lat: number;
  lng: number;
  tone: 'critical' | 'warning' | 'ok' | 'info' | 'muted' | 'accent';
  label: string;
  /** Bigger and drawn on top (e.g. P1 SOS, critical device). */
  emphasis?: boolean;
  href?: string;
  /** Pixel size override (density cells). */
  size?: number;
}

const CHENNAI: L.LatLngTuple = [13.04, 80.22];

// Default basemap: Stadia Maps "alidade_smooth_dark" (already dark; Stadia serves localhost without a key, a
// deployed domain must be registered with Stadia). VITE_MAP_TILE_URL overrides it, e.g. keyed CARTO dark_all:
// https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?api_key=...
// If the primary source keeps failing we fall back to OpenStreetMap's standard tiles darkened with a CSS
// filter (fine for a small control room; heavy use should stay on a proper provider per the OSM tile policy).
// Leaflet fills {r} with "@2x" on high-DPI screens.
interface TileSource { url: string; attribution: string; darken: boolean }
const env = import.meta.env;
const OSM: TileSource = {
  url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  darken: true,
};
const STADIA_DARK: TileSource = {
  url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png',
  attribution: '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  darken: false,
};
const PRIMARY: TileSource = env.VITE_MAP_TILE_URL
  ? {
    url: env.VITE_MAP_TILE_URL,
    attribution: env.VITE_MAP_TILE_ATTRIBUTION
      || (env.VITE_MAP_TILE_URL.includes('carto') ? `${OSM.attribution} &copy; <a href="https://carto.com/attributions">CARTO</a>` : OSM.attribution),
    darken: env.VITE_MAP_TILE_DARKEN === '1',
  }
  : STADIA_DARK;
/** Tried in order; the next one takes over after TILE_FAILS errors in a row. */
const TILE_SOURCES: TileSource[] = PRIMARY.url === OSM.url ? [{ ...PRIMARY, darken: true }] : [PRIMARY, OSM];
/** Consecutive tile failures before we say the basemap is unavailable (one bad tile is noise). */
const TILE_FAILS = 3;

const toneVar: Record<MapMarker['tone'], string> = {
  critical: '--critical', warning: '--warning', ok: '--ok', info: '--info', muted: '--fg-3', accent: '--accent',
};

function color(tone: MapMarker['tone']) {
  return getComputedStyle(document.documentElement).getPropertyValue(toneVar[tone]).trim() || '#999';
}

function icon(m: MapMarker) {
  const c = color(m.tone);
  const size = m.size ?? (m.emphasis ? 16 : 12);
  if (m.kind === 'cell') {
    const html = `<svg width="${size}" height="${size}" viewBox="0 0 12 12"><circle cx="6" cy="6" r="5.5" fill="${c}" fill-opacity="0.28" stroke="${c}" stroke-width="0.6"/></svg>`;
    return L.divIcon({ html, className: 'map-mk map-mk--cell', iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
  }
  if (m.kind === 'river') {
    const html = `<svg width="16" height="16" viewBox="0 0 12 12"><path d="M6 1 L11 10 L1 10 Z" fill="${c}" stroke="#0d0e10" stroke-width="1.2"/></svg>`;
    return L.divIcon({ html, className: 'map-mk map-mk--river', iconSize: [16, 16], iconAnchor: [8, 8] });
  }
  const shape = m.kind === 'sos'
    ? `<svg width="${size}" height="${size}" viewBox="0 0 12 12"><circle cx="6" cy="6" r="5" fill="${c}" stroke="#0d0e10" stroke-width="1.5"/></svg>`
    : m.kind === 'device'
      ? `<svg width="${size}" height="${size}" viewBox="0 0 12 12"><circle cx="6" cy="6" r="4.5" fill="#0d0e10" stroke="${c}" stroke-width="2.2"/></svg>`
      : m.kind === 'team'
        ? `<svg width="${size}" height="${size}" viewBox="0 0 12 12"><rect x="1.5" y="1.5" width="9" height="9" fill="${c}" stroke="#0d0e10" stroke-width="1.5"/></svg>`
        : `<svg width="${size + 2}" height="${size + 2}" viewBox="0 0 12 12"><path d="M6 1 L11 6 L6 11 L1 6 Z" fill="${c}" stroke="#0d0e10" stroke-width="1.2"/></svg>`;
  return L.divIcon({ html: shape, className: `map-mk map-mk--${m.kind}${m.emphasis ? ' map-mk--hot' : ''}`, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
}

/**
 * Leaflet renders string tooltip content as innerHTML, and labels carry public input (the SOS
 * caller's name, addresses), so they always go in as a text node.
 */
function tipContent(label: string): HTMLElement {
  const span = document.createElement('span');
  span.textContent = label;
  return span;
}

/** Leaflet on a dark basemap (see TILE_SOURCES). Markers are diffed by id so live updates do not rebuild the layer. */
export interface MapTrack {
  id: string;
  points: [number, number][];
  tone: MapMarker['tone'];
  dashed?: boolean;
}

export function MapView({ markers, tracks = [], onSelect, label = 'Map', fitKey, follow }: {
  markers: MapMarker[]; tracks?: MapTrack[]; onSelect?: (m: MapMarker) => void; label?: string; fitKey?: string;
  /** Keep this marker id in view (pans only when it leaves the inner area). */
  follow?: string;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const live = useRef(new Map<string, { mk: L.Marker; sig: string }>());
  const lines = useRef(new Map<string, L.Polyline>());
  const fitted = useRef<string | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const [tilesDown, setTilesDown] = useState(false);

  useEffect(() => {
    if (!el.current) return;
    const m = L.map(el.current, { center: CHENNAI, zoom: 11, zoomControl: true, attributionControl: true, preferCanvas: true });
    // Without internet the basemap fails but markers (our own data) still render: fall back, then say so quietly.
    let fails = 0;
    let tiles: L.TileLayer | null = null;
    const showSource = (i: number) => {
      const src = TILE_SOURCES[i];
      if (tiles) m.removeLayer(tiles);
      fails = 0;
      tiles = L.tileLayer(src.url, {
        attribution: src.attribution, subdomains: 'abcd', maxZoom: 19, className: src.darken ? 'tiles-darken' : undefined,
      })
        .on('tileerror', () => {
          fails += 1;
          if (fails < TILE_FAILS) return;
          if (i + 1 < TILE_SOURCES.length) showSource(i + 1);
          else setTilesDown(true);
        })
        .on('tileload', () => { fails = 0; setTilesDown(false); })
        .addTo(m);
      tiles.bringToBack();
    };
    showSource(0);
    layer.current = L.layerGroup().addTo(m);
    map.current = m;
    const ro = new ResizeObserver(() => m.invalidateSize());
    ro.observe(el.current);
    const store = live.current;
    const ls = lines.current;
    return () => { ro.disconnect(); m.remove(); map.current = null; store.clear(); ls.clear(); };
  }, []);

  useEffect(() => {
    const lg = layer.current;
    if (!lg) return;
    const seen = new Set<string>();
    for (const m of markers) {
      const key = `${m.kind}:${m.id}`;
      seen.add(key);
      const sig = `${m.tone}|${m.emphasis ? 1 : 0}|${m.size ?? 0}|${m.label}`;
      const cur = live.current.get(key);
      if (cur) {
        cur.mk.setLatLng([m.lat, m.lng]);
        if (cur.sig !== sig) { cur.mk.setIcon(icon(m)); cur.mk.setTooltipContent(tipContent(m.label)); cur.mk.setZIndexOffset(m.emphasis ? 1000 : 0); cur.sig = sig; }
      } else {
        const mk = L.marker([m.lat, m.lng], { icon: icon(m), keyboard: true, title: m.label, alt: m.label, zIndexOffset: m.emphasis ? 1000 : 0 })
          .bindTooltip(tipContent(m.label), { direction: 'top', offset: [0, -8], className: 'map-tip' })
          .on('click', () => onSelectRef.current?.(m))
          .on('keypress', (e: L.LeafletKeyboardEvent) => { if (e.originalEvent.key === 'Enter') onSelectRef.current?.(m); });
        mk.addTo(lg);
        live.current.set(key, { mk, sig });
      }
    }
    for (const [k, v] of live.current) if (!seen.has(k)) { lg.removeLayer(v.mk); live.current.delete(k); }

    if (map.current && markers.length && fitted.current !== (fitKey ?? 'once')) {
      fitted.current = fitKey ?? 'once';
      const b = L.latLngBounds(markers.map((m) => [m.lat, m.lng] as L.LatLngTuple));
      map.current.fitBounds(b.pad(0.15), { maxZoom: 14, animate: false });
    }
  }, [markers, fitKey]);

  useEffect(() => {
    const lg = layer.current;
    if (!lg) return;
    const seen = new Set<string>();
    for (const t of tracks) {
      seen.add(t.id);
      const cur = lines.current.get(t.id);
      if (cur) cur.setLatLngs(t.points);
      else {
        const pl = L.polyline(t.points, { color: color(t.tone), weight: 2, opacity: 0.8, dashArray: t.dashed ? '4 6' : undefined, interactive: false });
        pl.addTo(lg);
        lines.current.set(t.id, pl);
      }
    }
    for (const [k, v] of lines.current) if (!seen.has(k)) { lg.removeLayer(v); lines.current.delete(k); }
  }, [tracks]);

  useEffect(() => {
    if (!follow || !map.current) return;
    const m = markers.find((x) => `${x.kind}:${x.id}` === follow || x.id === follow);
    if (!m) return;
    const inner = map.current.getBounds().pad(-0.2);
    if (!inner.contains([m.lat, m.lng])) map.current.panTo([m.lat, m.lng], { animate: false });
  }, [markers, follow]);

  return (
    <div className="map-wrap">
      <div ref={el} className="map" role="region" aria-label={label} />
      {tilesDown && <p className="map-note" role="status">Map tiles unavailable offline — positions still shown</p>}
    </div>
  );
}

export function MapLegend() {
  return (
    <ul className="map-legend" aria-label="Map legend">
      <li><svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="5" fill="var(--critical)" /></svg>SOS</li>
      <li><svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="4.5" fill="none" stroke="var(--ok)" strokeWidth="2.2" /></svg>Wearable</li>
      <li><svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true"><rect x="1.5" y="1.5" width="9" height="9" fill="var(--info)" /></svg>Team</li>
      <li><svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true"><path d="M6 1 L11 6 L6 11 L1 6 Z" fill="var(--accent)" /></svg>ROV</li>
    </ul>
  );
}
