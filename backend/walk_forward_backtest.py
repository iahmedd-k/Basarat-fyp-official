"""
Walk-Forward Backtesting — calibration + classification metrics
===============================================================

Trains on an expanding window, predicts one day at a time, never using
future data.  Reports calibration (reliability diagram + ECE) and
standard classification metrics (macro-F1, per-class P/R/F1, balanced
accuracy).

Supports three model modes:
    --model gru        GRU only
    --model xgb        XGBoost only
    --model ensemble   GRU + XGB averaged probabilities

Usage:
    cd backend
    python walk_forward_backtest.py --model ensemble
    python walk_forward_backtest.py --model gru --retrain-freq 5
    python walk_forward_backtest.py --model xgb --backtest-start 2025-09-01
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

FEATURES_PATH = Path("data/features/features_daily.parquet")
SEQUENCES_DIR = Path("data/sequences")

LABEL_MAPPING = {"bullish": 0, "bearish": 1, "sideways": 2}
REVERSE_LABELS = {v: k for k, v in LABEL_MAPPING.items()}

CALIBRATION_BUCKETS = [(i * 10, (i + 1) * 10) for i in range(10)]

# Import explicit GRU feature list
import sys
sys.path.insert(0, str(Path(__file__).parent))
from app.data.features.gru_feature_list import GRU_FEATURE_LIST


# ── Data Loading ───────────────────────────────────────────────────────────

def load_features() -> pd.DataFrame:
    df = pd.read_parquet(FEATURES_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def load_sequences():
    path = SEQUENCES_DIR / "sequences.npz"
    meta_path = SEQUENCES_DIR / "sequences_meta.parquet"
    if not path.exists() or not meta_path.exists():
        return None, None
    data = np.load(path)
    meta = pd.read_parquet(meta_path)
    meta["date"] = pd.to_datetime(meta["date"])
    return data["X"], data["y"], meta


# Use explicit GRU feature list — NOT dynamic
def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return the explicit GRU feature list (versioned)."""
    # Verify all required features exist
    missing = [c for c in GRU_FEATURE_LIST if c not in df.columns]
    if missing:
        raise ValueError(f"Required GRU features missing: {missing}")
    return GRU_FEATURE_LIST.copy()


# ── Model Training ─────────────────────────────────────────────────────────

