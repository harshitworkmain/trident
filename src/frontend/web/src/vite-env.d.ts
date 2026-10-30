/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** '1' enables the in-app mock backend (see src/mock). */
  readonly VITE_MOCK?: string;
  /** Leaflet tile URL template; defaults to darkened OpenStreetMap tiles. */
  readonly VITE_MAP_TILE_URL?: string;
  readonly VITE_MAP_TILE_ATTRIBUTION?: string;
  /** '1' applies the dark CSS filter to a custom (light) tile source. */
  readonly VITE_MAP_TILE_DARKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
