"""Read-anything access to the original dataset archives, without extracting them.

Compaction keeps only the channels the pipeline uses. When a later step needs something
else (chest ECG, RespiBAN, questionnaires, E4 CSVs, ...), it reads it from the original
archive through this module: members are streamed, nested zips (PPG-DaLiA's data.zip
inside ppg+dalia.zip) are opened in place, and pickles go through the safe unpickler.

    python -m src.ml.wearable.data.archive list ppg_dalia --pattern S1/
    python -m src.ml.wearable.data.archive extract wesad WESAD/S2/S2_quest.csv --dest tmp/
    python -m src.ml.wearable.data.archive verify            # CRC-check every member
"""

from __future__ import annotations

import argparse
import fnmatch
import io
import shutil
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional

from .. import paths
from .compact import SafeUnpickler, load_registry


def _archive_cfg(dataset: str) -> dict:
    cfg = load_registry()[dataset]
    if 'archive' not in cfg:
        raise ValueError(f'{dataset} has no archive (it is a plain directory: {cfg["raw"]})')
    return cfg


@contextmanager
def open_archive(dataset: str) -> Iterator[zipfile.ZipFile]:
    """Yield the dataset's zip, descending into the nested archive when there is one."""
    cfg = _archive_cfg(dataset)
    with zipfile.ZipFile(paths.RAW_DIR / cfg['archive']) as outer:
        nested = cfg.get('archive_nested')
        if not nested:
            yield outer
            return
        # The nested zip is stored uncompressed, so its stream is seekable and opens in place.
        with outer.open(nested) as fh, zipfile.ZipFile(fh) as inner:
            yield inner


def list_members(dataset: str, pattern: Optional[str] = None) -> List[zipfile.ZipInfo]:
    with open_archive(dataset) as zf:
        members = [i for i in zf.infolist() if not i.is_dir()]
    if pattern:
        members = [i for i in members if pattern in i.filename or fnmatch.fnmatch(i.filename, pattern)]
    return members


def read_member(dataset: str, name: str) -> bytes:
    with open_archive(dataset) as zf:
        return zf.read(name)


def load_pickle(dataset: str, name: str):
    """Load a dataset pickle member (numpy arrays and plain containers only)."""
    with open_archive(dataset) as zf, zf.open(name) as fh:
        return SafeUnpickler(io.BufferedReader(fh, 1 << 24), encoding='latin1').load()


def extract(dataset: str, names: List[str], dest: Path) -> List[Path]:
    """Extract selected members (full relative paths kept) and return their local paths."""
    dest = Path(dest)
    written = []
    with open_archive(dataset) as zf:
        for name in names:
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, open(target, 'wb') as dst:
                shutil.copyfileobj(src, dst, 1 << 22)
            written.append(target)
    return written


def verify(dataset: str) -> dict:
    """Read every member end to end and check its CRC. Returns the first bad member, if any."""
    with open_archive(dataset) as zf:
        members = [i for i in zf.infolist() if not i.is_dir()]
        bad = zf.testzip()
    return {'dataset': dataset, 'members': len(members),
            'uncompressed_gb': round(sum(i.file_size for i in members) / 1e9, 2),
            'first_bad_member': bad, 'ok': bad is None}


def archived_datasets() -> List[str]:
    return [name for name, cfg in load_registry().items() if 'archive' in cfg]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    p_list = sub.add_parser('list')
    p_list.add_argument('dataset')
    p_list.add_argument('--pattern')
    p_ext = sub.add_parser('extract')
    p_ext.add_argument('dataset')
    p_ext.add_argument('members', nargs='+')
    p_ext.add_argument('--dest', required=True)
    p_ver = sub.add_parser('verify')
    p_ver.add_argument('datasets', nargs='*')
    args = parser.parse_args()

    if args.cmd == 'list':
        for info in list_members(args.dataset, args.pattern):
            print(f'{info.file_size / 1e6:10.1f} MB  {info.filename}')
    elif args.cmd == 'extract':
        for path in extract(args.dataset, args.members, Path(args.dest)):
            print(path)
    else:
        for name in args.datasets or archived_datasets():
            print(verify(name))


if __name__ == '__main__':
    main()
