"""Scenario tests for the Tier-2 fusion engine (synthetic trajectories are used only here)."""

import numpy as np

from src.ml.wearable.schema import FRAME_PERIOD_S, empty_values
from src.ml.wearable.serving.fusion import FusionEngine


def _frame(**kw):
    v = empty_values()
    v.update({'imu_acc_std_g': 0.15, 'imu_acc_max_g': 1.3, 'imu_acc_mean_g': 1.0, 'ppg_finger_on': 1,
              'ppg_bpm': 75.0, 'power_batt_v': 3.9, 'temp_skin_c': 33.5, 'eda_us': 2.0, 'eda_baseline_us': 2.0})
    v.update(kw)
    return v


def _run(engine, frames, t0=0.0):
    outs = []
    for i, (v, rr, heads) in enumerate(frames):
        outs.append(engine.step(t0 + i * FRAME_PERIOD_S, v, rr, heads))
    return outs


def _normal(n, **heads):
    h = {'fall': 0.01, 'stress': 0.1, 'activity': [0.2, 0.3, 0.5], 'hr_trust': 0.9, 'rhythm': 0.05, **heads}
    return [(_frame(), [800.0], h) for _ in range(n)]


def test_normal_activity_stays_stable():
    outs = _run(FusionEngine.from_config(), _normal(400))
    assert {o['ml_health_state'] for o in outs} == {'STABLE'}


def test_fall_then_immobility_gives_concussive_stasis_between_30_and_45_s():
    eng = FusionEngine.from_config(thresholds={'fall': 0.9})
    frames = _normal(100)
    frames.append((_frame(imu_acc_max_g=7.5, imu_acc_std_g=0.9), [800.0], {'fall': 0.97, 'activity': [0.9, 0.05, 0.05]}))
    still = {'fall': 0.02, 'activity': [0.95, 0.03, 0.02], 'hr_trust': 0.9, 'stress': 0.2}
    frames += [(_frame(imu_acc_std_g=0.01), [800.0], still) for _ in range(40)]
    outs = _run(eng, frames)
    impact_t = 100 * FRAME_PERIOD_S
    states = [(i * FRAME_PERIOD_S - impact_t, o['ml_health_state']) for i, o in enumerate(outs)]
    assert all(s != 'CONCUSSIVE_STASIS' for dt, s in states if dt <= 20)
    first = next(dt for dt, s in states if s == 'CONCUSSIVE_STASIS')
    assert 30 <= first <= 45
    assert any('severe impact' in e for e in outs[-1]['evidence'])


def test_fall_followed_by_walking_does_not_alarm():
    eng = FusionEngine.from_config(thresholds={'fall': 0.9})
    frames = _normal(100) + [(_frame(imu_acc_max_g=5.0, imu_acc_std_g=0.8), [800.0], {'fall': 0.95})] + _normal(60)
    assert all(o['ml_health_state'] == 'STABLE' for o in _run(eng, frames))


def test_no_beats_with_contact_and_immobile_is_cardiac_arrest():
    eng = FusionEngine.from_config()
    frames = _normal(100) + [(_frame(imu_acc_std_g=0.01, ppg_bpm=float('nan')), [], {'hr_trust': 0.9}) for _ in range(12)]
    outs = _run(eng, frames)
    assert outs[-1]['ml_health_state'] == 'CARDIAC_ARREST'
    assert outs[100 + 5]['ml_health_state'] != 'CARDIAC_ARREST'          # < 10 s without beats


def test_contact_lost_while_moving_is_sensor_fault_not_cardiac():
    eng = FusionEngine.from_config()
    frames = _normal(100) + [(_frame(ppg_finger_on=0, ppg_bpm=float('nan'), imu_acc_std_g=0.3), [], {}) for _ in range(30)]
    outs = _run(eng, frames)
    assert outs[-1]['sensor_fault'] and outs[-1]['ml_health_state'] != 'CARDIAC_ARREST'


def test_low_spo2_for_15_s_is_hypoxia_and_escalates_when_submerged():
    eng = FusionEngine.from_config()
    frames = _normal(60)
    frames += [(_frame(ppg_spo2=87.0, ppg_spo2_valid=1, baro_hpa=1013.0), [800.0], {}) for _ in range(5)]
    frames += [(_frame(ppg_spo2=87.0, ppg_spo2_valid=1, baro_hpa=1020.0, water_wet=1), [800.0], {}) for _ in range(10)]
    outs = _run(eng, frames)
    assert outs[60 + 5]['ml_health_state'] != 'ASPIRATION_HYPOXIA'       # 7.5 s: still in dwell
    assert outs[-1]['ml_health_state'] == 'ASPIRATION_HYPOXIA'
    assert outs[-1]['ml_risk_score'] > FusionEngine.from_config().cfg['base_risk']['ASPIRATION_HYPOXIA']


