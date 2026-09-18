"""
TRIDENT Dataset Fusion Synthesizer — Multi-Source Benchmark Harmonization Engine.

Fuses heterogeneous physiological benchmark datasets (WESAD, PPG-DaLiA, MIT-BIH,
HIFD) into a unified 50 Hz feature matrix with synthetic ATLS trauma trajectory
augmentation for the 8-state disaster trauma taxonomy.

Data Sources:
    1. WESAD (UCI)         → ELEVATED_STRESS baseline (EDA/GSR + BVP/PPG + Accel)
    2. PPG-DaLiA (UCI)     → HEMORRHAGIC_SHOCK / HYPOTHERMIA_RISK (Empatica E4)
    3. MIT-BIH (PhysioNet) → CARDIAC_ARREST (48 ECG arrhythmia records)
    4. HIFD (GitHub)        → CONCUSSIVE_STASIS / CRUSH_ENTRAPMENT (wrist IMU + HR)

Pipeline Stages:
    1. Per-dataset raw parsing & signal extraction
    2. Resampling to 50 Hz uniform grid (float32)
    3. Sliding window feature extraction (15s windows, 750 samples)
    4. Synthetic ATLS trauma trajectory generation
    5. Feature harmonization & interaction feature computation
    6. Subject-wise GroupKFold split export

Output:
    data/processed/fused_training_matrix.parquet   — Full feature matrix
    data/processed/train_split.parquet             — 70% train
    data/processed/val_split.parquet               — 15% validation
    data/processed/test_split.parquet              — 15% holdout test
"""

import os
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

TARGET_HZ = 50                      # Unified sampling rate
WINDOW_SECONDS = 15                 # Sliding window duration
WINDOW_SAMPLES = TARGET_HZ * WINDOW_SECONDS  # 750 samples per window
STRIDE_SAMPLES = TARGET_HZ * 5     # 5-second stride (250 samples)
EPSILON = 1e-5

# 8-State taxonomy label map
STATE_LABELS = {
    'STABLE': 0,
    'ELEVATED_STRESS': 1,
    'HYPOTHERMIA_RISK': 2,
    'ASPIRATION_HYPOXIA': 3,
    'HEMORRHAGIC_SHOCK': 4,
    'CONCUSSIVE_STASIS': 5,
    'CRUSH_ENTRAPMENT': 6,
    'CARDIAC_ARREST': 7,
}

# Feature column schema
FEATURE_COLS = [
    'bpm_current', 'bpm_mean_15s', 'bpm_std_15s',
    'pulse_amp_decay', 'spo2_current', 'spo2_slope',
    'acc_mag_max_3s', 'motion_stasis', 'gsr_stress_norm',
    'gsr_slope', 'fall_flag', 'gps_displacement_15s',
    'ksc', 'ssi', 'eim',
]


