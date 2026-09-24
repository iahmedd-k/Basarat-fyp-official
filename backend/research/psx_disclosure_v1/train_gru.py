"""Train isolated stationary-input GRU candidates for PSX disclosure research."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, classification_report,
                             confusion_matrix, f1_score, log_loss)
from sklearn.preprocessing import StandardScaler
import tensorflow as tf
from tensorflow.keras import callbacks, layers, models, optimizers

import common

HERE = Path(__file__).resolve().parent
OUT = HERE / "models" / "gru"
LOG = logging.getLogger("psx_disclosure_v1.gru")


class WindowDataset(tf.keras.utils.PyDataset):
    """Lazy sequence batches; avoids materializing all 45 x feature windows."""
    def __init__(self, matrix: np.ndarray, endpoints: list[tuple[int, int, int, float]],
                 batch_size: int = 128, training: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.matrix = matrix
        self.endpoints = endpoints
        self.batch_size = batch_size
        self.training = training
        self.order = np.arange(len(endpoints))
        self.indices = pd.DatetimeIndex([])
        if training:
            np.random.shuffle(self.order)

    def __len__(self):
        return int(np.ceil(len(self.order) / self.batch_size))

    def __getitem__(self, batch_index: int):
        ix = self.order[batch_index*self.batch_size:(batch_index+1)*self.batch_size]
        x = np.empty((len(ix), common.SEQUENCE_LENGTH, self.matrix.shape[1]), dtype=np.float32)
        y = np.empty(len(ix), dtype=np.int32)
        w = np.empty(len(ix), dtype=np.float32)
        for j, pos in enumerate(ix):
            start, end, label, weight = self.endpoints[pos]
            x[j] = self.matrix[start:end+1]
            y[j] = label
            w[j] = weight
        return (x, y, w) if self.training else (x, y)

    def on_epoch_end(self):
        if self.training:
            np.random.shuffle(self.order)


def _model(input_shape: tuple[int, int]) -> tf.keras.Model:
    inp = layers.Input(shape=input_shape, name="stationary_daily_sequence")
    x = layers.SpatialDropout1D(0.10)(inp)
    x = layers.Conv1D(filters=64, kernel_size=3, padding="same", activation="relu")(x)
    x = layers.LayerNormalization()(x)
    x = layers.Bidirectional(layers.GRU(64, return_sequences=True, dropout=0.15))(x)
    x = layers.LayerNormalization()(x)
    x = layers.Bidirectional(layers.GRU(32, return_sequences=True, dropout=0.15))(x)
    x = layers.LayerNormalization()(x)

    # Temporal Attention Pooling
    score = layers.Dense(1, activation="tanh")(x)
    weights = layers.Softmax(axis=1)(score)
    context = layers.Multiply()([x, weights])
    pooled = layers.Lambda(lambda z: tf.reduce_sum(z, axis=1))(context)

    dense = layers.Dense(32, activation="relu")(pooled)
    dense = layers.Dropout(0.20)(dense)
    dense = layers.Dense(16, activation="relu")(dense)
    dense = layers.Dropout(0.10)(dense)
    out = layers.Dense(1, activation="sigmoid", name="up_probability")(dense)
    model = models.Model(inp, out, name="psx_directional_attention_bigru")
    model.compile(optimizer=optimizers.Adam(learning_rate=4e-4),
                  loss="binary_crossentropy", metrics=["accuracy"])
    return model


def _collect_endpoints(df: pd.DataFrame) -> dict[str, list]:
    endpoints: dict[str, list] = {"train": [], "validation": [], "test": []}
    y = df.target_direction.to_numpy(dtype=float)
    dts = pd.to_datetime(df.date).to_numpy()
    split = df.split.to_numpy()
    counts = df.groupby("date").date.transform("size").to_numpy(dtype=float)
    weights = 1.0 / np.maximum(counts, 1)
    weights *= len(weights) / weights.sum()
    for _, group in df.groupby("symbol", sort=False):
        rows = group.index.to_numpy()
        for p in range(common.SEQUENCE_LENGTH - 1, len(rows)):
            start, end = int(rows[p-common.SEQUENCE_LENGTH+1]), int(rows[p])
            if not np.isfinite(y[end]) or df.iloc[end].volume <= 0:
                continue
            if (pd.Timestamp(dts[end]) - pd.Timestamp(dts[start])).days > common.MAX_SEQUENCE_CALENDAR_DAYS:
                continue
            part = split[end]
            if part in endpoints:
                endpoints[part].append((start, end, int(y[end]), float(weights[end])))
    return endpoints


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


def _eval(model: tf.keras.Model, dataset: WindowDataset, data: pd.DataFrame, endpoints: list) -> dict:
    probs = []
    labels = []
    for start in range(0, len(endpoints), 256):
        batch = endpoints[start:start+256]
        xb = np.stack([dataset.matrix[a:b+1] for a,b,_,_ in batch]).astype(np.float32)
        probs.append(model.predict(xb, verbose=0))
        labels.extend(y for _,_,y,_ in batch)
    p = np.concatenate(probs, axis=0).flatten()
    y = np.asarray(labels, dtype=int)
    preds = (p >= 0.5).astype(int)
    endpoint_rows = [end for _,end,_,_ in endpoints]
    frame = data.iloc[endpoint_rows].reset_index(drop=True)
    report = {
        "rows": int(len(y)),
        "directional_accuracy_all_samples": float(accuracy_score(y, preds)),
        "balanced_accuracy": float(balanced_accuracy_score(y, preds)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "brier_score": float(np.mean((p - y) ** 2)),
        "classification_report": classification_report(y, preds, labels=[0, 1],
            target_names=["down", "up"], output_dict=True, zero_division=0),
        "rejection_decision_layer": _rejection_metrics(y, p, frame),
    }
    # Rank metrics using P(UP) as cross-sectional alpha score
    d = frame[["date", "target_excess_return"]].copy()
    d["score"] = p
    ics, spreads, long_only = [], [], []
    for _, g in d.groupby("date"):
        if len(g) < 5 or g.score.nunique() < 2: continue
        ic = g.score.corr(g.target_excess_return, method="spearman")
        if pd.notna(ic): ics.append(float(ic))
        k = max(1, int(np.ceil(len(g)*0.2)))
        s = g.sort_values("score")
        spreads.append(float(s.tail(k).target_excess_return.mean()-s.head(k).target_excess_return.mean()))
        long_only.append(float(s.tail(k).target_excess_return.mean()))
    report.update({
        "mean_daily_spearman_ic": float(np.mean(ics)) if ics else None,
        "median_daily_spearman_ic": float(np.median(ics)) if ics else None,
        "mean_top_minus_bottom_20pct_excess_return": float(np.mean(spreads)) if spreads else None,
        "mean_top_20pct_excess_return": float(np.mean(long_only)) if long_only else None,
        "dates_evaluated": len(ics),
    })
    return report


def _fit_variant(data: pd.DataFrame, variant: str, feature_names: list[str]) -> dict:
    data = data.sort_values(["symbol","date"]).reset_index(drop=True)
    train_rows = (data.split == "train")
    medians = data.loc[train_rows, feature_names].median()
    medians = medians.replace([np.inf,-np.inf],np.nan).fillna(0.0)
    imputed = data[feature_names].replace([np.inf,-np.inf],np.nan).fillna(medians).astype(np.float32)
    scaler = StandardScaler()
    scaler.fit(imputed.loc[train_rows].to_numpy())
    matrix = scaler.transform(imputed.to_numpy()).astype(np.float32)
    endpoints = _collect_endpoints(data)
    if min(map(len,endpoints.values())) == 0:
        raise ValueError(f"No GRU endpoints for one or more splits: { {k:len(v) for k,v in endpoints.items()} }")
    ds_train = WindowDataset(matrix,endpoints["train"],batch_size=128,training=True)
    ds_val = WindowDataset(matrix,endpoints["validation"],batch_size=256,training=False)
    ds_test = WindowDataset(matrix,endpoints["test"],batch_size=256,training=False)

    model = _model((common.SEQUENCE_LENGTH,len(feature_names)))
    path = OUT / variant
    path.mkdir(parents=True,exist_ok=True)
    cb = [callbacks.EarlyStopping(monitor="val_loss",patience=6,restore_best_weights=True),
          callbacks.ReduceLROnPlateau(monitor="val_loss",factor=0.5,patience=3,min_lr=1e-5),
          callbacks.ModelCheckpoint(str(path/"best.weights.h5"),monitor="val_loss",save_best_only=True,save_weights_only=True)]
    history = model.fit(ds_train,validation_data=ds_val,epochs=60,callbacks=cb,verbose=2)
    model_path = path/"model.keras"
    model.save(model_path)
    joblib.dump(scaler,path/"scaler.joblib")
    (path/"train_medians.json").write_text(json.dumps(medians.to_dict(),indent=2,default=float),encoding="utf-8")
    (path/"feature_names.json").write_text(json.dumps(feature_names,indent=2),encoding="utf-8")
    metrics = {
        "train": _eval(model,WindowDataset(matrix,endpoints["train"],training=False),data,endpoints["train"]),
        "validation": _eval(model,ds_val,data,endpoints["validation"]),
        "sealed_test": _eval(model,ds_test,data,endpoints["test"]),
        "epochs_run": len(history.history.get("loss",[])),
        "best_validation_loss": float(min(history.history.get("val_loss",[float("nan")]))),
        "sequence_length_observations": common.SEQUENCE_LENGTH,
        "max_sequence_span_calendar_days": common.MAX_SEQUENCE_CALENDAR_DAYS,
        "feature_count":len(feature_names),"features":feature_names,
    }
    (path/"metrics.json").write_text(json.dumps(metrics,indent=2,default=float),encoding="utf-8")
    digest=hashlib.sha256(model_path.read_bytes()).hexdigest()
    (path/"manifest.json").write_text(json.dumps({
        "model":"bidirectional_gru_directional_binary","variant":variant,
        "target_semantics":common.DIRECTION_NAMES,"horizon_sessions":common.HORIZON_SESSIONS,
        "model_sha256":digest,"metrics_file":"metrics.json",
    },indent=2),encoding="utf-8")
    return metrics


def train(rebuild: bool=False,fetch: bool=False,years:int=8,allow_price_only:bool=False)->dict:
    data,meta=common.get_dataset(rebuild,fetch,years,allow_price_only)
    data=data[data.target_direction.notna() & (data.volume>0)].copy()
    results={}
    for variant,features in [("baseline",common.STATIONARY_CORE),("event_augmented",common.GRU_FEATURES)]:
        LOG.info("Training %s GRU with %d features",variant,len(features))
        results[variant]=_fit_variant(data,variant,features)
    summary={"target":meta["target"],"event_data":meta["event_data"],
             "baseline_test":results["baseline"]["sealed_test"],
             "event_augmented_test":results["event_augmented"]["sealed_test"],
             "interpretation":"Compare variants only on the same eligible endpoints. Test set is sealed; do not tune on these metrics."}
    (OUT/"comparison.json").write_text(json.dumps(summary,indent=2,default=float),encoding="utf-8")
    return summary


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    common.add_cli_args(parser)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    print(json.dumps(train(args.rebuild,args.fetch,args.years,args.allow_price_only),indent=2,default=float))


if __name__=="__main__":
    main()
