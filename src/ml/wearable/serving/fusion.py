"""Tier-2 fusion engine: deterministic per-device state machine over frames + Tier-1 head outputs.

Each frame the engine updates a few derived signals (immobility time, seconds since the last
beat, SpO2 / HR / skin-temperature trends, recent impact), evaluates every trauma state's
condition, applies its dwell (time to enter) and exit hysteresis, and reports the most severe
active state with its evidence. Heads that are unavailable simply disable the conditions that
need them - the engine never fails because a model is missing.

    engine = FusionEngine.from_config(thresholds={'fall': 0.9})
    out = engine.step(t_s, values, rr_ms, heads={'fall': 0.97, 'activity': [0.8, 0.1, 0.1], ...})
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Sequence, Tuple

import yaml

from .. import paths

ACTIVITY_CLASSES = ('rest', 'light', 'active')
IMPACT_WINDOW_S = 6.0          # = fall head window (4 frames x 1.5 s)


def load_fusion_config() -> dict:
    with open(paths.CONFIG_DIR / 'fusion.yaml', encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def _finite(x) -> bool:
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def _flag(v: Dict[str, float], key: str) -> bool:
    """A 0/1 device flag; missing (None/NaN) is False - bool(nan) would be True."""
    x = v.get(key)
    return _finite(x) and x > 0


class _Series:
    """Timestamped values over a sliding horizon, for slopes, minima and drops."""

    def __init__(self, horizon_s: float):
        self.horizon = horizon_s
        self.buf: Deque[Tuple[float, float]] = deque()

    def add(self, t: float, v) -> None:
        if _finite(v):
            self.buf.append((t, float(v)))
        while self.buf and t - self.buf[0][0] > self.horizon:
            self.buf.popleft()

    def window(self, t: float, span: float) -> List[Tuple[float, float]]:
        return [(ti, v) for ti, v in self.buf if t - ti <= span]

    def slope(self, t: float, span: float) -> Optional[float]:
        pts = self.window(t, span)
        if len(pts) < 3 or pts[-1][0] - pts[0][0] < span * 0.5:
            return None
        n = len(pts)
        mt = sum(p[0] for p in pts) / n
        mv = sum(p[1] for p in pts) / n
        den = sum((p[0] - mt) ** 2 for p in pts)
        return sum((p[0] - mt) * (p[1] - mv) for p in pts) / den if den else None

    def min(self, t: float, span: float) -> Optional[float]:
        pts = self.window(t, span)
        return min(v for _, v in pts) if pts else None

    def max(self, t: float, span: float) -> Optional[float]:
        pts = self.window(t, span)
        return max(v for _, v in pts) if pts else None

    def last(self) -> Optional[float]:
        return self.buf[-1][1] if self.buf else None


@dataclass
class _StateTimer:
    dwell_s: float
    exit_s: float
    true_since: Optional[float] = None
    false_since: Optional[float] = None
    active: bool = False

    def update(self, t: float, condition: bool) -> bool:
        if condition:
            self.false_since = None
            self.true_since = t if self.true_since is None else self.true_since
            if t - self.true_since >= self.dwell_s:
                self.active = True
        else:
            self.true_since = None
            if self.active:
                self.false_since = t if self.false_since is None else self.false_since
                if t - self.false_since >= self.exit_s:
                    self.active = False
        return self.active


@dataclass
class FusionEngine:
    cfg: dict
    thresholds: Dict[str, float] = field(default_factory=dict)   # Tier-1 operating thresholds (registry)
    model_versions: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.timers = {s: _StateTimer(v['dwell_s'], v['exit_s']) for s, v in self.cfg['states'].items()}
        self.hr = _Series(600)
        self.spo2 = _Series(120)
        self.temp = _Series(900)
        self.baro = _Series(120)
        self.gps: Deque[Tuple[float, float, float]] = deque()
        self.immobile_since: Optional[float] = None
        self.last_beat_t: Optional[float] = None
        self.contact_since: Optional[float] = None
        # (t, peak g over the fall window, baro before, fall p at detection)
        self.last_impact: Optional[Tuple[float, float, Optional[float], float]] = None
        self.acc_peak = _Series(IMPACT_WINDOW_S + 3)
        self.bpm_baseline: Optional[float] = None
        self._bpm_first: List[float] = []

    @classmethod
    def from_config(cls, thresholds: Optional[Dict[str, float]] = None, model_versions=None) -> 'FusionEngine':
        return cls(load_fusion_config(), dict(thresholds or {}), dict(model_versions or {}))

    # ─── derived signals ─────────────────────────────────────────────────────

    def _update_signals(self, t: float, v: Dict[str, float], rr_ms: Sequence[float], heads: Dict[str, object]):
        sig = self.cfg['signals']
        std = v.get('imu_acc_std_g')
        if _finite(std) and std < sig['immobile_acc_std_g']:
            self.immobile_since = t if self.immobile_since is None else self.immobile_since
        elif _finite(std):
            self.immobile_since = None
        contact = _flag(v, 'ppg_finger_on')
        if contact:
            self.contact_since = t if self.contact_since is None else self.contact_since
        else:
            self.contact_since = None
        if rr_ms:
            self.last_beat_t = t
        bpm = v.get('ppg_bpm')
        self.hr.add(t, bpm)
        if self.bpm_baseline is None and _finite(bpm):
            self._bpm_first.append(float(bpm))
            if len(self._bpm_first) >= 80:                    # same 2 min calibration as the feature layer
                self.bpm_baseline = sorted(self._bpm_first)[len(self._bpm_first) // 2]
        if _flag(v, 'ppg_spo2_valid'):
            self.spo2.add(t, v.get('ppg_spo2'))
        self.temp.add(t, v.get('temp_skin_c'))
        self.baro.add(t, v.get('baro_hpa'))
        if _finite(v.get('gps_lat')) and _finite(v.get('gps_lng')):
            self.gps.append((t, float(v['gps_lat']), float(v['gps_lng'])))
        while self.gps and t - self.gps[0][0] > 600:
            self.gps.popleft()
        p_fall = heads.get('fall')
        fall_thr = self.thresholds.get('fall', 0.5)
        firmware_flag = _flag(v, 'imu_fall_detected')
        self.acc_peak.add(t, v.get('imu_acc_max_g'))
        if (_finite(p_fall) and p_fall >= fall_thr) or firmware_flag:
            # the fall head scores a window, so its probability crosses the threshold a few frames after
            # the impact itself: take the peak over that window, not the current frame
            peak = self.acc_peak.max(t, IMPACT_WINDOW_S) or 0.0
            p = float(p_fall) if _finite(p_fall) else 1.0
            if self.last_impact is None or t - self.last_impact[0] > 5 or peak > self.last_impact[1]:
                self.last_impact = (t, float(peak), self.baro.min(t, 30), p)
            elif p > self.last_impact[3]:
                self.last_impact = self.last_impact[:3] + (p,)

    def _immobile_s(self, t):
        return t - self.immobile_since if self.immobile_since is not None else 0.0

    def _gps_moved_m(self, t, span) -> Optional[float]:
        pts = [(la, ln) for ti, la, ln in self.gps if t - ti <= span]
        if len(pts) < 2:
            return None
        (la0, ln0), (la1, ln1) = pts[0], pts[-1]
        dy = (la1 - la0) * 111_320
        dx = (ln1 - ln0) * 111_320 * math.cos(math.radians(la0))
        return math.hypot(dx, dy)

    # ─── state conditions ────────────────────────────────────────────────────

    def _conditions(self, t, v, heads) -> Tuple[Dict[str, bool], Dict[str, List[str]], dict]:
        c, ev = {}, {s: [] for s in self.cfg['states']}
        sig = self.cfg['signals']
        immobile = self._immobile_s(t)
        moving = _finite(v.get('imu_acc_std_g')) and v['imu_acc_std_g'] > sig['moving_acc_std_g']
        contact = self.contact_since is not None
        batt_low = _finite(v.get('power_batt_v')) and v['power_batt_v'] < sig['battery_low_v']
        sensor_fault = (not contact and moving) or batt_low
        p_trust = heads.get('hr_trust')
        hr_trusted = contact and (not _finite(p_trust) or p_trust >= self.thresholds.get('hr_trust', 0.5))
        bpm = v.get('ppg_bpm') if _finite(v.get('ppg_bpm')) else None
        act = heads.get('activity')
        activity = ACTIVITY_CLASSES[max(range(3), key=lambda i: act[i])] if act is not None else None
        info = {'sensor_fault': sensor_fault, 'immobile_s': immobile, 'activity': activity, 'hr_trusted': hr_trusted}

        # CARDIAC_ARREST
        k = self.cfg['cardiac']
        no_beat = (contact and t - self.contact_since >= k['no_beat_s'] and
                   (self.last_beat_t is None or t - self.last_beat_t >= k['no_beat_s']))
        a = no_beat and immobile >= k['no_beat_s'] and not sensor_fault
        if a:
            ev['CARDIAC_ARREST'].append(f'no beats {t - (self.last_beat_t or self.contact_since):.0f} s with contact, immobile')
        p_r = heads.get('rhythm')
        b = (hr_trusted and bpm is not None and _finite(p_r) and p_r >= k['rhythm_p']
             and (bpm > k['tachy_bpm'] or bpm < k['brady_bpm']))
        if b:
            ev['CARDIAC_ARREST'].append(f'irregular rhythm p={p_r:.2f} with BPM {bpm:.0f}')
        c['CARDIAC_ARREST'] = a or b

        # ASPIRATION_HYPOXIA
        k = self.cfg['hypoxia']
        s_now = self.spo2.last() if self.spo2.buf and t - self.spo2.buf[-1][0] < 5 else None
        low = s_now is not None and s_now < k['spo2_low']
        s_max = self.spo2.max(t, k['drop_window_s'])
        drop = s_now is not None and s_max is not None and s_max - s_now > k['drop_pct']
        c['ASPIRATION_HYPOXIA'] = (low or drop) and not sensor_fault
        if c['ASPIRATION_HYPOXIA']:
            ev['ASPIRATION_HYPOXIA'].append(f'SpO2 {s_now:.0f} %' + (f' (−{s_max - s_now:.1f} % in {k["drop_window_s"]} s)' if drop else ''))
        b_min = self.baro.min(t, 60)
        submerged = (_flag(v, 'water_wet') and _finite(v.get('baro_hpa')) and b_min is not None
                     and v['baro_hpa'] - b_min >= k['submerged_dp_hpa'])
        info['submerged'] = submerged

        # HEMORRHAGIC_SHOCK
        k = self.cfg['shock']
        hr_slope = self.hr.slope(t, k['hr_slope_window_s'])
        t_slope = self.temp.slope(t, k['temp_slope_window_s'])
        eda_ratio = (v['eda_us'] / v['eda_baseline_us']) if _finite(v.get('eda_us')) and _finite(v.get('eda_baseline_us')) \
            and v['eda_baseline_us'] > 0 else None
        c['HEMORRHAGIC_SHOCK'] = bool(hr_trusted and bpm is not None and bpm > k['hr_min'] and activity == 'rest'
                                      and hr_slope is not None and hr_slope > 0 and t_slope is not None and t_slope < 0
                                      and eda_ratio is not None and eda_ratio >= sig['eda_high_ratio'] and not sensor_fault)
        if c['HEMORRHAGIC_SHOCK']:
            ev['HEMORRHAGIC_SHOCK'].append(f'HR {bpm:.0f} at rest rising, skin temp falling, EDA ×{eda_ratio:.1f}')

        # CONCUSSIVE_STASIS
        k = self.cfg['concussion']
        recent = self.last_impact is not None and t - self.last_impact[0] <= k['fall_window_s']
        still_since_impact = recent and self.immobile_since is not None and self.immobile_since >= self.last_impact[0] - 3
        c['CONCUSSIVE_STASIS'] = bool(recent and still_since_impact and immobile >= k['immobile_s'])
        if c['CONCUSSIVE_STASIS']:
            ti, g, b0, p_imp = self.last_impact
            ev['CONCUSSIVE_STASIS'] += [f'fall p={p_imp:.2f} @ {g:.1f} g', f'immobile {immobile:.0f} s']
        info['severe_impact'] = bool(recent and (self.last_impact[1] >= k['severe_impact_g'] or (
            self.last_impact[2] is not None and _finite(v.get('baro_hpa'))
            and v['baro_hpa'] - self.last_impact[2] >= k['severe_drop_hpa'])))

        # CRUSH_ENTRAPMENT: still + heart rate raised from the person's own baseline, either soon after a
        # detected impact (triggered path) or for much longer without one (fallback path). P5 replay:
        # the stress head and untriggered 120 s stillness produced 14 false alarms / 8 h on Stress-Predict.
        k = self.cfg['crush']
        moved = self._gps_moved_m(t, k['immobile_s'])
        still_place = moved is None or moved < sig['gps_still_m']
        p_s = heads.get('stress')
        stress_high = k.get('use_stress_head', False) and _finite(p_s) and p_s >= k['stress_p']
        hr_high = (hr_trusted and bpm is not None and self.bpm_baseline is not None
                   and bpm - self.bpm_baseline >= k['hr_above_baseline_bpm'])
        trig_s = k.get('require_impact_s')
        after_impact = trig_s is None or (self.last_impact is not None and self.immobile_since is not None
                                          and 0 <= self.immobile_since - self.last_impact[0] + 3 <= trig_s)
        triggered = immobile >= k['immobile_s'] and after_impact
        fallback = k.get('untriggered_immobile_s') is not None and immobile >= k['untriggered_immobile_s']
        c['CRUSH_ENTRAPMENT'] = bool(still_place and (stress_high or hr_high) and (triggered or fallback))
        if c['CRUSH_ENTRAPMENT']:
            ev['CRUSH_ENTRAPMENT'].append(
                f'immobile {immobile:.0f} s' + (' after impact' if triggered and trig_s is not None else '') + ', '
                + (f'stress p={p_s:.2f}' if stress_high else f'HR {bpm:.0f} (+{bpm - self.bpm_baseline:.0f} vs baseline)'))

        # HYPOTHERMIA_RISK
        k = self.cfg['hypothermia']
        skin = v.get('temp_skin_c') if _finite(v.get('temp_skin_c')) else None
        ts = self.temp.slope(t, k['temp_slope_window_s'])
        c['HYPOTHERMIA_RISK'] = bool(skin is not None and skin < k['skin_c'] and ts is not None and ts < 0 and
                                     ((hr_trusted and bpm is not None and bpm < k['brady_bpm']) or _flag(v, 'water_wet')))
        if c['HYPOTHERMIA_RISK']:
            ev['HYPOTHERMIA_RISK'].append(f'skin {skin:.1f} °C falling')

        # ELEVATED_STRESS
        k = self.cfg['stress']
        c['ELEVATED_STRESS'] = bool(_finite(p_s) and p_s > k['p'] and activity in ('rest', 'light', None))
        if c['ELEVATED_STRESS']:
            ev['ELEVATED_STRESS'].append(f'stress p={p_s:.2f}, activity {activity or "unknown"}')
        return c, ev, info

    # ─── step ────────────────────────────────────────────────────────────────

    def step(self, t: float, values: Dict[str, float], rr_ms: Sequence[float] = (),
             heads: Optional[Dict[str, object]] = None) -> dict:
        heads = heads or {}
        self._update_signals(t, values, rr_ms, heads)
        cond, ev, info = self._conditions(t, values, heads)
        active = [s for s in self.cfg['severity'] if self.timers[s].update(t, cond[s])]
        state = active[0] if active else 'STABLE'
        risk = self.cfg['base_risk'][state]
        if state == 'ASPIRATION_HYPOXIA' and info['submerged']:
            risk = min(1.0, risk + 0.1)
            ev[state].append('submerged (wet, pressure rising)')
        if state == 'CONCUSSIVE_STASIS' and info['severe_impact']:
            risk = min(1.0, risk + 0.1)
            ev[state].append('severe impact (> 6 g or ~1 m drop)')
        evidence = list(ev.get(state, []))
        if info['sensor_fault']:
            evidence.append('SENSOR_FAULT: contact lost while moving or battery low - cardiac rules suppressed')
        if values.get('ppg_bpm') is not None and _finite(values.get('ppg_bpm')):
            evidence.append(f"HR {values['ppg_bpm']:.0f} {'trusted' if info['hr_trusted'] else 'untrusted'}")
        return {
            'ml_health_state': state, 'ml_state_id': self.cfg['state_ids'][state], 'ml_risk_score': round(risk, 3),
            'alert_level': self.cfg.get('alert_level', {}).get(state, 'critical' if state != 'STABLE' else 'none'),
            'basis': self.cfg['basis'][state], 'evidence': evidence, 'active_states': active,
            'sensor_fault': info['sensor_fault'],
            'heads': {k: (ACTIVITY_CLASSES[max(range(3), key=lambda i: v[i])] if k == 'activity' and v is not None
                          else (round(float(v), 3) if _finite(v) else None)) for k, v in heads.items()},
            'unavailable_inputs': sorted(h for h in ('stress', 'fall', 'activity', 'hr_trust', 'rhythm') if heads.get(h) is None),
            'model_versions': self.model_versions, 'fusion_version': self.cfg['version'], 'ml_mode': 'hybrid',
        }
