"""
Comprehensive model evaluation with proper metrics for imbalanced classes.

Replaces plain accuracy with:
  - Macro-averaged F1 (headline metric)
  - Balanced accuracy
  - Full classification report (precision, recall, F1 per class)
  - Confusion matrix (printed + optional plot)

Provides side-by-side comparison for: GRU alone, XGBoost alone, Ensemble.
"""

import json
import logging
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)

log = logging.getLogger("ml.comprehensive_evaluation")

# ── Label ordering ───────────────────────────────────────────────────────────
DEFAULT_LABELS = ["bearish", "bullish", "sideways"]


def _load_label_mapping() -> dict:
    """Load label mapping from label_mapping.json (name -> int)."""
    path = Path("data/features/label_mapping.json")
    if not path.exists():
        raise FileNotFoundError(
            f"Required label_mapping.json not found at {path}. "
            "Cannot evaluate without a consistent label mapping."
        )
    return json.loads(path.read_text(encoding="utf-8"))


# ── Core metrics ─────────────────────────────────────────────────────────────


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    label_names: dict | None = None,
    model_name: str = "model",
) -> dict:
    """Compute full metrics for a single model.

    Parameters
    ----------
    y_true : ground-truth integer labels
    y_pred : predicted integer labels
    label_names : {int: str} mapping, e.g. {0: "bearish", 1: "bullish", 2: "sideways"}
    model_name : for display in logs

    Returns
    -------
    dict with keys: macro_f1, balanced_accuracy, accuracy, per_class, confusion_matrix,
                    classification_report_str
    """
    if label_names is None:
        lm = _load_label_mapping()
        label_names = {v: k for k, v in lm.items()}

    labels_sorted = sorted(label_names.keys())
    target_names = [label_names[i] for i in labels_sorted]

    # Overall accuracy
    accuracy = float((y_pred == y_true).sum() / len(y_true))

    # Macro-averaged F1 (unweighted mean of per-class F1 — treats all classes equally)
    macro_f1 = float(f1_score(y_true, y_pred, labels=labels_sorted, average="macro", zero_division=0))

    # Weighted F1
    weighted_f1 = float(f1_score(y_true, y_pred, labels=labels_sorted, average="weighted", zero_division=0))

    # Balanced accuracy (recall averaged per class, then macro-averaged — same as macro recall)
    bal_acc = float(balanced_accuracy_score(y_true, y_pred))

    # Full classification report
    report_str = classification_report(
        y_true, y_pred,
        labels=labels_sorted,
        target_names=target_names,
        digits=4,
        zero_division=0,
    )

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=labels_sorted)
    cm_list = cm.tolist()

    # Per-class dict for JSON serialization
    report_dict = classification_report(
        y_true, y_pred,
        labels=labels_sorted,
        target_names=target_names,
        output_dict=True,
        zero_division=0,
    )
    per_class = {}
    for cls_name in target_names:
        cls_metrics = report_dict[cls_name]
        per_class[cls_name] = {
            "precision": round(cls_metrics["precision"], 4),
            "recall": round(cls_metrics["recall"], 4),
            "f1": round(cls_metrics["f1-score"], 4),
            "support": int(cls_metrics["support"]),
        }

    log.info(
        "[%s] accuracy=%.4f  balanced_acc=%.4f  macro_f1=%.4f  weighted_f1=%.4f",
        model_name, accuracy, bal_acc, macro_f1, weighted_f1,
    )

    return {
        "model_name": model_name,
        "accuracy": round(accuracy, 4),
        "balanced_accuracy": round(bal_acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_class": per_class,
        "confusion_matrix": cm_list,
        "classification_report_str": report_str,
        "label_names": {str(k): v for k, v in label_names.items()},
    }


def print_single_report(metrics: dict, indent: int = 2) -> None:
    """Print a clean single-model evaluation report."""
    pad = " " * indent
    name = metrics["model_name"]

    print(f"\n{pad}{'=' * 64}")
    print(f"{pad}  EVALUATION REPORT — {name.upper()}")
    print(f"{pad}{'=' * 64}")

    # Headline metrics
    print(f"{pad}  Accuracy:            {metrics['accuracy']:.4f}")
    print(f"{pad}  Balanced Accuracy:   {metrics['balanced_accuracy']:.4f}")
    print(f"{pad}  Macro F1:            {metrics['macro_f1']:.4f}")
    print(f"{pad}{'-' * 64}")

    # Classification report
    print(f"{pad}  Classification Report:")
    for line in metrics["classification_report_str"].splitlines():
        print(f"{pad}    {line}")
    print(f"{pad}{'-' * 64}")

    # Confusion matrix
    cm = metrics["confusion_matrix"]
    labels = list(metrics.get("label_names", {}).values())
    if not labels:
        labels = [f"class_{i}" for i in range(len(cm))]

    print(f"{pad}  Confusion Matrix (rows=true, cols=pred):")
    header = f"{pad}    {'':>12}" + "".join(f"{lbl:>12}" for lbl in labels)
    print(header)
    for i, row in enumerate(cm):
        row_str = "".join(f"{v:>12}" for v in row)
        print(f"{pad}    {labels[i]:>12}{row_str}")
    print(f"{pad}{'=' * 64}")


def print_confusion_matrix_plot(metrics: dict, save_path: str | Path | None = None) -> None:
    """Optionally plot confusion matrix as a heatmap (requires matplotlib)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        log.warning("matplotlib/seaborn not installed — skipping confusion matrix plot.")
        return

    cm = np.array(metrics["confusion_matrix"])
    labels = list(metrics.get("label_names", {}).values())
    if not labels:
        labels = [f"class_{i}" for i in range(len(cm))]

    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=labels, yticklabels=labels, ax=ax)
    ax.set_xlabel("Predicted", fontsize=12)
    ax.set_ylabel("True", fontsize=12)
    ax.set_title(f"Confusion Matrix — {metrics['model_name']}", fontsize=14)
    plt.tight_layout()

    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=150)
        log.info("Confusion matrix plot saved -> %s", save_path)
    plt.close(fig)


# ── Ensemble evaluation ──────────────────────────────────────────────────────


def evaluate_ensemble(
    gru_proba: np.ndarray,
    xgb_proba: np.ndarray,
    y_true: np.ndarray,
    label_names: dict | None = None,
    gru_weight: float = 0.5,
    xgb_weight: float = 0.5,
    model_name: str = "ensemble (GRU+XGB)",
) -> dict:
    """Evaluate a soft-voting ensemble of GRU and XGBoost probabilities.

    Parameters
    ----------
    gru_proba : (n_samples, n_classes) probability array from GRU
    xgb_proba : (n_samples, n_classes) probability array from XGBoost
    y_true : ground-truth integer labels
    gru_weight, xgb_weight : voting weights (default 50/50)

    Returns
    -------
    dict with the same structure as compute_metrics()
    """
    if label_names is None:
        lm = _load_label_mapping()
        label_names = {v: k for k, v in lm.items()}

    # Weighted average of probabilities
    combined_proba = gru_weight * gru_proba + xgb_weight * xgb_proba
    y_pred = np.argmax(combined_proba, axis=1)

    metrics = compute_metrics(y_true, y_pred, label_names, model_name=model_name)
    metrics["gru_weight"] = gru_weight
    metrics["xgb_weight"] = xgb_weight
    return metrics


# ── Side-by-side comparison table ────────────────────────────────────────────


def print_comparison_table(
    gru_metrics: dict,
    xgb_metrics: dict,
    ensemble_metrics: dict | None = None,
) -> None:
    """Print a clean side-by-side comparison of GRU vs XGB vs Ensemble.

    Headline metric is Macro F1 (not plain accuracy).
    """
    models = [gru_metrics, xgb_metrics]
    col_headers = ["GRU", "XGB"]
    if ensemble_metrics is not None:
        models.append(ensemble_metrics)
        col_headers.append("Ensemble")

    col_w = 14  # width per model column
    label_w = 28

    def _fmt(d: dict, *keys) -> str:
        val = d
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return "N/A"
        if val is None:
            return "N/A"
        if isinstance(val, float):
            return f"{val:.4f}"
        return str(val)

    sep = f"  {'─' * label_w}" + "".join(f" {'─' * col_w}" for _ in models)
    header = f"  {'Metric':<{label_w}}" + "".join(
        f" {h:>{col_w}}" for h in col_headers
    )

    print(f"\n{'=' * (label_w + col_w * len(models) + 4)}")
    print("  SIDE-BY-SIDE MODEL COMPARISON")
    print(f"{'=' * (label_w + col_w * len(models) + 4)}")
    print(header)
    print(sep)

    # Headline metrics
    headline_rows = [
        ("Macro F1 (headline)", "macro_f1"),
        ("Balanced Accuracy", "balanced_accuracy"),
        ("Plain Accuracy", "accuracy"),
    ]
    for label, key in headline_rows:
        vals = " ".join(f"{_fmt(m, key):>{col_w}}" for m in models)
        print(f"  {label:<{label_w}} {vals}")
    print(sep)

    # Per-class metrics
    class_names = list(gru_metrics.get("per_class", {}).keys())
    for cls in class_names:
        for metric in ("precision", "recall", "f1"):
            vals = " ".join(
                f"{_fmt(m, 'per_class', cls, metric):>{col_w}}" for m in models
            )
            print(f"  {cls + ' ' + metric:<{label_w}} {vals}")
        print(sep)

    # Support (should be identical across models)
    for cls in class_names:
        vals = " ".join(
            f"{_fmt(m, 'per_class', cls, 'support'):>{col_w}}" for m in models
        )
        print(f"  {cls + ' support':<{label_w}} {vals}")

    print(f"{'=' * (label_w + col_w * len(models) + 4)}\n")


# ── Full evaluation pipeline (convenience) ───────────────────────────────────


def run_full_evaluation(
    gru_y_pred: np.ndarray,
    xgb_y_pred: np.ndarray,
    y_true: np.ndarray,
    y_train: np.ndarray | None = None,
    gru_proba: np.ndarray | None = None,
    xgb_proba: np.ndarray | None = None,
    label_mapping: dict | None = None,
    report_dir: str | Path = "data/reports",
    plot_confusion: bool = False,
) -> dict:
    """Run comprehensive evaluation for GRU, XGB, and Ensemble.

    Parameters
    ----------
    gru_y_pred : GRU predicted labels (n_samples,)
    xgb_y_pred : XGBoost predicted labels (n_samples,)
    y_true : ground-truth labels (n_samples,)
    y_train : training labels (optional, for baseline info)
    gru_proba : GRU probability outputs (n_samples, n_classes) — needed for ensemble
    xgb_proba : XGBoost probability outputs (n_samples, n_classes) — needed for ensemble
    label_mapping : {"bullish": 0, "bearish": 1, "sideways": 2}
    report_dir : where to save JSON reports and plots
    plot_confusion : whether to save confusion matrix plots

    Returns
    -------
    dict with keys: gru, xgb, ensemble, each containing full metrics.
    """
    if label_mapping is None:
        label_mapping = _load_label_mapping()

    label_names = {v: k for k, v in label_mapping.items()}
    labels_sorted = sorted(label_names.keys())
    target_names = [label_names[i] for i in labels_sorted]

    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    # ── GRU metrics ─────────────────────────────────────────────────────
    gru_m = compute_metrics(y_true, gru_y_pred, label_names, model_name="GRU")
    print_single_report(gru_m)
    if plot_confusion:
        print_confusion_matrix_plot(gru_m, report_dir / "cm_gru.png")

    # ── XGB metrics ─────────────────────────────────────────────────────
    xgb_m = compute_metrics(y_true, xgb_y_pred, label_names, model_name="XGBoost")
    print_single_report(xgb_m)
    if plot_confusion:
        print_confusion_matrix_plot(xgb_m, report_dir / "cm_xgb.png")

    # ── Ensemble metrics ────────────────────────────────────────────────
    ensemble_m = None
    if gru_proba is not None and xgb_proba is not None:
        ensemble_m = evaluate_ensemble(
            gru_proba, xgb_proba, y_true,
            label_names=label_names,
            model_name="Ensemble (GRU+XGB)",
        )
        print_single_report(ensemble_m)
        if plot_confusion:
            print_confusion_matrix_plot(ensemble_m, report_dir / "cm_ensemble.png")
    else:
        log.warning("GRU/XGB probabilities not provided — skipping ensemble evaluation.")

    # ── Side-by-side comparison ─────────────────────────────────────────
    print_comparison_table(gru_m, xgb_m, ensemble_m)

    # ── Majority-class baseline ─────────────────────────────────────────
    baseline_info = None
    if y_train is not None:
        from collections import Counter
        train_counts = Counter(y_train.tolist())
        majority_class = max(train_counts, key=train_counts.get)
        baseline_acc = float((y_true == majority_class).sum() / len(y_true))
        baseline_info = {
            "strategy": f"always_predict_{label_names[majority_class]}",
            "majority_class_id": int(majority_class),
            "majority_class_name": label_names[majority_class],
            "accuracy": round(baseline_acc, 4),
        }
        print(f"  Majority-class baseline: {baseline_info['strategy']} "
              f"(accuracy={baseline_acc:.4f})")

    # ── Save JSON reports ───────────────────────────────────────────────
    def _to_serializable(m: dict) -> dict:
        out = {k: v for k, v in m.items() if k != "classification_report_str"}
        return out

    full_report = {
        "gru": _to_serializable(gru_m),
        "xgb": _to_serializable(xgb_m),
        "baseline": baseline_info,
    }
    if ensemble_m is not None:
        full_report["ensemble"] = _to_serializable(ensemble_m)

    out_path = report_dir / "comprehensive_evaluation.json"
    out_path.write_text(json.dumps(full_report, indent=2), encoding="utf-8")
    log.info("Full evaluation report saved -> %s", out_path)

    return full_report
