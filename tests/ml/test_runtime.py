"""Serving runtime: streaming (per frame) and batched replay must agree; availability gating."""

import numpy as np
import pandas as pd
import pytest

from src.ml.wearable import paths
from src.ml.wearable.heads.build import HEADS
from src.ml.wearable.schema import FIELD_NAMES, FRAME_PERIOD_S
from src.ml.wearable.serving.runtime import HEAD_STRIDE, DeviceRuntime, head_available, load_heads, replay_frames

needs_registry = pytest.mark.skipif(not (paths.MODELS_DIR / 'registry.json').exists(), reason='no P4 registry')


def test_head_strides_match_training():
    assert HEAD_STRIDE == {h: s.stride for h, s in HEADS.items()}


def test_availability_needs_trained_inputs():
    block = np.full((8, len(FIELD_NAMES)), np.nan)
    block[:, FIELD_NAMES.index('imu_acc_max_g')] = 1.2
    assert head_available('fall', block, [[]] * 8)
    assert not head_available('hr_trust', block, [[]] * 8)          # accelerometer-only device
    block[:, FIELD_NAMES.index('ppg_finger_on')] = 1
    assert head_available('hr_trust', block, [[]] * 8)
    assert not head_available('stress', block, [[]] * 8)            # no EDA
    assert not head_available('rhythm', block, [[]] * 6 + [[800.0]] * 2)
    assert head_available('rhythm', block, [[800.0]] * 8)


@needs_registry
def test_streaming_equals_batched_replay():
    df = pd.read_parquet(paths.FRAMES_DIR / 'wesad.parquet')
    sub = df[df['subject'] == df['subject'].iloc[0]].sort_values('frame').iloc[:300].reset_index(drop=True)
    models = load_heads()
    batched = replay_frames(sub, models)
    rt = DeviceRuntime(models)
    values = sub[FIELD_NAMES].to_dict('records')
    for i, v in enumerate(values):
        out = rt.step(i * FRAME_PERIOD_S, v, list(sub['rr_ms'].iloc[i]))
        b = batched[i]
        assert out['ml_health_state'] == b['ml_health_state']
        for h, val in b['heads'].items():
            if isinstance(val, float):
                assert out['heads'][h] == pytest.approx(val, abs=1e-5)
            else:
                assert out['heads'][h] == val


@needs_registry
def test_runtime_reproduces_p4_golden_outputs():
    # golden.npz = inputs and calibrated outputs of the ONNX ensemble at P4; the runtime may serve tree
    # members from compiled forests, which must give the same probabilities
    for head, m in load_heads().items():
        g = np.load(paths.MODELS_DIR / m.entry['path'] / 'golden.npz')
        assert np.abs(m.predict(g['X'], g['S']) - g['proba']).max() < 1e-4, head
