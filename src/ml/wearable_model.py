"""
TRIDENT Wearable Health Predictor — 8-State Disaster Trauma Classification Engine.

Provides real-time health state classification from ESP32 wearable sensor telemetry
using a trained XGBoost model with deterministic rule-based fallback when the model
file (.pkl) is unavailable.

Architecture:
    - Single-pass XGBoost multi-class classifier (< 0.5ms inference)
    - 12 base features + 3 physics interaction features (KSC, SSI, EIM)
    - Native NaN default-split branching for missing sensor data
    - Deterministic heuristic fallback for pre-training deployment

8-State Disaster Trauma Taxonomy:
    0: STABLE              — Nominal vitals & activity
    1: ELEVATED_STRESS     — Panic / autonomic shock (GSR > 0.8, HR elevated)
    2: HYPOTHERMIA_RISK    — Sub-zero immersion (BPM < 50, falling SpO2)
    3: ASPIRATION_HYPOXIA  — Mud aspiration / drowning (rapid SpO2 collapse)
    4: HEMORRHAGIC_SHOCK   — Arterial bleeding (BPM > 130, pulse_amp_decay < 0.4)
    5: CONCUSSIVE_STASIS   — Head/spinal impact (acc > 4.5g, motion stasis)
    6: CRUSH_ENTRAPMENT    — Rubble collapse (stasis + zero GPS + high GSR)
    7: CARDIAC_ARREST      — Sudden pulse collapse (BPM < 30 or > 185)
"""

import os
import logging
import numpy as np
from typing import Dict, Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

HEALTH_STATES = {
    0: 'STABLE',
    1: 'ELEVATED_STRESS',
    2: 'HYPOTHERMIA_RISK',
    3: 'ASPIRATION_HYPOXIA',
    4: 'HEMORRHAGIC_SHOCK',
    5: 'CONCUSSIVE_STASIS',
    6: 'CRUSH_ENTRAPMENT',
    7: 'CARDIAC_ARREST',
}

FEATURE_NAMES = [
    'bpm_current', 'bpm_mean_15s', 'bpm_std_15s',
    'pulse_amp_decay', 'spo2_current', 'spo2_slope',
    'acc_mag_max_3s', 'motion_stasis', 'gsr_stress_norm',
    'gsr_slope', 'fall_flag', 'gps_displacement_15s',
    # Interaction features
    'ksc', 'ssi', 'eim',
]

WINDOW_SIZE = 10  # Rolling window of 10 telemetry frames (~15s at 1.5s cadence)
EPSILON = 1e-5    # Numerical stability constant


