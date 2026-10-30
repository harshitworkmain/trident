"""Tournament candidates behind one interface.

    logreg   - baseline: median impute + standardise + L2 logistic regression
    xgboost  - gradient-boosted trees, native NaN handling
    lightgbm - leaf-wise gradient-boosted trees, native NaN handling
    mlp      - PyTorch MLP (BatchNorm, ReLU, Dropout) on tabular features
    cnn1d    - PyTorch temporal 1D-CNN on the raw frame sequence (T x C) of each window
    extratrees - extremely randomised trees (P3 v2)
    minirocket - MiniRocket sequence features + tabular features -> logistic regression (P3 v2)

Stage 3 additionally scores a soft-vote (mean probability) of the two tuned finalists.

All candidates are class-balanced, deterministic for a given seed and expose
`fit / predict_proba / size_bytes`, plus an Optuna search space via `suggest`.
"""

from __future__ import annotations

import io
import pickle
from typing import Dict, Optional

import numpy as np
import optuna
import torch
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight, compute_sample_weight

N_JOBS = 4
torch.set_num_threads(N_JOBS)


class Candidate:
    name: str = ''
    input_kind: str = 'tabular'   # 'tabular' -> X (n, F); 'sequence' -> S (n, T, C)

    def __init__(self, n_classes: int, params: Optional[dict] = None, seed: int = 42):
        self.n_classes = n_classes
        self.params = {**self.default_params(), **(params or {})}
        self.seed = seed

    @staticmethod
    def default_params() -> dict:
        return {}

    @staticmethod
    def suggest(trial: optuna.Trial) -> dict:
        return {}

    def fit(self, X: np.ndarray, S: np.ndarray, y: np.ndarray, groups: np.ndarray) -> 'Candidate':
        raise NotImplementedError

    def predict_proba(self, X: np.ndarray, S: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def size_bytes(self) -> int:
        raise NotImplementedError


# ─── classical ───────────────────────────────────────────────────────────────

class LogRegCandidate(Candidate):
    name = 'logreg'

    @staticmethod
    def default_params() -> dict:
        return {'C': 1.0}

    @staticmethod
    def suggest(trial):
        return {'C': trial.suggest_float('C', 1e-3, 10.0, log=True)}

    def fit(self, X, S, y, groups):
        self.model = make_pipeline(
            SimpleImputer(strategy='median', keep_empty_features=True), StandardScaler(),
            LogisticRegression(C=self.params['C'], class_weight='balanced', max_iter=3000))
        self.model.fit(X, y)
        return self

    def predict_proba(self, X, S):
        return self.model.predict_proba(X)

    def size_bytes(self):
        return len(pickle.dumps(self.model))


class XGBoostCandidate(Candidate):
    name = 'xgboost'

    @staticmethod
    def default_params():
        return {'n_estimators': 300, 'max_depth': 6, 'learning_rate': 0.08, 'subsample': 0.8,
                'colsample_bytree': 0.8, 'min_child_weight': 1.0, 'reg_lambda': 1.0}

    @staticmethod
    def suggest(trial):
        return {
            'n_estimators': trial.suggest_int('n_estimators', 100, 800, step=50),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'learning_rate': trial.suggest_float('learning_rate', 0.02, 0.3, log=True),
            'subsample': trial.suggest_float('subsample', 0.6, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
            'min_child_weight': trial.suggest_float('min_child_weight', 1.0, 20.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-3, 10.0, log=True),
        }

    def fit(self, X, S, y, groups):
        import xgboost as xgb
        self.model = xgb.XGBClassifier(**self.params, tree_method='hist', n_jobs=N_JOBS,
                                       random_state=self.seed, verbosity=0)
        self.model.fit(X, y, sample_weight=compute_sample_weight('balanced', y))
        return self

    def predict_proba(self, X, S):
        return self.model.predict_proba(X)

    def size_bytes(self):
        return len(self.model.get_booster().save_raw('ubj'))


class LightGBMCandidate(Candidate):
    name = 'lightgbm'

    @staticmethod
    def default_params():
        return {'n_estimators': 300, 'num_leaves': 31, 'learning_rate': 0.08, 'min_child_samples': 20,
                'subsample': 0.8, 'colsample_bytree': 0.8, 'reg_lambda': 1.0}

    @staticmethod
    def suggest(trial):
        return {
            'n_estimators': trial.suggest_int('n_estimators', 100, 800, step=50),
            'num_leaves': trial.suggest_int('num_leaves', 15, 127),
            'learning_rate': trial.suggest_float('learning_rate', 0.02, 0.3, log=True),
            'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
            'subsample': trial.suggest_float('subsample', 0.6, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-3, 10.0, log=True),
        }

    def fit(self, X, S, y, groups):
        import lightgbm as lgb
        self.model = lgb.LGBMClassifier(**self.params, subsample_freq=1, class_weight='balanced',
                                        n_jobs=N_JOBS, random_state=self.seed, verbose=-1)
        self.model.fit(X, y)
        return self

    def predict_proba(self, X, S):
        return self.model.predict_proba(X)

    def size_bytes(self):
        return len(self.model.booster_.model_to_string().encode())


# ─── neural ──────────────────────────────────────────────────────────────────

class _MLPNet(torch.nn.Module):
    def __init__(self, n_in, h1, h2, dropout, n_out):
        super().__init__()
        nn = torch.nn
        self.net = nn.Sequential(
            nn.Linear(n_in, h1), nn.BatchNorm1d(h1), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(h1, h2), nn.BatchNorm1d(h2), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(h2, n_out))

    def forward(self, x):
        return self.net(x)


class _CNNNet(torch.nn.Module):
    def __init__(self, c_in, T, channels, dropout, n_out):
        super().__init__()
        nn = torch.nn
        k = 3 if T >= 3 else 1
        self.conv = nn.Sequential(
            nn.Conv1d(c_in, channels, k, padding=k // 2), nn.BatchNorm1d(channels), nn.ReLU(), nn.Dropout(dropout),
            nn.Conv1d(channels, 2 * channels, k, padding=k // 2), nn.BatchNorm1d(2 * channels), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(4 * channels, 2 * channels), nn.ReLU(), nn.Dropout(dropout),
                                  nn.Linear(2 * channels, n_out))

    def forward(self, x):                      # x: (N, C, T)
        h = self.conv(x)
        return self.head(torch.cat([h.mean(dim=2), h.amax(dim=2)], dim=1))


class _TorchCandidate(Candidate):
    max_epochs = 40
    patience = 6
    batch_size = 256

    def _prepare_fit(self, A: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def _prepare(self, A: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def _build(self, sample: np.ndarray) -> torch.nn.Module:
        raise NotImplementedError

    def _input(self, X, S):
        return S if self.input_kind == 'sequence' else X

    def fit(self, X, S, y, groups):
        torch.manual_seed(self.seed)
        A = self._prepare_fit(self._input(X, S))
        tr, va = next(GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=self.seed).split(A, y, groups))
        self.net = self._build(A)
        weights = compute_class_weight('balanced', classes=np.arange(self.n_classes), y=y[tr]) \
            if len(np.unique(y[tr])) == self.n_classes else np.ones(self.n_classes)
        loss_fn = torch.nn.CrossEntropyLoss(weight=torch.tensor(weights, dtype=torch.float32))
        opt = torch.optim.AdamW(self.net.parameters(), lr=self.params['lr'], weight_decay=self.params['weight_decay'])
        Xt, yt = torch.tensor(A[tr]), torch.tensor(y[tr], dtype=torch.long)
        Xv, yv = torch.tensor(A[va]), torch.tensor(y[va], dtype=torch.long)
        gen = torch.Generator().manual_seed(self.seed)
        best, best_state, bad = np.inf, None, 0
        bs = self.batch_size if len(Xt) < 100_000 else 1024     # keep epochs short on large heads
        for _ in range(self.max_epochs):
            self.net.train()
            order = torch.randperm(len(Xt), generator=gen)
            for i in range(0, len(order), bs):
                idx = order[i:i + bs]
                if len(idx) < 2:
                    continue
                opt.zero_grad()
                loss_fn(self.net(Xt[idx]), yt[idx]).backward()
                opt.step()
            self.net.eval()
            with torch.no_grad():
                val = float(sum(loss_fn(self.net(Xv[j:j + 8192]), yv[j:j + 8192]) * len(yv[j:j + 8192])
                                for j in range(0, len(Xv), 8192)) / len(Xv)) if len(Xv) else 0.0
            if val < best - 1e-4:
                best, bad = val, 0
                best_state = {k: v.clone() for k, v in self.net.state_dict().items()}
            else:
                bad += 1
                if bad >= self.patience:
                    break
        if best_state is not None:
            self.net.load_state_dict(best_state)
        self.net.eval()
        return self

    def predict_proba(self, X, S):
        A = torch.tensor(self._prepare(self._input(X, S)))
        with torch.no_grad():
            out = [torch.softmax(self.net(A[i:i + 4096]).double(), dim=1) for i in range(0, len(A), 4096)]
        return torch.cat(out).numpy()

    def size_bytes(self):
        buf = io.BytesIO()
        torch.save(self.net.state_dict(), buf)
        return buf.tell()


class MLPCandidate(_TorchCandidate):
    name = 'mlp'

    @staticmethod
    def default_params():
        return {'h1': 128, 'h2': 64, 'dropout': 0.2, 'lr': 1e-3, 'weight_decay': 1e-4}

    @staticmethod
    def suggest(trial):
        return {'h1': trial.suggest_categorical('h1', [64, 128, 256]),
                'h2': trial.suggest_categorical('h2', [32, 64, 128]),
                'dropout': trial.suggest_float('dropout', 0.05, 0.5),
                'lr': trial.suggest_float('lr', 3e-4, 3e-3, log=True),
                'weight_decay': trial.suggest_float('weight_decay', 1e-5, 1e-2, log=True)}

    def _prepare_fit(self, X):
        self.imputer = SimpleImputer(strategy='median', keep_empty_features=True).fit(X)
        Z = self.imputer.transform(X)
        self.mu, self.sd = Z.mean(axis=0), Z.std(axis=0) + 1e-6
        return self._prepare(X)

    def _prepare(self, X):
        return np.clip((self.imputer.transform(X) - self.mu) / self.sd, -10, 10).astype(np.float32)

    def _build(self, A):
        p = self.params
        return _MLPNet(A.shape[1], p['h1'], p['h2'], p['dropout'], self.n_classes)


class CNN1DCandidate(_TorchCandidate):
    name = 'cnn1d'
    input_kind = 'sequence'

    @staticmethod
    def default_params():
        return {'channels': 32, 'dropout': 0.2, 'lr': 1e-3, 'weight_decay': 1e-4}

    @staticmethod
    def suggest(trial):
        return {'channels': trial.suggest_categorical('channels', [16, 32, 64]),
                'dropout': trial.suggest_float('dropout', 0.05, 0.5),
                'lr': trial.suggest_float('lr', 3e-4, 3e-3, log=True),
                'weight_decay': trial.suggest_float('weight_decay', 1e-5, 1e-2, log=True)}

    def _prepare_fit(self, S):
        flat = S.reshape(-1, S.shape[2]).astype(np.float64)
        self.mu = np.nan_to_num(np.nanmean(flat, axis=0))
        self.sd = np.nan_to_num(np.nanstd(flat, axis=0), nan=1.0) + 1e-6
        return self._prepare(S)

    def _prepare(self, S):
        Z = np.clip((S - self.mu) / self.sd, -10, 10)
        return np.nan_to_num(Z, nan=0.0).transpose(0, 2, 1).astype(np.float32)  # (N, C, T)

    def _build(self, A):
        p = self.params
        return _CNNNet(A.shape[1], A.shape[2], p['channels'], p['dropout'], self.n_classes)


# ─── added in P3 v2 ──────────────────────────────────────────────────────────

class ExtraTreesCandidate(Candidate):
    """Extremely randomised trees: more variance reduction than boosting on few subjects."""
    name = 'extratrees'
    max_rows_per_tree = 60_000      # bootstrap cap so forests stay small on 500k-window heads

    @staticmethod
    def default_params():
        return {'n_estimators': 200, 'max_features': 0.5, 'min_samples_leaf': 3}

    @staticmethod
    def suggest(trial):
        return {'n_estimators': trial.suggest_int('n_estimators', 100, 400, step=50),
                'max_features': trial.suggest_float('max_features', 0.2, 1.0),
                'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 30, log=True)}

    def fit(self, X, S, y, groups):
        # joblib's threading backend races on pool shutdown under Python 3.13 / Windows
        # ("concurrent send_bytes() calls are not supported"), so instead of n_jobs we grow
        # N_JOBS single-threaded sub-forests in our own threads (tree building releases the GIL)
        # and merge them into one ordinary ExtraTreesClassifier.
        from concurrent.futures import ThreadPoolExecutor
        from sklearn.ensemble import ExtraTreesClassifier
        big = len(y) > self.max_rows_per_tree
        n_total = self.params['n_estimators']
        sizes = [n_total // N_JOBS + (i < n_total % N_JOBS) for i in range(N_JOBS)]

        def grow(i):
            return ExtraTreesClassifier(
                n_estimators=sizes[i], max_features=self.params['max_features'],
                min_samples_leaf=self.params['min_samples_leaf'], class_weight='balanced',
                bootstrap=big, max_samples=self.max_rows_per_tree / len(y) if big else None,
                n_jobs=1, random_state=self.seed + i).fit(X, y)

        with ThreadPoolExecutor(N_JOBS) as ex:
            parts = list(ex.map(grow, range(N_JOBS)))
        self.model = parts[0]
        for p in parts[1:]:
            self.model.estimators_ += p.estimators_
        self.model.n_estimators = len(self.model.estimators_)
        return self

    def predict_proba(self, X, S):
        if len(X) < 4096:
            return self.model.predict_proba(X)
        chunks = np.array_split(np.arange(len(X)), N_JOBS)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(N_JOBS) as ex:
            parts = list(ex.map(lambda idx: self.model.predict_proba(X[idx]), chunks))
        return np.concatenate(parts)

    def size_bytes(self):
        return len(pickle.dumps(self.model))


class MiniRocketTransform:
    """Multivariate MiniRocket (Dempster et al., KDD 2021) in plain numpy.

    84 fixed length-9 kernels (weights -1, three taps of +2), exponentially spaced dilations,
    random channel subsets per kernel, biases from quantiles of training convolutions and
    proportion-of-positive-values (PPV) pooling. Deterministic for a given seed.
    """

    KERNELS = np.array([c for c in __import__('itertools').combinations(range(9), 3)])  # (84, 3)

    def __init__(self, n_features: int = 1000, seed: int = 42):
        self.n_features, self.seed = n_features, seed

    def _conv(self, A: np.ndarray, d: int, pad: bool) -> np.ndarray:
        """All 84 kernel outputs for dilation d: (n, 84, C, L)."""
        n, C, T = A.shape
        p = 4 * d if pad else 0
        Z = np.pad(A, ((0, 0), (0, 0), (p, p))) if p else A
        L = Z.shape[2] - 8 * d
        taps = np.stack([Z[:, :, k * d:k * d + L] for k in range(9)], axis=1)   # (n, 9, C, L)
        base = -taps.sum(axis=1, keepdims=True)
        return base + 3.0 * taps[:, self.KERNELS].sum(axis=2)

    def fit(self, A: np.ndarray) -> 'MiniRocketTransform':
        rng = np.random.default_rng(self.seed)
        n, C, T = A.shape
        max_exp = np.log2(max((T - 1) / 8, 1.0))
        self.dilations = np.unique(np.floor(2 ** np.linspace(0, max_exp, 4)).astype(int))
        per = max(1, self.n_features // (84 * len(self.dilations)))
        self.plan = []
        sample = A[rng.choice(n, min(n, 256), replace=False)]
        phi = (np.arange(1, per * 84 + 1) * 0.6180339887) % 1        # low-discrepancy quantiles
        for di, d in enumerate(self.dilations):
            pad = di % 2 == 0
            out = self._conv(sample, d, pad)                         # (s, 84, C, L)
            chans = [rng.choice(C, rng.integers(1, min(C, 3) + 1), replace=False) for _ in range(84)]
            q = phi.reshape(84, per)
            biases = np.empty((84, per))
            for k in range(84):
                conv = out[:, k][:, chans[k]].sum(axis=1)            # (s, L)
                biases[k] = np.quantile(conv[rng.integers(len(conv))], q[k])
            self.plan.append((d, pad, chans, biases))
        return self

    def transform(self, A: np.ndarray, batch: int = 1024) -> np.ndarray:
        feats = []
        for i in range(0, len(A), batch):
            block = []
            for d, pad, chans, biases in self.plan:
                out = self._conv(A[i:i + batch], d, pad)
                for k in range(84):
                    conv = out[:, k][:, chans[k]].sum(axis=1)        # (b, L)
                    block.append((conv[:, None, :] > biases[k][None, :, None]).mean(axis=2))
            feats.append(np.concatenate(block, axis=1).astype(np.float32))
        return np.concatenate(feats)


class MiniRocketCandidate(Candidate):
    """MiniRocket features of the frame sequence + the tabular features -> logistic regression."""
    name = 'minirocket'
    input_kind = 'sequence'
    min_T = 8

    @staticmethod
    def default_params():
        return {'n_features': 1000, 'C': 0.1}

    @staticmethod
    def suggest(trial):
        return {'n_features': trial.suggest_categorical('n_features', [500, 1000, 2000]),
                'C': trial.suggest_float('C', 1e-3, 3.0, log=True)}

    def _seq(self, S, fit=False):
        if fit:
            flat = S.reshape(-1, S.shape[2]).astype(np.float64)
            self.mu = np.nan_to_num(np.nanmean(flat, axis=0))
            self.sd = np.nan_to_num(np.nanstd(flat, axis=0), nan=1.0) + 1e-6
        Z = np.clip((S - self.mu) / self.sd, -10, 10)
        return np.nan_to_num(Z, nan=0.0).transpose(0, 2, 1).astype(np.float32)

    def _features(self, X, S):
        return np.hstack([self.rocket.transform(self._seq(S)), self.tab.transform(X)])

    def fit(self, X, S, y, groups):
        A = self._seq(S, fit=True)
        self.rocket = MiniRocketTransform(self.params['n_features'], self.seed).fit(A)
        self.tab = make_pipeline(SimpleImputer(strategy='median', keep_empty_features=True), StandardScaler()).fit(X)
        F = np.hstack([self.rocket.transform(A), self.tab.transform(X)])
        self.scaler = StandardScaler().fit(F)
        self.clf = LogisticRegression(C=self.params['C'], class_weight='balanced', max_iter=2000)
        self.clf.fit(self.scaler.transform(F), y)
        return self

    def predict_proba(self, X, S):
        return self.clf.predict_proba(self.scaler.transform(self._features(X, S)))

    def size_bytes(self):
        return len(pickle.dumps((self.rocket, self.tab, self.scaler, self.clf, self.mu, self.sd)))


CANDIDATES: Dict[str, type] = {c.name: c for c in
                               [LogRegCandidate, XGBoostCandidate, LightGBMCandidate, ExtraTreesCandidate,
                                MLPCandidate, CNN1DCandidate, MiniRocketCandidate]}
BASELINE = 'logreg'
CONTENDERS = ['xgboost', 'lightgbm', 'extratrees', 'mlp', 'cnn1d', 'minirocket']


def applicable(name: str, T: int) -> bool:
    """MiniRocket's length-9 kernels need windows of at least 8 frames (fall uses 4)."""
    return T >= getattr(CANDIDATES[name], 'min_T', 1)
