"""Export fitted tournament candidates to self-contained ONNX graphs (serving format).

Every exported graph has the same contract, whatever the model family:

    inputs : X float32 (n, F) tabular features (NaN allowed)   - always present
             S float32 (n, T, C) frame sequence (NaN allowed)  - always present
    output : proba float32 (n, K) class probabilities (uncalibrated)

Unused inputs are kept so the server can feed every head the same way. Preprocessing
(median imputation, scaling, clipping, MiniRocket transform) is baked into the graph,
so the serving side only needs onnxruntime + numpy (py3.10 / numpy 1.26 in Docker).
"""

from __future__ import annotations

import io
from typing import Tuple

import numpy as np
import onnx
import torch
from onnx import TensorProto, helper

from ..models.candidates import (CNN1DCandidate, ExtraTreesCandidate, LightGBMCandidate, LogRegCandidate,
                                 MiniRocketCandidate, MLPCandidate, XGBoostCandidate)

OPSET = 17
ML_OPSET = 15          # highest opset onnxmltools supports for XGBoost / LightGBM


# ─── torch wrappers (MLP, 1D-CNN, MiniRocket) ────────────────────────────────

def _t(a) -> torch.Tensor:
    return torch.tensor(np.asarray(a), dtype=torch.float32)


class _Impute(torch.nn.Module):
    def __init__(self, fill):
        super().__init__()
        self.register_buffer('fill', _t(fill))

    def forward(self, x):
        return torch.where(torch.isnan(x), self.fill.expand_as(x), x)


class _MLPGraph(torch.nn.Module):
    def __init__(self, c: MLPCandidate):
        super().__init__()
        self.impute = _Impute(c.imputer.statistics_)
        self.register_buffer('mu', _t(c.mu))
        self.register_buffer('sd', _t(c.sd))
        self.net = c.net

    def forward(self, X, S):
        z = torch.clamp((self.impute(X) - self.mu) / self.sd, -10.0, 10.0)
        return torch.softmax(self.net(z), dim=1)


class _CNNGraph(torch.nn.Module):
    def __init__(self, c: CNN1DCandidate):
        super().__init__()
        self.register_buffer('mu', _t(c.mu))
        self.register_buffer('sd', _t(c.sd))
        self.net = c.net

    def forward(self, X, S):
        z = torch.clamp((S - self.mu) / self.sd, -10.0, 10.0)
        z = torch.where(torch.isnan(z), torch.zeros_like(z), z).transpose(1, 2)
        return torch.softmax(self.net(z), dim=1)


class _MiniRocketGraph(torch.nn.Module):
    """Re-implements MiniRocketTransform.transform with fixed tensors (verified against numpy)."""

    def __init__(self, c: MiniRocketCandidate):
        super().__init__()
        r = c.rocket
        W = -np.ones((84, 9), dtype=np.float32)
        for k, taps in enumerate(r.KERNELS):
            W[k, taps] = 2.0
        self.register_buffer('W', _t(W))
        self.register_buffer('mu', _t(c.mu))
        self.register_buffer('sd', _t(c.sd))
        self.plan = []
        C = len(c.mu)
        for i, (d, pad, chans, biases) in enumerate(r.plan):
            M = np.zeros((84, C), dtype=np.float32)
            for k, ch in enumerate(chans):
                M[k, ch] = 1.0
            self.register_buffer(f'M{i}', _t(M))
            self.register_buffer(f'B{i}', _t(biases))
            self.plan.append((int(d), bool(pad)))
        imp, tab_scaler = c.tab.steps[0][1], c.tab.steps[1][1]
        self.tab_impute = _Impute(imp.statistics_)
        self.register_buffer('tab_mu', _t(tab_scaler.mean_))
        self.register_buffer('tab_sd', _t(tab_scaler.scale_))
        self.register_buffer('f_mu', _t(c.scaler.mean_))
        self.register_buffer('f_sd', _t(c.scaler.scale_))
        coef, icpt = c.clf.coef_, c.clf.intercept_
        if coef.shape[0] == 1:                       # binary sklearn LR -> two logits [0, z]
            coef = np.vstack([np.zeros_like(coef), coef])
            icpt = np.array([0.0, icpt[0]])
        self.register_buffer('coef', _t(coef))
        self.register_buffer('icpt', _t(icpt))

    def forward(self, X, S):
        z = torch.clamp((S - self.mu) / self.sd, -10.0, 10.0)
        A = torch.where(torch.isnan(z), torch.zeros_like(z), z).transpose(1, 2)    # (n, C, T)
        feats = []
        for i, (d, pad) in enumerate(self.plan):
            Z = torch.nn.functional.pad(A, (4 * d, 4 * d)) if pad else A
            L = Z.shape[2] - 8 * d
            taps = torch.stack([Z[:, :, j * d:j * d + L] for j in range(9)], dim=1)  # (n, 9, C, L)
            out = torch.einsum('kj,njcl->nkcl', self.W, taps)                          # (n, 84, C, L)
            conv = torch.einsum('kc,nkcl->nkl', getattr(self, f'M{i}'), out)          # (n, 84, L)
            B = getattr(self, f'B{i}')                                                # (84, per)
            ppv = (conv.unsqueeze(2) > B.unsqueeze(0).unsqueeze(3)).float().mean(dim=3)  # (n, 84, per)
            feats.append(ppv.reshape(ppv.shape[0], -1))
        tab = (self.tab_impute(X) - self.tab_mu) / self.tab_sd
        F = (torch.cat(feats + [tab], dim=1) - self.f_mu) / self.f_sd
        return torch.softmax(F @ self.coef.T + self.icpt, dim=1)