def train_gru(X_train: np.ndarray, y_train: np.ndarray, input_shape: tuple):
    import os
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
    import tensorflow as tf
    from app.ml.training.model import build_model

    n, T, F = X_train.shape
    flat = X_train.reshape(n * T, F)
    scaler = __import__("sklearn.preprocessing", fromlist=["StandardScaler"]).StandardScaler()
    scaler.fit(flat)

    X_scaled = scaler.transform(flat).reshape(n, T, F)

    X_val = X_scaled[:len(X_scaled) // 10]
    y_val = y_train[:len(y_train) // 10]
    X_tr = X_scaled[len(X_scaled) // 10:]
    y_tr = y_train[len(y_train) // 10:]

    model = build_model(input_shape, n_classes=3)
    model.fit(
        X_tr, y_tr,
        validation_data=(X_val, y_val),
        epochs=20, batch_size=32,
        callbacks=[tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=5, restore_best_weights=True
        )],
        verbose=0,
    )
    return model, scaler


def train_xgb(X_train: np.ndarray, y_train: np.ndarray):
    from app.ml.training_xgb.model import build_xgb_classifier
    model = build_xgb_classifier()
    model.fit(X_train, y_train, verbose=False)
    return model


# ── Prediction Helpers ─────────────────────────────────────────────────────

def predict_gru(model, scaler, X_seq: np.ndarray):
    from sklearn.preprocessing import StandardScaler as _SC
    n, T, F = X_seq.shape
    flat = X_seq.reshape(n * T, F)
    scaled = scaler.transform(flat).reshape(n, T, F)
    proba = model.predict(scaled, verbose=0)[0]
    pred_class = int(np.argmax(proba))
    return REVERSE_LABELS[pred_class], float(proba[pred_class]) * 100, proba


def predict_xgb(model, X_row: np.ndarray):
    proba = model.predict_proba(X_row)[0]
    pred_class = int(np.argmax(proba))
    return REVERSE_LABELS[pred_class], float(proba[pred_class]) * 100, proba


def ensemble_decide(gru_proba, xgb_proba, gru_weight=0.5):
    avg = gru_weight * gru_proba + (1 - gru_weight) * xgb_proba
    pred_class = int(np.argmax(avg))
    return REVERSE_LABELS[pred_class], float(avg[pred_class]) * 100, avg


# ── Walk-Forward Engine ───────────────────────────────────────────────────

def run_walk_forward(
    model_type: str = "ensemble",
    initial_train_days: int = 500,
    retrain_freq: int = 5,
    backtest_start: str = "2025-07-01",
    backtest_end: str | None = None,
):
    print("=" * 80)
    print(f"  WALK-FORWARD BACKTEST — {model_type.upper()}")
    print("=" * 80)

    features = load_features()
    seq_X, seq_y, seq_meta = load_sequences() if model_type in ("gru", "ensemble") else (None, None, None)

    feature_cols = get_feature_columns(features)
    all_dates = sorted(features["date"].unique())
    all_dates = pd.DatetimeIndex(all_dates)
    symbols = sorted(features["symbol"].unique())

    bt_start = pd.Timestamp(backtest_start)
    bt_end = pd.Timestamp(backtest_end) if backtest_end else all_dates[-1]

    start_idx = int(np.searchsorted(all_dates, bt_start))
    if start_idx < initial_train_days:
        raise ValueError(f"Not enough history before {backtest_start}")

    end_idx = int(np.searchsorted(all_dates, bt_end, side="right"))
    backtest_dates = all_dates[start_idx:end_idx]

    print(f"  Period:    {backtest_dates[0].date()} -> {backtest_dates[-1].date()}")
    print(f"  Symbols:   {len(symbols)}")
    print(f"  Retrain:   every {retrain_freq} days")
    print(f"  Train up:  {all_dates[0].date()} -> initial window {initial_train_days} days")
    print()

    gru_model, gru_scaler = None, None
    xgb_model = None
    last_retrain = -retrain_freq

    results = []

    for i, pred_date in enumerate(backtest_dates):
        should_retrain = (i - last_retrain) >= retrain_freq
        if not should_retrain and gru_model is None and xgb_model is None:
            should_retrain = True

        if should_retrain:
            t0 = time.time()
            train_end_idx = int(np.searchsorted(all_dates, pred_date, side="left"))
            n_train_days = train_end_idx

            if model_type in ("gru", "ensemble") and seq_X is not None:
                train_meta_mask = (seq_meta["date"] < pred_date) & (seq_meta["date"] >= all_dates[0])
                train_indices = np.where(train_meta_mask)[0]
                if len(train_indices) > 50:
                    X_tr = seq_X[train_indices]
                    y_tr = seq_y[train_indices]
                    gru_model, gru_scaler = train_gru(X_tr, y_tr, (X_tr.shape[1], X_tr.shape[2]))

            if model_type in ("xgb", "ensemble"):
                train_feat_mask = features["date"] < pred_date
                train_df = features[train_feat_mask]
                if len(train_df) > 500:
                    X_tr = train_df[feature_cols].values.astype(np.float32)
                    y_tr = train_df["label"].map(LABEL_MAPPING).values

                    medians = np.zeros(X_tr.shape[1], dtype=np.float32)
                    for f in range(X_tr.shape[1]):
                        valid = X_tr[:, f][~np.isnan(X_tr[:, f])]
                        medians[f] = np.median(valid) if len(valid) > 0 else 0.0
                    for f in range(X_tr.shape[1]):
                        X_tr[np.isnan(X_tr[:, f]), f] = medians[f]

                    xgb_model = train_xgb(X_tr, y_tr)

            elapsed = time.time() - t0
            last_retrain = i
            print(f"  [{pred_date.date()}] Retrained in {elapsed:.1f}s  (train days={n_train_days})")

        for sym in symbols:
            actual_row = features[(features["symbol"] == sym) & (features["date"] == pred_date)]
            if actual_row.empty:
                continue
            actual_label = actual_row.iloc[0].get("label")
            actual_return = actual_row.iloc[0].get("forward_return")
            if pd.isna(actual_label) or pd.isna(actual_return):
                continue

            gru_pred = None
            xgb_pred = None

            if model_type in ("gru", "ensemble") and gru_model is not None and seq_X is not None:
                seq_mask = (seq_meta["symbol"] == sym) & (seq_meta["date"] == pred_date)
                seq_idx = np.where(seq_mask)[0]
                if len(seq_idx) > 0:
                    X_test = seq_X[seq_idx[0]:seq_idx[0] + 1]
                    cls, conf, proba = predict_gru(gru_model, gru_scaler, X_test)
                    gru_pred = {"class": cls, "confidence": conf, "proba": proba}

            if model_type in ("xgb", "ensemble") and xgb_model is not None:
                feat_mask = (features["symbol"] == sym) & (features["date"] == pred_date)
                feat_idx = np.where(feat_mask)[0]
                if len(feat_idx) > 0:
                    row = features.iloc[feat_idx[0]]
                    vals = []
                    for fname in feature_cols:
                        v = row.get(fname, 0.0)
                        vals.append(float(v) if not pd.isna(v) else 0.0)
                    X_test = np.array([vals], dtype=np.float32)
                    cls, conf, proba = predict_xgb(xgb_model, X_test)
                    xgb_pred = {"class": cls, "confidence": conf, "proba": proba}

            if model_type == "gru":
                final = gru_pred
            elif model_type == "xgb":
                final = xgb_pred
            else:
                if gru_pred and xgb_pred:
                    cls, conf, proba = ensemble_decide(gru_pred["proba"], xgb_pred["proba"])
                    final = {"class": cls, "confidence": conf, "proba": proba}
                elif gru_pred:
                    final = gru_pred
                elif xgb_pred:
                    final = xgb_pred
                else:
                    continue

            results.append({
                "symbol": sym,
                "date": pred_date,
                "predicted_class": final["class"],
                "confidence": final["confidence"],
                "actual_class": actual_label,
                "actual_return": float(actual_return),
                "correct": final["class"] == actual_label,
            })

        if (i + 1) % 20 == 0:
            n_correct = sum(1 for r in results[-len(symbols):] if r["correct"])
            n_total = min(len(symbols), len(results[-len(symbols):]))
            acc = n_correct / n_total * 100 if n_total > 0 else 0
            print(f"  [{pred_date.date()}] Progress: {i+1}/{len(backtest_dates)} days, "
                  f"running acc={acc:.1f}%")

    print(f"\n  Total predictions: {len(results)}")
    return results


# ── Analysis ───────────────────────────────────────────────────────────────

def analyze(results: list[dict], model_type: str):
    if not results:
        print("No results to analyze.")
        return

    df = pd.DataFrame(results)
    y_true = df["actual_class"].values
    y_pred = df["predicted_class"].values

    n_correct = int(df["correct"].sum())
    accuracy = n_correct / len(df)
    balanced_acc = _balanced_accuracy(y_true, y_pred)
    macro_p, macro_r, macro_f1, _ = _macro_prf(y_true, y_pred)

    print()
    print("=" * 80)
    print(f"  CLASSIFICATION METRICS — {model_type.upper()}")
    print("=" * 80)
    print(f"  Total predictions:  {len(df)}")
    print(f"  Overall accuracy:   {accuracy:.4f}")
    print(f"  Balanced accuracy:  {balanced_acc:.4f}")
    print(f"  Macro precision:    {macro_p:.4f}")
    print(f"  Macro recall:       {macro_r:.4f}")
    print(f"  Macro F1:           {macro_f1:.4f}")

    print()
    print(f"  {'Class':<12} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10} {'Pred Count':>12}")
    print(f"  {'-' * 64}")
    for cls in ["bullish", "bearish", "sideways"]:
        tp = int(((y_pred == cls) & (y_true == cls)).sum())
        fp = int(((y_pred == cls) & (y_true != cls)).sum())
        fn = int(((y_pred != cls) & (y_true == cls)).sum())
        support = int((y_true == cls).sum())
        pred_count = int((y_pred == cls).sum())
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        print(f"  {cls:<12} {p:>10.4f} {r:>10.4f} {f1:>10.4f} {support:>10} {pred_count:>12}")

    _print_calibration(df)

    report_path = Path("data/reports") / f"walkforward_{model_type}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({
        "model_type": model_type,
        "total_predictions": len(df),
        "accuracy": round(accuracy, 4),
        "balanced_accuracy": round(balanced_acc, 4),
        "macro_f1": round(macro_f1, 4),
        "macro_precision": round(macro_p, 4),
        "macro_recall": round(macro_r, 4),
    }, indent=2), encoding="utf-8")
    print(f"\n  Report saved -> {report_path}")

    return df


