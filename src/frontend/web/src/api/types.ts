// Hand-written from docs/PLATFORM_DESIGN.md §2 (the authoritative contract).
// Fields marked "assumed" are not pinned down by the contract; the UI reads them defensively.

export type Role = 'admin' | 'dispatcher' | 'responder' | 'viewer';

export interface User {
  id: number | string;
  username: string;
  display_name: string;
  role: Role;
  team_id: number | string | null;
  is_active?: boolean; // assumed (admin list)
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: User;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details?: Record<string, unknown> };
  request_id?: string;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

// ─── SOS ─────────────────────────────────────────────────────────────────────

export const SOS_STATUSES = ['pending', 'triaged', 'assigned', 'en_route', 'on_scene', 'resolved', 'cancelled'] as const;
export type SosStatus = (typeof SOS_STATUSES)[number];

export const EMERGENCY_TYPES = [
  'flood', 'tsunami', 'dam-breach', 'storm', 'water-level-rising', 'coastal-erosion', 'medical', 'other',
] as const;
export type EmergencyType = (typeof EMERGENCY_TYPES)[number];

export const SUPPLY_LEVELS = ['adequate', 'limited', 'critical', 'none'] as const;
export type SupplyLevel = (typeof SUPPLY_LEVELS)[number];

export interface Vulnerabilities {
  pregnant: boolean;
  elderly: boolean;
  children: boolean;
  disabled: boolean;
  medical: boolean;
}

export interface SosSubmit {
  name: string;
  /** Optional: null when not given (0-120 when given). */
  age: number | null;
  phone: string;
  email?: string;
  address: string;
  city: string;
  /** Optional: omitted or null when the person does not know it (3-12 chars when given). */
  pincode: string | null;
  people_to_rescue: number;
  people_injured: number;
  food_availability: SupplyLevel;
  water_availability: SupplyLevel;
  vulnerabilities: Vulnerabilities;
  emergency_type: EmergencyType;
  additional_info?: string;
  latitude?: number;
  longitude?: number;
  device_id?: string;
}

export interface SosSubmitResponse {
  reference_id: string;
  tracking_token: string;
  priority: number;
  status: SosStatus;
}

export interface TeamRef {
  id: number | string;
  name: string;
}

export interface SosRecord extends SosSubmit {
  reference_id: string;
  priority: number; // 1 (highest) .. 5
  priority_score: number; // 0..100
  priority_reasons: string[];
  status: SosStatus;
  version: number;
  assigned_team: TeamRef | null;
  created_at: string;
  updated_at: string;
  /** Capacity contract (all optional: older servers omit them). */
  source?: SosSource;
  /** Reference of an earlier open request from the same phone or within ~100 m. */
  duplicate_of?: string | null;
  /** Minutes since creation while unassigned, as of when the server produced this record. */
  waiting_min?: number | null;
  /** P1/P2 still unassigned because no team has capacity. */
  awaiting_resources?: boolean;
  /** True once staff confirmed that `device_id` belongs to this caller; a band ID typed by the public is only a claim. */
  device_verified?: boolean;
}

export type SosSource = 'web' | 'sms' | 'wearable';

/** One SOS event: a status change (kind "status"), an assignment (kind "assign", status "assigned") or a re-score ("priority"). */
export interface StatusHistoryEntry {
  id?: number | string;
  kind?: 'status' | 'assign' | 'priority' | string;
  /** null on events that do not change the status (e.g. "priority"). */
  status: SosStatus | null;
  at: string;
  /** Who did it (`actor` is the same value); "auto-dispatch" for automatic moves. */
  by?: string | null;
  actor?: string | null;
  team_id?: number | string | null;
  /** Free text, e.g. a reason, or "Auto-reallocated (extreme case) …" with the evidence. */
  text?: string | null;
  /** Older name of `text`; the server sends both. */
  note?: string | null;
}

export interface SosNote {
  id?: number | string;
  text: string;
  author?: string; // assumed
  at?: string; // assumed (also accepts created_at)
  created_at?: string;
}

export interface Assignment {
  id?: number | string;
  team_id: number | string;
  team_name?: string | null;
  assigned_at?: string | null;
  assigned_by?: string | null;
  /** Same values as assigned_at / assigned_by (the event fields). */
  at?: string | null;
  by?: string | null;
  actor?: string | null;
  text?: string | null;
}

