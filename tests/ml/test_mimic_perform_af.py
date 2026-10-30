import itertools

import numpy as np
import pytest

from src.ml.wearable import paths
from src.ml.wearable.data.loaders import E4_FS, load_mimic_perform_af

pytestmark = pytest.mark.skipif(
    not all((paths.RAW_DIR / '_zips' / f'mimic_perform_{g}_wfdb.zip').exists() for g in ('af', 'non_af')),
    reason='MIMIC PERform AF archives not downloaded')


def test_loader_reads_ppg_ecg_and_labels_in_place():
    recs = list(load_mimic_perform_af())
    assert len(recs) == 35 and sum(r.meta['af'] for r in recs) == 19
    r = recs[0]
    assert r.bvp.fs == E4_FS['BVP'] and r.beats_s is None      # beats come from the PPG, as on the device
    assert abs(r.duration - 1200) < 2 and np.isfinite(r.bvp.data).all()


def test_ecg_reference_beats_are_plausible():
    r = next(itertools.islice(load_mimic_perform_af(with_ecg_beats=True), 1))
    hr = 60 * len(r.meta['ecg_beats_s']) / r.meta['duration_s']
    assert 40 < hr < 160