def _balanced_accuracy(y_true, y_pred):
    classes = np.unique(np.concatenate([y_true, y_pred]))
    recalls = []
    for cls in classes:
        mask = y_true == cls
        if mask.sum() > 0:
            recalls.append((y_pred[mask] == cls).mean())
    return float(np.mean(recalls)) if recalls else 0.0


def _macro_prf(y_true, y_pred):
    classes = np.unique(np.concatenate([y_true, y_pred]))
    ps, rs, f1s = [], [], []
    for cls in classes:
        tp = ((y_pred == cls) & (y_true == cls)).sum()
        fp = ((y_pred == cls) & (y_true != cls)).sum()
        fn = ((y_pred != cls) & (y_true == cls)).sum()
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        ps.append(p)
        rs.append(r)
        f1s.append(f1)
    return float(np.mean(ps)), float(np.mean(rs)), float(np.mean(f1s)), f1s


def _print_calibration(df: pd.DataFrame):
    print()
    print("=" * 80)
    print("  CALIBRATION (RELIABILITY) ANALYSIS")
    print("=" * 80)
    print()
    print(f"  {'Bucket':<14} {'Mean Predicted':>15} {'Actual Accuracy':>16} {'Count':>8} {'Gap':>8}")
    print(f"  {'-' * 62}")

    calib_data = []
    for low, high in CALIBRATION_BUCKETS:
        mask = (df["confidence"] >= low) & (df["confidence"] < high)
        bucket = df[mask]
        if len(bucket) == 0:
            continue
        avg_pred = bucket["confidence"].mean()
        actual_acc = bucket["correct"].mean() * 100
        gap = actual_acc - avg_pred
        count = len(bucket)
        calib_data.append({"bucket": f"{low}-{high}%", "avg_pred": avg_pred,
                           "actual_acc": actual_acc, "count": count, "gap": gap})
        flag = " ***" if abs(gap) > 10 else (" *" if abs(gap) > 5 else "")
        print(f"  {low:>2}-{high:<2}%    {avg_pred:>13.1f}%  {actual_acc:>14.1f}%  {count:>7}  {gap:>+6.1f}%{flag}")

    total = len(df)
    ece = sum(d["count"] / total * abs(d["gap"]) for d in calib_data) if calib_data else 0
    print(f"  {'-' * 62}")
    print(f"  ECE (Expected Calibration Error): {ece:.2f}%")
    print()
    if ece < 5:
        print("  Verdict: WELL CALIBRATED (ECE < 5%)")
    elif ece < 10:
        print("  Verdict: MODERATELY CALIBRATED (5% < ECE < 10%)")
    else:
        print("  Verdict: POORLY CALIBRATED (ECE > 10%) — probabilities are NOT trustworthy")