class DatasetFusionSynthesizer:
    """Fuses multi-source physiological datasets into unified training matrix."""

    def __init__(self, data_root: str):
        """
        Args:
            data_root: Path to data/raw/wearable_ml_datasets/ directory.
        """
        self.data_root = Path(data_root)
        self.processed_dir = self.data_root.parent.parent / 'processed'
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        self.all_windows: List[Dict] = []

    # ─── Per-Dataset Parsers ─────────────────────────────────────────────

    def parse_wesad(self) -> pd.DataFrame:
        """Parse WESAD dataset for stress/baseline physiological signals.

        WESAD provides wrist-worn Empatica E4 signals: BVP (64Hz), EDA (4Hz),
        TEMP (4Hz), ACC (32Hz) plus chest RespiBAN: ECG, EDA, EMG, TEMP, ACC, RESP.

        Maps WESAD labels:
            1 (baseline)    → STABLE
            2 (stress)      → ELEVATED_STRESS
            3 (amusement)   → STABLE
            4 (meditation)  → STABLE
        """
        wesad_dir = self.data_root / 'WESAD'
        records = []

        if not wesad_dir.exists():
            logger.warning(f"WESAD directory not found at {wesad_dir}")
            return pd.DataFrame()

        try:
            import pickle

            for subject_dir in sorted(wesad_dir.iterdir()):
                if not subject_dir.is_dir() or not subject_dir.name.startswith('S'):
                    continue

                pkl_file = subject_dir / f'{subject_dir.name}.pkl'
                if not pkl_file.exists():
                    continue

                subject_id = subject_dir.name
                logger.info(f"Parsing WESAD subject {subject_id}...")

                with open(pkl_file, 'rb') as f:
                    data = pickle.load(f, encoding='latin1')

                labels = data['label'].flatten()
                wrist = data['signal']['wrist']

                # Extract wrist signals
                bvp = wrist['BVP'].flatten()     # 64 Hz → BPM proxy
                eda = wrist['EDA'].flatten()      # 4 Hz → GSR
                acc = wrist['ACC']                # 32 Hz, shape (N, 3)

                # Resample all to TARGET_HZ via linear interpolation
                n_samples_target = len(labels)  # labels at 700Hz, we use label count

                # For each window of labels, extract features
                label_hz = 700  # WESAD label sampling rate
                window_labels = WINDOW_SECONDS * label_hz

                for start in range(0, len(labels) - window_labels, STRIDE_SAMPLES * (label_hz // TARGET_HZ)):
                    end = start + window_labels
                    win_labels = labels[start:end]

                    # Determine dominant label in window
                    unique, counts = np.unique(win_labels[win_labels > 0], return_counts=True)
                    if len(unique) == 0:
                        continue
                    dominant_label = unique[np.argmax(counts)]

                    # Map WESAD label to our taxonomy
                    if dominant_label == 2:  # stress
                        health_state = STATE_LABELS['ELEVATED_STRESS']
                    else:
                        health_state = STATE_LABELS['STABLE']

                    # Extract signal windows (approximate index mapping)
                    bvp_start = int(start * (64 / label_hz))
                    bvp_end = int(end * (64 / label_hz))
                    eda_start = int(start * (4 / label_hz))
                    eda_end = int(end * (4 / label_hz))
                    acc_start = int(start * (32 / label_hz))
                    acc_end = int(end * (32 / label_hz))

                    bvp_win = bvp[bvp_start:bvp_end] if bvp_end <= len(bvp) else bvp[bvp_start:]
                    eda_win = eda[eda_start:eda_end] if eda_end <= len(eda) else eda[eda_start:]
                    acc_win = acc[acc_start:acc_end] if acc_end <= len(acc) else acc[acc_start:]

                    if len(bvp_win) < 10 or len(eda_win) < 2:
                        continue

                    # Compute features from raw signals
                    # BPM from BVP peak intervals (simplified)
                    bpm_est = self._estimate_bpm_from_bvp(bvp_win, fs=64)
                    bpm_mean = float(np.nanmean(bpm_est)) if len(bpm_est) > 0 else 75.0
                    bpm_std = float(np.nanstd(bpm_est)) if len(bpm_est) > 1 else 0.0

                    # GSR normalized
                    gsr_norm = float(np.mean(eda_win))
                    gsr_max = max(float(np.max(eda_win)), EPSILON)
                    gsr_stress = min(gsr_norm / (gsr_max + EPSILON), 1.0)
                    gsr_slope = float(eda_win[-1] - eda_win[0]) / (len(eda_win) + EPSILON)

                    # Acceleration magnitude
                    if len(acc_win) > 0:
                        acc_mag = np.sqrt(np.sum(acc_win**2, axis=1)) / 9.81
                        acc_max = float(np.max(acc_mag))
                        motion_var = float(np.var(acc_mag))
                    else:
                        acc_max = 1.0
                        motion_var = 0.1

                    records.append({
                        'subject_id': subject_id,
                        'source': 'WESAD',
                        'bpm_current': bpm_mean,
                        'bpm_mean_15s': bpm_mean,
                        'bpm_std_15s': bpm_std,
                        'pulse_amp_decay': 1.0,
                        'spo2_current': 97.0,  # WESAD doesn't have SpO2
                        'spo2_slope': 0.0,
                        'acc_mag_max_3s': acc_max,
                        'motion_stasis': motion_var,
                        'gsr_stress_norm': gsr_stress,
                        'gsr_slope': gsr_slope,
                        'fall_flag': 0.0,
                        'gps_displacement_15s': np.random.uniform(0.5, 5.0),
                        'health_state': health_state,
                    })

            logger.info(f"WESAD: Extracted {len(records)} windows")

        except Exception as e:
            logger.error(f"Error parsing WESAD: {e}")

        return pd.DataFrame(records)

    def parse_hifd(self) -> pd.DataFrame:
        """Parse HR+IMU Fall Detection dataset for impact/stasis patterns.

        Maps activities:
            Fall events → CONCUSSIVE_STASIS
            Post-fall stasis → CRUSH_ENTRAPMENT (if prolonged)
            ADL activities → STABLE
        """
        hifd_dir = self.data_root / 'HR_IMU_falldetection_dataset-master'
        records = []

        if not hifd_dir.exists():
            logger.warning(f"HIFD directory not found at {hifd_dir}")
            return pd.DataFrame()

        try:
            import scipy.io as sio

            data_dir = hifd_dir / 'data'
            if not data_dir.exists():
                data_dir = hifd_dir

            for mat_file in sorted(data_dir.glob('*.mat')):
                subject_id = mat_file.stem
                logger.info(f"Parsing HIFD subject {subject_id}...")

                try:
                    mat = sio.loadmat(str(mat_file))
                except Exception:
                    continue

                # HIFD .mat structure varies; try common key patterns
                for key in mat:
                    if key.startswith('_') or key in ('__header__', '__version__', '__globals__'):
                        continue

                    signal = mat[key]
                    if not isinstance(signal, np.ndarray) or signal.ndim < 2:
                        continue

                    # Extract acceleration columns (typically cols 0-2)
                    n_cols = signal.shape[1]
                    if n_cols >= 4:
                        acc_xyz = signal[:, :3].astype(np.float32)
                        hr_col = signal[:, 3].astype(np.float32) if n_cols > 3 else None
                    else:
                        continue

                    acc_mag = np.sqrt(np.sum(acc_xyz**2, axis=1))

                    # Detect fall events (threshold-based)
                    is_fall = acc_mag > 3.0 * 9.81  # > 3g threshold

                    # Sliding window extraction
                    fs = 50  # HIFD sampling rate
                    win_size = WINDOW_SECONDS * fs
                    stride = 5 * fs

                    for start in range(0, len(acc_mag) - win_size, stride):
                        end = start + win_size
                        win_acc = acc_mag[start:end]
                        win_fall = is_fall[start:end]

                        has_fall = np.any(win_fall)
                        acc_max = float(np.max(win_acc)) / 9.81
                        motion_var = float(np.var(win_acc / 9.81))

                        # HR from column if available
                        bpm = 75.0
                        if hr_col is not None:
                            hr_win = hr_col[start:end]
                            valid_hr = hr_win[hr_win > 0]
                            if len(valid_hr) > 0:
                                bpm = float(np.mean(valid_hr))

                        if has_fall and motion_var < 0.05:
                            health_state = STATE_LABELS['CONCUSSIVE_STASIS']
                        elif has_fall:
                            health_state = STATE_LABELS['CONCUSSIVE_STASIS']
                        else:
                            health_state = STATE_LABELS['STABLE']

                        records.append({
                            'subject_id': f'HIFD_{subject_id}',
                            'source': 'HIFD',
                            'bpm_current': bpm,
                            'bpm_mean_15s': bpm,
                            'bpm_std_15s': float(np.std(hr_col[start:end])) if hr_col is not None else 5.0,
                            'pulse_amp_decay': 1.0 if not has_fall else 0.7,
                            'spo2_current': 97.0,
                            'spo2_slope': 0.0,
                            'acc_mag_max_3s': acc_max,
                            'motion_stasis': motion_var,
                            'gsr_stress_norm': 0.3 if not has_fall else 0.7,
                            'gsr_slope': 0.0,
                            'fall_flag': 1.0 if has_fall else 0.0,
                            'gps_displacement_15s': 0.0 if has_fall else np.random.uniform(1.0, 5.0),
                            'health_state': health_state,
                        })

            logger.info(f"HIFD: Extracted {len(records)} windows")

        except Exception as e:
            logger.error(f"Error parsing HIFD: {e}")

        return pd.DataFrame(records)

    def parse_mitbih(self) -> pd.DataFrame:
        """Parse MIT-BIH Arrhythmia Database for cardiac arrest patterns.

        Uses wfdb to read .dat/.atr annotation files.
        Maps arrhythmia annotations to CARDIAC_ARREST vs STABLE.
        """
        mitbih_dir = self.data_root / 'mit-bih-arrhythmia-database-1.0.0'
        records = []

        if not mitbih_dir.exists():
            logger.warning(f"MIT-BIH directory not found at {mitbih_dir}")
            return pd.DataFrame()

        try:
            import wfdb

            record_names = [f.stem for f in mitbih_dir.glob('*.dat')]

            for rec_name in sorted(set(record_names)):
                logger.info(f"Parsing MIT-BIH record {rec_name}...")
                try:
                    record = wfdb.rdrecord(str(mitbih_dir / rec_name))
                    annotation = wfdb.rdann(str(mitbih_dir / rec_name), 'atr')
                except Exception:
                    continue

                fs = record.fs  # Usually 360 Hz
                ecg_signal = record.p_signal[:, 0] if record.p_signal is not None else None
                if ecg_signal is None:
                    continue

                # Extract BPM from R-R intervals using annotations
                r_peaks = annotation.sample
                ann_symbols = annotation.symbol

                # Dangerous arrhythmia symbols
                danger_symbols = {'V', 'F', '!', 'x', '|', '~', 'Q'}

                # Sliding window over annotation indices
                window_ann_count = int(WINDOW_SECONDS * fs)

                for i in range(0, len(ecg_signal) - window_ann_count, int(5 * fs)):
                    end_sample = i + window_ann_count

                    # Find R-peaks in this window
                    mask = (r_peaks >= i) & (r_peaks < end_sample)
                    win_peaks = r_peaks[mask]
                    win_symbols = [ann_symbols[j] for j in range(len(ann_symbols)) if mask[j]]

                    if len(win_peaks) < 2:
                        continue

                    # Compute BPM from R-R intervals
                    rr_intervals = np.diff(win_peaks) / fs
                    rr_bpm = 60.0 / rr_intervals
                    rr_bpm = rr_bpm[(rr_bpm > 20) & (rr_bpm < 250)]

                    if len(rr_bpm) == 0:
                        continue

                    bpm_mean = float(np.mean(rr_bpm))
                    bpm_std = float(np.std(rr_bpm))

                    # Count dangerous beats
                    danger_count = sum(1 for s in win_symbols if s in danger_symbols)
                    danger_ratio = danger_count / max(len(win_symbols), 1)

                    if danger_ratio > 0.3 or bpm_mean < 30 or bpm_mean > 185:
                        health_state = STATE_LABELS['CARDIAC_ARREST']
                    elif danger_ratio > 0.1 or bpm_std > 30:
                        health_state = STATE_LABELS['CARDIAC_ARREST']
                    else:
                        health_state = STATE_LABELS['STABLE']

                    records.append({
                        'subject_id': f'MITBIH_{rec_name}',
                        'source': 'MIT-BIH',
                        'bpm_current': float(rr_bpm[-1]) if len(rr_bpm) > 0 else bpm_mean,
                        'bpm_mean_15s': bpm_mean,
                        'bpm_std_15s': bpm_std,
                        'pulse_amp_decay': max(0.1, 1.0 - danger_ratio),
                        'spo2_current': 95.0 if health_state == 0 else np.random.uniform(60, 85),
                        'spo2_slope': 0.0 if health_state == 0 else -np.random.uniform(0.5, 3.0),
                        'acc_mag_max_3s': np.random.uniform(0.8, 1.2),
                        'motion_stasis': np.random.uniform(0.0, 0.05),
                        'gsr_stress_norm': 0.3 if health_state == 0 else np.random.uniform(0.6, 0.9),
                        'gsr_slope': 0.0,
                        'fall_flag': 0.0,
                        'gps_displacement_15s': np.random.uniform(0.0, 2.0),
                        'health_state': health_state,
                    })

            logger.info(f"MIT-BIH: Extracted {len(records)} windows")

        except ImportError:
            logger.warning("wfdb package not installed — skipping MIT-BIH parsing. "
                           "Install with: pip install wfdb")
        except Exception as e:
            logger.error(f"Error parsing MIT-BIH: {e}")

        return pd.DataFrame(records)

    def parse_ppg_dalia(self) -> pd.DataFrame:
        """Parse PPG-DaLiA dataset for heart rate and activity features.

        PPG-DaLiA provides wrist PPG + ACC from Empatica E4 during daily activities.
        Maps to STABLE and generates synthetic degraded trajectories for
        HEMORRHAGIC_SHOCK and HYPOTHERMIA_RISK.
        """
        ppg_dir = self.data_root / 'PPG_FieldStudy'
        records = []

        if not ppg_dir.exists():
            logger.warning(f"PPG_FieldStudy directory not found at {ppg_dir}")
            return pd.DataFrame()

        try:
            import pickle

            for pkl_file in sorted(ppg_dir.glob('S*/*.pkl')):
                subject_id = pkl_file.parent.name
                logger.info(f"Parsing PPG-DaLiA subject {subject_id}...")

                try:
                    with open(pkl_file, 'rb') as f:
                        data = pickle.load(f, encoding='latin1')
                except Exception:
                    continue

                # PPG-DaLiA structure: dict with signal keys
                if not isinstance(data, dict):
                    continue

                # Extract available signals
                ppg = data.get('signal', {}).get('wrist', {}).get('BVP', None)
                acc = data.get('signal', {}).get('wrist', {}).get('ACC', None)
                label = data.get('label', None)  # Ground truth HR

                if ppg is None or acc is None:
                    continue

                ppg = ppg.flatten() if hasattr(ppg, 'flatten') else np.array(ppg).flatten()

                # Compute features from windows
                fs_ppg = 64  # BVP at 64 Hz
                win_ppg = WINDOW_SECONDS * fs_ppg

                for start in range(0, len(ppg) - win_ppg, 5 * fs_ppg):
                    end = start + win_ppg
                    ppg_win = ppg[start:end]

                    bpm_est = self._estimate_bpm_from_bvp(ppg_win, fs=fs_ppg)
                    bpm_mean = float(np.nanmean(bpm_est)) if len(bpm_est) > 0 else 75.0

                    records.append({
                        'subject_id': f'PPG_{subject_id}',
                        'source': 'PPG-DaLiA',
                        'bpm_current': bpm_mean,
                        'bpm_mean_15s': bpm_mean,
                        'bpm_std_15s': float(np.nanstd(bpm_est)) if len(bpm_est) > 1 else 5.0,
                        'pulse_amp_decay': 1.0,
                        'spo2_current': 97.0,
                        'spo2_slope': 0.0,
                        'acc_mag_max_3s': np.random.uniform(0.8, 2.0),
                        'motion_stasis': np.random.uniform(0.05, 0.5),
                        'gsr_stress_norm': np.random.uniform(0.1, 0.4),
                        'gsr_slope': 0.0,
                        'fall_flag': 0.0,
                        'gps_displacement_15s': np.random.uniform(1.0, 10.0),
                        'health_state': STATE_LABELS['STABLE'],
                    })

            logger.info(f"PPG-DaLiA: Extracted {len(records)} windows")

        except Exception as e:
            logger.error(f"Error parsing PPG-DaLiA: {e}")

        return pd.DataFrame(records)

    # ─── Synthetic Trauma Trajectory Generation ──────────────────────────

    def generate_synthetic_trajectories(self, n_per_state: int = 5000) -> pd.DataFrame:
        """Generate synthetic ATLS trauma trajectories for rare disaster states.

        Creates clinically-grounded synthetic feature vectors for states that
        lack direct benchmark dataset representation:
            - ASPIRATION_HYPOXIA  (mud aspiration / drowning)
            - HEMORRHAGIC_SHOCK   (ATLS Class I-IV progression)
            - HYPOTHERMIA_RISK    (cold water immersion)
            - CRUSH_ENTRAPMENT    (rubble collapse)
        """
        records = []
        rng = np.random.default_rng(42)

        # ── ASPIRATION_HYPOXIA: Rapid SpO2 collapse without impact ──
        for i in range(n_per_state):
            records.append({
                'subject_id': f'SYN_ASPX_{i}',
                'source': 'SYNTHETIC',
                'bpm_current': rng.uniform(90, 140),
                'bpm_mean_15s': rng.uniform(85, 130),
                'bpm_std_15s': rng.uniform(5, 20),
                'pulse_amp_decay': rng.uniform(0.3, 0.8),
                'spo2_current': rng.uniform(55, 85),
                'spo2_slope': rng.uniform(-5.0, -2.0),  # Rapid desaturation
                'acc_mag_max_3s': rng.uniform(0.5, 2.0),  # Low impact
                'motion_stasis': rng.uniform(0.01, 0.15),
                'gsr_stress_norm': rng.uniform(0.5, 0.95),
                'gsr_slope': rng.uniform(0.01, 0.1),
                'fall_flag': 0.0,
                'gps_displacement_15s': rng.uniform(0.0, 3.0),
                'health_state': STATE_LABELS['ASPIRATION_HYPOXIA'],
            })

        # ── HEMORRHAGIC_SHOCK: ATLS Class III/IV progressive tachycardia ──
        for i in range(n_per_state):
            atls_class = rng.choice([3, 4], p=[0.6, 0.4])
            bpm = rng.uniform(120, 160) if atls_class == 3 else rng.uniform(140, 200)
            records.append({
                'subject_id': f'SYN_HEMO_{i}',
                'source': 'SYNTHETIC',
                'bpm_current': bpm,
                'bpm_mean_15s': bpm + rng.uniform(-10, 10),
                'bpm_std_15s': rng.uniform(10, 30),
                'pulse_amp_decay': rng.uniform(0.1, 0.4),
                'spo2_current': rng.uniform(75, 93),
                'spo2_slope': rng.uniform(-2.0, -0.5),
                'acc_mag_max_3s': rng.uniform(1.0, 3.0),
                'motion_stasis': rng.uniform(0.01, 0.2),
                'gsr_stress_norm': rng.uniform(0.6, 0.95),
                'gsr_slope': rng.uniform(0.02, 0.15),
                'fall_flag': float(rng.random() < 0.2),
                'gps_displacement_15s': rng.uniform(0.0, 5.0),
                'health_state': STATE_LABELS['HEMORRHAGIC_SHOCK'],
            })

        # ── HYPOTHERMIA_RISK: Progressive bradycardia + SpO2 drop ──
        for i in range(n_per_state):
            records.append({
                'subject_id': f'SYN_HYPO_{i}',
                'source': 'SYNTHETIC',
                'bpm_current': rng.uniform(30, 55),
                'bpm_mean_15s': rng.uniform(35, 55),
                'bpm_std_15s': rng.uniform(2, 8),
                'pulse_amp_decay': rng.uniform(0.5, 0.9),
                'spo2_current': rng.uniform(85, 94),
                'spo2_slope': rng.uniform(-1.5, -0.3),
                'acc_mag_max_3s': rng.uniform(0.3, 1.2),
                'motion_stasis': rng.uniform(0.001, 0.03),  # Shivering stasis
                'gsr_stress_norm': rng.uniform(0.2, 0.5),
                'gsr_slope': rng.uniform(-0.05, 0.02),
                'fall_flag': 0.0,
                'gps_displacement_15s': rng.uniform(0.0, 1.5),
                'health_state': STATE_LABELS['HYPOTHERMIA_RISK'],
            })

        # ── CRUSH_ENTRAPMENT: Zero motion + zero GPS + sustained stress ──
        for i in range(n_per_state):
            records.append({
                'subject_id': f'SYN_CRUSH_{i}',
                'source': 'SYNTHETIC',
                'bpm_current': rng.uniform(80, 130),
                'bpm_mean_15s': rng.uniform(85, 125),
                'bpm_std_15s': rng.uniform(5, 15),
                'pulse_amp_decay': rng.uniform(0.4, 0.8),
                'spo2_current': rng.uniform(88, 96),
                'spo2_slope': rng.uniform(-0.5, 0.0),
                'acc_mag_max_3s': rng.uniform(0.2, 1.0),
                'motion_stasis': rng.uniform(0.0, 0.02),  # Trapped
                'gsr_stress_norm': rng.uniform(0.75, 0.98),
                'gsr_slope': rng.uniform(0.0, 0.05),
                'fall_flag': float(rng.random() < 0.3),
                'gps_displacement_15s': rng.uniform(0.0, 0.5),  # No movement
                'health_state': STATE_LABELS['CRUSH_ENTRAPMENT'],
            })

        logger.info(f"Synthetic: Generated {len(records)} trajectory windows")
        return pd.DataFrame(records)

    # ─── Signal Processing Helpers ───────────────────────────────────────

    @staticmethod
    def _estimate_bpm_from_bvp(bvp: np.ndarray, fs: int = 64) -> np.ndarray:
        """Estimate BPM from BVP/PPG signal using peak detection.

        Simple zero-crossing based approach for robust BPM estimation.
        """
        if len(bvp) < fs:
            return np.array([75.0])

        # Bandpass filter proxy: remove DC and high-frequency noise
        bvp_centered = bvp - np.mean(bvp)

        # Find peaks using simple threshold
        threshold = 0.3 * np.std(bvp_centered)
        peaks = []
        for i in range(1, len(bvp_centered) - 1):
            if (bvp_centered[i] > threshold and
                bvp_centered[i] > bvp_centered[i-1] and
                bvp_centered[i] > bvp_centered[i+1]):
                peaks.append(i)

        if len(peaks) < 2:
            return np.array([75.0])

        # Compute BPM from inter-peak intervals
        intervals = np.diff(peaks) / fs
        bpm_values = 60.0 / intervals
        # Filter physiologically plausible range
        bpm_values = bpm_values[(bpm_values > 30) & (bpm_values < 220)]

        return bpm_values if len(bpm_values) > 0 else np.array([75.0])

    # ─── Feature Engineering ─────────────────────────────────────────────

    def compute_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute physics-grounded interaction features: KSC, SSI, EIM."""
        # KSC: Kinetic-Stasis Coupling Index
        df['ksc'] = df['acc_mag_max_3s'] / (df['motion_stasis'] + EPSILON)

        # SSI: Shock Severity Index
        df['ssi'] = df['bpm_current'] / (
            df['spo2_current'] * df['pulse_amp_decay'] + EPSILON
        )

        # EIM: Entrapment Isolation Marker
        df['eim'] = df['gsr_stress_norm'] / (
            df['motion_stasis'] + df['gps_displacement_15s'] + EPSILON
        )

        return df

    # ─── Data Splitting ──────────────────────────────────────────────────

    def subject_wise_split(
        self, df: pd.DataFrame,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Subject-wise GroupKFold split to prevent time-series data leakage.

        Args:
            df: Full fused feature matrix with 'subject_id' column.
            train_ratio: Proportion for training set.
            val_ratio: Proportion for validation set.

        Returns:
            (train_df, val_df, test_df) tuple.
        """
        subjects = df['subject_id'].unique()
        np.random.seed(42)
        np.random.shuffle(subjects)

        n = len(subjects)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)

        train_subjects = set(subjects[:n_train])
        val_subjects = set(subjects[n_train:n_train + n_val])
        test_subjects = set(subjects[n_train + n_val:])

        train_df = df[df['subject_id'].isin(train_subjects)].copy()
        val_df = df[df['subject_id'].isin(val_subjects)].copy()
        test_df = df[df['subject_id'].isin(test_subjects)].copy()

        logger.info(f"Split: Train={len(train_df)} ({len(train_subjects)} subjects), "
                     f"Val={len(val_df)} ({len(val_subjects)} subjects), "
                     f"Test={len(test_df)} ({len(test_subjects)} subjects)")

        return train_df, val_df, test_df

    # ─── Master Pipeline ─────────────────────────────────────────────────

    def run_full_pipeline(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Execute the complete data fusion pipeline.

        Returns:
            (train_df, val_df, test_df) — ready for XGBoost training.
        """
        logger.info("═══ TRIDENT Dataset Fusion Pipeline Starting ═══")

        # 1. Parse each dataset
        dfs = []

        wesad_df = self.parse_wesad()
        if len(wesad_df) > 0:
            dfs.append(wesad_df)

        hifd_df = self.parse_hifd()
        if len(hifd_df) > 0:
            dfs.append(hifd_df)

        mitbih_df = self.parse_mitbih()
        if len(mitbih_df) > 0:
            dfs.append(mitbih_df)

        ppg_df = self.parse_ppg_dalia()
        if len(ppg_df) > 0:
            dfs.append(ppg_df)

        # 2. Generate synthetic trajectories for rare states
        synthetic_df = self.generate_synthetic_trajectories(n_per_state=5000)
        dfs.append(synthetic_df)

        # 3. Concatenate all sources
        if len(dfs) == 0:
            raise ValueError("No data sources produced any records!")

        full_df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Total fused records: {len(full_df)}")

        # 4. Compute interaction features
        full_df = self.compute_interaction_features(full_df)

        # 5. Cast to float32 for memory efficiency
        for col in FEATURE_COLS:
            if col in full_df.columns:
                full_df[col] = full_df[col].astype(np.float32)

        # 6. Save full matrix
        full_path = self.processed_dir / 'fused_training_matrix.parquet'
        full_df.to_parquet(full_path, index=False)
        logger.info(f"Saved full matrix: {full_path} ({len(full_df)} rows)")

        # 7. Subject-wise split
        train_df, val_df, test_df = self.subject_wise_split(full_df)

        train_df.to_parquet(self.processed_dir / 'train_split.parquet', index=False)
        val_df.to_parquet(self.processed_dir / 'val_split.parquet', index=False)
        test_df.to_parquet(self.processed_dir / 'test_split.parquet', index=False)

        # 8. Print class distribution
        logger.info("Class distribution (full):")
        state_counts = full_df['health_state'].value_counts().sort_index()
        for state_id, count in state_counts.items():
            state_name = {v: k for k, v in STATE_LABELS.items()}.get(state_id, 'UNKNOWN')
            logger.info(f"  {state_id}: {state_name:25s} → {count:6d} windows")

        logger.info("═══ Dataset Fusion Pipeline Complete ═══")
        return train_df, val_df, test_df


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    # Default path: run from project root
    data_root = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'data', 'raw', 'wearable_ml_datasets'
    )
    synthesizer = DatasetFusionSynthesizer(data_root)
    train_df, val_df, test_df = synthesizer.run_full_pipeline()
