import os
import sys
import time
import datetime
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, log_loss
from sklearn.model_selection import GroupShuffleSplit
import joblib

# ML libraries
import xgboost as xgb
import lightgbm as lgb
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader

# ---------------------------------------------------------------------------
# Setup Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FEATURE_COLS = [
    'bpm_current', 'bpm_mean_15s', 'bpm_std_15s',
    'pulse_amp_decay', 'spo2_current', 'spo2_slope',
    'acc_mag_max_3s', 'motion_stasis', 'gsr_stress_norm',
    'gsr_slope', 'fall_flag', 'gps_displacement_15s',
    'ksc', 'ssi', 'eim',
]

STATE_NAMES = {
    0: 'STABLE', 1: 'ELEVATED_STRESS', 2: 'HYPOTHERMIA_RISK',
    3: 'ASPIRATION_HYPOXIA', 4: 'HEMORRHAGIC_SHOCK',
    5: 'CONCUSSIVE_STASIS', 6: 'CRUSH_ENTRAPMENT', 7: 'CARDIAC_ARREST'
}

NUM_CLASSES = len(STATE_NAMES)

# ---------------------------------------------------------------------------
# Device Configuration
# ---------------------------------------------------------------------------
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
logger.info(f"Using PyTorch device: {DEVICE}")

# ---------------------------------------------------------------------------
# Base Model Interface
# ---------------------------------------------------------------------------
class BaseModel(ABC):
    name: str

    @abstractmethod
    def train(self, X_train: pd.DataFrame, y_train: pd.Series, X_val: pd.DataFrame, y_val: pd.Series) -> dict:
        """Trains the model and returns training info."""
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predicts class labels."""
        pass

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predicts class probabilities."""
        pass

    @abstractmethod
    def save(self, path: str):
        """Saves the model to the given path."""
        pass

    @abstractmethod
    def get_model_size_mb(self) -> float:
        """Returns the size of the model in MB."""
        pass

# ---------------------------------------------------------------------------
# XGBoost Model
# ---------------------------------------------------------------------------
class XGBoostModel(BaseModel):
    def __init__(self):
        self.name = 'XGBoost'
        self.model = None

    def train(self, X_train, y_train, X_val, y_val) -> dict:
        tree_method = 'gpu_hist' if torch.cuda.is_available() else 'hist'
        self.model = xgb.XGBClassifier(
            tree_method=tree_method,
            objective='multi:softprob',
            num_class=NUM_CLASSES,
            eval_metric='mlogloss',
            early_stopping_rounds=15,
            n_estimators=500,
            use_label_encoder=False
        )
        
        start_time = time.time()
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        train_time = time.time() - start_time
        return {"train_time": train_time, "best_iteration": self.model.best_iteration}

    def predict(self, X) -> np.ndarray:
        return self.model.predict(X)

    def predict_proba(self, X) -> np.ndarray:
        return self.model.predict_proba(X)

    def save(self, path: str):
        joblib.dump(self.model, path)

    def get_model_size_mb(self) -> float:
        temp_path = 'temp_xgb.pkl'
        joblib.dump(self.model, temp_path)
        size = os.path.getsize(temp_path) / (1024 * 1024)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return size

# ---------------------------------------------------------------------------
# LightGBM Model
# ---------------------------------------------------------------------------
class LightGBMModel(BaseModel):
    def __init__(self):
        self.name = 'LightGBM'
        self.model = None

    def train(self, X_train, y_train, X_val, y_val) -> dict:
        device_type = 'gpu' if torch.cuda.is_available() else 'cpu'
        self.model = lgb.LGBMClassifier(
            objective='multiclass',
            num_class=NUM_CLASSES,
            n_estimators=500,
            device=device_type
        )
        
        # LightGBM early stopping is configured via callbacks in newer versions
        start_time = time.time()
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(stopping_rounds=15, verbose=False)]
        )
        train_time = time.time() - start_time
        return {"train_time": train_time, "best_iteration": self.model.best_iteration_}

    def predict(self, X) -> np.ndarray:
        return self.model.predict(X)

    def predict_proba(self, X) -> np.ndarray:
        return self.model.predict_proba(X)

    def save(self, path: str):
        joblib.dump(self.model, path)

    def get_model_size_mb(self) -> float:
        temp_path = 'temp_lgb.pkl'
        joblib.dump(self.model, temp_path)
        size = os.path.getsize(temp_path) / (1024 * 1024)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return size