export interface SosDetail extends SosRecord {
  history: StatusHistoryEntry[];
  notes: SosNote[];
  assignments: Assignment[];
  /** Same shape as GET /devices; null when no band is linked or the ID is not registered. */
  linked_device: DeviceSummary | null;
}

export interface SosTrack {
  reference_id: string;
  status: SosStatus;
  priority: number;
  created_at: string;
  updated_at: string;
  team_name?: string | null;
  eta_min?: number | null;
  history: { status: SosStatus; at: string }[];
}

// ─── Teams ───────────────────────────────────────────────────────────────────

export interface LatLng {
  lat: number;
  lng: number;
}

export interface Team {
  id: number | string;
  name: string;
  type?: string;
  team_type?: string;
  /** The server sends the base's name here and the coordinates in `latitude`/`longitude`; see teamLatLng(). */
  location: LatLng | string | null;
  latitude?: number | null;
  longitude?: number | null;
  capacity: number;
  current_load: number;
  is_available: boolean;
  deployment_mode: string;
}

/** A team's base on the map: `{lat, lng}` in `location`, or the flat `latitude`/`longitude` the API sends. */
export function teamLatLng(t: Pick<Team, 'location' | 'latitude' | 'longitude'>): LatLng | null {
  if (t.location && typeof t.location !== 'string') return t.location;
  if (t.latitude != null && t.longitude != null) return { lat: t.latitude, lng: t.longitude };
  return null;
}

// ─── Devices ─────────────────────────────────────────────────────────────────

export type AlertLevel = 'none' | 'advisory' | 'critical';

export const HEALTH_STATES = [
  'STABLE', 'ELEVATED_STRESS', 'HYPOTHERMIA_RISK', 'ASPIRATION_HYPOXIA', 'HEMORRHAGIC_SHOCK',
  'CONCUSSIVE_STASIS', 'CRUSH_ENTRAPMENT', 'CARDIAC_ARREST',
] as const;
/** Alert-only state: the device stopped reporting while it was in a non-STABLE state. */
export const LOST_CONTACT = 'LOST_CONTACT';
/** Alert-only state: the victim pressed the SOS button on their band. */
export const SOS_BUTTON = 'SOS_BUTTON';
export type HealthState = (typeof HEALTH_STATES)[number] | typeof LOST_CONTACT | typeof SOS_BUTTON | string;

export interface Heads {
  stress?: number | null;
  fall?: number | null;
  activity?: string | null; // 'rest' | 'light' | 'active'
  hr_trust?: number | null;
  rhythm?: number | null;
  [k: string]: number | string | null | undefined;
}

export interface DeviceState {
  ml_health_state: HealthState;
  alert_level: AlertLevel;
  risk: number;
  evidence: string[];
}

export interface DeviceSummary {
  device_id: string;
  label: string;
  online: boolean;
  last_seen: string | null;
  battery_v: number | null;
  location: LatLng | null;
  state: DeviceState;
  heads: Heads;
  boot_id?: string | null;
}

/** devices topic, event=frame: throttled to one per device per 1.5 s. */
export interface FrameSummary {
  bpm: number | null;
  spo2: number | null;
  temp_skin_c: number | null;
  eda_us: number | null;
  acc_std_g: number | null;
  battery_v: number | null;
  lat: number | null;
  lng: number | null;
  state: HealthState;
  risk: number;
  heads: Heads;
  alert_level?: AlertLevel; // assumed, derived client-side when absent
}

/** GET /devices/{id}/frames: flat schema fields + fusion output (shape of fusion assumed, see README). */
export interface FlatFrame {
  seq?: number;
  ts?: string;
  received_at?: string;
  at?: string;
  ppg_bpm?: number | null;
  ppg_spo2?: number | null;
  temp_skin_c?: number | null;
  eda_us?: number | null;
  imu_acc_std_g?: number | null;
  imu_acc_max_g?: number | null;
  power_batt_v?: number | null;
  fusion?: { ml_health_state: HealthState; ml_risk_score: number; alert_level: AlertLevel; evidence?: string[]; heads?: Heads };
  ml_health_state?: HealthState;
  ml_risk_score?: number;
  alert_level?: AlertLevel;
  [k: string]: unknown;
}

