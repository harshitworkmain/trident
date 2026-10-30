"""Candidate forecasters behind one interface (no torch): used identically by the backtest and serving.

`Predictor(model_dir, spec)` loads baselines, LightGBM boosters and the ONNX sequence model of a
model directory. `predict(prep, pos, H, candidates)` returns raw quantile forecasts
{candidate: {var: (n, H, 3)}} for origins at integer positions `pos` of a prepared frame.
Because the backtest scores exactly this code path, what is evaluated is what is served.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from . import baselines
from .config import DELTA_TARGETS, TARGETS, clip_bounds
from .features import origin_features, seq_inputs

BASELINES = ('persistence', 'seasonal_naive', 'climatology')
LEARNED = ('lgbm', 'gru', 'blend')
CANDIDATES = BASELINES + LEARNED


class Prepared:
    """A history frame with everything the candidates need, computed once."""

    def __init__(self, df: pd.DataFrame, tz: str, seq_spec: Optional[dict] = None):
        self.df = df
        self.F = origin_features(df, tz)
        self.values = {c: df[c].to_numpy(dtype=np.float32) for c in df.columns}
        self.Xn = normalised_inputs(df, tz, seq_spec) if seq_spec else None


def normalised_inputs(df: pd.DataFrame, tz: str, spec: dict) -> np.ndarray:
    X = (seq_inputs(df, tz) - np.asarray(spec['mean'], np.float32)) / np.asarray(spec['std'], np.float32)
    return np.nan_to_num(X, nan=0.0).astype(np.float32)


class SeqForecaster:
    """onnxruntime wrapper around the exported GRU; converts normalised outputs to physical units."""

    def __init__(self, onnx_path: Path, spec: dict):
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = 3
        self.sess = ort.InferenceSession(str(onnx_path), so, providers=['CPUExecutionProvider'])
        self.spec = spec

    def raw(self, Xn: np.ndarray, pos: np.ndarray) -> np.ndarray:
        L = self.spec['lookback']
        win = pos[:, None] + np.arange(-L + 1, 1)[None, :]
        out = [self.sess.run(None, {'x': Xn[win[i:i + 2048]]})[0] for i in range(0, len(pos), 2048)]
        return np.concatenate(out)                                   # (n, H, 5, 3) normalised

    def predict(self, prep: Prepared, pos: np.ndarray, H: int) -> Dict[str, np.ndarray]:
        z = self.raw(prep.Xn, pos)[:, :H]
        out = {}
        for j, v in enumerate(self.spec['vars']):
            q = z[:, :, j, :].astype(np.float64) * self.spec['target_scale'][v]
            if v in DELTA_TARGETS:
                q = q + prep.values[v][pos].astype(np.float64)[:, None, None]
            else:
                q = np.expm1(q)
            out[v] = q
        return out


class Predictor:
    def __init__(self, model_dir: Path, spec: dict, load: Iterable[str] = CANDIDATES):
        load = set(load)
        if 'blend' in load:
            load |= {'lgbm', 'gru'}
        self.model_dir, self.spec = Path(model_dir), spec
        self.H = spec['horizons']
        self.tables = json.loads((self.model_dir / 'baselines.json').read_text())
        self.gbm = self.seq = None
        if 'lgbm' in load:
            from .gbm import GBMForecaster
            self.gbm = GBMForecaster(self.model_dir / 'lgbm', spec['horizon_groups'], spec['lgbm_features'])
        if 'gru' in load and (self.model_dir / 'seq.onnx').exists():
            self.seq = SeqForecaster(self.model_dir / 'seq.onnx', spec['seq'])

    def prepare(self, df: pd.DataFrame) -> Prepared:
        return Prepared(df, self.spec['site']['timezone'], self.spec['seq'] if self.seq else None)

    def predict(self, prep: Prepared, pos: np.ndarray, H: Optional[int] = None,
                candidates: Iterable[str] = CANDIDATES) -> Dict[str, Dict[str, np.ndarray]]:
        H, pos = H or self.H, np.asarray(pos, dtype=np.int64)
        out: Dict[str, Dict[str, np.ndarray]] = {}
        cands = list(candidates)
        for kind in BASELINES:
            if kind in cands:
                out[kind] = baselines.predict(self.tables, kind, prep.values, prep.F, pos, H)
        if self.gbm is not None and ({'lgbm', 'blend'} & set(cands)):
            out['lgbm'] = self.gbm.predict(prep.F, prep.values, pos, H)
        if self.seq is not None and ({'gru', 'blend'} & set(cands)):
            out['gru'] = self.seq.predict(prep, pos, H)
        if 'blend' in cands and 'lgbm' in out and 'gru' in out:
            # quantile averaging (Vincentization) of the two learned models
            out['blend'] = {v: 0.5 * (out['lgbm'][v] + out['gru'][v]) for v in TARGETS}
        return out


def finalize(var: str, q: np.ndarray) -> np.ndarray:
    """Physical bounds, then sort the quantile axis so p10 <= p50 <= p90 always holds."""
    return np.sort(clip_bounds(var, q), axis=-1)


def load_spec(model_dir: Path) -> dict:
    return json.loads((Path(model_dir) / 'spec.json').read_text())


def band_of(h: int, groups: List[List[int]]) -> str:
    for g in groups:
        if g[0] <= h <= g[1]:
            return f'{g[0]}-{g[1]}'
    raise ValueError(h)