# ---------------------------------------------------------------------------
# PyTorch Helper for Training
# ---------------------------------------------------------------------------
def train_pytorch_model(model, X_train, y_train, X_val, y_val, reshape_1d=False):
    # Impute NaNs with 0
    X_train_clean = X_train.fillna(0).values
    X_val_clean = X_val.fillna(0).values
    y_train_clean = y_train.values
    y_val_clean = y_val.values

    if reshape_1d:
        X_train_clean = X_train_clean.reshape(-1, 1, X_train_clean.shape[1])
        X_val_clean = X_val_clean.reshape(-1, 1, X_val_clean.shape[1])

    X_train_t = torch.tensor(X_train_clean, dtype=torch.float32)
    y_train_t = torch.tensor(y_train_clean, dtype=torch.long)
    X_val_t = torch.tensor(X_val_clean, dtype=torch.float32)
    y_val_t = torch.tensor(y_val_clean, dtype=torch.long)

    train_dataset = TensorDataset(X_train_t, y_train_t)
    val_dataset = TensorDataset(X_val_t, y_val_t)
    
    batch_size = 256
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    model.to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-3)

    best_val_loss = float('inf')
    patience = 10
    patience_counter = 0
    best_model_state = None

    start_time = time.time()
    epochs = 100
    
    for epoch in range(epochs):
        model.train()
        for batch_x, batch_y in train_loader:
            batch_x, batch_y = batch_x.to(DEVICE), batch_y.to(DEVICE)
            optimizer.zero_grad()
            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                batch_x, batch_y = batch_x.to(DEVICE), batch_y.to(DEVICE)
                outputs = model(batch_x)
                loss = criterion(outputs, batch_y)
                val_loss += loss.item() * batch_x.size(0)
        val_loss /= len(val_dataset)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_model_state = model.state_dict().copy()
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break
                
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
        
    train_time = time.time() - start_time
    return {"train_time": train_time, "epochs_trained": epoch + 1 - patience_counter}

def predict_pytorch_model(model, X, reshape_1d=False, proba=False):
    model.eval()
    X_clean = X.fillna(0).values
    if reshape_1d:
        X_clean = X_clean.reshape(-1, 1, X_clean.shape[1])
        
    X_t = torch.tensor(X_clean, dtype=torch.float32)
    dataset = TensorDataset(X_t)
    loader = DataLoader(dataset, batch_size=256, shuffle=False)
    
    all_preds = []
    with torch.no_grad():
        for batch_x, in loader:
            batch_x = batch_x.to(DEVICE)
            outputs = model(batch_x)
            if proba:
                probs = torch.softmax(outputs, dim=1)
                all_preds.append(probs.cpu().numpy())
            else:
                preds = torch.argmax(outputs, dim=1)
                all_preds.append(preds.cpu().numpy())
                
    return np.concatenate(all_preds, axis=0)