export interface StateTransition {
  state: HealthState;
  alert_level: AlertLevel;
  risk: number;
  evidence: string[];
  at: string;
}

export const DEVICE_ACTIONS = ['reset_fall', 'calibrate_gsr', 'set_geofence', 'buzz'] as const;
export type DeviceAction = (typeof DEVICE_ACTIONS)[number];

export interface DeviceCommand {
  id: string;
  action: DeviceAction;
  params: Record<string, unknown>;
  status?: 'queued' | 'delivered' | 'acked';
  created_at?: string;
}

// ─── Alerts ──────────────────────────────────────────────────────────────────

export type AlertStatus = 'open' | 'acked' | 'resolved';

export interface Alert {
  id: number | string;
  device_id: string;
  state: HealthState;
  risk: number;
  evidence: string[];
  status: AlertStatus;
  opened_at: string;
  acked_by?: string | null;
  acked_at?: string | null;
  resolved_at?: string | null;
  sos_reference_id?: string | null;
  escalated?: boolean; // assumed; set client-side on an `escalated` event
}

// ─── Weather ─────────────────────────────────────────────────────────────────

export interface WeatherCurrent {
  site: string | { name: string; lat?: number; lon?: number };
  observed_at: string;
  temp_c: number | null;
  rh: number | null;
  rain_mm: number | null;
  wind_ms: number | null;
  gust_ms?: number | null;
  pressure_hpa: number | null;
  source: 'open-meteo' | 'offline-csv' | string;
}

export interface Quantiles {
  p10: number;
  p50: number;
  p90: number;
}

export const FORECAST_VARS = ['temp_c', 'rain_mm', 'wind_ms', 'pressure_hpa', 'rh'] as const;
export type ForecastVar = (typeof FORECAST_VARS)[number];

export type ForecastStep = { time: string } & Record<ForecastVar, Quantiles>;

export type HazardType = 'heat' | 'heavy_rain' | 'flood_risk' | 'high_wind';

export interface Hazard {
  type: HazardType | string;
  level: 'watch' | 'warning';
  from: string;
  to: string;
  reason: string;
}

export interface Forecast {
  site: string | { name: string };
  generated_at: string;
  model_version: string;
  horizon: ForecastStep[];
  hazards: Hazard[];
}

/** /weather/model is loosely specified; we render known keys and fall back to a key/value dump. */
export interface ModelCard {
  model_version?: string;
  training_range?: { from: string; to: string };
  training_data?: { from: string; to: string; rows?: number; source?: string };
  candidates?: (string | { name: string; [k: string]: unknown })[];
  chosen?: Record<string, string>;
  skill?: { variable: string; horizon_h: number; model_mae: number; persistence_mae: number; skill: number }[];
  [k: string]: unknown;
}

// ─── Analytics / ROV / public ────────────────────────────────────────────────

export interface Summary {
  sos_open: number;
  sos_critical: number;
  avg_response_min: number | null;
  teams_available: number;
  devices_online: number;
  alerts_open: number;
}

export interface PublicSummary {
  teams_available: number;
  teams_total: number;
  sos_open: number;
  sos_resolved_24h: number;
  devices_online: number;
  weather: { temp_c: number | null; hazards: { type: string; level: string }[] };
  /** Number that accepts the compact SMS format (see features/public/offline.ts); null when not configured. */
  sms_number?: string | null;
  updated_at: string;
}

// ─── SMS intake (admin test) ─────────────────────────────────────────────────

export interface SmsTestRequest {
  from: string;
  text: string;
}

/** POST /sms/test: what /sms/inbound would do with this message. `parsed` keys beyond these are shown as-is. */
export interface SmsTestResponse {
  reference_id: string | null;
  priority: number | null;
  /** The text the sender would receive back. */
  reply: string;
  parsed: {
    latitude?: number | null;
    longitude?: number | null;
    people_to_rescue?: number | null;
    people_injured?: number | null;
    emergency_type?: string | null;
    note?: string | null;
    [k: string]: unknown;
  } | null;
}

// ─── Audit log (admin) ───────────────────────────────────────────────────────

