"""
Centralized Reproducibility Helper — deterministic seeding.

Sets identical random seeds across Python, NumPy, TensorFlow, and XGBoost
to ensure training and evaluation runs are fully reproducible.
"""

import logging
import os
import random
from typing import Any, Dict

import numpy as np

log = logging.getLogger("training.reproducibility")

DEFAULT_SEED = 42


def set_seed(seed: int = DEFAULT_SEED) -> Dict[str, Any]:
    """Set random seeds for Python, NumPy, TensorFlow, and OS environment.

    Parameters
    ----------
    seed : int
        Deterministic seed (default: 42).

    Returns
    -------
    dict
        Metadata dictionary recording the seed and initialized libraries.
    """
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)

    info: Dict[str, Any] = {
        "seed": seed,
        "python_seeded": True,
        "numpy_seeded": True,
        "tensorflow_seeded": False,
        "xgboost_seed_param": seed,
    }

    try:
        import tensorflow as tf
        tf.random.set_seed(seed)
        info["tensorflow_seeded"] = True
    except ImportError:
        pass

    log.info("Reproducibility seed set to %d across libraries", seed)
    return info
