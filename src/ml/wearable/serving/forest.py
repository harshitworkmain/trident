"""Compiled tree ensembles: an ONNX `TreeEnsembleClassifier` as flat numpy arrays.

onnxruntime builds its tree kernel node by node at session creation, which takes minutes for the
large Extra-Trees members (HR-trust: 1.9 M nodes, ~280 s; same with the .ort format). The same
trees as arrays load in well under a second. The ONNX file stays the canonical artefact: the
arrays are derived from it and must reproduce its probabilities (`check_parity`, run at compile time).

Semantics follow ai.onnx.ml TreeEnsembleClassifier with post_transform NONE and BRANCH_LEQ nodes:
go to the true child when x <= value, or when x is NaN and missing_value_tracks_true is set; the
class scores are the sums of the reached leaves' weights; a binary model that stores a single
weight column (skl2onnx writes it under class id 0) holds s = P(class 1) and reports [1 - s, s].
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np

ARRAYS = ('feature', 'threshold', 'true_child', 'false_child', 'missing_true', 'is_leaf', 'roots', 'leaf_values')


def _attrs(model) -> Dict[str, object]:
    from onnx import helper                         # compile time only; serving needs numpy
    nodes = [n for n in model.graph.node if n.op_type == 'TreeEnsembleClassifier']
    if len(nodes) != 1 or len(model.graph.node) > 2:
        raise ValueError('expected a single TreeEnsembleClassifier (plus Identity)')
    a = {x.name: helper.get_attribute_value(x) for x in nodes[0].attribute}
    if a.get('post_transform', b'NONE') not in (b'NONE', 'NONE'):
        raise ValueError(f"unsupported post_transform {a['post_transform']}")
    return a


def compile_forest(model) -> Dict[str, np.ndarray]:
    """Arrays from an onnx.ModelProto holding one TreeEnsembleClassifier."""
    a = _attrs(model)
    tree, node = np.asarray(a['nodes_treeids'], np.int64), np.asarray(a['nodes_nodeids'], np.int64)
    modes = np.asarray([m.decode() if isinstance(m, bytes) else m for m in a['nodes_modes']])
    if not set(modes) <= {'BRANCH_LEQ', 'LEAF'}:
        raise ValueError(f'unsupported node modes {set(modes)}')
    n_classes = len(a['classlabels_int64s'])
    # global index of (tree, node id)
    order = np.lexsort((node, tree))
    tree, node, modes = tree[order], node[order], modes[order]
    key = {(t, n): i for i, (t, n) in enumerate(zip(tree.tolist(), node.tolist()))}
    pick = lambda name, dt: np.asarray(a[name], dt)[order]
    true_ids, false_ids = pick('nodes_truenodeids', np.int64), pick('nodes_falsenodeids', np.int64)
    is_leaf = modes == 'LEAF'
    true_child = np.array([i if l else key[(t, c)] for i, (t, c, l) in enumerate(zip(tree, true_ids, is_leaf))], np.int32)
    false_child = np.array([i if l else key[(t, c)] for i, (t, c, l) in enumerate(zip(tree, false_ids, is_leaf))], np.int32)
    missing = a.get('nodes_missing_value_tracks_true')
    missing_true = (pick('nodes_missing_value_tracks_true', np.int64) if missing else np.zeros(len(tree), np.int64)).astype(bool)
    binary_one_column = n_classes == 2 and len(np.unique(a['class_ids'])) == 1
    leaf_values = np.zeros((len(tree), n_classes), np.float64)
    for t, n, c, w in zip(a['class_treeids'], a['class_nodeids'], a['class_ids'], a['class_weights']):
        leaf_values[key[(t, n)], 1 if binary_one_column else c] += w
    roots = np.array([key[(t, 0)] for t in np.unique(tree)], np.int32)
    return {'feature': pick('nodes_featureids', np.int32), 'threshold': pick('nodes_values', np.float32),
            'true_child': true_child, 'false_child': false_child, 'missing_true': missing_true,
            'is_leaf': is_leaf, 'roots': roots, 'leaf_values': leaf_values,
            'binary_one_column': np.array(binary_one_column)}


def predict_proba(f: Dict[str, np.ndarray], X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, np.float32)
    n, T = len(X), len(f['roots'])
    cur = np.broadcast_to(f['roots'], (n, T)).copy()
    rows = np.arange(n)[:, None]
    while True:
        leaf = f['is_leaf'][cur]
        if leaf.all():
            break
        x = X[rows, f['feature'][cur]]
        go_true = np.where(np.isnan(x), f['missing_true'][cur], x <= f['threshold'][cur])
        cur = np.where(leaf, cur, np.where(go_true, f['true_child'][cur], f['false_child'][cur]))
    scores = f['leaf_values'][cur].sum(axis=1)
    if bool(f['binary_one_column']):
        scores[:, 0] = 1.0 - scores[:, 1]
    return scores.astype(np.float32)


def save(f: Dict[str, np.ndarray], path: Path) -> None:
    np.savez(path, **f)


def load(path: Path) -> Dict[str, np.ndarray]:
    with np.load(path) as z:
        return {k: z[k] for k in z.files}