/** GET /audit: newest first. */
export interface AuditEntry {
  id: number | string;
  actor: string | null;
  action: string;
  target: string | null;
  details: Record<string, unknown> | string | null;
  request_id: string | null;
  at: string;
}

/** POST /rov/{id}/bridge-key and /vision-key: the plain key, shown once. */
export interface RovKey {
  rov_id?: number | string;
  api_key: string;
}

// ─── Dispatch capacity ───────────────────────────────────────────────────────

export type CapacityStatus = 'ok' | 'strained' | 'exhausted';

export interface CapacityWaiting {
  reference_id: string;
  priority: number;
  waiting_min: number;
  emergency_type: string;
}

export interface CapacitySuggestion {
  for_reference_id: string;
  team_id: number | string;
  team_name: string;
  from_reference_id: string;
  from_priority: number;
  reason: string;
}

export interface Capacity {
  status: CapacityStatus;
  teams_free: number;
  teams_total: number;
  waiting: CapacityWaiting[];
  suggestions: CapacitySuggestion[];
  updated_at: string;
}

export interface TimePoint {
  t: string;
  value: number;
}
export type Bucket = 'minute' | 'hour' | 'day';
export type Metric = 'sos_created' | 'sos_resolved' | 'alerts' | 'telemetry_frames' | 'state_changes';
export interface TimeSeries {
  metric: string;
  bucket: Bucket;
  points: TimePoint[];
}
export interface Breakdown {
  by: string;
  items: { key: string; count: number }[];
}
export interface ResponseTimes {
  items: { priority: number; n: number; p50: number | null; p90: number | null; p95: number | null }[];
}

export type RovStatus = 'idle' | 'deploying' | 'on_mission' | 'returning' | 'stopped' | string;
/** Statuses that count as "on a mission" for /missions ('manual' kept for tolerance; it is a mode). */
export const ACTIVE_ROV: RovStatus[] = ['deploying', 'on_mission', 'returning', 'manual'];

export interface Rov {
  id: string;
  name: string;
  status: RovStatus;
  mode: 'auto' | 'manual';
  pilot: string | null;
  battery_pct: number | null;
  latitude: number | null;
  longitude: number | null;
  depth_m: number | null;
  heading_deg: number | null;
  water_temp_c: number | null;
  speed_pct: number | null;
  thrust?: number | null;
  lights_on: boolean;
  link: 'simulated' | 'online' | 'offline' | string;
  last_seen: string | null;
  target: LatLng | null;
  home: LatLng | null;
  mission_reference_id: string | null;
  team_id: number | string | null;
  video_url: string | null;
  simulated: boolean;
  /** Computer-vision feed from the worker next to the unit; `{active: false}` (or absent) when there is none. */
  vision?: RovVision;
  mission_started_at?: string | null;
  updated_at: string;
}

/** A face the LBPH recogniser matched (or not: name "Unknown"). */
export interface VisionFace {
  name: string;
  /** 0-1, null when unknown. */
  match: number | null;
  /** Pinhole estimate, roughly ±30 %. */
  distance_m: number | null;
}

/** A YOLO detection. `box` is [x1, y1, x2, y2] in frame pixels. */
export interface VisionObject {
  label: string;
  confidence: number | null;
  distance_m: number | null;
  box: [number, number, number, number] | null;
}

export interface RovVision {
  active: boolean;
  fps?: number;
  last_frame_at?: string | null;
  persons?: number;
  faces?: VisionFace[];
  objects?: VisionObject[];
  model?: string;
}

/** POST /rov/{id}/vision/ticket: single-use, valid for `expires_in` seconds. */
export interface VisionTicket {
  ticket: string;
  expires_in: number;
  url: string;
}

export type RovCommand = 'forward' | 'backward' | 'left' | 'right' | 'up' | 'down' | 'stop' | 'lights_on' | 'lights_off';

export interface RovTrackPoint {
  t: string;
  lat: number;
  lng: number;
  depth_m: number | null;
  heading_deg: number | null;
  battery_pct: number | null;
  water_temp_c: number | null;
}

export interface MissionVictim {
  reference_id: string;
  name: string;
  status: SosStatus;
  priority: number;
  device_id: string | null;
  device: DeviceSummary | null;
}

