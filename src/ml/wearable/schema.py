"""Telemetry frame contract shared by firmware, server, emulator and tests.

A frame summarises one FRAME_PERIOD_S interval of wearable sensing. Firmware v2 sends
schema 2 natively; legacy firmware (schema 1, single sensor snapshot) is mapped onto the
same structure with every field it cannot provide set to NaN.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_VERSION = 2
FRAME_PERIOD_S = 1.5          # firmware telemetry cadence
IMU_HZ = 50                   # firmware IMU sampling rate (emulator resamples to match)
RR_MIN_MS, RR_MAX_MS = 270, 2000  # firmware beat-interval acceptance window (222-30 bpm)
ACC_MAG_MAX_G = 16 * math.sqrt(3)  # |a| with every axis at the +-16 g full scale


@dataclass(frozen=True)
class FieldSpec:
    name: str                  # flat column name used everywhere downstream
    path: Tuple[str, str]      # (group, key) inside the v2 JSON payload
    unit: str
    lo: float                  # plausible physical range; outside -> NaN + warning
    hi: float
    is_bool: bool = False


FIELDS: List[FieldSpec] = [
    # Motion (MPU6050 @ IMU_HZ, aggregated over the frame). The +-16 g range is per axis, so the
    # vector magnitude reaches 16*sqrt(3) = 27.7 g on hard impacts (HIFD falls peak at 27.2 g).
    FieldSpec('imu_acc_max_g', ('imu', 'acc_max_g'), 'g', 0, ACC_MAG_MAX_G),
    FieldSpec('imu_acc_min_g', ('imu', 'acc_min_g'), 'g', 0, ACC_MAG_MAX_G),
    FieldSpec('imu_acc_mean_g', ('imu', 'acc_mean_g'), 'g', 0, ACC_MAG_MAX_G),
    FieldSpec('imu_acc_std_g', ('imu', 'acc_std_g'), 'g', 0, ACC_MAG_MAX_G),
    FieldSpec('imu_gyro_max_dps', ('imu', 'gyro_max_dps'), 'deg/s', 0, 2000),
    FieldSpec('imu_gyro_mean_dps', ('imu', 'gyro_mean_dps'), 'deg/s', 0, 2000),
    FieldSpec('imu_tilt_deg', ('imu', 'tilt_deg'), 'deg', 0, 180),
    FieldSpec('imu_n', ('imu', 'n'), 'samples', 0, 1000),
    FieldSpec('imu_fall_detected', ('imu', 'fall_detected'), 'bool', 0, 1, is_bool=True),
    # Optical pulse (MAX30102)
    FieldSpec('ppg_finger_on', ('ppg', 'finger_on'), 'bool', 0, 1, is_bool=True),
    FieldSpec('ppg_bpm', ('ppg', 'bpm'), 'bpm', 20, 250),
    FieldSpec('ppg_spo2', ('ppg', 'spo2'), '%', 50, 100),
    FieldSpec('ppg_spo2_valid', ('ppg', 'spo2_valid'), 'bool', 0, 1, is_bool=True),
    FieldSpec('ppg_perfusion', ('ppg', 'perfusion'), '%', 0, 100),
    # Electrodermal activity (Grove GSR, converted to skin conductance on device)
    FieldSpec('eda_us', ('eda', 'us'), 'uS', 0, 100),
    FieldSpec('eda_slope_us_s', ('eda', 'slope_us_s'), 'uS/s', -10, 10),
    FieldSpec('eda_baseline_us', ('eda', 'baseline_us'), 'uS', 0, 100),
    FieldSpec('eda_raw', ('eda', 'raw'), 'adc', 0, 4095),
    FieldSpec('eda_norm', ('eda', 'norm'), 'ratio', 0, 1),
    # Skin temperature (MAX30205)
    FieldSpec('temp_skin_c', ('temp', 'skin_c'), 'degC', 10, 45),
    # Barometer (BMP388)
    FieldSpec('baro_hpa', ('baro', 'hpa'), 'hPa', 300, 1300),
    FieldSpec('baro_dmax_hpa', ('baro', 'dmax_hpa'), 'hPa', 0, 200),
    # Water contact
    FieldSpec('water_wet', ('water', 'wet'), 'bool', 0, 1, is_bool=True),
    # Power
    FieldSpec('power_batt_v', ('power', 'batt_v'), 'V', 2.5, 4.5),
    # GPS (NEO-6M)
    FieldSpec('gps_lat', ('gps', 'lat'), 'deg', -90, 90),
    FieldSpec('gps_lng', ('gps', 'lng'), 'deg', -180, 180),
    FieldSpec('gps_sats', ('gps', 'sats'), 'count', 0, 50),
    FieldSpec('gps_hdop', ('gps', 'hdop'), 'ratio', 0, 99.99),
    FieldSpec('gps_breached', ('gps', 'breached'), 'bool', 0, 1, is_bool=True),
]

FIELD_NAMES: List[str] = [f.name for f in FIELDS]
_BY_PATH = {f.path: f for f in FIELDS}


@dataclass
class Frame:
    """One normalised telemetry frame (schema-version independent)."""

    device_id: str
    schema: int
    values: Dict[str, float]               # every FIELD_NAMES key present; NaN if unavailable
    rr_ms: List[float] = field(default_factory=list)
    seq: Optional[int] = None
    uptime_ms: Optional[int] = None
    fw: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    @property
    def unavailable(self) -> List[str]:
        return [k for k, v in self.values.items() if math.isnan(v)]

    def to_flat(self) -> Dict[str, Any]:
        row: Dict[str, Any] = dict(self.values)
        row['rr_ms'] = list(self.rr_ms)
        return row


def _to_float(value: Any, spec: FieldSpec, warnings: List[str]) -> float:
    if value is None:
        return math.nan
    try:
        x = float(bool(value)) if spec.is_bool else float(value)
    except (TypeError, ValueError):
        warnings.append(f'{spec.name}: non-numeric {value!r}')
        return math.nan
    if math.isnan(x):
        return x
    if not spec.lo <= x <= spec.hi:
        warnings.append(f'{spec.name}: {x} outside [{spec.lo}, {spec.hi}]')
        return math.nan
    return x


def _clean_rr(raw: Any, warnings: List[str]) -> List[float]:
    if not isinstance(raw, (list, tuple)):
        return []
    rr = []
    for v in raw:
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if RR_MIN_MS <= x <= RR_MAX_MS:
            rr.append(x)
        else:
            warnings.append(f'rr_ms: dropped {x}')
    return rr


def _group(payload: Dict[str, Any], name: str, warnings: List[str]) -> Dict[str, Any]:
    g = payload.get(name)
    if g is None:
        return {}
    if not isinstance(g, dict):
        warnings.append(f'{name}: expected an object, got {type(g).__name__}')
        return {}
    return g


def _parse_v2(payload: Dict[str, Any]) -> Frame:
    warnings: List[str] = []
    values = {}
    for spec in FIELDS:
        values[spec.name] = _to_float(_group(payload, spec.path[0], warnings).get(spec.path[1]), spec, warnings)
    rr = _clean_rr(_group(payload, 'ppg', warnings).get('rr_ms'), warnings)
    return Frame(
        device_id=str(payload.get('device_id', 'unknown')), schema=2, values=values, rr_ms=rr,
        seq=payload.get('seq'), uptime_ms=payload.get('uptime_ms'), fw=payload.get('fw'),
        warnings=warnings,
    )


def _parse_v1(payload: Dict[str, Any]) -> Frame:
    """Map legacy firmware payloads (one instantaneous snapshot) onto the v2 frame.

    Interval aggregates cannot be recovered from a snapshot, so only the fields with an
    exact meaning are filled. v1 SpO2 is simulated in that firmware and is never trusted.
    """
    warnings: List[str] = []
    fall = _group(payload, 'fall', warnings)
    vitals = _group(payload, 'vitals', warnings)
    stress = _group(payload, 'stress', warnings)
    gps = _group(payload, 'gps', warnings)
    finger_on = vitals.get('category', 'Unknown') != 'No Finger'
    bpm = vitals.get('bpm')
    mapped = {
        ('imu', 'acc_mean_g'): fall.get('acc_mag'),
        ('imu', 'gyro_mean_dps'): fall.get('gyro_mag'),
        ('imu', 'fall_detected'): fall.get('fall_detected'),
        ('ppg', 'finger_on'): finger_on,
        ('ppg', 'bpm'): bpm if finger_on and bpm else None,
        ('ppg', 'spo2_valid'): False,
        ('eda', 'raw'): stress.get('gsr_raw'),
        ('eda', 'norm'): stress.get('gsr_norm'),
        ('gps', 'lat'): gps.get('lat'),
        ('gps', 'lng'): gps.get('lng'),
        ('gps', 'sats'): gps.get('satellites'),
        ('gps', 'breached'): gps.get('breached'),
    }
    values = {}
    for spec in FIELDS:
        values[spec.name] = _to_float(mapped.get(spec.path), spec, warnings)
    return Frame(device_id=str(payload.get('device_id', 'unknown')), schema=1, values=values,
                 warnings=warnings)


def parse_payload(payload: Dict[str, Any]) -> Frame:
    """Validate and normalise a raw telemetry JSON payload into a Frame."""
    if not isinstance(payload, dict):
        raise ValueError('telemetry payload must be a JSON object')
    if payload.get('schema') == 2:
        return _parse_v2(payload)
    return _parse_v1(payload)


def to_payload(values: Dict[str, float], rr_ms: List[float], device_id: str = 'SIM-01',
               seq: Optional[int] = None) -> Dict[str, Any]:
    """Inverse of parse_payload for schema 2: flat values -> firmware-style JSON (NaN -> null)."""
    payload: Dict[str, Any] = {'schema': SCHEMA_VERSION, 'device_id': device_id, 'fw': 'sim'}
    if seq is not None:
        payload['seq'] = seq
    for spec in FIELDS:
        x = values.get(spec.name, math.nan)
        if x is None or (isinstance(x, float) and math.isnan(x)):
            out = None
        elif spec.is_bool:
            out = bool(x)
        else:
            out = float(x)
        payload.setdefault(spec.path[0], {})[spec.path[1]] = out
    payload.setdefault('ppg', {})['rr_ms'] = [float(r) for r in rr_ms]
    return payload


def empty_values() -> Dict[str, float]:
    return {name: math.nan for name in FIELD_NAMES}


def json_schema() -> Dict[str, Any]:
    """JSON Schema (draft 2020-12) for schema-2 payloads, generated from FIELDS."""
    groups: Dict[str, Dict[str, Any]] = {}
    for spec in FIELDS:
        prop = {'type': 'boolean'} if spec.is_bool else {
            'type': 'number', 'minimum': spec.lo, 'maximum': spec.hi, 'description': spec.unit}
        groups.setdefault(spec.path[0], {'type': 'object', 'properties': {}})
        groups[spec.path[0]]['properties'][spec.path[1]] = prop
    groups['ppg']['properties']['rr_ms'] = {
        'type': 'array', 'items': {'type': 'number', 'minimum': RR_MIN_MS, 'maximum': RR_MAX_MS}}
    return {
        '$schema': 'https://json-schema.org/draft/2020-12/schema',
        'title': 'TRIDENT wearable telemetry frame',
        'type': 'object',
        'required': ['schema', 'device_id'],
        'properties': {
            'schema': {'const': SCHEMA_VERSION},
            'device_id': {'type': 'string'},
            'fw': {'type': 'string'},
            'seq': {'type': 'integer', 'minimum': 0},
            'uptime_ms': {'type': 'integer', 'minimum': 0},
            **groups,
        },
    }
