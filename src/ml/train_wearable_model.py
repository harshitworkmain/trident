"""
TRIDENT XGBoost Training Script — 8-State Disaster Trauma Classifier.

Training entrypoint designed to run on a high-RAM / GPU compute machine.
Reads fused parquet splits, trains a multi-class XGBoost classifier, and
exports the trained model as wearable_health_model.pkl.

Usage (from project root):
    python src/ml/train_wearable_model.py

    Optional arguments:
        --data-root    Path to data/raw/wearable_ml_datasets/ (runs fusion first)
        --skip-fusion  Skip dataset fusion, use existing parquet splits
        --n-estimators Number of boosting rounds (default: 500)
        --max-depth    Maximum tree depth (default: 8)
        --learning-rate Learning rate (default: 0.05)
        --output       Output model path (default: src/ml/wearable_health_model.pkl)

Requirements:
    pip install xgboost scikit-learn joblib pandas numpy
    pip install wfdb scipy  (for dataset parsing)
"""

import os
import sys
import logging
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

FEATURE_COLS = [
    'bpm_current', 'bpm_mean_15s', 'bpm_std_15s',
    'pulse_amp_decay', 'spo2_current', 'spo2_slope',
    'acc_mag_max_3s', 'motion_stasis', 'gsr_stress_norm',
    'gsr_slope', 'fall_flag', 'gps_displacement_15s',
    'ksc', 'ssi', 'eim',
]

HEALTH_STATES = {
    0: 'STABLE',
    1: 'ELEVATED_STRESS',
    2: 'HYPOTHERMIA_RISK',
    3: 'ASPIRATION_HYPOXIA',
    4: 'HEMORRHAGIC_SHOCK',
    5: 'CONCUSSIVE_STASIS',
    6: 'CRUSH_ENTRAPMENT',
    7: 'CARDIAC_ARREST',
}

TARGET_COL = 'health_state'


