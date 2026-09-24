"""Train isolated price-only and disclosure-augmented XGBoost candidates."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, classification_report,
                             f1_score, log_loss, confusion_matrix)

import common

HERE = Path(__file__).resolve().parent
OUT = HERE / "models" / "xgb"
LOG = logging.getLogger("psx_disclosure_v1.xgb")
BASE_FEATURES = common.XGB_CORE
EVENT_FEATURES = common.XGB_FEATURES


def _weights(frame: pd.DataFrame) -> np.ndarray:
    # Give each date equal total weight so high-coverage dates do not dominate.
    counts = frame.groupby("date").date.transform("size").to_numpy(dtype=float)
    w = 1.0 / np.maximum(counts, 1)
    return (w * len(w) / w.sum()).astype(np.float32)


def _rank_metrics(frame: pd.DataFrame, probability: np.ndarray) -> dict:
    temp = frame[["date", "target_excess_return"]].copy()
    temp["score"] = probability[:, 2] - probability[:, 0]
    ics, spreads, long_returns = [], [], []
    for _, g in temp.groupby("date"):
        if len(g) < 5 or g.score.nunique() < 2:
            continue
        corr = g.score.corr(g.target_excess_return, method="spearman")
        if pd.notna(corr): ics.append(float(corr))
        k = max(1, int(np.ceil(len(g) * 0.2)))
        ordered = g.sort_values("score")
        spreads.append(float(ordered.tail(k).target_excess_return.mean() - ordered.head(k).target_excess_return.mean()))
        long_returns.append(float(ordered.tail(k).target_excess_return.mean()))
    return {"mean_daily_spearman_ic": float(np.mean(ics)) if ics else None,
            "median_daily_spearman_ic": float(np.median(ics)) if ics else None,
            "mean_top_minus_bottom_20pct_excess_return": float(np.mean(spreads)) if spreads else None,
            "mean_top_20pct_excess_return": float(np.mean(long_returns)) if long_returns else None,
            "dates_evaluated": len(ics)}


def _rejection_metrics(y_true: np.ndarray, proba: np.ndarray, frame: pd.DataFrame) -> dict:
    thresholds = [0.50, 0.52, 0.54, 0.55, 0.56, 0.58, 0.60]
    out = {}
    excess = frame["target_excess_return"].to_numpy()
    for th in thresholds:
        buy_mask = proba >= th
        sell_mask = proba <= (1.0 - th)
        actionable = buy_mask | sell_mask
        n_act = int(actionable.sum())
        if n_act > 0:
            pred_act = (proba[actionable] >= 0.5).astype(int)
            acc = float(accuracy_score(y_true[actionable], pred_act))
            cov = float(actionable.mean()) * 100.0
            buy_ret = float(np.mean(excess[buy_mask])) if buy_mask.sum() > 0 else 0.0
            sell_ret = float(np.mean(excess[sell_mask])) if sell_mask.sum() > 0 else 0.0
            spread = buy_ret - sell_ret
        else:
            acc, cov, spread, buy_ret, sell_ret = None, 0.0, 0.0, 0.0, 0.0
        out[f"threshold_{th:.2f}"] = {
            "threshold": th,
            "actionable_accuracy": acc,
            "coverage_pct": cov,
            "signals_generated_count": n_act,
            "no_signal_count": int((~actionable).sum()),
            "mean_buy_excess_return": buy_ret,
            "long_short_alpha_spread": spread,
        }
    return out


def _metrics(model: xgb.XGBClassifier, frame: pd.DataFrame, x: pd.DataFrame) -> dict:
    y = frame.target_direction.astype(int).to_numpy()
    proba = model.predict_proba(x)[:, 1]
    pred = (proba >= 0.5).astype(int)
    labels = [0, 1]
    result = {
        "rows": int(len(y)),
        "directional_accuracy_all_samples": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "log_loss": float(log_loss(y, proba, labels=labels)),
        "brier_score": float(np.mean((proba - y) ** 2)),
        "classification_report": classification_report(y, pred, labels=labels,
            target_names=["down", "up"], output_dict=True, zero_division=0),
        "rejection_decision_layer": _rejection_metrics(y, proba, frame),
    }
    # Rank metrics using P(UP) as cross-sectional alpha score
    temp = frame[["date", "target_excess_return"]].copy()
    temp["score"] = proba
    ics, spreads, long_returns = [], [], []
    for _, g in temp.groupby("date"):
        if len(g) < 5 or g.score.nunique() < 2: continue
        corr = g.score.corr(g.target_excess_return, method="spearman")
        if pd.notna(corr): ics.append(float(corr))
        k = max(1, int(np.ceil(len(g) * 0.2)))
        ordered = g.sort_values("score")
        spreads.append(float(ordered.tail(k).target_excess_return.mean() - ordered.head(k).target_excess_return.mean()))
        long_returns.append(float(ordered.tail(k).target_excess_return.mean()))
    result.update({
        "mean_daily_spearman_ic": float(np.mean(ics)) if ics else None,
        "median_daily_spearman_ic": float(np.median(ics)) if ics else None,
        "mean_top_minus_bottom_20pct_excess_return": float(np.mean(spreads)) if spreads else None,
        "mean_top_20pct_excess_return": float(np.mean(long_returns)) if long_returns else None,
        "dates_evaluated": len(ics),
    })
    return result


def _fit_variant(data: pd.DataFrame, feature_names: list[str], variant: str) -> dict:
    train = data[data.split == "train"].dropna(subset=["target_direction"]).copy()
    val = data[data.split == "validation"].dropna(subset=["target_direction"]).copy()
    test = data[data.split == "test"].dropna(subset=["target_direction"]).copy()
    if min(len(train), len(val), len(test)) == 0:
        raise ValueError(f"Empty split: train={len(train)} val={len(val)} test={len(test)}")

    x_train = train[feature_names].replace([np.inf, -np.inf], np.nan).astype(np.float32)
    x_val = val[feature_names].replace([np.inf, -np.inf], np.nan).astype(np.float32)
    x_test = test[feature_names].replace([np.inf, -np.inf], np.nan).astype(np.float32)

    y_train = train.target_direction.astype(int).to_numpy()
    y_val = val.target_direction.astype(int).to_numpy()

    model = xgb.XGBClassifier(
        objective="binary:logistic", n_estimators=2500,
        learning_rate=0.015, max_depth=5, min_child_weight=25,
        subsample=0.85, colsample_bytree=0.75, reg_lambda=15.0, reg_alpha=2.0,
        eval_metric="logloss", early_stopping_rounds=80, tree_method="hist",
        n_jobs=-1, random_state=20260924,
    )
    model.fit(x_train, y_train, sample_weight=_weights(train),
              eval_set=[(x_val, y_val)], verbose=False)
    metrics = {
        "train": _metrics(model, train, x_train),
        "validation": _metrics(model, val, x_val),
        "sealed_test": _metrics(model, test, x_test),
        "best_iteration": int(getattr(model, "best_iteration", model.n_estimators - 1)),
        "feature_count": len(feature_names), "features": feature_names,
        "split_dates": {
            "train_start": str(train.date.min().date()), "train_end": str(train.date.max().date()),
            "validation_start": str(val.date.min().date()), "validation_end": str(val.date.max().date()),
            "test_start": str(test.date.min().date()), "test_end": str(test.date.max().date()),
        },
    }
    path = OUT / variant
    path.mkdir(parents=True, exist_ok=True)
    model_path = path / "model.ubj"
    model.save_model(str(model_path))
    joblib.dump(model, path / "model.joblib")
    (path / "feature_names.json").write_text(json.dumps(feature_names, indent=2), encoding="utf-8")
    metrics_path = path / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, default=float), encoding="utf-8")
    manifest = {
        "model": "xgboost_directional_binary", "variant": variant,
        "target_semantics": common.DIRECTION_NAMES,
        "horizon_sessions": common.HORIZON_SESSIONS,
        "training_metadata": common.META_PATH.name,
        "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "metrics_file": metrics_path.name,
    }
    (path / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return metrics


def train(rebuild: bool = False, fetch: bool = False, years: int = 8, allow_price_only: bool = False) -> dict:
    data, meta = common.get_dataset(rebuild, fetch, years, allow_price_only)
    # Baseline and event model use exactly the same eligible rows and split.
    data = data[data.target_direction.notna() & (data.volume > 0)].copy()
    results = {}
    for variant, cols in [("baseline", BASE_FEATURES), ("event_augmented", EVENT_FEATURES)]:
        LOG.info("Training %s: %d features", variant, len(cols))
        results[variant] = _fit_variant(data, cols, variant)
    summary = {
        "target": meta["target"], "event_data": meta["event_data"],
        "baseline_test": results["baseline"]["sealed_test"],
        "event_augmented_test": results["event_augmented"]["sealed_test"],
        "interpretation": "Compare variants only on this identical eligible sample. Test set is sealed; do not tune on these metrics.",
    }
    (OUT / "comparison.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    common.add_cli_args(parser)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = train(args.rebuild, args.fetch, args.years, args.allow_price_only)
    print(json.dumps(result, indent=2, default=float))


if __name__ == "__main__":
    main()