def _torch_to_onnx(module: torch.nn.Module, F: int, T: int, C: int) -> onnx.ModelProto:
    module.eval()
    buf = io.BytesIO()
    x, s = torch.zeros(2, F), torch.zeros(2, T, C)
    torch.onnx.export(module, (x, s), buf, input_names=['X', 'S'], output_names=['proba'],
                      dynamic_axes={'X': {0: 'n'}, 'S': {0: 'n'}, 'proba': {0: 'n'}},
                      opset_version=OPSET, dynamo=False)
    return onnx.load_from_string(buf.getvalue())


# ─── tree / linear models via skl2onnx / onnxmltools ─────────────────────────

def _sklearn_like_to_onnx(c, F: int) -> onnx.ModelProto:
    if isinstance(c, (XGBoostCandidate, LightGBMCandidate)):
        from onnxmltools import convert_lightgbm, convert_xgboost
        from onnxmltools.convert.common.data_types import FloatTensorType as MLFloat
        init = [('X', MLFloat([None, F]))]
        if isinstance(c, XGBoostCandidate):
            return convert_xgboost(c.model, initial_types=init, target_opset=ML_OPSET)
        return convert_lightgbm(c.model, initial_types=init, target_opset=ML_OPSET, zipmap=False)
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    model = convert_sklearn(c.model, initial_types=[('X', FloatTensorType([None, F]))],
                            target_opset={'': OPSET, 'ai.onnx.ml': 3}, options={id(c.model): {'zipmap': False}})
    if isinstance(c, ExtraTreesCandidate):
        _route_missing_like_sklearn(model, c.model)
    return model


def _route_missing_like_sklearn(model: onnx.ModelProto, forest) -> None:
    """skl2onnx ignores sklearn's learned NaN routing; copy `missing_go_to_left` into the graph.

    In TreeEnsembleClassifier (BRANCH_LEQ) the true branch is sklearn's left child, so
    nodes_missing_value_tracks_true = missing_go_to_left for every split node.
    """
    node = next(n for n in model.graph.node if n.op_type == 'TreeEnsembleClassifier')
    attrs = {a.name: a for a in node.attribute}
    tree_ids, node_ids = list(attrs['nodes_treeids'].ints), list(attrs['nodes_nodeids'].ints)
    go_left = [est.tree_.missing_go_to_left for est in forest.estimators_]
    tracks = [int(go_left[t][n]) if n < len(go_left[t]) else 0 for t, n in zip(tree_ids, node_ids)]
    if 'nodes_missing_value_tracks_true' in attrs:
        node.attribute.remove(attrs['nodes_missing_value_tracks_true'])
    node.attribute.append(helper.make_attribute('nodes_missing_value_tracks_true', tracks))


def _standardise_outputs(model: onnx.ModelProto, T: int, C: int) -> onnx.ModelProto:
    """Rename the probability output to `proba`, drop the label output, add the unused `S` input."""
    g = model.graph
    prob = next(o for o in g.output if 'prob' in o.name.lower())
    g.node.append(helper.make_node('Identity', [prob.name], ['proba']))
    del g.output[:]
    g.output.append(helper.make_tensor_value_info('proba', TensorProto.FLOAT, [None, None]))
    g.input.append(helper.make_tensor_value_info('S', TensorProto.FLOAT, [None, T, C]))
    return model


def export_candidate(c, F: int, T: int, C: int) -> onnx.ModelProto:
    if isinstance(c, MLPCandidate):
        return _torch_to_onnx(_MLPGraph(c), F, T, C)
    if isinstance(c, CNN1DCandidate):
        return _torch_to_onnx(_CNNGraph(c), F, T, C)
    if isinstance(c, MiniRocketCandidate):
        return _torch_to_onnx(_MiniRocketGraph(c), F, T, C)
    if isinstance(c, (LogRegCandidate, XGBoostCandidate, LightGBMCandidate, ExtraTreesCandidate)):
        return _standardise_outputs(_sklearn_like_to_onnx(c, F), T, C)
    raise TypeError(f'no exporter for {type(c).__name__}')


def onnx_predict(model_bytes: bytes, X: np.ndarray, S: np.ndarray) -> np.ndarray:
    import onnxruntime as ort
    sess = ort.InferenceSession(model_bytes, providers=['CPUExecutionProvider'])
    names = {i.name for i in sess.get_inputs()}
    feed = {'X': X.astype(np.float32), 'S': S.astype(np.float32)}
    return sess.run(['proba'], {k: v for k, v in feed.items() if k in names})[0]


def max_abs_diff(c, model: onnx.ModelProto, X: np.ndarray, S: np.ndarray) -> Tuple[float, float]:
    """(max |p_onnx - p_python|, share of rows whose argmax differs)."""
    p_py = c.predict_proba(X, S)
    p_ox = onnx_predict(model.SerializeToString(), X, S)
    return float(np.abs(p_py - p_ox).max()), float((p_py.argmax(1) != p_ox.argmax(1)).mean())