def load_splits(processed_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load pre-computed train/val/test parquet splits."""
    train_path = processed_dir / 'train_split.parquet'
    val_path = processed_dir / 'val_split.parquet'
    test_path = processed_dir / 'test_split.parquet'

    for p in [train_path, val_path, test_path]:
        if not p.exists():
            raise FileNotFoundError(
                f"Split file not found: {p}\n"
                "Run dataset fusion first: python src/ml/dataset_fusion_synthesizer.py"
            )

    train_df = pd.read_parquet(train_path)
    val_df = pd.read_parquet(val_path)
    test_df = pd.read_parquet(test_path)

    logger.info(f"Loaded splits — Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")
    return train_df, val_df, test_df


def train_xgboost(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    n_estimators: int = 500,
    max_depth: int = 8,
    learning_rate: float = 0.05,
):
    """Train multi-class XGBoost classifier with early stopping.

    Returns:
        Trained XGBClassifier model.
    """
    try:
        from xgboost import XGBClassifier
    except ImportError:
        logger.error("xgboost not installed. Install with: pip install xgboost")
        sys.exit(1)

    X_train = train_df[FEATURE_COLS].values.astype(np.float32)
    y_train = train_df[TARGET_COL].values.astype(int)
    X_val = val_df[FEATURE_COLS].values.astype(np.float32)
    y_val = val_df[TARGET_COL].values.astype(int)

    n_classes = len(HEALTH_STATES)

    logger.info(f"Training XGBoost: {n_estimators} rounds, depth={max_depth}, lr={learning_rate}")
    logger.info(f"Features: {len(FEATURE_COLS)}, Classes: {n_classes}")
    logger.info(f"Train shape: {X_train.shape}, Val shape: {X_val.shape}")

    model = XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        objective='multi:softprob',
        num_class=n_classes,
        eval_metric='mlogloss',
        early_stopping_rounds=15,
        tree_method='hist',        # Memory-efficient histogram-based
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        min_child_weight=5,
        random_state=42,
        n_jobs=-1,
        verbosity=1,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=True,
    )

    logger.info(f"Best iteration: {model.best_iteration}, Best score: {model.best_score:.6f}")
    return model


def evaluate_model(model, test_df: pd.DataFrame) -> None:
    """Evaluate trained model on holdout test set."""
    try:
        from sklearn.metrics import classification_report, confusion_matrix
    except ImportError:
        logger.warning("sklearn not available for evaluation metrics")
        return

    X_test = test_df[FEATURE_COLS].values.astype(np.float32)
    y_test = test_df[TARGET_COL].values.astype(int)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)

    # Classification report
    target_names = [f"{k}: {v}" for k, v in sorted(HEALTH_STATES.items())]
    report = classification_report(y_test, y_pred, target_names=target_names, zero_division=0)
    logger.info(f"\n{'='*60}\nClassification Report (Holdout Test Set)\n{'='*60}\n{report}")

    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    logger.info(f"\nConfusion Matrix:\n{cm}")

    # Per-class accuracy
    for state_id, state_name in sorted(HEALTH_STATES.items()):
        mask = y_test == state_id
        if mask.sum() > 0:
            acc = (y_pred[mask] == state_id).mean()
            logger.info(f"  {state_name:25s}: {acc:.3f} accuracy ({mask.sum()} samples)")

    # Risk score bounds check
    risk_scores = 1.0 - y_proba[:, 0]  # 1 - P(STABLE)
    logger.info(f"\nRisk score range: [{risk_scores.min():.4f}, {risk_scores.max():.4f}]")
    assert 0.0 <= risk_scores.min() and risk_scores.max() <= 1.0, \
        "Risk score out of bounds [0, 1]!"


def save_model(model, output_path: str) -> None:
    """Save trained model using joblib."""
    try:
        import joblib
    except ImportError:
        logger.error("joblib not installed. Install with: pip install joblib")
        sys.exit(1)

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    joblib.dump(model, output_path)
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    logger.info(f"✅ Model saved: {output_path} ({size_mb:.2f} MB)")


def main():
    parser = argparse.ArgumentParser(description='TRIDENT XGBoost Wearable Health Model Training')
    parser.add_argument('--data-root', type=str, default=None,
                        help='Path to data/raw/wearable_ml_datasets/')
    parser.add_argument('--skip-fusion', action='store_true',
                        help='Skip dataset fusion, use existing parquet splits')
    parser.add_argument('--n-estimators', type=int, default=500,
                        help='Number of boosting rounds')
    parser.add_argument('--max-depth', type=int, default=8,
                        help='Maximum tree depth')
    parser.add_argument('--learning-rate', type=float, default=0.05,
                        help='Learning rate (eta)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output model path')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )

    # Resolve paths
    project_root = Path(__file__).resolve().parent.parent.parent
    ml_dir = Path(__file__).resolve().parent

    if args.data_root:
        data_root = Path(args.data_root)
    else:
        data_root = project_root / 'data' / 'raw' / 'wearable_ml_datasets'

    processed_dir = project_root / 'data' / 'processed'
    output_path = args.output or str(ml_dir / 'wearable_health_model.pkl')

    logger.info("═══════════════════════════════════════════════════════════")
    logger.info("  TRIDENT Wearable Health Model — XGBoost Training Script")
    logger.info("═══════════════════════════════════════════════════════════")
    logger.info(f"Data root:     {data_root}")
    logger.info(f"Processed dir: {processed_dir}")
    logger.info(f"Output model:  {output_path}")

    # Step 1: Dataset fusion (or load existing)
    if not args.skip_fusion:
        from dataset_fusion_synthesizer import DatasetFusionSynthesizer
        synthesizer = DatasetFusionSynthesizer(str(data_root))
        train_df, val_df, test_df = synthesizer.run_full_pipeline()
    else:
        train_df, val_df, test_df = load_splits(processed_dir)

    # Step 2: Train XGBoost
    model = train_xgboost(
        train_df, val_df,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
    )

    # Step 3: Evaluate on holdout test
    evaluate_model(model, test_df)

    # Step 4: Save model
    save_model(model, output_path)

    logger.info("═══ Training Complete ═══")


if __name__ == '__main__':
    main()