export interface Mission {
  rov: Rov;
  sos: SosRecord | null;
  team: TeamRef | null;
  victims: MissionVictim[];
}

// ─── Analytics (extended) ────────────────────────────────────────────────────

export type SensorKey = 'ppg' | 'spo2' | 'eda' | 'temp' | 'imu' | 'gps';
export interface SensorDevice {
  device_id: string;
  online: boolean;
  frames_5min: number;
  frame_rate_hz: number | null;
  battery_v: number | null;
  signal_availability: Partial<Record<SensorKey, number>>;
  state_share_24h: Record<string, number>;
  sensor_fault_share: number | null;
}
export interface SensorsReport {
  devices: SensorDevice[];
  totals: { frames_per_min: number; devices_online: number; devices_total: number };
  generated_at?: string;
}

export interface Performance {
  response_times: ResponseTimes;
  alert_ack: { n: number; p50_s: number | null; p90_s: number | null };
  team_utilization: { team_id: number | string; name: string; load: number; capacity: number; utilization: number }[];
  missions: { n: number; median_transit_min: number | null };
  generated_at?: string;
}

export interface River {
  name: string;
  lat: number;
  lng: number;
  discharge_m3s: number | null;
  discharge_p50_30d: number | null;
  trend: 'rising' | 'falling' | 'steady';
  /** Daily discharge up to today (the server asks for 30 past days). */
  history?: { date: string; discharge_m3s: number | null }[];
  /** Daily discharge after today (the server asks for 14 forecast days). */
  forecast: { date: string; discharge_m3s: number | null }[];
  source: string;
  updated_at?: string;
}

export interface GeoReport {
  sos: { reference_id: string; lat: number; lng: number; priority: number; status: SosStatus; emergency_type: string }[];
  devices: { device_id: string; lat: number; lng: number; state: HealthState; alert_level: AlertLevel }[];
  teams: { id: number | string; name: string; lat: number; lng: number; current_load?: number; capacity?: number }[];
  rovs: { id: string; name: string; lat: number; lng: number; status: RovStatus }[];
  rivers: River[];
  grid: { lat: number; lng: number; count: number }[];
  generated_at?: string;
}

export interface WearableHeadReport {
  head: string;
  model: string;
  macro_f1: number | null;
  ci95: number[] | null;
  auroc: number | null;
  threshold: number | null;
  external: Record<string, unknown> | null;
}

export interface ModelsReport {
  wearable: WearableHeadReport[];
  fusion: { version: string; false_alarms_per_8h: Record<string, number>; falls_caught: unknown; [k: string]: unknown };
  weather: ModelCard;
  rhythm_ppg_af?: Record<string, unknown> | null;
  generated_at?: string;
}

// ─── WebSocket ───────────────────────────────────────────────────────────────

export type Topic = 'sos' | 'alerts' | 'devices' | 'weather' | 'rov' | 'system';

export interface WsHello {
  type: 'hello';
  server_time: string;
  topics: Topic[];
}

export interface WsEvent<T = unknown> {
  type: 'event';
  topic: Topic;
  seq: number;
  ts: string;
  data: T;
}

export type SosEventData = { event: 'created' | 'updated' | 'assigned' | 'note'; sos: SosRecord };
export type AlertEventData = { event: 'opened' | 'acked' | 'resolved' | 'escalated'; alert: Alert };
export type DeviceEventData = {
  event: 'frame' | 'state' | 'online' | 'offline';
  device_id: string;
  summary: Partial<Omit<FrameSummary, 'state'>> & Partial<Omit<DeviceSummary, 'state'>> & {
    state?: HealthState | DeviceState;
    evidence?: string[];
  };
};
export type WeatherEventData = { event: 'updated'; current: WeatherCurrent; forecast_summary?: { hazards?: Hazard[] } };
export type SystemEventData = ({ event: 'capacity' } & Capacity) | { event: string; [k: string]: unknown };
export type RovEventData =
  | { event: 'telemetry' | 'deployed' | 'recalled' | 'stopped' | 'control' | 'mode'; rov: Rov }
  /** About twice a second while a vision feed runs; `rov_id` is the unit's id as a string. */
  | { event: 'vision'; rov_id: string; vision: RovVision; rov?: undefined };
