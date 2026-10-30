"""Filesystem layout for the wearable ML pipeline.

Large data lives outside git (see .gitignore). Set TRIDENT_DATA_ROOT to relocate the whole
data tree, e.g. onto an external drive.
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = Path(os.environ.get('TRIDENT_DATA_ROOT', PROJECT_ROOT / 'data'))

RAW_DIR = DATA_ROOT / 'raw' / 'wearable_ml_datasets'        # downloaded archives/repos
COMPACT_DIR = DATA_ROOT / 'interim' / 'wearable' / 'compact'  # lossless per-subject .npz
FRAMES_DIR = DATA_ROOT / 'processed' / 'wearable' / 'frames'  # emulated 1.5 s frame tables
REPORTS_DIR = DATA_ROOT / 'processed' / 'wearable' / 'reports'

MANIFEST_PATH = PROJECT_ROOT / 'data' / 'manifest' / 'wearable_datasets.json'  # tracked in git
CONFIG_DIR = Path(__file__).resolve().parent / 'config'
MODELS_DIR = PROJECT_ROOT / 'models' / 'wearable'
