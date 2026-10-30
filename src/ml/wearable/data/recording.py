"""Common in-memory representation of one raw recording, independent of dataset."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np


@dataclass
class Signal:
    """Uniformly sampled signal starting at t0 seconds (relative to recording start)."""

    data: np.ndarray            # (n,) or (n, channels)
    fs: float
    t0: float = 0.0
    kind: str = 'continuous'    # 'continuous' (aggregate by mean) | 'categorical' (by mode)

    @property
    def duration(self) -> float:
        return self.t0 + len(self.data) / self.fs

    def times(self) -> np.ndarray:
        return self.t0 + np.arange(len(self.data)) / self.fs


@dataclass
class Recording:
    """Raw sensor streams in canonical units plus labels for one subject/trial.

    Canonical units: acceleration in g *including* gravity, angular rate in deg/s,
    EDA in microsiemens, skin temperature in degC, beat times in seconds.
    """

    dataset: str
    subject: str
    trial: str
    placement: str
    acc: Optional[Signal] = None           # (n, 3) g
    gyro: Optional[Signal] = None          # (n, 3) deg/s
    bvp: Optional[Signal] = None           # raw optical pulse wave (arbitrary units)
    beats_s: Optional[np.ndarray] = None   # beat times when known (ECG R-peaks / pulse edges)
    beat_symbols: Optional[np.ndarray] = None  # per-beat annotation symbol (MIT-BIH)
    eda: Optional[Signal] = None           # uS
    temp: Optional[Signal] = None          # degC
    labels: Dict[str, Signal] = field(default_factory=dict)
    state_labels: Dict[str, Tuple[np.ndarray, np.ndarray]] = field(default_factory=dict)
    meta: Dict[str, object] = field(default_factory=dict)  # constants copied onto every frame

    @property
    def duration(self) -> float:
        spans = [s.duration for s in (self.acc, self.gyro, self.bvp, self.eda, self.temp) if s]
        spans += [s.duration for s in self.labels.values()]
        if self.beats_s is not None and len(self.beats_s):
            spans.append(float(self.beats_s[-1]))
        if 'duration_s' in self.meta:
            spans.append(float(self.meta['duration_s']))
        return max(spans) if spans else 0.0
