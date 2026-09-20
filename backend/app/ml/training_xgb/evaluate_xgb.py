"""
XGBoost Evaluation — test-set evaluation using the EXACT SAME report
format as all previous GRU evaluation reports.

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
import pandas as pd
from sklearn.metrics import (
    balanced_accuracy_score,
    classification_report,
    confusion_matrix as sk_confusion_matrix,
    f1_score,
)

log = logging.getLogger("training_xgb.evaluate")

REPORTS_DIR = Path("data/reports")


def evaluate_xgb(
    model,
    X_test: np.ndarray,
    y_test: np.ndarray,
    y_train: np.ndarray,
    label_mapping: dict | None = None,
    report_path: Path | None = None,
    variant: str = "unweighted",
) -> dict:
    """Evaluate an XGBoost model on the test set.

    Uses the EXACT SAME report format as the GRU evaluation reports
    (evaluation.json, evaluation_v4.json, etc.).

    Parameters
    ----------
    model : fitted XGBClassifier
    X_test, y_test : test split features and labels
    y_train : training labels (to determine majority class for baseline)
    label_mapping : {"bullish": 0, "bearish": 1, "sideways": 2}
    report_path : where to save the JSON report
    variant : "unweighted" or "weighted" (for report labeling)

    Returns
    -------
    dict with accuracy, per_class metrics, confusion matrix, baseline info.
    """
    if label_mapping is None:
        _path = Path("data/features/label_mapping.json")
        if not _path.exists():
            raise FileNotFoundError(
                f"Required label_mapping.json not found at {_path}. "
                "Cannot evaluate without a consistent label mapping."
            )
        label_mapping = json.loads(_path.read_text(encoding="utf-8"))

    # Reverse mapping: int -> name
    label_names = {v: k for k, v in label_mapping.items()}

    # ── Model predictions ───────────────────────────────────────────────
    y_proba = model.predict_proba(X_test)
    y_pred = np.argmax(y_proba, axis=1)

    # ── Overall accuracy ────────────────────────────────────────────────
    correct = int((y_pred == y_test).sum())
    accuracy = correct / len(y_test)
    log.info("Test accuracy: %.4f (%d / %d)", accuracy, correct, len(y_test))

    # ── Per-class metrics ───────────────────────────────────────────────
    n_classes = len(label_mapping)
    per_class = {}

    # Use label IDs sorted for consistent ordering (same as GRU evaluate.py)
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

    # ── Confusion matrix ────────────────────────────────────────────────
    # Use sklearn for correctness, then verify shape
    cm = sk_confusion_matrix(y_test, y_pred, labels=sorted(label_names.keys()))
    cm_list = cm.tolist()

    log.info("Confusion matrix (rows=true, cols=pred, order=%s):",
             "/".join(label_names[i] for i in sorted(label_names.keys())))
    for i, cls_id in enumerate(sorted(label_names.keys())):
        log.info("  %10s %s", label_names[cls_id], cm_list[i])

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

    # ── Build report (same format as GRU evaluation) ────────────────────
    report = {
        "label_mapping": label_mapping,
        "test_samples": len(y_test),
        "test_accuracy": round(accuracy, 4),
        "balanced_accuracy": round(bal_acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_class": per_class,
        "confusion_matrix": cm_list,
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

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        log.info("Evaluation report saved -> %s", report_path)

    # ── Console summary ─────────────────────────────────────────────────
    print("\n" + "=" * 64)
    print(f"  EVALUATION SUMMARY — XGBoost ({variant})")
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
    for i, row in enumerate(cm_list):
        row_str = "".join(f"{v:>12}" for v in row)
        print(f"    {target_names[i]:>12}{row_str}")
    print("=" * 64 + "\n")

    return report


def load_gru_v1_report(report_path: Path | None = None) -> dict | None:
    """Load the GRU v1 evaluation report for comparison.

    Returns None if the report doesn't exist.
    """
    report_path = report_path or Path("data/reports/evaluation.json")
    if not report_path.exists():
        log.warning("GRU v1 report not found: %s", report_path)
        return None
    return json.loads(report_path.read_text(encoding="utf-8"))


def print_comparison_table(
    gru_report: dict | None,
    xgb_unweighted_report: dict,
    xgb_weighted_report: dict,
) -> None:
    """Print a direct side-by-side comparison table.

    Headline metric is Macro F1 (not plain accuracy).

    metric                     | gru_v1 | xgb_unweighted | xgb_weighted
    """
    print("\n" + "=" * 90)
    print("  DIRECT COMPARISON: GRU v1 vs XGBoost (unweighted) vs XGBoost (weighted)")
    print("=" * 90)

    def _val(report: dict | None, *keys) -> str:
        if report is None:
            return "N/A"
        d = report
        for k in keys:
            if isinstance(d, dict):
                d = d.get(k)
            else:
                return "N/A"
        if d is None:
            return "N/A"
        if isinstance(d, float):
            return f"{d:.4f}"
        return str(d)

    header = f"  {'metric':<30} {'gru_v1':>12} {'xgb_unweighted':>15} {'xgb_weighted':>15}"
    sep = f"  {'-'*30} {'-'*12} {'-'*15} {'-'*15}"

    print(header)
    print(sep)

    rows = [
        ("macro f1 (headline)", "macro_f1"),
        ("balanced accuracy", "balanced_accuracy"),
        ("test accuracy", "test_accuracy"),
        ("baseline accuracy", "baseline", "accuracy"),
        ("improvement over baseline", "improvement_over_baseline"),
    ]

    for label, *keys in rows:
        g = _val(gru_report, *keys)
        u = _val(xgb_unweighted_report, *keys)
        w = _val(xgb_weighted_report, *keys)
        print(f"  {label:<30} {g:>12} {u:>15} {w:>15}")

    print(sep)

    # Per-class metrics
    for class_name in ("bullish", "bearish", "sideways"):
        for metric in ("recall", "precision", "f1"):
            g = _val(gru_report, "per_class", class_name, metric)
            u = _val(xgb_unweighted_report, "per_class", class_name, metric)
            w = _val(xgb_weighted_report, "per_class", class_name, metric)
            label_str = f"{class_name} {metric}"
            print(f"  {label_str:<30} {g:>12} {u:>15} {w:>15}")

    print("=" * 90)


def print_top_features(
    importance_path: Path,
    top_n: int = 10,
    variant: str = "unweighted",
) -> None:
    """Print the top N most important features from the importance file."""
    if not importance_path.exists():
        log.warning("Feature importance file not found: %s", importance_path)
        return

    feat_imp = json.loads(importance_path.read_text(encoding="utf-8"))
    items = list(feat_imp.items())[:top_n]

    print(f"\n  Top {top_n} most important features ({variant}):")
    print(f"  {'Rank':<6} {'Feature':<30} {'Importance':>12}")
    print(f"  {'-'*6} {'-'*30} {'-'*12}")
    for i, (fname, score) in enumerate(items):
        print(f"  {i+1:<6} {fname:<30} {score:>12.6f}")
    print()
