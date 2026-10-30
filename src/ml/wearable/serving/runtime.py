"""Serving runtime: registry ONNX heads + online FeatureEngine + Tier-2 fusion, one per device session.

Each frame is pushed into the same `FeatureEngine` the training tables were built with. Every head
is evaluated every `stride` frames (its training stride) once its window is full, and only when
the inputs it was trained on are present in that window; between evaluations the last output is
held. Missing inputs make a head `None` (reported as unavailable by fusion), never a guess from NaNs.

    rt = DeviceRuntime.from_registry()
    out = rt.step(t_s, values, rr_ms)            # fusion output dict, see serving/fusion.py

`replay_frames` is the batched equivalent for offline replays: identical windows, availability and
hold logic, with ONNX run once per head per recording instead of once per frame.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .. import paths
from ..features.engine import FeatureEngine
from ..schema import FIELD_NAMES, FRAME_PERIOD_S
from . import forest
from .calibration import apply_calibrator
from .fusion import FusionEngine

HEAD_NAMES = ('stress', 'fall', 'activity', 'hr_trust', 'rhythm')
HEAD_STRIDE = {'stress': 4, 'fall': 1, 'activity': 4, 'hr_trust': 2, 'rhythm': 4}   # = HeadSpec.stride
REGISTRY_PATH = paths.MODELS_DIR / 'registry.json'


def _present(block: np.ndarray, field: str) -> bool:
    return bool(np.isfinite(block[:, FIELD_NAMES.index(field)]).any())


def head_available(head: str, block: np.ndarray, rr: Sequence[Sequence[float]]) -> bool:
    """Whether the window holds the inputs the head was trained on (block: T x FIELD_NAMES)."""
    if head in ('fall', 'activity'):
        return _present(block, 'imu_acc_max_g')
    contact = block[:, FIELD_NAMES.index('ppg_finger_on')]
    if not (np.nan_to_num(contact) > 0).any():
        return False
    if head == 'stress':
        return _present(block, 'eda_us')
    if head == 'rhythm':                        # rhythm features are RR statistics: need beats in most frames
        return sum(1 for r in rr if len(r)) >= len(rr) / 2
    return True                                 # hr_trust


@dataclass
class HeadModel:
    head: str
    entry: dict
    sessions: list

    @classmethod
    def load(cls, head: str, entry: dict) -> 'HeadModel':
        """One predictor per member: the compiled forest when the registry lists one (parity-checked
        against the ONNX at P4; onnxruntime needs minutes to build large tree kernels), else ONNX."""
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        model_dir = paths.MODELS_DIR / entry['path']
        sessions = []
        for m in entry['members']:
            if f'forest_{m}.npz' in entry['files']:
                sessions.append(forest.load(model_dir / f'forest_{m}.npz'))
            else:
                sessions.append(ort.InferenceSession(str(model_dir / f'model_{m}.onnx'), opts,
                                                     providers=['CPUExecutionProvider']))
        return cls(head, entry, sessions)

    @property
    def feature_set(self) -> str:
        return self.entry['feature_set']

    @property
    def T(self) -> int:
        return self.entry['window_frames']

    @property
    def threshold(self) -> Optional[float]:
        return self.entry.get('threshold')

    def predict(self, X: np.ndarray, S: np.ndarray) -> np.ndarray:
        """Calibrated class probabilities of the (mean-combined) members."""
        feed = {'X': X.astype(np.float32), 'S': S.astype(np.float32)}
        probs = []
        for sess in self.sessions:
            if isinstance(sess, dict):                       # compiled forest (tabular input only)
                probs.append(forest.predict_proba(sess, feed['X']))
                continue
            names = {i.name for i in sess.get_inputs()}
            probs.append(sess.run(['proba'], {k: v for k, v in feed.items() if k in names})[0])
        return apply_calibrator(self.entry['calibration'], np.mean(probs, axis=0).astype(np.float64))

    def output(self, proba_row: np.ndarray):
        """What fusion consumes: P(positive) for binary heads, the class vector for activity."""
        return [float(p) for p in proba_row] if len(proba_row) > 2 else float(proba_row[1])


def load_heads(registry_path=REGISTRY_PATH, heads: Optional[Sequence[str]] = None) -> Dict[str, HeadModel]:
    reg = json.loads(registry_path.read_text(encoding='utf-8'))['heads']
    return {h: HeadModel.load(h, reg[h]) for h in (heads or HEAD_NAMES) if h in reg}


def fusion_for(models: Dict[str, HeadModel]) -> FusionEngine:
    """Fusion with the registry's Tier-1 thresholds, overridden by fusion.yaml `head_thresholds`
    (operating points chosen on the P5 end-to-end replay, e.g. the fall impact trigger)."""
    from .fusion import load_fusion_config
    cfg = load_fusion_config()
    thresholds = {h: m.threshold for h, m in models.items() if m.threshold is not None}
    thresholds.update({h: t for h, t in (cfg.get('head_thresholds') or {}).items() if h in models})
    versions = {h: m.entry['version'] for h, m in models.items()}
    return FusionEngine(cfg, thresholds, versions)


def _due(head: str, frames_seen: int, T: int) -> bool:
    i = frames_seen - 1                          # index of the frame just pushed
    return i >= T - 1 and (i - (T - 1)) % HEAD_STRIDE[head] == 0


def _window_inputs(engine: FeatureEngine, m: HeadModel):
    """(available, X row, sequence) for the head's current window."""
    block = np.stack(list(engine._values)[-m.T:])
    if not head_available(m.head, block, list(engine._rr)[-m.T:]):
        return False, None, None
    tab, seq = engine.features(m.feature_set)
    return True, np.array([tab[f] for f in m.entry['features']], dtype=np.float64), seq