# ---------------------------------------------------------------------------
# Temporal 1D CNN Model
# ---------------------------------------------------------------------------
class CNN1DNetwork(nn.Module):
    def __init__(self, num_features, num_classes):
        super(CNN1DNetwork, self).__init__()
        self.conv1 = nn.Conv1d(1, 32, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm1d(32)
        self.conv2 = nn.Conv1d(32, 64, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm1d(64)
        self.conv3 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm1d(128)
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.fc1 = nn.Linear(128, 64)
        self.dropout = nn.Dropout(0.3)
        self.fc2 = nn.Linear(64, num_classes)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.relu(self.bn1(self.conv1(x)))
        x = self.relu(self.bn2(self.conv2(x)))
        x = self.relu(self.bn3(self.conv3(x)))
        x = self.pool(x)
        x = torch.flatten(x, 1)
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        return x

class TemporalCNN1DModel(BaseModel):
    def __init__(self):
        self.name = 'TemporalCNN1D'
        self.model = CNN1DNetwork(num_features=len(FEATURE_COLS), num_classes=NUM_CLASSES)

    def train(self, X_train, y_train, X_val, y_val) -> dict:
        return train_pytorch_model(self.model, X_train, y_train, X_val, y_val, reshape_1d=True)

    def predict(self, X) -> np.ndarray:
        return predict_pytorch_model(self.model, X, reshape_1d=True, proba=False)

    def predict_proba(self, X) -> np.ndarray:
        return predict_pytorch_model(self.model, X, reshape_1d=True, proba=True)

    def save(self, path: str):
        torch.save(self.model.state_dict(), path)

    def get_model_size_mb(self) -> float:
        temp_path = 'temp_cnn.pth'
        torch.save(self.model.state_dict(), temp_path)
        size = os.path.getsize(temp_path) / (1024 * 1024)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return size

# ---------------------------------------------------------------------------
# Feed Forward MLP Model
# ---------------------------------------------------------------------------
class MLPNetwork(nn.Module):
    def __init__(self, num_features, num_classes):
        super(MLPNetwork, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(num_features, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.3),
            
            nn.Linear(128, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.3),
            
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.3),
            
            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(0.3),
            
            nn.Linear(64, num_classes)
        )

    def forward(self, x):
        return self.net(x)

class FeedForwardMLPModel(BaseModel):
    def __init__(self):
        self.name = 'FeedForwardMLP'
        self.model = MLPNetwork(num_features=len(FEATURE_COLS), num_classes=NUM_CLASSES)

    def train(self, X_train, y_train, X_val, y_val) -> dict:
        return train_pytorch_model(self.model, X_train, y_train, X_val, y_val, reshape_1d=False)

    def predict(self, X) -> np.ndarray:
        return predict_pytorch_model(self.model, X, reshape_1d=False, proba=False)

    def predict_proba(self, X) -> np.ndarray:
        return predict_pytorch_model(self.model, X, reshape_1d=False, proba=True)

    def save(self, path: str):
        torch.save(self.model.state_dict(), path)

    def get_model_size_mb(self) -> float:
        temp_path = 'temp_mlp.pth'
        torch.save(self.model.state_dict(), temp_path)
        size = os.path.getsize(temp_path) / (1024 * 1024)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return size

# ---------------------------------------------------------------------------
# Tournament Logic
# ---------------------------------------------------------------------------
def split_by_subject(df: pd.DataFrame, subject_col: str = 'subject_id'):
    """Splits data 70/15/15 by subject_id"""
    gss1 = GroupShuffleSplit(n_splits=1, train_size=0.7, random_state=42)
    train_idx, temp_idx = next(gss1.split(df, groups=df[subject_col]))
    
    train_df = df.iloc[train_idx]
    temp_df = df.iloc[temp_idx]
    
    gss2 = GroupShuffleSplit(n_splits=1, train_size=0.5, random_state=42)
    val_idx, test_idx = next(gss2.split(temp_df, groups=temp_df[subject_col]))
    
    val_df = temp_df.iloc[val_idx]
    test_df = temp_df.iloc[test_idx]
    
    return train_df, val_df, test_df

def evaluate_model(model: BaseModel, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    start_time = time.perf_counter()
    y_pred = model.predict(X_test)
    end_time = time.perf_counter()
    
    latency_ms = ((end_time - start_time) / len(X_test)) * 1000
    
    y_proba = model.predict_proba(X_test)
    
    acc = accuracy_score(y_test, y_pred)
    mac_f1 = f1_score(y_test, y_pred, average='macro', zero_division=0)
    mac_prec = precision_score(y_test, y_pred, average='macro', zero_division=0)
    mac_rec = recall_score(y_test, y_pred, average='macro', zero_division=0)
    ll = log_loss(y_test, y_proba, labels=range(NUM_CLASSES))
    
    class_f1 = f1_score(y_test, y_pred, average=None, zero_division=0, labels=range(NUM_CLASSES))
    
    return {
        "Accuracy": acc,
        "Macro-F1": mac_f1,
        "Precision": mac_prec,
        "Recall": mac_rec,
        "Log-Loss": ll,
        "Latency(ms)": latency_ms,
        "Size(MB)": model.get_model_size_mb(),
        "Class_F1": {STATE_NAMES[i]: class_f1[i] for i in range(NUM_CLASSES)}
    }

def generate_markdown_report(docs_dir: Path, stage_name: str, results: list, winner_name: str):
    docs_dir.mkdir(parents=True, exist_ok=True)
    report_path = docs_dir / 'MODEL_TOURNAMENT_RESULTS.md'
    
    is_new = not report_path.exists()
    
    with open(report_path, 'a') as f:
        if is_new:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"# TRIDENT Multi-Model Tournament Results\n")
            f.write(f"> Auto-generated by `multi_model_tournament.py`\n")
            f.write(f"> Date: {timestamp}\n\n")
            
        f.write(f"## {stage_name}\n\n")
        f.write("| Model | Accuracy | Macro-F1 | Precision | Recall | Log-Loss | Latency(ms) | Size(MB) |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        
        for res in results:
            f.write(f"| {res['model']} | {res['Accuracy']:.4f} | {res['Macro-F1']:.4f} | {res['Precision']:.4f} | "
                    f"{res['Recall']:.4f} | {res['Log-Loss']:.4f} | {res['Latency(ms)']:.4f} | {res['Size(MB)']:.2f} |\n")
            
        f.write("\n### Per-Class F1 Scores\n\n")
        header_classes = " | ".join(STATE_NAMES.values())
        header_sep = " | ".join(["---"] * len(STATE_NAMES))
        f.write(f"| Model | {header_classes} |\n")
        f.write(f"|---|{header_sep}|\n")
        
        for res in results:
            class_scores = " | ".join([f"{res['Class_F1'][c]:.4f}" for c in STATE_NAMES.values()])
            f.write(f"| {res['model']} | {class_scores} |\n")
            
        f.write(f"\n**Stage Winner(s) / Advancing:** {winner_name}\n\n")

def run_tournament(parquet_path: str, output_dir: str, docs_dir: str):
    logger.info(f"Loading data from {parquet_path}")
    df = pd.read_parquet(parquet_path)
    
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    d_path = Path(docs_dir)
    d_path.mkdir(parents=True, exist_ok=True)
    
    subjects = df['subject_id'].unique()
    np.random.seed(42)
    shuffled_subjects = np.random.permutation(subjects)
    
    # Init Models
    models = [
        XGBoostModel(),
        LightGBMModel(),
        TemporalCNN1DModel(),
        FeedForwardMLPModel()
    ]
    
    # -----------------------------------------------------------------------
    # Stage 1: 10% Screening
    # -----------------------------------------------------------------------
    logger.info("=== Stage 1: 10% Screening ===")
    n_subj_s1 = max(1, int(len(shuffled_subjects) * 0.10))
    s1_subjects = shuffled_subjects[:n_subj_s1]
    df_s1 = df[df['subject_id'].isin(s1_subjects)].copy()
    
    train_s1, val_s1, test_s1 = split_by_subject(df_s1)
    
    X_tr, y_tr = train_s1[FEATURE_COLS], train_s1['health_state']
    X_v, y_v = val_s1[FEATURE_COLS], val_s1['health_state']
    X_te, y_te = test_s1[FEATURE_COLS], test_s1['health_state']
    
    s1_results = []
    for model in models:
        logger.info(f"Training {model.name}...")
        model.train(X_tr, y_tr, X_v, y_v)
        res = evaluate_model(model, X_te, y_te)
        res['model'] = model.name
        res['obj'] = model
        s1_results.append(res)
        
    # Rank by Macro F1
    s1_results.sort(key=lambda x: x['Macro-F1'], reverse=True)
    top_2 = s1_results[:2]
    top_2_names = ", ".join([r['model'] for r in top_2])
    
    logger.info(f"Stage 1 Top 2: {top_2_names}")
    generate_markdown_report(d_path, "Stage 1: 10% Screening", s1_results, top_2_names)
    
    # -----------------------------------------------------------------------
    # Stage 2: 35% Semifinal
    # -----------------------------------------------------------------------
    logger.info("=== Stage 2: 35% Semifinal ===")
    n_subj_s2 = max(1, int(len(shuffled_subjects) * 0.35))
    s2_subjects = shuffled_subjects[:n_subj_s2]
    df_s2 = df[df['subject_id'].isin(s2_subjects)].copy()
    
    train_s2, val_s2, test_s2 = split_by_subject(df_s2)
    
    X_tr, y_tr = train_s2[FEATURE_COLS], train_s2['health_state']
    X_v, y_v = val_s2[FEATURE_COLS], val_s2['health_state']
    X_te, y_te = test_s2[FEATURE_COLS], test_s2['health_state']
    
    s2_models = [r['obj'] for r in top_2]
    s2_results = []
    
    for model in s2_models:
        # Re-initialize to avoid data leakage / continue training
        if model.name == 'XGBoost':
            model = XGBoostModel()
        elif model.name == 'LightGBM':
            model = LightGBMModel()
        elif model.name == 'TemporalCNN1D':
            model = TemporalCNN1DModel()
        elif model.name == 'FeedForwardMLP':
            model = FeedForwardMLPModel()
            
        logger.info(f"Training {model.name}...")
        model.train(X_tr, y_tr, X_v, y_v)
        res = evaluate_model(model, X_te, y_te)
        res['model'] = model.name
        res['obj'] = model
        s2_results.append(res)
        
    s2_results.sort(key=lambda x: x['Macro-F1'], reverse=True)
    top_1 = s2_results[0]
    top_1_name = top_1['model']
    
    logger.info(f"Stage 2 Winner: {top_1_name}")
    generate_markdown_report(d_path, "Stage 2: 35% Semifinal", s2_results, top_1_name)
    
    # -----------------------------------------------------------------------
    # Stage 3: 100% Champion
    # -----------------------------------------------------------------------
    logger.info("=== Stage 3: 100% Champion ===")
    train_s3, val_s3, test_s3 = split_by_subject(df)
    
    X_tr, y_tr = train_s3[FEATURE_COLS], train_s3['health_state']
    X_v, y_v = val_s3[FEATURE_COLS], val_s3['health_state']
    X_te, y_te = test_s3[FEATURE_COLS], test_s3['health_state']
    
    champion_model = top_1['obj']
    # Re-initialize champion
    if champion_model.name == 'XGBoost':
        champion_model = XGBoostModel()
    elif champion_model.name == 'LightGBM':
        champion_model = LightGBMModel()
    elif champion_model.name == 'TemporalCNN1D':
        champion_model = TemporalCNN1DModel()
    elif champion_model.name == 'FeedForwardMLP':
        champion_model = FeedForwardMLPModel()
        
    logger.info(f"Training Champion {champion_model.name} on 100% data...")
    champion_model.train(X_tr, y_tr, X_v, y_v)
    res = evaluate_model(champion_model, X_te, y_te)
    res['model'] = champion_model.name
    
    logger.info(f"Stage 3 completed. Final Macro-F1: {res['Macro-F1']:.4f}")
    generate_markdown_report(d_path, "Stage 3: 100% Champion", [res], champion_model.name)
    
    # Save Model
    final_model_path = out_path / 'wearable_health_model.pkl'
    logger.info(f"Exporting model to {final_model_path}")
    
    # Even PyTorch models get saved via joblib wrap or custom logic, 
    # but the instructions requested `joblib` for the final model export.
    # To satisfy `joblib` constraint explicitly:
    if champion_model.name in ['TemporalCNN1D', 'FeedForwardMLP']:
        # PyTorch models should ideally be saved via torch.save but we will use joblib to serialize the object
        joblib.dump(champion_model, final_model_path)
    else:
        champion_model.save(final_model_path)
        
    logger.info("Tournament Complete!")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="TRIDENT Multi-Model Tournament")
    parser.add_argument('--data', default='data/processed/fused_training_matrix.parquet', help="Path to parquet data file")
    parser.add_argument('--output', default='src/ml', help="Directory to save the final model")
    parser.add_argument('--docs', default='docs', help="Directory to save the markdown report")
    args = parser.parse_args()
    
    run_tournament(args.data, args.output, args.docs)
