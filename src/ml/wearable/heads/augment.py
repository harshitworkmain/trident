"""Make ECG beat annotations look like wrist-PPG beat detections.

The rhythm head learns from MIT-BIH ECG beats, but the device measures beats optically at
the wrist. Each augmented copy perturbs the true beat times with:

* timing jitter  - Gaussian per-beat noise giving an RR error of `sigma_rr_ms`,
* missed beats   - each beat dropped with probability `p_miss`,
* spurious beats - an extra detection inside an interval with probability `p_extra`.

Ranges are calibrated on PPG-DaLiA, where wrist PPG and chest ECG were recorded together
(measured at rest, 2026-10-30: median |RR error| 58 ms, beat-count ratio IQR 0.96-1.03).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SIGMA_RR_MS = (30.0, 90.0)
P_MISS = (0.01, 0.06)
P_EXTRA = (0.0, 0.04)


@dataclass(frozen=True)
class PPGNoise:
    sigma_rr_ms: float
    p_miss: float
    p_extra: float

    @classmethod
    def sample(cls, rng: np.random.Generator) -> 'PPGNoise':
        return cls(rng.uniform(*SIGMA_RR_MS), rng.uniform(*P_MISS), rng.uniform(*P_EXTRA))


def ppg_like_beats(beats_s: np.ndarray, noise: PPGNoise, rng: np.random.Generator) -> np.ndarray:
    beats = np.asarray(beats_s, dtype=np.float64)
    sigma_t = noise.sigma_rr_ms / 1000.0 / np.sqrt(2.0)  # RR = difference of two jittered beats
    jittered = beats + rng.normal(0.0, sigma_t, size=len(beats))
    kept = jittered[rng.random(len(jittered)) >= noise.p_miss]
    gaps = np.flatnonzero(rng.random(max(len(kept) - 1, 0)) < noise.p_extra)
    extra = kept[gaps] + rng.uniform(0.25, 0.75, size=len(gaps)) * np.diff(kept)[gaps]
    return np.sort(np.concatenate([kept, extra]))
