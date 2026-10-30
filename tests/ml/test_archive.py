import pytest

from src.ml.wearable import paths
from src.ml.wearable.data import archive

pytestmark = pytest.mark.skipif(not (paths.RAW_DIR / '_zips' / 'mitdb.zip').exists(),
                                reason='MIT-BIH archive not downloaded')


def test_list_and_read_member_without_extraction():
    members = archive.list_members('mitbih', pattern='100.hea')
    assert len(members) == 1
    header = archive.read_member('mitbih', members[0].filename).decode()
    assert header.startswith('100 2 360')


def test_selective_extract(tmp_path):
    name = archive.list_members('mitbih', pattern='100.atr')[0].filename
    [written] = archive.extract('mitbih', [name], tmp_path)
    assert written.exists() and written.stat().st_size > 0


def test_directory_dataset_has_no_archive():
    with pytest.raises(ValueError):
        archive.list_members('hifd')