class WearableHealthPredictor:
    """Unified 8-state wearable health classifier with XGBoost + fallback."""

    def __init__(self, model_path: Optional[str] = None):
        """Initialize predictor, loading trained XGBoost model if available.

        Args:
            model_path: Absolute or relative path to the trained .pkl model file.
                        Defaults to src/ml/wearable_health_model.pkl relative to
                        the project root.
        """
        self.model = None
        self.model_loaded = False
        self._rolling_buffer: Dict[str, deque] = {}  # per-device rolling windows

        if model_path is None:
            # Default path relative to this file's location
            model_path = os.path.join(os.path.dirname(__file__), 'wearable_health_model.pkl')

        self._load_model(model_path)

    def _load_model(self, model_path: str) -> None:
        """Attempt to load the trained XGBoost model from disk."""
        try:
            if os.path.exists(model_path):
                import joblib
                self.model = joblib.load(model_path)
                self.model_loaded = True
                logger.info(f"✅ WearableHealthPredictor: XGBoost model loaded from {model_path}")
            else:
                logger.warning(
                    f"⚠️ WearableHealthPredictor: Model file not found at {model_path}. "
                    "Using deterministic heuristic fallback mode."
                )
        except Exception as e:
            logger.error(f"❌ WearableHealthPredictor: Failed to load model — {e}. "
                         "Falling back to heuristic mode.")
            self.model = None
            self.model_loaded = False

    # ─── Feature Extraction ──────────────────────────────────────────────

    def _get_device_buffer(self, device_id: str) -> deque:
        """Get or create a rolling buffer for a specific device."""
        if device_id not in self._rolling_buffer:
            self._rolling_buffer[device_id] = deque(maxlen=WINDOW_SIZE)
        return self._rolling_buffer[device_id]

    def _sanitize_telemetry(self, raw: Dict) -> Dict:
        """Pre-filter telemetry: reject out-of-bound I2C spikes, mask disconnects.

        Returns sanitized dict with np.nan for invalid/disconnected sensors.
        """
        bpm = float(raw.get('bpm', 0.0))
        spo2 = float(raw.get('spo2', 0.0))
        acc_mag = float(raw.get('acc_mag', 0.0))
        gyro_mag = float(raw.get('gyro_mag', 0.0))
        gsr_norm = float(raw.get('gsr_norm', 0.0))
        fall_detected = bool(raw.get('fall_detected', False))
        vitals_cat = raw.get('vitals_cat', 'Unknown')
        lat = float(raw.get('lat', 0.0))
        lng = float(raw.get('lng', 0.0))

        # Reject corrupted I2C spikes
        if bpm > 250 or bpm < 0:
            bpm = np.nan
        if spo2 > 100 or spo2 < 0:
            spo2 = np.nan

        # Sensor disconnect: "No Finger" → mask vitals as NaN
        if vitals_cat == 'No Finger' or spo2 == 0:
            spo2 = np.nan
            bpm = np.nan

        return {
            'bpm': bpm,
            'spo2': spo2,
            'acc_mag': acc_mag,
            'gyro_mag': gyro_mag,
            'gsr_norm': gsr_norm,
            'fall_detected': fall_detected,
            'lat': lat,
            'lng': lng,
        }

    def _compute_gps_displacement(self, buffer: deque) -> float:
        """Compute GPS displacement over the rolling window (Haversine approx)."""
        if len(buffer) < 2:
            return 0.0

        first = buffer[0]
        last = buffer[-1]
        lat1, lng1 = first.get('lat', 0.0), first.get('lng', 0.0)
        lat2, lng2 = last.get('lat', 0.0), last.get('lng', 0.0)

        # Quick equirectangular approximation (meters)
        dlat = np.radians(lat2 - lat1)
        dlng = np.radians(lng2 - lng1) * np.cos(np.radians((lat1 + lat2) / 2))
        return np.sqrt(dlat**2 + dlng**2) * 6371000  # Earth radius in meters

    def extract_features(self, device_id: str, raw_telemetry: Dict) -> np.ndarray:
        """Extract the 15-feature vector from rolling telemetry window.

        Args:
            device_id: Unique wearable device identifier.
            raw_telemetry: Latest telemetry snapshot from ESP32.

        Returns:
            1-D numpy array of shape (15,) with float32 features.
            Missing sensors are represented as np.nan for XGBoost native handling.
        """
        sanitized = self._sanitize_telemetry(raw_telemetry)
        buffer = self._get_device_buffer(device_id)
        buffer.append(sanitized)

        # ── Base features from rolling window ──
        bpms = np.array([f['bpm'] for f in buffer], dtype=np.float32)
        spo2s = np.array([f['spo2'] for f in buffer], dtype=np.float32)
        accs = np.array([f['acc_mag'] for f in buffer], dtype=np.float32)
        gsrs = np.array([f['gsr_norm'] for f in buffer], dtype=np.float32)

        bpm_current = sanitized['bpm']
        bpm_mean = float(np.nanmean(bpms)) if len(bpms) > 0 else np.nan
        bpm_std = float(np.nanstd(bpms)) if len(bpms) > 1 else 0.0

        # Pulse amplitude decay proxy: ratio of current BPM variance to baseline
        # In production this would use raw PPG waveform; here we approximate
        pulse_amp_decay = 1.0  # default nominal
        if len(bpms) >= 3 and not np.all(np.isnan(bpms)):
            recent_range = float(np.nanmax(bpms[-3:])) - float(np.nanmin(bpms[-3:]))
            full_range = float(np.nanmax(bpms)) - float(np.nanmin(bpms))
            if full_range > EPSILON:
                pulse_amp_decay = min(recent_range / (full_range + EPSILON), 1.0)

        spo2_current = sanitized['spo2']

        # SpO2 slope: rate of change per sample
        spo2_slope = 0.0
        valid_spo2 = spo2s[~np.isnan(spo2s)]
        if len(valid_spo2) >= 2:
            spo2_slope = float(valid_spo2[-1] - valid_spo2[0]) / len(valid_spo2)

        acc_mag_max_3s = float(np.nanmax(accs[-2:])) if len(accs) >= 1 else 0.0

        # Motion stasis: variance of acceleration magnitude
        motion_stasis = float(np.nanvar(accs)) if len(accs) > 1 else 0.0

        gsr_stress_norm = sanitized['gsr_norm']

        # GSR slope
        gsr_slope = 0.0
        valid_gsr = gsrs[~np.isnan(gsrs)]
        if len(valid_gsr) >= 2:
            gsr_slope = float(valid_gsr[-1] - valid_gsr[0]) / len(valid_gsr)

        fall_flag = 1.0 if sanitized['fall_detected'] else 0.0
        gps_disp = self._compute_gps_displacement(buffer)

        # ── Interaction features ──
        # KSC: Kinetic-Stasis Coupling Index
        ksc = acc_mag_max_3s / (motion_stasis + EPSILON)

        # SSI: Shock Severity Index
        ssi_denom = (spo2_current if not np.isnan(spo2_current) else 95.0) * (pulse_amp_decay + EPSILON)
        ssi = (bpm_current if not np.isnan(bpm_current) else 75.0) / (ssi_denom + EPSILON)

        # EIM: Entrapment Isolation Marker
        eim = gsr_stress_norm / (motion_stasis + gps_disp + EPSILON)

        features = np.array([
            bpm_current, bpm_mean, bpm_std,
            pulse_amp_decay, spo2_current, spo2_slope,
            acc_mag_max_3s, motion_stasis, gsr_stress_norm,
            gsr_slope, fall_flag, gps_disp,
            ksc, ssi, eim,
        ], dtype=np.float32)

        return features

    # ─── Prediction ──────────────────────────────────────────────────────

    def predict(self, device_id: str, raw_telemetry: Dict) -> Dict:
        """Run health state classification on latest telemetry.

        Returns:
            Dict with keys:
                - ml_health_state (str): One of the 8 state names
                - ml_state_id (int): State integer code 0-7
                - ml_risk_score (float): Risk probability 0.0 - 1.0
                - ml_mode (str): 'xgboost' or 'heuristic'
                - sensor_warning (str|None): Warning if sensors disconnected
        """
        features = self.extract_features(device_id, raw_telemetry)

        # Detect sensor disconnect
        sensor_warning = None
        vitals_cat = raw_telemetry.get('vitals_cat', 'Unknown')
        if vitals_cat == 'No Finger':
            sensor_warning = 'SENSOR_DISCONNECT'

        if self.model_loaded and self.model is not None:
            return self._predict_xgboost(features, sensor_warning)
        else:
            return self._predict_heuristic(features, sensor_warning)

    def _predict_xgboost(self, features: np.ndarray, sensor_warning: Optional[str]) -> Dict:
        """Run prediction through the trained XGBoost model."""
        try:
            X = features.reshape(1, -1)
            probas = self.model.predict_proba(X)[0]
            state_id = int(np.argmax(probas))
            risk_score = float(1.0 - probas[0])  # 1 - P(STABLE)

            return {
                'ml_health_state': HEALTH_STATES[state_id],
                'ml_state_id': state_id,
                'ml_risk_score': round(min(max(risk_score, 0.0), 1.0), 4),
                'ml_mode': 'xgboost',
                'sensor_warning': sensor_warning,
            }
        except Exception as e:
            logger.error(f"XGBoost prediction failed: {e}. Falling back to heuristic.")
            return self._predict_heuristic(features, sensor_warning)

    def _predict_heuristic(self, features: np.ndarray, sensor_warning: Optional[str]) -> Dict:
        """Deterministic rule-based fallback classification.

        Uses clinically-grounded physiological thresholds from the implementation
        plan to classify health state when the trained model is unavailable.
        """
        bpm = features[0]
        spo2 = features[4]
        spo2_slope = features[5]
        acc_max = features[6]
        motion_stasis = features[7]
        gsr = features[8]
        fall_flag = features[10]
        gps_disp = features[11]
        pulse_amp = features[3]

        state_id = 0  # Default: STABLE
        risk_score = 0.05

        # Check for NaN (sensor disconnect)
        bpm_valid = not np.isnan(bpm)
        spo2_valid = not np.isnan(spo2)

        # ── Rule cascade (highest acuity first) ──

        # 7: CARDIAC_ARREST — extreme arrhythmia or pulselessness
        if bpm_valid and (bpm < 30 or bpm > 185):
            state_id = 7
            risk_score = 0.95
        # 5: CONCUSSIVE_STASIS — high-g impact + immediate stasis
        elif acc_max > 4.5 and motion_stasis < 0.02:
            state_id = 5
            risk_score = 0.88
        # 3: ASPIRATION_HYPOXIA — rapid SpO2 collapse without impact
        elif spo2_valid and spo2_slope < -2.0 and acc_max < 2.5:
            state_id = 3
            risk_score = 0.90
        # 4: HEMORRHAGIC_SHOCK — tachycardia + PPG decay + pain
        elif bpm_valid and bpm > 130 and pulse_amp < 0.4 and gsr > 0.5:
            state_id = 4
            risk_score = 0.85
        # 6: CRUSH_ENTRAPMENT — stasis + no GPS movement + high stress
        elif motion_stasis < 0.02 and gps_disp < 1.0 and gsr > 0.75:
            state_id = 6
            risk_score = 0.82
        # 2: HYPOTHERMIA_RISK — progressive bradycardia
        elif bpm_valid and bpm < 50 and spo2_valid and spo2 < 94:
            state_id = 2
            risk_score = 0.70
        # 1: ELEVATED_STRESS — high GSR + elevated HR
        elif gsr > 0.8 and bpm_valid and bpm > 100:
            state_id = 1
            risk_score = 0.45
        # Fall detected but no other critical indicators
        elif fall_flag > 0.5:
            state_id = 5
            risk_score = 0.60
        # Moderate stress
        elif gsr > 0.6 and bpm_valid and bpm > 90:
            state_id = 1
            risk_score = 0.30
        # Default: STABLE
        else:
            state_id = 0
            risk_score = 0.05

        return {
            'ml_health_state': HEALTH_STATES[state_id],
            'ml_state_id': state_id,
            'ml_risk_score': round(min(max(risk_score, 0.0), 1.0), 4),
            'ml_mode': 'heuristic',
            'sensor_warning': sensor_warning,
        }

    def get_status(self) -> Dict:
        """Return predictor status for health checks."""
        return {
            'model_loaded': self.model_loaded,
            'mode': 'xgboost' if self.model_loaded else 'heuristic',
            'active_devices': list(self._rolling_buffer.keys()),
            'window_size': WINDOW_SIZE,
            'feature_count': len(FEATURE_NAMES),
            'health_states': list(HEALTH_STATES.values()),
        }
