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
    """Fit a StandardScaler on the training split.

    Parameters
    ----------
    X_train : np.ndarray, shape (n, T, F)

    Returns
    -------
    Fitted StandardScaler.
    """
    n, T, F = X_train.shape
    flat = X_train.reshape(n * T, F)
    scaler = StandardScaler()
    scaler.fit(flat)
    log.info(
        "Scaler fitted on %d rows (reshaped from %d sequences x %d timesteps, %d features)",
        flat.shape[0], n, T, F,
    )
    return scaler


def apply_scaler(X: np.ndarray, scaler: StandardScaler) -> np.ndarray:
    """Transform a 3-D array using a fitted scaler."""
    n, T, F = X.shape
    flat = X.reshape(n * T, F)
    transformed = scaler.transform(flat)
    return transformed.reshape(n, T, F)


def save_scaler(scaler: StandardScaler, path: Path = SCALER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, path)
    log.info("Scaler saved -> %s", path)


def load_scaler(path: Path = SCALER_PATH) -> StandardScaler:
    scaler = joblib.load(path)
    log.info("Scaler loaded <- %s", path)
    return scaler