class DeviceRuntime:
    """Streaming, one frame at a time (the serving path)."""

    def __init__(self, models: Dict[str, HeadModel]):
        self.models = models
        self.engine = FeatureEngine(sorted({m.feature_set for m in models.values()}))
        self.fusion = fusion_for(models)
        self.last: Dict[str, object] = {h: None for h in models}

    @classmethod
    def from_registry(cls, registry_path=REGISTRY_PATH) -> 'DeviceRuntime':
        return cls(load_heads(registry_path))

    def step(self, t: float, values: Dict[str, float], rr_ms: Sequence[float]) -> dict:
        self.engine.push(values, rr_ms)
        for h, m in self.models.items():
            if not _due(h, self.engine.frames_seen, m.T):
                continue
            ok, x, seq = _window_inputs(self.engine, m)
            self.last[h] = m.output(m.predict(x[None], seq[None])[0]) if ok else None
        return self.fusion.step(t, values, rr_ms, self.last)


def head_outputs(frames: pd.DataFrame, models: Dict[str, HeadModel]) -> Dict[str, List[object]]:
    """Per-frame held head outputs for a whole recording, batched (same logic as DeviceRuntime)."""
    engine = FeatureEngine(sorted({m.feature_set for m in models.values()}))
    values = frames[FIELD_NAMES].to_dict('records')
    rr = [list(x) for x in frames['rr_ms']]
    pending = {h: ([], [], [], []) for h in models}          # frame idx, X rows, sequences, available idx
    for i, (v, r) in enumerate(zip(values, rr)):
        engine.push(v, r)
        for h, m in models.items():
            if _due(h, engine.frames_seen, m.T):
                ok, x, seq = _window_inputs(engine, m)
                idx, xs, ss, avail = pending[h]
                idx.append(i)
                if ok:
                    avail.append(len(idx) - 1)
                    xs.append(x)
                    ss.append(seq)
    out = {}
    for h, m in models.items():
        idx, xs, ss, avail = pending[h]
        evals: List[object] = [None] * len(idx)
        if xs:
            proba = np.concatenate([m.predict(np.stack(xs[j:j + 50_000]), np.stack(ss[j:j + 50_000]))
                                    for j in range(0, len(xs), 50_000)])
            for k, row in zip(avail, proba):
                evals[k] = m.output(row)
        held, cur, e = [], None, 0
        for i in range(len(frames)):
            while e < len(idx) and idx[e] == i:
                cur = evals[e]
                e += 1
            held.append(cur)
        out[h] = held
    return out


def replay_frames(frames: pd.DataFrame, models: Dict[str, HeadModel], t0: float = 0.0) -> List[dict]:
    """Fusion outputs for every frame of one recording (offline replay)."""
    outs = head_outputs(frames, models)
    fusion = fusion_for(models)
    values = frames[FIELD_NAMES].to_dict('records')
    res = []
    for i, v in enumerate(values):
        heads = {h: outs[h][i] for h in models}
        res.append(fusion.step(t0 + i * FRAME_PERIOD_S, v, list(frames['rr_ms'].iloc[i]), heads))
    return res