def plot_reliability(df: pd.DataFrame, model_type: str):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib not installed — skipping plot")
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

    buckets_labels, avg_preds, actual_accs, counts = [], [], [], []
    for low, high in CALIBRATION_BUCKETS:
        mask = (df["confidence"] >= low) & (df["confidence"] < high)
        bucket = df[mask]
        if len(bucket) == 0:
            continue
        buckets_labels.append(f"{low}-{high}")
        avg_preds.append(bucket["confidence"].mean())
        actual_accs.append(bucket["correct"].mean() * 100)
        counts.append(len(bucket))

    x = np.arange(len(buckets_labels))

    ax = axes[0]
    w = 0.35
    ax.bar(x - w / 2, avg_preds, w, label="Avg Predicted Conf.", color="#4C72B0", alpha=0.85)
    ax.bar(x + w / 2, actual_accs, w, label="Actual Accuracy", color="#DD8452", alpha=0.85)
    ax.plot([-0.5, len(x) - 0.5], [0, 100], "k--", alpha=0.4, linewidth=1, label="Perfect")
    ax.set_xticks(x)
    ax.set_xticklabels(buckets_labels, rotation=45, fontsize=8)
    ax.set_ylabel("%")
    ax.set_title(f"Reliability Diagram — {model_type.upper()}")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)

    ax2 = axes[1]
    ax2.plot(avg_preds, actual_accs, "o-", color="#4C72B0", linewidth=2, markersize=7, zorder=3)
    ax2.plot([0, 100], [0, 100], "k--", alpha=0.4, linewidth=1, label="Perfect")
    for i, (ap, aa, c) in enumerate(zip(avg_preds, actual_accs, counts)):
        ax2.annotate(f"n={c}", (ap, aa), textcoords="offset points",
                     xytext=(5, 5), fontsize=7, color="gray")
    ax2.set_xlabel("Mean Predicted Confidence (%)")
    ax2.set_ylabel("Actual Accuracy (%)")
    ax2.set_title(f"Calibration Curve — {model_type.upper()}")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.25)
    ax2.set_xlim(-2, 102)
    ax2.set_ylim(-2, 102)

    plt.tight_layout()
    out = Path("data/reports") / f"reliability_{model_type}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"  Reliability diagram saved -> {out}")
    plt.close(fig)


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Walk-Forward Backtest")
    parser.add_argument("--model", choices=["gru", "xgb", "ensemble"], default="ensemble",
                        help="Model to backtest (default: ensemble)")
    parser.add_argument("--initial-train-days", type=int, default=500,
                        help="Minimum training window in days (default: 500)")
    parser.add_argument("--retrain-freq", type=int, default=5,
                        help="Retrain every N backtest days (default: 5)")
    parser.add_argument("--backtest-start", type=str, default="2025-07-01",
                        help="First prediction date (default: 2025-07-01)")
    parser.add_argument("--backtest-end", type=str, default=None,
                        help="Last prediction date (default: latest available)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    results = run_walk_forward(
        model_type=args.model,
        initial_train_days=args.initial_train_days,
        retrain_freq=args.retrain_freq,
        backtest_start=args.backtest_start,
        backtest_end=args.backtest_end,
    )

    df = analyze(results, args.model)
    if df is not None:
        plot_reliability(df, args.model)

    print()


if __name__ == "__main__":
    main()
