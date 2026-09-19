"""
Test-set evaluation + majority-class baseline comparison.

Now includes comprehensive metrics for imbalanced classes:
  - Macro-averaged F1 (headline metric)
  - Balanced accuracy
  - Full classification report (precision, recall, F1 per class)
  - Confusion matrix with proper formatting
"""

import json
import logging
from collections import Counter
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import (
    balanced_accuracy_score,
    classification_report,
    confusion_matrix as sk_confusion_matrix,
    f1_score,
)

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

    # ── Comprehensive metrics for imbalanced classes ────────────────────
    labels_sorted = sorted(label_names.keys())
    target_names = [label_names[i] for i in labels_sorted]

    # Macro-averaged F1 (unweighted mean — treats all classes equally)
    macro_f1 = float(f1_score(y_test, y_pred, labels=labels_sorted, average="macro", zero_division=0))

    # Weighted F1 (weighted by class support)
    weighted_f1 = float(f1_score(y_test, y_pred, labels=labels_sorted, average="weighted", zero_division=0))

    # Balanced accuracy (recall averaged per class, then macro-averaged)
    bal_acc = float(balanced_accuracy_score(y_test, y_pred))

    # Full sklearn classification report string (for display)
    sklearn_report_str = classification_report(
        y_test, y_pred,
        labels=labels_sorted,
        target_names=target_names,
        digits=4,
        zero_division=0,
    )

    # Sklearn confusion matrix (canonical)
    sk_cm = sk_confusion_matrix(y_test, y_pred, labels=labels_sorted)
    sk_cm_list = sk_cm.tolist()

    log.info("Macro F1: %.4f | Weighted F1: %.4f | Balanced Accuracy: %.4f", macro_f1, weighted_f1, bal_acc)

    # ── Majority-class baseline (Task 15) ───────────────────────────────
    train_counts = Counter(y_train.tolist())
    majority_class = max(train_counts, key=train_counts.get)
    baseline_preds = np.full_like(y_test, majority_class)
    baseline_acc = float((y_test == majority_class).sum() / len(y_test))
    baseline_macro_f1 = float(f1_score(y_test, baseline_preds, labels=labels_sorted, average="macro", zero_division=0))
    baseline_bal_acc = float(balanced_accuracy_score(y_test, baseline_preds))

    log.info(
        "Baseline (always %s): accuracy=%.4f, macro_f1=%.4f, bal_acc=%.4f",
        label_names[majority_class], baseline_acc, baseline_macro_f1, baseline_bal_acc,
    )
    log.info(
        "Model improvement over baseline: acc=%+.4f, macro_f1=%+.4f, bal_acc=%+.4f",
        accuracy - baseline_acc, macro_f1 - baseline_macro_f1, bal_acc - baseline_bal_acc,
    )

    # ── Build report ────────────────────────────────────────────────────
    report = {
        "label_mapping": label_mapping,
        "test_samples": len(y_test),
        "test_accuracy": round(accuracy, 4),
        "balanced_accuracy": round(bal_acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_class": per_class,
        "confusion_matrix": cm_list,
        "sklearn_confusion_matrix": sk_cm_list,
        "baseline": {
            "strategy": f"always_predict_{label_names[majority_class]}",
            "majority_class_id": int(majority_class),
            "majority_class_name": label_names[majority_class],
            "accuracy": round(baseline_acc, 4),
            "macro_f1": round(baseline_macro_f1, 4),
            "balanced_accuracy": round(baseline_bal_acc, 4),
        },
        "improvement_over_baseline": {
            "accuracy": round(accuracy - baseline_acc, 4),
            "macro_f1": round(macro_f1 - baseline_macro_f1, 4),
            "balanced_accuracy": round(bal_acc - baseline_bal_acc, 4),
        },
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info("Evaluation report saved -> %s", report_path)

    # ── Console summary ─────────────────────────────────────────────────
    print("\n" + "=" * 64)
    print("  EVALUATION SUMMARY — GRU")
    print("=" * 64)
    print(f"  Test samples:        {len(y_test)}")
    print(f"  Macro F1 (headline): {macro_f1:.4f}")
    print(f"  Balanced Accuracy:   {bal_acc:.4f}")
    print(f"  Plain Accuracy:      {accuracy:.4f}")
    print(f"  Baseline accuracy:   {baseline_acc:.4f}  (always {label_names[majority_class]})")
    print(f"  Improvement:         {accuracy - baseline_acc:+.4f}")
    print("-" * 64)
    print("  Classification Report:")
    for line in sklearn_report_str.splitlines():
        print(f"    {line}")
    print("-" * 64)
    print("  Confusion Matrix (rows=true, cols=pred):")
    header = f"    {'':>12}" + "".join(f"{target_names[i]:>12}" for i in range(len(target_names)))
    print(header)
    for i, row in enumerate(sk_cm_list):
        row_str = "".join(f"{v:>12}" for v in row)
        print(f"    {target_names[i]:>12}{row_str}")
    print("=" * 64 + "\n")

    return report
