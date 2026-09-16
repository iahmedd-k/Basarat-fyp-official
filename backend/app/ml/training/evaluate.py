"""
Test-set evaluation + majority-class baseline comparison.
"""

import json
import logging
from collections import Counter
from pathlib import Path

import numpy as np
import tensorflow as tf

log = logging.getLogger("training.evaluate")

REPORT_PATH = Path("data/reports/evaluation.json")


def _load_label_mapping() -> dict:
    """Load label mapping from label_mapping.json (name -> int)."""
    path = Path("data/features/label_mapping.json")
    if not path.exists():
        raise FileNotFoundError(
            f"Required label_mapping.json not found at {path}. "
            "Cannot evaluate without a consistent label mapping."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(
    model: tf.keras.Model,
    X_test: np.ndarray,
    y_test: np.ndarray,
    y_train: np.ndarray,
    report_path: Path = REPORT_PATH,
    label_mapping: dict | None = None,
) -> dict:
    """Evaluate on the held-out test set and compare to a naive baseline.

    Parameters
    ----------
    model : trained Keras model
    X_test, y_test : test split
    y_train : training labels (to determine majority class)
    report_path : where to save the JSON report
    label_mapping : {"bullish": 0, "bearish": 1, "sideways": 2} — if None,
        loaded from data/features/label_mapping.json

    Returns
    -------
    dict with accuracy, per-class metrics, confusion matrix, baseline info.
    """
    if label_mapping is None:
        label_mapping = _load_label_mapping()

    # Reverse mapping: int -> name, SORTED by class ID for consistent order
    label_names = {v: k for k, v in label_mapping.items()}

    # ── Model predictions ───────────────────────────────────────────────
    y_proba = model.predict(X_test, verbose=0)
    y_pred = np.argmax(y_proba, axis=1)

    # ── Overall accuracy ────────────────────────────────────────────────
    correct = (y_pred == y_test).sum()
    accuracy = float(correct / len(y_test))
    log.info("Test accuracy: %.4f (%d / %d)", accuracy, correct, len(y_test))

    # ── Per-class metrics (ordered by class ID, matching confusion matrix rows) ─
    n_classes = len(label_mapping)
    per_class = {}
    for cls_id in sorted(label_names.keys()):
        cls_name = label_names[cls_id]
        tp = int(((y_pred == cls_id) & (y_test == cls_id)).sum())
        fp = int(((y_pred == cls_id) & (y_test != cls_id)).sum())
        fn = int(((y_pred != cls_id) & (y_test == cls_id)).sum())

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        support = int((y_test == cls_id).sum())

        per_class[cls_name] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }
        log.info(
            "  %10s  P=%.3f  R=%.3f  F1=%.3f  support=%d",
            cls_name, precision, recall, f1, support,
        )

    # ── Confusion matrix (rows/cols ordered by class ID) ────────────────
    cm = np.zeros((n_classes, n_classes), dtype=int)
    for true, pred in zip(y_test, y_pred):
        cm[true][pred] += 1

    cm_list = cm.tolist()
    log.info("Confusion matrix (rows=true, cols=pred, order=%s):",
             "/".join(label_names[i] for i in sorted(label_names.keys())))
    for i in sorted(label_names.keys()):
        log.info("  %10s %s", label_names[i], cm_list[i])

    # ── Verification: per_class support must match CM row sums ───────────
    for cls_id in sorted(label_names.keys()):
        cls_name = label_names[cls_id]
        row_sum = sum(cm_list[cls_id])
        if per_class[cls_name]["support"] != row_sum:
            raise ValueError(
                f"per_class['{cls_name}'].support={per_class[cls_name]['support']} "
                f"!= CM row {cls_id} sum={row_sum}. "
                f"label_mapping may not match the data used for y_test."
            )

    # ── Majority-class baseline ─────────────────────────────────────────
    train_counts = Counter(y_train.tolist())
    majority_class = max(train_counts, key=train_counts.get)
    baseline_acc = float((y_test == majority_class).sum() / len(y_test))
    log.info(
        "Baseline (always %s): accuracy=%.4f",
        label_names[majority_class], baseline_acc,
    )
    log.info(
        "Model improvement over baseline: %.4f (%.1f%%)",
        accuracy - baseline_acc,
        (accuracy - baseline_acc) * 100,
    )

    # ── Build report ────────────────────────────────────────────────────
    report = {
        "label_mapping": label_mapping,
        "test_samples": len(y_test),
        "test_accuracy": round(accuracy, 4),
        "per_class": per_class,
        "confusion_matrix": cm_list,
        "baseline": {
            "strategy": f"always_predict_{label_names[majority_class]}",
            "majority_class_id": int(majority_class),
            "majority_class_name": label_names[majority_class],
            "accuracy": round(baseline_acc, 4),
        },
        "improvement_over_baseline": round(accuracy - baseline_acc, 4),
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info("Evaluation report saved -> %s", report_path)

    # ── Console summary ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  EVALUATION SUMMARY")
    print("=" * 60)
    print(f"  Test samples:        {len(y_test)}")
    print(f"  Test accuracy:       {accuracy:.4f}")
    print(f"  Baseline accuracy:   {baseline_acc:.4f}  (always {label_names[majority_class]})")
    print(f"  Improvement:         {accuracy - baseline_acc:+.4f}")
    if accuracy > baseline_acc:
        print("  Verdict:             Model BEATS baseline")
    else:
        print("  Verdict:             Model DOES NOT beat baseline")
    print("=" * 60 + "\n")

    return report
