from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (balanced_accuracy_score, classification_report,
                             f1_score, precision_recall_fscore_support)
from sklearn.dummy import DummyClassifier
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "ohlcv"
MODELS = ROOT / "models"
REPORTS = ROOT / "reports"
LEDGER = DATA / "forecast_ledger.sqlite3"
HORIZONS = (1, 3, 7)
CLASSES = ("bearish", "neutral", "bullish")
VERSION = "psx-volband-xgb-v1"
TRAIN_END = pd.Timestamp("2023-12-31")
CAL_END = pd.Timestamp("2024-12-31")
TEST_START = pd.Timestamp("2025-01-01")
FETCH_START = "2020-01-01"
FEATURES = [
    "ret_1", "ret_3", "ret_7", "ret_14", "ret_21", "vol_5", "vol_20",
    "close_sma5", "close_sma20", "close_sma50", "rsi_14", "range_pct",
    "volume_log_z20", "volume_change_5", "peer_median_ret", "peer_momentum_5",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("forecast_research")


def ensure_dirs() -> None:
    for path in (DATA, RAW, MODELS, REPORTS):
        path.mkdir(parents=True, exist_ok=True)


def read_universe() -> list[str]:
    existing = sorted(p.stem.upper() for p in (ROOT.parent / "data" / "raw" / "ohlcv").glob("*.parquet") if p.stem.lower() != "all_symbols")
    if not existing:
        existing = sorted(p.stem.upper() for p in RAW.glob("*.parquet"))
    return existing


def fetch() -> None:
    """Fetch through psxdata; normalize order and preserve its anomaly flag."""
    ensure_dirs()
    try:
        from psxdata import PSXClient
    except ImportError as exc:
        raise RuntimeError("psxdata is required in the active Python environment") from exc
    symbols = read_universe()
    results = []
    errors = []

    def fetch_symbol(symbol: str) -> tuple[str, pd.DataFrame | None, str | None]:
        try:
            # Separate clients avoid sharing requests.Session across workers.
            client = PSXClient(cache_dir=str(DATA / "psx_cache"))
            frame = client.stocks(symbol, start=FETCH_START, end=pd.Timestamp.now().date().isoformat(), cache=True)
            if frame is None or frame.empty:
                return symbol, None, "empty response"
            frame = frame.rename(columns={c: c.lower() for c in frame.columns})
            required = {"date", "open", "high", "low", "close", "volume"}
            if not required.issubset(frame.columns):
                return symbol, None, f"missing columns: {sorted(required - set(frame.columns))}"
            if "is_anomaly" not in frame:
                frame["is_anomaly"] = False
            frame["symbol"] = symbol
            return symbol, frame, None
        except Exception as exc:  # keep a per-symbol failure manifest
            return symbol, None, f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_symbol, symbol): symbol for symbol in symbols}
        for i, future in enumerate(as_completed(futures), 1):
            symbol, frame, error = future.result()
            if error:
                errors.append({"symbol": symbol, "error": error})
                LOG.error("Fetch failed for %s: %s", symbol, error)
            else:
                results.append(frame)
                LOG.info("Fetched %s (%s/%s), rows=%s", symbol, i, len(symbols), len(frame))
    if not results:
        raise RuntimeError("No PSX data fetched")
    combined = pd.concat(results, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    combined = combined.dropna(subset=["date", "close"]).sort_values(["symbol", "date"])
    combined = combined.drop_duplicates(["symbol", "date"], keep="last")
    for col in ("open", "high", "low", "close", "volume"):
        combined[col] = pd.to_numeric(combined[col], errors="coerce")
    combined.to_parquet(DATA / "psx_ohlcv.parquet", index=False)
    manifest = {
        "source": "PSX historical data via psxdata",
        "source_docs": "https://psxdata.readthedocs.io/en/latest/api/client/",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbols_requested": len(symbols), "symbols_received": len(results),
        "rows": len(combined), "date_min": str(combined.date.min().date()),
        "date_max": str(combined.date.max().date()), "errors": errors,
    }
    (DATA / "fetch_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    LOG.info("Saved %s rows. Failures: %s", len(combined), len(errors))


def build_frame(path: Path | None = None) -> pd.DataFrame:
    path = path or DATA / "psx_ohlcv.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}; run `python -m forecast_research.pipeline fetch` first")
    df = pd.read_parquet(path)
    df.columns = [str(c).lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    df = df.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"], keep="last").copy()
    df["symbol"] = df.symbol.astype(str).str.upper()
    df["close"] = pd.to_numeric(df.close, errors="coerce")
    df["volume"] = pd.to_numeric(df.volume, errors="coerce")
    g = df.groupby("symbol", group_keys=False)
    df["ret_1"] = g.close.pct_change(fill_method=None)
    # Never join rows across different symbols when calculating peer returns.
    # Leave-one-symbol-out cross-sectional median; then roll over the actual
    # sequence of trading dates (never over symbols within a date).
    peer_values = pd.Series(index=df.index, dtype=float)
    for _, group in df.groupby("date", sort=False):
        vals = group.ret_1.to_numpy(dtype=float)
        valid = np.isfinite(vals)
        if valid.sum() < 3:
            continue
        for pos, idx in enumerate(group.index):
            peers = vals[valid & (np.arange(len(vals)) != pos)]
            if len(peers) >= 2:
                peer_values.loc[idx] = float(np.median(peers))
    df["peer_median_ret"] = peer_values
    daily_peer = df.groupby("date").peer_median_ret.median().sort_index()
    peer_momentum = daily_peer.rolling(5, min_periods=3).sum()
    df["peer_momentum_5"] = df.date.map(peer_momentum)
    for n in (3, 7, 14, 21):
        df[f"ret_{n}"] = g.close.pct_change(n, fill_method=None)
    df["vol_5"] = g.ret_1.transform(lambda s: s.rolling(5, min_periods=5).std())
    df["vol_20"] = g.ret_1.transform(lambda s: s.rolling(20, min_periods=15).std())
    for n in (5, 20, 50):
        sma = g.close.transform(lambda s: s.rolling(n, min_periods=n).mean())
        df[f"close_sma{n}"] = df.close / sma - 1
    delta = g.close.diff()
    gain = delta.clip(lower=0).groupby(df.symbol).transform(lambda s: s.rolling(14, min_periods=14).mean())
    loss = (-delta.clip(upper=0)).groupby(df.symbol).transform(lambda s: s.rolling(14, min_periods=14).mean())
    rs = gain / loss.replace(0, np.nan)
    df["rsi_14"] = 100 - (100 / (1 + rs))
    df["rsi_14"] = df["rsi_14"].fillna(50)
    if {"high", "low"}.issubset(df.columns):
        df["range_pct"] = (pd.to_numeric(df.high, errors="coerce") - pd.to_numeric(df.low, errors="coerce")) / df.close
    else:
        df["range_pct"] = np.nan
    logvol = np.log1p(df.volume.clip(lower=0))
    df["volume_log_z20"] = (logvol - logvol.groupby(df.symbol).transform(lambda s: s.rolling(20, min_periods=15).mean())) / logvol.groupby(df.symbol).transform(lambda s: s.rolling(20, min_periods=15).std()).replace(0, np.nan)
    df["volume_change_5"] = df.groupby("symbol").volume.pct_change(5, fill_method=None)
    # Flag abrupt raw-price jumps and source anomalies; without adjusted prices,
    # do not train/evaluate samples whose lookback or label interval crosses one.
    jump = df.ret_1.abs() > 0.15
    src = df.get("is_anomaly", pd.Series(False, index=df.index)).fillna(False).astype(bool)
    df["price_anomaly"] = jump | src
    # Features after a flagged price discontinuity are excluded for 50 sessions.
    df["clean_feature_window"] = ~df.groupby("symbol").price_anomaly.transform(lambda s: s.astype(int).rolling(50, min_periods=1).max().shift(1).fillna(0).astype(bool))
    for h in HORIZONS:
        future = g.close.shift(-h)
        forward = future / df.close - 1
        band = 0.5 * df.vol_20 * np.sqrt(h)
        label = np.select([forward < -band, forward > band], [0, 2], default=1)
        df[f"forward_return_{h}"] = forward
        df[f"label_{h}"] = label.astype(float)
        # Any flagged anomaly between as-of and outcome invalidates the label.
        bad_future = df.groupby("symbol").price_anomaly.transform(lambda s: s.iloc[::-1].rolling(h + 1, min_periods=1).max().iloc[::-1].astype(bool))
        df.loc[bad_future, f"label_{h}"] = np.nan
    df[FEATURES] = df[FEATURES].replace([np.inf, -np.inf], np.nan)
    return df


def model_for(h: int) -> XGBClassifier:
    # One preregistered, fixed recipe; no parameter search against the holdout.
    return XGBClassifier(
        objective="multi:softprob", num_class=3, n_estimators=350, max_depth=4,
        learning_rate=0.035, min_child_weight=12, subsample=0.8,
        colsample_bytree=0.8, reg_lambda=5.0, reg_alpha=0.1,
        random_state=4100 + h, n_jobs=4, eval_metric="mlogloss",
        tree_method="hist",
    )


def eligible(df: pd.DataFrame, h: int) -> pd.DataFrame:
    x = df.loc[df.clean_feature_window & df[f"label_{h}"].notna()].copy()
    return x.dropna(subset=FEATURES + [f"label_{h}"])


def metrics(y: np.ndarray, p: np.ndarray) -> dict:
    pred = p.argmax(axis=1)
    pr, rc, f1, support = precision_recall_fscore_support(y, pred, labels=[0, 1, 2], zero_division=0)
    return {
        "n": int(len(y)), "macro_f1": float(f1_score(y, pred, average="macro")),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "per_class": {c: {"precision": float(pr[i]), "recall": float(rc[i]), "f1": float(f1[i]), "support": int(support[i])} for i, c in enumerate(CLASSES)},
        "confusion_matrix_labels": list(CLASSES),
        "confusion_matrix": __import__("sklearn.metrics", fromlist=["confusion_matrix"]).confusion_matrix(y, pred, labels=[0, 1, 2]).tolist(),
        "multiclass_brier": float(np.mean(np.sum((p - np.eye(3)[y]) ** 2, axis=1))),
        "log_loss": float(__import__("sklearn.metrics", fromlist=["log_loss"]).log_loss(y, p, labels=[0, 1, 2])),
    }


def apply_temperature(probs: np.ndarray, temperature: float) -> np.ndarray:
    logits = np.log(np.clip(probs, 1e-12, 1.0)) / float(temperature)
    logits -= logits.max(axis=1, keepdims=True)
    out = np.exp(logits)
    return out / out.sum(axis=1, keepdims=True)


def fit_temperature(probs: np.ndarray, y: np.ndarray) -> float:
    from scipy.optimize import minimize_scalar
    from sklearn.metrics import log_loss
    result = minimize_scalar(lambda t: log_loss(y, apply_temperature(probs, t), labels=[0, 1, 2]), bounds=(0.2, 5.0), method="bounded")
    return float(result.x)


def evaluate() -> None:
    ensure_dirs()
    df = build_frame()
    report = {"model_version": VERSION, "train_end": str(TRAIN_END.date()), "calibration_period": ["2024-01-01", str(CAL_END.date())], "test_start": str(TEST_START.date()), "target": "forward return versus +/- 0.5 * point-in-time 20-session volatility * sqrt(horizon)", "horizons": {}}
    temperatures = {}
    for h in HORIZONS:
        d = eligible(df, h)
        train, calibration, test = d[d.date <= TRAIN_END], d[(d.date > TRAIN_END) & (d.date <= CAL_END)], d[d.date >= TEST_START]
        # Purge h global trading sessions so training labels cannot consume
        # prices from the first holdout sessions.
        pre_cal_dates = pd.Series(df.loc[df.date <= TRAIN_END, "date"].drop_duplicates().sort_values().to_numpy())
        pretest_dates = pd.Series(df.loc[df.date < TEST_START, "date"].drop_duplicates().sort_values().to_numpy())
        if len(pre_cal_dates) <= h or len(pretest_dates) <= h:
            raise RuntimeError(f"Cannot purge {h} sessions before holdout")
        train = train[train.date <= pre_cal_dates.iloc[-(h + 1)]]
        purge_cutoff = pretest_dates.iloc[-(h + 1)]
        calibration = calibration[calibration.date <= purge_cutoff]
        if train.empty or calibration.empty or test.empty:
            raise RuntimeError(f"Insufficient train/calibration/test data for {h}d: {len(train)}/{len(calibration)}/{len(test)}")
        ytr = train[f"label_{h}"].astype(int).to_numpy()
        yc = calibration[f"label_{h}"].astype(int).to_numpy()
        yte = test[f"label_{h}"].astype(int).to_numpy()
        mdl = model_for(h)
        mdl.fit(train[FEATURES], ytr)
        calibration_probs = mdl.predict_proba(calibration[FEATURES])
        temperature = fit_temperature(calibration_probs, yc)
        temperatures[str(h)] = temperature
        probs = apply_temperature(mdl.predict_proba(test[FEATURES]), temperature)
        majority = DummyClassifier(strategy="prior").fit(train[FEATURES], ytr)
        dummy_probs = majority.predict_proba(test[FEATURES])
        # XGBoost can omit a class if training has none; require all three.
        if list(mdl.classes_) != [0, 1, 2]:
            raise RuntimeError(f"Training labels for {h}d do not include all classes: {mdl.classes_}")
        report["horizons"][f"{h}d"] = {
            "n_train": len(train), "n_calibration": len(calibration), "n_test": len(test), "temperature": temperature,
            "calibration_log_loss": float(__import__("sklearn.metrics", fromlist=["log_loss"]).log_loss(yc, apply_temperature(calibration_probs, temperature), labels=[0, 1, 2])),
            "train_class_counts": {c: int((ytr == i).sum()) for i, c in enumerate(CLASSES)},
            "test_class_counts": {c: int((yte == i).sum()) for i, c in enumerate(CLASSES)},
            "xgboost": metrics(yte, probs), "majority_baseline": metrics(yte, dummy_probs),
            "test_dates": [str(test.date.min().date()), str(test.date.max().date())],
        }
        LOG.info("%sd holdout macro-F1 %.4f balanced-accuracy %.4f (n=%s)", h, report["horizons"][f"{h}d"]["xgboost"]["macro_f1"], report["horizons"][f"{h}d"]["xgboost"]["balanced_accuracy"], len(test))
    report["data_rows"] = int(len(df))
    report["symbols"] = int(df.symbol.nunique())
    report["anomaly_rows"] = int(df.price_anomaly.sum())
    report["interpretation"] = "Calibrated historical holdout metrics; not evidence of tradable excess return. Existing project experiments have already examined overlapping historical dates."
    (MODELS / "calibration.json").write_text(json.dumps({"model_version": VERSION, "method": "single scalar temperature fitted on 2024 time-separated calibration set", "temperatures": temperatures}, indent=2), encoding="utf-8")
    (REPORTS / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (REPORTS / "evaluation.md").write_text(render_report(report), encoding="utf-8")


def render_report(report: dict) -> str:
    lines = ["# Forecast model evaluation", "", f"Version: `{report['model_version']}`  ", f"Train through: {report['train_end']}  ", f"Calibration: {report['calibration_period'][0]} through {report['calibration_period'][1]}  ", f"Historical test: {report['test_start']} onward", "", "Macro-F1 and balanced accuracy are the primary metrics. The multiclass probabilities are temperature-scaled using the separate 2024 calibration period. Majority-class probabilities provide the baseline. Per-class precision/recall and confusion matrices are in `evaluation.json`.", "", "| Horizon | Train n | Cal n | Test n | XGB macro-F1 | Majority macro-F1 | XGB balanced accuracy | Majority balanced accuracy |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for h, m in report["horizons"].items():
        x, b = m["xgboost"], m["majority_baseline"]
        lines.append(f"| {h} | {m['n_train']} | {m['n_calibration']} | {m['n_test']} | {x['macro_f1']:.4f} | {b['macro_f1']:.4f} | {x['balanced_accuracy']:.4f} | {b['balanced_accuracy']:.4f} |")
    lines.extend(["", f"Rows: {report['data_rows']}; symbols: {report['symbols']}; flagged anomaly/jump rows: {report['anomaly_rows']}.", "", "## Limitations", "", "The holdout period has appeared in prior repository research, so it is not a virgin holdout. Raw PSX OHLCV lacks verified corporate-action adjusted total returns and historic constituents. Reported classification metrics do not establish a profitable strategy, calibrated confidence, or future performance. Use shadow forecasts and collect forward outcomes before considering integration.", ""])
    return "\n".join(lines)


def train() -> None:
    ensure_dirs()
    df = build_frame()
    for h in HORIZONS:
        d = eligible(df, h)
        y = d[f"label_{h}"].astype(int).to_numpy()
        if set(np.unique(y)) != {0, 1, 2}:
            raise RuntimeError(f"Final {h}d dataset does not contain all classes")
        model = model_for(h).fit(d[FEATURES], y)
        model.save_model(str(MODELS / f"xgb_{h}d.json"))
    manifest = {"model_version": VERSION, "trained_at_utc": datetime.now(timezone.utc).isoformat(), "data_as_of": str(df.date.max().date()), "horizons": list(HORIZONS), "classes": {"0": "bearish", "1": "neutral", "2": "bullish"}, "features": FEATURES, "train_rows": {str(h): int(len(eligible(df, h))) for h in HORIZONS}, "protocol": "fixed XGBoost recipe; all eligible observations for shadow inference", "calibration": "separate scalar temperatures in calibration.json fitted on 2024", "data_path": "../data/psx_ohlcv.parquet"}
    (MODELS / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS forecasts (
      id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, horizon_sessions INTEGER NOT NULL,
      as_of TEXT NOT NULL, model_version TEXT NOT NULL, class_label TEXT NOT NULL,
      confidence REAL NOT NULL, probabilities_json TEXT NOT NULL, drivers_json TEXT NOT NULL,
      target_date TEXT, actual_return REAL, actual_class TEXT, settled_at TEXT,
      UNIQUE(symbol, horizon_sessions, as_of, model_version)
    );
    CREATE INDEX IF NOT EXISTS idx_forecast_lookup ON forecasts(symbol, as_of DESC, horizon_sessions);
    """)


def infer(symbols: list[str] | None = None, as_of: str | None = None) -> None:
    df = build_frame()
    asof = pd.Timestamp(as_of).normalize() if as_of else df.date.max()
    symbols = [s.upper() for s in symbols] if symbols else sorted(df.symbol.unique())
    slice_df = df.loc[(df.date == asof) & df.symbol.isin(symbols) & df.clean_feature_window].dropna(subset=FEATURES)
    if slice_df.empty:
        raise RuntimeError(f"No eligible feature rows for {symbols} at as_of={asof.date()}")
    conn = sqlite3.connect(LEDGER)
    init_db(conn)
    manifest = json.loads((MODELS / "manifest.json").read_text(encoding="utf-8"))
    version = manifest["model_version"]
    temperatures = json.loads((MODELS / "calibration.json").read_text(encoding="utf-8"))["temperatures"]
    for h in HORIZONS:
        model = XGBClassifier()
        model.load_model(str(MODELS / f"xgb_{h}d.json"))
        probs = apply_temperature(model.predict_proba(slice_df[FEATURES]), float(temperatures[str(h)]))
        # XGBoost native additive feature contributions on the predicted class margin.
        contrib = model.get_booster().predict(__import__("xgboost").DMatrix(slice_df[FEATURES], feature_names=FEATURES), pred_contribs=True)
        contrib = np.asarray(contrib)
        for ix, (_, row) in enumerate(slice_df.iterrows()):
            predicted = int(np.argmax(probs[ix]))
            # Multiclass XGBoost yields [row, class, feature+base]; support documented shape.
            local = contrib[ix, predicted, :-1] if contrib.ndim == 3 else contrib[ix, :-1]
            top = np.argsort(np.abs(local))[::-1][:3]
            drivers = []
            for j in top:
                feature = FEATURES[int(j)]
                direction = "increases" if local[j] > 0 else "decreases"
                drivers.append({"feature": feature, "value": float(row[feature]), "effect": direction, "contribution": float(local[j])})
            target_date = df.loc[(df.symbol == row.symbol) & (df.date > asof), "date"].head(h)
            target = str(target_date.iloc[-1].date()) if len(target_date) == h else None
            conn.execute("INSERT OR IGNORE INTO forecasts(symbol,horizon_sessions,as_of,model_version,class_label,confidence,probabilities_json,drivers_json,target_date) VALUES(?,?,?,?,?,?,?,?,?)", (row.symbol, h, asof.date().isoformat(), version, CLASSES[predicted], float(probs[ix, predicted]), json.dumps({c: float(probs[ix, i]) for i, c in enumerate(CLASSES)}), json.dumps(drivers), target))
    conn.commit()
    rows = conn.execute("SELECT symbol,horizon_sessions,class_label,confidence,as_of,model_version FROM forecasts WHERE as_of=? ORDER BY symbol,horizon_sessions", (asof.date().isoformat(),)).fetchall()
    conn.close()
    output = [{"symbol": r[0], "horizon_sessions": r[1], "class_label": r[2], "confidence": r[3], "as_of": r[4], "model_version": r[5]} for r in rows]
    (REPORTS / "latest_forecasts.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    LOG.info("Stored %s horizon forecasts at %s", len(rows), asof.date())


def settle() -> None:
    df = build_frame()
    conn = sqlite3.connect(LEDGER)
    init_db(conn)
    rows = conn.execute("SELECT id,symbol,horizon_sessions,as_of FROM forecasts WHERE settled_at IS NULL").fetchall()
    updates = 0
    lookup = df.set_index(["symbol", "date"])
    for rid, symbol, h, asof in rows:
        dates = df.loc[(df.symbol == symbol) & (df.date > pd.Timestamp(asof)), "date"].head(h)
        if len(dates) != h:
            continue
        end = dates.iloc[-1]
        try:
            start_px = float(lookup.loc[(symbol, pd.Timestamp(asof)), "close"])
            end_px = float(lookup.loc[(symbol, end), "close"])
        except KeyError:
            continue
        forward = end_px / start_px - 1
        vol = float(lookup.loc[(symbol, pd.Timestamp(asof)), "vol_20"])
        band = 0.5 * vol * np.sqrt(h)
        actual = "bearish" if forward < -band else "bullish" if forward > band else "neutral"
        conn.execute("UPDATE forecasts SET actual_return=?,actual_class=?,settled_at=? WHERE id=?", (forward, actual, datetime.now(timezone.utc).isoformat(), rid))
        updates += 1
    conn.commit()
    conn.close()
    LOG.info("Settled %s forecasts", updates)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "evaluate", "train", "forecast", "settle"])
    parser.add_argument("--symbols", help="Comma-separated symbols for forecast")
    parser.add_argument("--as-of", help="Forecast date YYYY-MM-DD; defaults to last data date")
    args = parser.parse_args()
    if args.command == "fetch":
        fetch()
    elif args.command == "evaluate":
        evaluate()
    elif args.command == "train":
        train()
    elif args.command == "forecast":
        infer(args.symbols.split(",") if args.symbols else None, args.as_of)
    elif args.command == "settle":
        settle()


if __name__ == "__main__":
    main()
