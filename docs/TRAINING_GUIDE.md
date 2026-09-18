# TRIDENT Wearable ML — Model Training Guide

> **Standalone guide for training the 8-State Disaster Trauma XGBoost classifier.**  
> This file is designed to be followed without any AI IDE (Antigravity/Cursor/etc).  
> All you need is a terminal, Python 3.10+, and ≥16 GB RAM.

---

## Table of Contents
1. [Quick Start (TL;DR)](#1-quick-start-tldr)
2. [Prerequisites & System Requirements](#2-prerequisites--system-requirements)
3. [Scenario A: Personal Device / Friend's Laptop (Full Access)](#3-scenario-a-personal-device--friends-laptop)
4. [Scenario B: College Lab PC (No External Devices)](#4-scenario-b-college-lab-pc)
5. [Dataset Downloads (Manual)](#5-dataset-downloads)
6. [Environment Setup](#6-environment-setup)
7. [Training Execution](#7-training-execution)
8. [Post-Training: Deploy the Model](#8-post-training-deploy-the-model)
9. [Troubleshooting & Debugging](#9-troubleshooting--debugging)

---

## 1. Quick Start (TL;DR)

```bash
# 1. Get the repo (pick one)
git clone https://github.com/harshitworkmain/trident.git
# OR: extract from SSD/pendrive zip

# 2. Enter project
cd trident

# 3. Create venv & install deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-prod.txt
pip install xgboost joblib wfdb pyarrow

# 4. Download datasets into data/raw/wearable_ml_datasets/ (see Section 5)

# 5. Run training
python src/ml/train_wearable_model.py

# 6. Verify model was created
ls -lh src/ml/wearable_health_model.pkl

# 7. Commit & push
git add src/ml/wearable_health_model.pkl
git commit -m "feat(ml): trained XGBoost 8-state wearable health model"
git push origin main
```

---

## 2. Prerequisites & System Requirements

### Minimum Hardware
| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 16 GB | 32 GB |
| CPU Cores | 4 | 8+ |
| Storage | 30 GB free | 50 GB free |
| GPU | Not required | Not required (XGBoost uses CPU `tree_method='hist'`) |

### Software
| Tool | Version | Check Command |
|------|---------|---------------|
| Python | 3.10+ | `python3 --version` |
| pip | latest | `pip --version` |
| git | 2.x | `git --version` |

---

## 3. Scenario A: Personal Device / Friend's Laptop

**You have**: Full admin access, can connect SSD/pendrive, install software.

### Step 1: Transfer Repository
**Option A — From SSD/Pendrive:**
```bash
# Mount your drive
sudo mount /dev/sdb1 /mnt/usb  # adjust device name

# Copy repo
cp -r /mnt/usb/trident ~/trident
cd ~/trident
```

**Option B — From GitHub:**
```bash
git clone https://github.com/harshitworkmain/trident.git
cd trident
```

### Step 2: Transfer Datasets (if on SSD/Pendrive)
```bash
# If datasets are on the drive
cp -r /mnt/usb/wearable_ml_datasets/* data/raw/wearable_ml_datasets/
```

### Step 3: Verify Dataset Structure
```bash
# Should show: WESAD/ PPG_FieldStudy/ mit-bih-*/ HR_IMU_*/ sisfall/ upfall/ README.md
ls data/raw/wearable_ml_datasets/
```

Then proceed to [Section 6: Environment Setup](#6-environment-setup).

---

## 4. Scenario B: College Lab PC

**You have**: No admin/sudo, no external devices, browser + terminal access only.

### Step 1: Get Repository
```bash
# Option A: git clone (if git is available)
git clone https://github.com/harshitworkmain/trident.git
cd trident

# Option B: Download ZIP via browser
# Go to: https://github.com/harshitworkmain/trident/archive/refs/heads/main.zip
# Extract to home directory
unzip trident-main.zip
cd trident-main
```

### Step 2: Use Local Python (no sudo)
```bash
# Check if python3 is available
python3 --version

# Create user-local venv (no sudo needed)
python3 -m venv .venv
source .venv/bin/activate

# Install packages to user space
pip install --user -r requirements-prod.txt
pip install --user xgboost joblib wfdb pyarrow
```

### Step 3: Download Datasets via Terminal
See [Section 5](#5-dataset-downloads) — use `wget` or `curl` commands.

Then proceed to [Section 6: Environment Setup](#6-environment-setup).

---

## 5. Dataset Downloads

### Directory Structure Required
```
data/raw/wearable_ml_datasets/
├── WESAD/                         # ~17.6 GB (15 subjects)
│   └── S2/, S3/, ... S17/
│       └── S*.pkl
├── PPG_FieldStudy/                # ~2.7 GB (15 subjects)
│   └── S1/, S2/, ... S15/
│       └── S*.pkl
├── mit-bih-arrhythmia-database-1.0.0/  # ~104 MB (48 records)
│   └── *.dat, *.hea, *.atr
├── HR_IMU_falldetection_dataset-master/ # ~50 MB (21 subjects)
│   └── *.mat
├── sisfall/                       # Reference code repo
└── upfall/                        # Reference code repo
```

### Download Commands

#### 1. WESAD (UCI ML Repository)
```bash
# Direct download from UCI
# URL: https://archive.ics.uci.edu/dataset/465/wesad+wearable+stress+and+affect+detection
# DOI: 10.24432/C57K5T
#
# Manual: Go to the URL above, click "Download", extract to:
#   data/raw/wearable_ml_datasets/WESAD/

# Alternative via wget (if direct link available):
cd data/raw/wearable_ml_datasets/
wget -O WESAD.zip "https://archive.ics.uci.edu/static/public/465/wesad+wearable+stress+and+affect+detection.zip"
unzip WESAD.zip -d WESAD/
cd ../../..
```

#### 2. PPG-DaLiA (UCI ML Repository)
```bash
# URL: https://archive.ics.uci.edu/dataset/495/ppg+dalia
# DOI: 10.24432/C53890

cd data/raw/wearable_ml_datasets/
wget -O PPG_DaLiA.zip "https://archive.ics.uci.edu/static/public/495/ppg+dalia.zip"
unzip PPG_DaLiA.zip -d PPG_FieldStudy/
cd ../../..
```

#### 3. MIT-BIH Arrhythmia Database (PhysioNet)
```bash
# URL: https://physionet.org/content/mitdb/1.0.0/
# DOI: 10.13026/C2F305

cd data/raw/wearable_ml_datasets/
wget -r -N -c -np https://physionet.org/files/mitdb/1.0.0/
mv physionet.org/files/mitdb/1.0.0 mit-bih-arrhythmia-database-1.0.0
rm -rf physionet.org
cd ../../..
```

#### 4. HIFD — HR + IMU Fall Detection (GitHub)
```bash
cd data/raw/wearable_ml_datasets/
git clone https://github.com/nhoyh/HR_IMU_falldetection_dataset.git HR_IMU_falldetection_dataset-master
cd ../../..
```

#### 5. Reference Repos (SisFall + UP-Fall)
```bash
cd data/raw/wearable_ml_datasets/
git clone https://github.com/mojtabaSefidi/Fall-Detection-System.git sisfall
git clone https://github.com/jpnm561/HAR-UP.git upfall
cd ../../..
```

### Verify All Downloads
```bash
echo "=== Dataset Verification ==="
echo "WESAD:"     && ls data/raw/wearable_ml_datasets/WESAD/S*/S*.pkl 2>/dev/null | wc -l && echo "subjects found"
echo "PPG-DaLiA:" && ls data/raw/wearable_ml_datasets/PPG_FieldStudy/S*/S*.pkl 2>/dev/null | wc -l && echo "subjects found"
echo "MIT-BIH:"   && ls data/raw/wearable_ml_datasets/mit-bih-arrhythmia-database-1.0.0/*.dat 2>/dev/null | wc -l && echo "records found"
echo "HIFD:"      && ls data/raw/wearable_ml_datasets/HR_IMU_falldetection_dataset-master/*.mat 2>/dev/null | wc -l && echo "mat files found"
```

Expected output:
```
WESAD:     15 subjects found
PPG-DaLiA: 15 subjects found
MIT-BIH:   48 records found
HIFD:      ~20 mat files found
```

---

## 6. Environment Setup

### Create Virtual Environment
```bash
cd trident  # or wherever the repo is

# Create venv
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### Install Dependencies
```bash
# Core project deps
pip install -r requirements-prod.txt

# ML training-specific deps (not in prod requirements)
pip install xgboost joblib wfdb pyarrow

# Verify critical imports
python3 -c "
import xgboost; print(f'✅ XGBoost {xgboost.__version__}')
import sklearn; print(f'✅ scikit-learn {sklearn.__version__}')
import pandas; print(f'✅ pandas {pandas.__version__}')
import numpy; print(f'✅ numpy {numpy.__version__}')
import scipy; print(f'✅ scipy {scipy.__version__}')
import joblib; print(f'✅ joblib {joblib.__version__}')
try:
    import wfdb; print(f'✅ wfdb {wfdb.__version__}')
except: print('⚠️  wfdb not installed (needed for MIT-BIH)')
print('All imports OK')
"
```

---

## 7. Training Execution

### Option A: Full Pipeline (Fusion + Training)
This parses all raw datasets, generates synthetic trajectories, fuses everything, and trains:
```bash
python src/ml/train_wearable_model.py
```

### Option B: With Custom Parameters
```bash
python src/ml/train_wearable_model.py \
    --n-estimators 500 \
    --max-depth 8 \
    --learning-rate 0.05 \
    --data-root data/raw/wearable_ml_datasets/
```

### Option C: Run Fusion Separately, Then Train
```bash
# Step 1: Run fusion only (creates parquet splits)
python src/ml/dataset_fusion_synthesizer.py

# Step 2: Train from existing splits (skip re-fusion)
python src/ml/train_wearable_model.py --skip-fusion
```

### Expected Output
```
═══ TRIDENT Dataset Fusion Pipeline Starting ═══
Parsing WESAD subject S2...
...
WESAD: Extracted XXXX windows
Parsing HIFD subject fall1...
...
MIT-BIH: Extracted XXXX windows
Synthetic: Generated 20000 trajectory windows
Total fused records: XXXXX
Saved full matrix: data/processed/fused_training_matrix.parquet
Split: Train=XXXXX, Val=XXXX, Test=XXXX

Training XGBoost: 500 rounds, depth=8, lr=0.05
...
Best iteration: XXX, Best score: X.XXXXXX

Classification Report (Holdout Test Set)
...

✅ Model saved: src/ml/wearable_health_model.pkl (X.XX MB)
═══ Training Complete ═══
```

### Verify Trained Model
```bash
# Check model file exists and is reasonable size
ls -lh src/ml/wearable_health_model.pkl

# Quick inference test
python3 -c "
import joblib
import numpy as np

model = joblib.load('src/ml/wearable_health_model.pkl')
print(f'✅ Model loaded: {type(model).__name__}')
print(f'   Classes: {model.classes_}')
print(f'   Best iteration: {model.best_iteration}')

# Test with dummy feature vector (15 features)
X = np.array([[75, 75, 5, 1.0, 97, 0, 1.0, 0.1, 0.3, 0, 0, 5.0, 10, 0.8, 0.5]], dtype=np.float32)
pred = model.predict(X)
proba = model.predict_proba(X)
print(f'   Test prediction: state={pred[0]}, risk={1-proba[0][0]:.4f}')
print('✅ Inference working!')
"
```

---

## 8. Post-Training: Deploy the Model

### Commit & Push to GitHub
```bash
git add src/ml/wearable_health_model.pkl
git add data/processed/*.parquet  # optional: include processed data
git commit -m "feat(ml): trained XGBoost 8-state wearable health model"
git push origin main
```

After pushing, Render will auto-deploy. The startup logs should now show:
```
✅ WearableHealthPredictor: XGBoost model loaded from /code/src/ml/wearable_health_model.pkl
🩺 WearableHealthPredictor initialized — mode: xgboost, features: 15, states: 8
```

### If You Can't Push (Lab PC, no git credentials)
```bash
# Export just the model file
cp src/ml/wearable_health_model.pkl /tmp/wearable_health_model.pkl

# Transfer via email/drive/USB later, then on your own machine:
cp wearable_health_model.pkl ~/trident/src/ml/
cd ~/trident
git add src/ml/wearable_health_model.pkl
git commit -m "feat(ml): trained XGBoost 8-state model"
git push origin main
```

---

## 9. Troubleshooting & Debugging

### Problem: `ModuleNotFoundError: No module named 'xgboost'`
```bash
pip install xgboost
# If pip is restricted:
pip install --user xgboost
```

### Problem: `ModuleNotFoundError: No module named 'wfdb'`
```bash
pip install wfdb
# This is only needed for MIT-BIH parsing. Training will still work
# with other datasets + synthetic data even without wfdb.
```

### Problem: `MemoryError` or system hangs during fusion
```bash
# Check available RAM
free -h

# If RAM < 16GB, process datasets one at a time:
python3 -c "
from src.ml.dataset_fusion_synthesizer import DatasetFusionSynthesizer
s = DatasetFusionSynthesizer('data/raw/wearable_ml_datasets')

# Parse one dataset at a time to check memory
print('Testing HIFD...')
df = s.parse_hifd()
print(f'HIFD OK: {len(df)} rows')

print('Testing MIT-BIH...')
df = s.parse_mitbih()
print(f'MIT-BIH OK: {len(df)} rows')

# If WESAD fails due to memory, skip it and rely on synthetic data:
print('Testing synthetic generation...')
df = s.generate_synthetic_trajectories(n_per_state=5000)
print(f'Synthetic OK: {len(df)} rows')
"
```

### Problem: `FileNotFoundError` for dataset paths
```bash
# Verify the expected directory structure
find data/raw/wearable_ml_datasets/ -maxdepth 2 -type d | sort

# Check specific datasets
ls data/raw/wearable_ml_datasets/WESAD/S*/
ls data/raw/wearable_ml_datasets/HR_IMU_falldetection_dataset-master/
ls data/raw/wearable_ml_datasets/mit-bih-arrhythmia-database-1.0.0/*.dat | head -5
```

### Problem: Training runs but accuracy is low
```bash
# Try tuning hyperparameters
python src/ml/train_wearable_model.py \
    --n-estimators 1000 \
    --max-depth 10 \
    --learning-rate 0.03

# Check class distribution in the parquet
python3 -c "
import pandas as pd
df = pd.read_parquet('data/processed/fused_training_matrix.parquet')
print(df['health_state'].value_counts().sort_index())
print(f'Total: {len(df)} rows, Sources: {df[\"source\"].unique()}')
"
```

### Problem: `pickle.UnpicklingError` on WESAD `.pkl` files
```bash
# WESAD pickles require Python 3 with latin1 encoding
python3 -c "
import pickle
with open('data/raw/wearable_ml_datasets/WESAD/S2/S2.pkl', 'rb') as f:
    data = pickle.load(f, encoding='latin1')
print(f'Keys: {data.keys()}')
print(f'Signal keys: {data[\"signal\"].keys()}')
"
```

### Problem: Can't install packages at all (restricted lab PC)
```bash
# Use --user flag for all pip installs
pip install --user -r requirements-prod.txt
pip install --user xgboost joblib wfdb pyarrow

# If pip itself is missing, try:
python3 -m ensurepip --user
python3 -m pip install --user xgboost joblib
```

### Problem: `git push` authentication fails
```bash
# Option 1: Use HTTPS with token
git remote set-url origin https://<your-github-token>@github.com/harshitworkmain/trident.git

# Option 2: Just export the model file and transfer it manually
cp src/ml/wearable_health_model.pkl ~/Desktop/
# Transfer via email, Google Drive, USB, etc.
```

### Check Everything Is Working (Master Diagnostic)
```bash
echo "=== TRIDENT Training Diagnostic ==="
echo ""
echo "1. Python:"
python3 --version
echo ""
echo "2. Critical Packages:"
python3 -c "import xgboost, sklearn, pandas, numpy, scipy, joblib; print('All OK')" 2>&1
echo ""
echo "3. Dataset Directories:"
for d in WESAD PPG_FieldStudy mit-bih-arrhythmia-database-1.0.0 HR_IMU_falldetection_dataset-master; do
    if [ -d "data/raw/wearable_ml_datasets/$d" ]; then
        echo "  ✅ $d"
    else
        echo "  ❌ $d MISSING"
    fi
done
echo ""
echo "4. ML Scripts:"
for f in src/ml/wearable_model.py src/ml/dataset_fusion_synthesizer.py src/ml/train_wearable_model.py; do
    python3 -c "import py_compile; py_compile.compile('$f', doraise=True)" 2>/dev/null && echo "  ✅ $f" || echo "  ❌ $f SYNTAX ERROR"
done
echo ""
echo "5. Model Status:"
if [ -f "src/ml/wearable_health_model.pkl" ]; then
    echo "  ✅ Model exists ($(du -h src/ml/wearable_health_model.pkl | cut -f1))"
else
    echo "  ⏳ Model not yet trained — run: python src/ml/train_wearable_model.py"
fi
echo ""
echo "=== Diagnostic Complete ==="
```

---

## File Reference

| File | Purpose |
|------|---------|
| `src/ml/wearable_model.py` | WearableHealthPredictor class (inference + heuristic fallback) |
| `src/ml/dataset_fusion_synthesizer.py` | Multi-dataset parser + synthetic trajectory generator |
| `src/ml/train_wearable_model.py` | Training entrypoint (CLI with argparse) |
| `src/ml/wearable_health_model.pkl` | Trained model output (created after training) |
| `data/processed/fused_training_matrix.parquet` | Full fused feature matrix |
| `data/processed/train_split.parquet` | 70% training split |
| `data/processed/val_split.parquet` | 15% validation split |
| `data/processed/test_split.parquet` | 15% holdout test split |
| `docs/WEARABLE_ML_SUBPROJECT_CONTEXT.md` | Full architecture context & iteration log |
| `docs/TRAINING_GUIDE.md` | This file |
