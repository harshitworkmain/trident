"""Online feature engine: one per device session.

The offline head-dataset builder replays every emulated recording through this same class,
so training features and live features are produced by identical code.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from ..schema import FIELD_NAMES, Frame
from .frame_features import FEATURE_SETS, Calibrator, Window, compute


class FeatureEngine:
    def __init__(self, feature_sets: Optional[Iterable[str]] = None) -> None:
        self.feature_sets = list(feature_sets or FEATURE_SETS)
        self.maxlen = max(FEATURE_SETS[n].T for n in self.feature_sets)
        self._values: deque = deque(maxlen=self.maxlen)
        self._rr: deque = deque(maxlen=self.maxlen)
        self.calibrator = Calibrator()
        self.frames_seen = 0

    def push(self, values: Dict[str, float], rr_ms: Sequence[float]) -> None:
        row = np.array([values.get(k, np.nan) for k in FIELD_NAMES], dtype=np.float64)
        self._values.append(row)
        self._rr.append([float(r) for r in rr_ms])
        self.calibrator.update(values)
        self.frames_seen += 1

    def push_frame(self, frame: Frame) -> None:
        self.push(frame.values, frame.rr_ms)

    def ready(self, feature_set: str) -> bool:
        return len(self._values) >= FEATURE_SETS[feature_set].T

    def window(self, T: int) -> Window:
        block = np.stack(list(self._values)[-T:])
        return Window(v={k: block[:, i] for i, k in enumerate(FIELD_NAMES)},
                      rr=list(self._rr)[-T:], calib=self.calibrator.values())

    def features(self, feature_set: str) -> Tuple[Dict[str, float], np.ndarray]:
        if not self.ready(feature_set):
            raise ValueError(f'{feature_set} needs {FEATURE_SETS[feature_set].T} frames, have {len(self._values)}')
        return compute(feature_set, self.window(FEATURE_SETS[feature_set].T))


def replay(values: List[Dict[str, float]], rr: List[List[float]], feature_set: str,
           stride: int, phase: int = 0, extra_ends: Optional[Iterable[int]] = None
           ) -> List[Tuple[int, Dict[str, float], np.ndarray]]:
    """Feed a recording frame by frame and emit features every `stride` frames.

    `extra_ends` adds windows ending at specific frames (e.g. around motion peaks); every
    frame is still pushed, so calibration state matches a live session exactly.
    Returns (end_frame_index, tabular, sequence) for each emitted window.
    """
    engine = FeatureEngine([feature_set])
    T = FEATURE_SETS[feature_set].T
    extra = set(extra_ends or ())
    out = []
    for i, (v, r) in enumerate(zip(values, rr)):
        engine.push(v, r)
        if i >= T - 1 and ((i - (T - 1) - phase) % stride == 0 or i in extra):
            tab, seq = engine.features(feature_set)
            out.append((i, tab, seq))
    return out
