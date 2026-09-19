"""
Feature scaling — fit on train, apply to val / test.

Approach
--------
The 3-D array ``X`` has shape ``(n_samples, window_size, n_features)``.
We reshape to 2-D ``(n_samples * window_size, n_features)``, fit a
``StandardScaler`` on the **training split only**, then apply it to all
splits.  This treats every timestep independently — which is correct for
cross-sectional features (each timestep's value is an independent
observation of that feature's distribution).

The fitted scaler is saved to ``scaler.pkl`` via ``joblib`` so the exact
same transformation can be applied at inference time.
"""

import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.preprocessing import StandardScaler

log = logging.getLogger("training.scaling")

SCALER_PATH = Path("data/scalers/scaler.pkl")


def fit_scaler(X_train: np.ndarray) -> StandardScaler:
    """Fit a StandardScaler on the training split using batching for memory efficiency."""
    n, T, F = X_train.shape
    flat = X_train.reshape(n * T, F)
    scaler = StandardScaler()
    batch_size = 50000
    for i in range(0, len(flat), batch_size):
        scaler.partial_fit(flat[i : i + batch_size].astype(np.float32, copy=False))
    log.info(
        "Scaler fitted on %d rows (reshaped from %d sequences x %d timesteps, %d features)",
        flat.shape[0], n, T, F,
    )
    return scaler


def apply_scaler(X: np.ndarray, scaler: StandardScaler) -> np.ndarray:
    """Transform a 3-D array using a fitted scaler in memory-efficient batches."""
    n, T, F = X.shape
    flat = X.reshape(n * T, F)
    out = np.empty((flat.shape[0], F), dtype=np.float32)
    batch_size = 50000
    for i in range(0, len(flat), batch_size):
        out[i : i + batch_size] = scaler.transform(flat[i : i + batch_size]).astype(np.float32)
    return out.reshape(n, T, F)


def save_scaler(scaler: StandardScaler, path: Path = SCALER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, path)
    log.info("Scaler saved -> %s", path)


def load_scaler(path: Path = SCALER_PATH) -> StandardScaler:
    scaler = joblib.load(path)
    log.info("Scaler loaded <- %s", path)
    return scaler
