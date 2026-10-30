"""GRU encoder -> multi-horizon quantile head (training + ONNX export). The only torch user.

Input : the last `lookback` hours of 8 weather channels (rain as log1p) + 4 calendar channels,
        standardised with training-period statistics.
Output: (48 horizons, 5 variables, 3 quantiles) in a normalised target space - change from
        the origin / scale for smooth variables, log1p(rain) / scale for rain. The head emits the
        median and two softplus widths, so p10 <= p50 <= p90 holds by construction.
Loss  : pinball loss averaged over quantiles, horizons and variables.
Serving runs the exported ONNX graph with onnxruntime (see predict.SeqForecaster); torch is
never imported at serving time.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict

import numpy as np
import torch
from torch import nn

from .config import TARGETS
from .features import seq_inputs
from .predict import normalised_inputs

logger = logging.getLogger('weather.seq')
QS = (0.1, 0.5, 0.9)
VARS = list(TARGETS)


class QuantileGRU(nn.Module):
    def __init__(self, n_in: int, hidden: int, H: int, n_vars: int):
        super().__init__()
        self.H, self.n_vars = H, n_vars
        self.gru = nn.GRU(n_in, hidden, batch_first=True)
        self.head = nn.Sequential(nn.Linear(hidden + n_in, 256), nn.ReLU(), nn.Linear(256, H * n_vars * 3))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, h = self.gru(x)
        # the last observed hour goes straight to the head as well: the GRU state alone blurs it
        z = self.head(torch.cat([h[-1], x[:, -1, :]], dim=1)).view(-1, self.H, self.n_vars, 3)
        mid = z[..., 0]
        lo = mid - nn.functional.softplus(z[..., 1])
        hi = mid + nn.functional.softplus(z[..., 2])
        return torch.stack([lo, mid, hi], dim=-1)


def pinball(pred: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    q = torch.tensor(QS, dtype=pred.dtype).view(1, 1, 1, 3)
    e = y.unsqueeze(-1) - pred
    return torch.maximum(q * e, (q - 1) * e).mean()


def make_spec(df, tz: str, train_pos: np.ndarray, lookback: int, H: int) -> dict:
    X = seq_inputs(df, tz)[train_pos]
    mean, std = np.nanmean(X, axis=0), np.nanstd(X, axis=0) + 1e-6
    scale = {}
    for v in VARS:
        x = df[v].to_numpy(dtype=np.float64)
        scale[v] = float(np.nanstd(np.log1p(x[train_pos]) if v == 'rain' else x[train_pos + 24] - x[train_pos]) + 1e-6)
    return {'lookback': lookback, 'H': H, 'vars': VARS, 'mean': mean.tolist(), 'std': std.tolist(),
            'target_scale': scale, 'quantiles': list(QS)}


def normalised_targets(df, spec: dict) -> np.ndarray:
    """(T, 5) per-hour transformed levels; targets for origin t are rows t+1..t+H minus (delta vars) row t."""
    cols = []
    for v in VARS:
        x = df[v].to_numpy(dtype=np.float64)
        cols.append((np.log1p(x) if v == 'rain' else x) / spec['target_scale'][v])
    return np.column_stack(cols).astype(np.float32)


def _batch(Xn, Yn, pos, L, H, delta_mask):
    win = pos[:, None] + np.arange(-L + 1, 1)[None, :]
    fut = pos[:, None] + np.arange(1, H + 1)[None, :]
    y = Yn[fut] - Yn[pos][:, None, :] * delta_mask[None, None, :]
    return torch.from_numpy(Xn[win]), torch.from_numpy(np.ascontiguousarray(y))


def fit(df, tz: str, train_pos: np.ndarray, last_target: int, cfg: dict, H: int, seed: int = 0):
    """Train on origins whose whole 48 h target window lies inside the training period."""
    torch.manual_seed(seed)
    torch.set_num_threads(3)
    L = cfg['lookback']
    pos = train_pos[(train_pos >= L - 1) & (train_pos + H <= last_target)]
    spec = make_spec(df, tz, pos, L, H)
    Xn, Yn = normalised_inputs(df, tz, spec), normalised_targets(df, spec)
    delta_mask = np.array([0.0 if v == 'rain' else 1.0 for v in VARS], dtype=np.float32)
    ok = np.isfinite(Yn[pos[:, None] + np.arange(1, H + 1)]).all(axis=(1, 2)) & np.isfinite(Yn[pos]).all(axis=1)
    pos = pos[ok]
    n_val = max(len(pos) // 20, 1)
    tr, va = pos[:-n_val - H][::cfg.get('train_stride_h', 1)], pos[-n_val:]   # H-hour gap: no target overlap
    model = QuantileGRU(Xn.shape[1], cfg['hidden'], H, len(VARS))
    opt = torch.optim.AdamW(model.parameters(), lr=cfg['lr'], weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=cfg['lr'], total_steps=cfg['epochs'] * (len(tr) // cfg['batch'] + 1))
    rng = np.random.default_rng(seed)
    best, best_state, history, t0 = np.inf, None, [], time.perf_counter()
    for ep in range(cfg['epochs']):
        model.train()
        perm, losses = rng.permutation(tr), []
        for i in range(0, len(perm), cfg['batch']):
            xb, yb = _batch(Xn, Yn, perm[i:i + cfg['batch']], L, H, delta_mask)
            loss = pinball(model(xb), yb)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            losses.append(loss.item())
        model.eval()
        with torch.no_grad():
            vl = float(np.mean([pinball(model(xb), yb).item() for xb, yb in
                                (_batch(Xn, Yn, va[i:i + 1024], L, H, delta_mask) for i in range(0, len(va), 1024))]))
        history.append({'epoch': ep + 1, 'train_pinball': float(np.mean(losses)), 'val_pinball': vl})
        logger.info('gru epoch %d train %.4f val %.4f (%.0fs)', ep + 1, np.mean(losses), vl, time.perf_counter() - t0)
        if vl < best:
            best, best_state = vl, {k: v.detach().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    model.eval()
    spec.update({'history': history, 'train_seconds': time.perf_counter() - t0, 'n_train_windows': int(len(tr))})
    return model, spec


def export_onnx(model: QuantileGRU, spec: dict, path: Path, n_check: int = 64, seed: int = 0) -> Dict[str, float]:
    """Export with a dynamic batch axis and check onnxruntime against torch on random inputs."""
    import onnxruntime as ort
    L, C = spec['lookback'], len(spec['mean'])
    dummy = torch.zeros(1, L, C)
    torch.onnx.export(model, dummy, str(path), input_names=['x'], output_names=['q'], opset_version=17,
                      dynamic_axes={'x': {0: 'batch'}, 'q': {0: 'batch'}}, dynamo=False)
    x = np.random.default_rng(seed).standard_normal((n_check, L, C)).astype(np.float32)
    with torch.no_grad():
        ref = model(torch.from_numpy(x)).numpy()
    got = ort.InferenceSession(str(path), providers=['CPUExecutionProvider']).run(None, {'x': x})[0]
    return {'max_abs_diff': float(np.abs(ref - got).max()), 'n': n_check}
