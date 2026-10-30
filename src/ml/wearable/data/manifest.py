"""Dataset manifest: content hashes of every source and compacted file (tracked in git).

The manifest pins exactly which bytes a model was trained on. Processed artefacts carry
`data_hash()`, so a changed source, compaction or emulator version is always detectable.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from .. import paths
from ..emulator import EMULATOR_VERSION
from .compact import load_registry


def sha256_file(path: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(chunk), b''):
            h.update(block)
    return h.hexdigest()


def _tree_hash(root: Path) -> Dict[str, object]:
    files = sorted(p for p in root.rglob('*') if p.is_file() and '.git' not in p.parts)
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(root).as_posix().encode())
        h.update(sha256_file(p).encode())
    return {'files': len(files), 'bytes': sum(p.stat().st_size for p in files), 'sha256': h.hexdigest()}


def build_manifest() -> Dict[str, object]:
    registry = load_registry()
    datasets = {}
    for name, cfg in registry.items():
        raw_rel = cfg.get('raw', cfg.get('archive'))
        raw = paths.RAW_DIR / raw_rel
        entry = {k: cfg[k] for k in ('title', 'url', 'license', 'citation') if k in cfg}
        if raw.is_file():
            entry['raw'] = {'path': raw_rel, 'bytes': raw.stat().st_size, 'sha256': sha256_file(raw)}
        elif raw.is_dir():
            entry['raw'] = {'path': raw_rel, **_tree_hash(raw)}
        else:
            entry['raw'] = {'path': raw_rel, 'status': 'deleted after verified lossless compaction'}
        compact = paths.COMPACT_DIR / cfg['compact']
        if compact.exists():
            entry['compact'] = _tree_hash(compact)
        datasets[name] = entry
    return {
        'generated_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'emulator_version': EMULATOR_VERSION,
        'datasets': datasets,
    }


def write_manifest() -> Dict[str, object]:
    manifest = build_manifest()
    paths.MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    paths.MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def data_hash(dataset: str) -> str:
    """Identity of a dataset's processed output: compacted bytes + emulator version."""
    manifest = json.loads(paths.MANIFEST_PATH.read_text(encoding='utf-8'))
    entry = manifest['datasets'][dataset]
    source_sha = entry['compact']['sha256'] if 'compact' in entry else entry['raw']['sha256']  # read in place
    return hashlib.sha256(f'{source_sha}:{EMULATOR_VERSION}'.encode()).hexdigest()[:16]