def test_stress_needs_dwell_and_rest_context():
    eng = FusionEngine.from_config()
    rest = {'stress': 0.9, 'activity': [0.9, 0.05, 0.05], 'hr_trust': 0.9}
    outs = _run(eng, [(_frame(imu_acc_std_g=0.05), [800.0], rest) for _ in range(100)])     # 150 s; dwell 120 s
    assert outs[60]['ml_health_state'] == 'STABLE' and outs[-1]['ml_health_state'] == 'ELEVATED_STRESS'
    assert outs[-1]['alert_level'] == 'advisory'
    eng = FusionEngine.from_config()
    active = {'stress': 0.9, 'activity': [0.05, 0.05, 0.9]}
    assert _run(eng, [(_frame(), [800.0], active) for _ in range(60)])[-1]['ml_health_state'] == 'STABLE'


def test_missing_heads_are_reported_and_rules_still_run():
    eng = FusionEngine.from_config()
    out = _run(eng, [(_frame(), [800.0], {}) for _ in range(5)])[-1]
    assert out['unavailable_inputs'] == ['activity', 'fall', 'hr_trust', 'rhythm', 'stress']
    assert out['ml_health_state'] == 'STABLE'


def test_hysteresis_keeps_state_briefly_after_condition_clears():
    eng = FusionEngine.from_config()
    rest = {'stress': 0.9, 'activity': [0.9, 0.05, 0.05]}
    calm = {'stress': 0.1, 'activity': [0.9, 0.05, 0.05]}
    outs = _run(eng, [(_frame(imu_acc_std_g=0.05), [800.0], rest) for _ in range(100)] +
                [(_frame(imu_acc_std_g=0.05), [800.0], calm) for _ in range(50)])
    assert outs[100 + 20]['ml_health_state'] == 'ELEVATED_STRESS'          # 30 s after: inside 60 s exit window
    assert outs[-1]['ml_health_state'] == 'STABLE'
    assert np.isfinite(outs[-1]['ml_risk_score'])


def test_missing_wet_flag_is_not_wet():
    # bool(nan) is True: a device without a water sensor must not count as immersed
    eng = FusionEngine.from_config()
    frames = [(_frame(temp_skin_c=31.5 - 0.005 * i, ppg_bpm=85.0, water_wet=float('nan'), imu_acc_std_g=0.05),
               [700.0], {'hr_trust': 0.9}) for i in range(400)]
    assert all(o['ml_health_state'] != 'HYPOTHERMIA_RISK' for o in _run(eng, frames))
    eng = FusionEngine.from_config()
    wet = [(_frame(temp_skin_c=31.5 - 0.005 * i, ppg_bpm=85.0, water_wet=1, imu_acc_std_g=0.05), [700.0], {})
           for i in range(400)]
    assert _run(eng, wet)[-1]['ml_health_state'] == 'HYPOTHERMIA_RISK'


def _calibrate(n=90):
    # 2-min HR baseline of 70 bpm, moving normally
    return [(_frame(ppg_bpm=70.0), [850.0], {'hr_trust': 0.9}) for _ in range(n)]


def test_stressed_sitting_without_impact_is_not_crush():
    eng = FusionEngine.from_config(thresholds={'fall': 0.9})
    still = [(_frame(imu_acc_std_g=0.01, ppg_bpm=95.0), [630.0], {'stress': 0.99, 'hr_trust': 0.9}) for _ in range(120)]
    assert all(o['ml_health_state'] != 'CRUSH_ENTRAPMENT' for o in _run(eng, _calibrate() + still))   # 180 s still


def test_impact_then_still_with_raised_hr_is_crush():
    eng = FusionEngine.from_config(thresholds={'fall': 0.9})
    impact = [(_frame(imu_acc_max_g=5.0, imu_acc_std_g=0.8, ppg_bpm=90.0), [660.0], {'fall': 0.97, 'hr_trust': 0.9})]
    still = [(_frame(imu_acc_std_g=0.01, ppg_bpm=95.0), [630.0], {'fall': 0.02, 'hr_trust': 0.9}) for _ in range(100)]
    outs = _run(eng, _calibrate() + impact + still)
    assert 'CRUSH_ENTRAPMENT' in outs[-1]['active_states']
    assert any('after impact' in e for e in outs[-1]['evidence']) or outs[-1]['ml_health_state'] != 'CRUSH_ENTRAPMENT'


def test_long_stillness_with_raised_hr_is_crush_without_impact():
    eng = FusionEngine.from_config()
    still = [(_frame(imu_acc_std_g=0.01, ppg_bpm=95.0), [630.0], {'hr_trust': 0.9}) for _ in range(210)]   # 315 s
    assert _run(eng, _calibrate() + still)[-1]['ml_health_state'] == 'CRUSH_ENTRAPMENT'
