import math

import numpy as np

from src.ml.wearable.data.loaders import hifd_restore_gravity
from src.ml.wearable.data.recording import Recording, Signal
from src.ml.wearable.emulator import detect_beats, emulate, firmware_bpm, to_imu_rate
from src.ml.wearable.schema import FIELD_NAMES, FRAME_PERIOD_S, IMU_HZ


def _still_acc(seconds, fs):
    data = np.tile([0.0, 0.0, 1.0], (int(seconds * fs), 1))
    return Signal(data, fs)


def test_frame_count_and_columns():
    rec = Recording('t', 's1', 'tr', 'wrist', acc=_still_acc(30, 50))
    df = emulate(rec)
    assert len(df) == int(30 // FRAME_PERIOD_S)
    assert set(FIELD_NAMES) <= set(df.columns)
    assert df['imu_n'].iloc[0] == 75  # 50 Hz * 1.5 s
    assert np.allclose(df['imu_acc_mean_g'], 1.0)
    assert np.allclose(df['imu_tilt_deg'], 0.0)
    assert df['ppg_bpm'].isna().all() and df['eda_us'].isna().all()


def test_impact_peak_lands_in_the_right_frame():
    acc = _still_acc(15, 50)
    acc.data = acc.data.copy()
    acc.data[int(7.6 * 50)] = [0.0, 0.0, 6.0]  # 6 g spike at t = 7.6 s -> frame 5
    df = emulate(Recording('t', 's', 'tr', 'wrist', acc=acc))
    assert df['imu_acc_max_g'].idxmax() == 5
    assert math.isclose(df['imu_acc_max_g'].max(), 6.0)


def test_high_rate_imu_is_resampled_to_firmware_rate():
    sig = to_imu_rate(_still_acc(10, 200))
    assert sig.fs == IMU_HZ and len(sig.data) == 10 * IMU_HZ


def test_bvp_beat_detection_recovers_72_bpm():
    fs, f_hr = 64.0, 1.2
    t = np.arange(0, 60, 1 / fs)
    bvp = Signal(np.sin(2 * np.pi * f_hr * t) + 0.1 * np.sin(2 * np.pi * 0.2 * t), fs)
    beats = detect_beats(bvp)
    assert abs(60.0 / np.median(np.diff(beats)) - 72.0) < 1.0
    df = emulate(Recording('t', 's', 'tr', 'wrist', bvp=bvp))
    assert abs(df['ppg_bpm'].iloc[-1] - 72.0) < 1.0
    assert all(abs(r - 833.3) < 20 for rr in df['rr_ms'].iloc[5:] for r in rr)


def test_firmware_ema_and_rr_window():
    beats = np.array([0.0, 1.0, 2.0, 2.1, 3.1])  # 100 ms interval is rejected (< 270 ms)
    rr, ends, ema = firmware_bpm(beats)
    assert list(rr) == [1000.0, 1000.0, 1000.0]
    assert np.allclose(ema, 60.0)


def test_bpm_drops_out_after_timeout_like_firmware():
    beats = np.arange(0, 10, 1.0)  # beats stop at 9 s
    rec = Recording('t', 's', 'tr', 'wrist', beats_s=beats, meta={'duration_s': 30.0})
    df = emulate(rec)
    assert not np.isnan(df['ppg_bpm'].iloc[5])
    assert np.isnan(df['ppg_bpm'].iloc[-1])


def test_categorical_label_mode_and_purity():
    labels = np.r_[np.full(700, 1), np.full(350, 2)]  # 1.5 s at 700 Hz: 2/3 class 1
    rec = Recording('t', 's', 'tr', 'wrist', acc=_still_acc(1.5, 50),
                    labels={'protocol': Signal(labels, 700.0, kind='categorical')})
    df = emulate(rec)
    assert df['y_protocol'].iloc[0] == 1
    assert math.isclose(df['y_protocol_purity'].iloc[0], 2 / 3)


def test_eda_slope_and_baseline():
    fs = 4.0
    t = np.arange(0, 300, 1 / fs)
    rec = Recording('t', 's', 'tr', 'wrist', eda=Signal(2.0 + 0.01 * t, fs))
    df = emulate(rec)
    assert np.allclose(df['eda_slope_us_s'], 0.01)
    assert math.isclose(df['eda_baseline_us'].iloc[0], np.mean(2.0 + 0.01 * t[t < 120]))


def test_hifd_gravity_restoration_identity_orientation():
    quat = np.tile([1.0, 0.0, 0.0, 0.0], (5, 1))  # w, x, y, z
    restored = hifd_restore_gravity(quat, np.zeros((5, 3)))
    assert np.allclose(restored, [0.0, 0.0, 1.0])
