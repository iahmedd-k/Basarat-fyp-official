"""
Training pipeline for GRU-v2 deep sequence model on stationary PSX features.
Features: 36 scale-invariant technical, breadth, and volatility features over 45-day sequences.
Target: 5-day forward return with volatility-adaptive & fixed class targets.
"""

from pathlib import Path
import json
import logging
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
import tensorflow as tf
from tensorflow.keras import layers, models, callbacks, optimizers

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
log = logging.getLogger("train_gru_v2")

ROOT_DIR = Path(__file__).resolve().parents[3]
FEATURES_PARQUET = ROOT_DIR / "data" / "processed_v2" / "features_v2.parquet"
METADATA_JSON = ROOT_DIR / "data" / "processed_v2" / "v2_features_metadata.json"
MODELS_V2_DIR = ROOT_DIR / "models" / "final" / "final_v2"

SEQUENCE_LENGTH = 45
SPLIT_TRAIN_DATE = "2025-01-01"
SPLIT_VAL_DATE = "2025-09-01"


class SequenceDataGenerator(tf.keras.utils.PyDataset):
    def __init__(self, feat_matrix, idx_list, batch_size=128, sample_weights=None, shuffle=True, **kwargs):
        super().__init__(**kwargs)
        self.feat_matrix = feat_matrix
        self.idx_list = idx_list
        self.batch_size = batch_size
        self.sample_weights = sample_weights
        self.shuffle = shuffle
        self.indices = np.arange(len(idx_list))
        if self.shuffle:
            np.random.shuffle(self.indices)

    def __len__(self):
        return int(np.ceil(len(self.idx_list) / self.batch_size))

    def __getitem__(self, idx):
        batch_idx = self.indices[idx * self.batch_size : (idx + 1) * self.batch_size]
        batch_len = len(batch_idx)
        X = np.empty((batch_len, SEQUENCE_LENGTH, self.feat_matrix.shape[1]), dtype=np.float32)
        y = np.empty(batch_len, dtype=np.int32)

        for k, b_i in enumerate(batch_idx):
            s, e, lbl = self.idx_list[b_i]
            X[k] = self.feat_matrix[s : e + 1]
            y[k] = int(lbl)

        if self.sample_weights is not None:
            w = self.sample_weights[batch_idx]
            return X, y, w
        return X, y

    def on_epoch_end(self):
        if self.shuffle:
            np.random.shuffle(self.indices)


def load_and_prepare_sequences():
    log.info("Loading v2 features from %s", FEATURES_PARQUET)
    with open(METADATA_JSON, "r") as f:
        meta = json.load(f)
    feature_cols = meta["gru_features"]
    log.info("GRU v2 feature count: %d", len(feature_cols))

    needed_cols = ["symbol", "date", "target_fixed_class"] + feature_cols
    df = pd.read_parquet(FEATURES_PARQUET, columns=needed_cols)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # Split masks
    train_mask = df["date"] < SPLIT_TRAIN_DATE
    val_mask = (df["date"] >= SPLIT_TRAIN_DATE) & (df["date"] < SPLIT_VAL_DATE)
    test_mask = df["date"] >= SPLIT_VAL_DATE

    log.info("Date splits: Train < %s, Val %s to %s, Test >= %s",
             SPLIT_TRAIN_DATE, SPLIT_TRAIN_DATE, SPLIT_VAL_DATE, SPLIT_VAL_DATE)

    # Imputation medians on Train strictly
    train_medians = df.loc[train_mask, feature_cols].median().to_dict()
    for col in feature_cols:
        df[col] = df[col].fillna(train_medians[col]).astype(np.float32)

    # Fit scaler strictly on Train
    scaler = StandardScaler()
    scaler.fit(df.loc[train_mask, feature_cols].values)

    # Scale feature matrix directly
    feat_matrix = scaler.transform(df[feature_cols].values).astype(np.float32)
    labels_arr = df["target_fixed_class"].values.astype(np.int32)
    dates_arr = df["date"].values

    # Efficient Index-based Sequence Slicing
    log.info("Collecting sequence indices per symbol...")
    t_train = np.datetime64(SPLIT_TRAIN_DATE)
    t_val = np.datetime64(SPLIT_VAL_DATE)

    train_indices = []
    val_indices = []
    test_indices = []

    for sym, group in df.groupby("symbol"):
        indices = group.index.values
        n_rows = len(indices)
        if n_rows < SEQUENCE_LENGTH + 5:
            continue

        for i in range(SEQUENCE_LENGTH - 1, n_rows - 5):
            idx_end = indices[i]
            idx_start = indices[i - SEQUENCE_LENGTH + 1]
            dt = dates_arr[idx_end]
            lbl = labels_arr[idx_end]

            if dt < t_train:
                train_indices.append((idx_start, idx_end, lbl))
            elif dt < t_val:
                val_indices.append((idx_start, idx_end, lbl))
            else:
                test_indices.append((idx_start, idx_end, lbl))

    log.info("Index count: Train=%d, Val=%d, Test=%d", len(train_indices), len(val_indices), len(test_indices))

    y_train_arr = np.array([lbl for _, _, lbl in train_indices], dtype=np.int32)
    y_val_arr = np.array([lbl for _, _, lbl in val_indices], dtype=np.int32)
    sample_weights_train = compute_sample_weight("balanced", y_train_arr)
    sample_weights_val = compute_sample_weight("balanced", y_val_arr)

    gen_train = SequenceDataGenerator(feat_matrix, train_indices, batch_size=128, sample_weights=sample_weights_train, shuffle=True)
    gen_val = SequenceDataGenerator(feat_matrix, val_indices, batch_size=128, sample_weights=sample_weights_val, shuffle=False)
    gen_test = SequenceDataGenerator(feat_matrix, test_indices, batch_size=256, shuffle=False)

    return gen_train, gen_val, gen_test, scaler, train_medians, feature_cols


def build_gru_v2_model(input_shape):
    inputs = layers.Input(shape=input_shape)
    x = layers.SpatialDropout1D(0.10)(inputs)
    x = layers.Bidirectional(layers.GRU(48, return_sequences=True))(x)
    x = layers.LayerNormalization()(x)
    x = layers.GRU(48, return_sequences=False)(x)
    x = layers.Dropout(0.20)(x)
    x = layers.Dense(32, activation="relu")(x)
    x = layers.Dropout(0.15)(x)
    outputs = layers.Dense(3, activation="softmax")(x)

    model = models.Model(inputs=inputs, outputs=outputs, name="gru_v2_model")
    opt = optimizers.Adam(learning_rate=0.001)
    model.compile(
        optimizer=opt,
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"]
    )
    return model


def train_and_export():
    gen_train, gen_val, gen_test, scaler, medians, feature_cols = load_and_prepare_sequences()

    model = build_gru_v2_model(input_shape=(SEQUENCE_LENGTH, len(feature_cols)))
    model.summary(print_fn=log.info)

    MODELS_V2_DIR.mkdir(parents=True, exist_ok=True)
    best_weights_path = MODELS_V2_DIR / "gru_best_weights.weights.h5"

    cbs = [
        callbacks.EarlyStopping(monitor="val_loss", patience=4, restore_best_weights=True, verbose=1),
        callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5, verbose=1),
        callbacks.ModelCheckpoint(filepath=str(best_weights_path), monitor="val_loss", save_best_only=True, save_weights_only=True, verbose=1)
    ]

    log.info("Starting GRU-v2 model training using on-the-fly batch generator...")
    history = model.fit(
        gen_train,
        validation_data=gen_val,
        epochs=5,
        callbacks=cbs,
        verbose=1
    )

    # Save final artifacts to models/final/final_v2/
    model_export_path = MODELS_V2_DIR / "gru_model.keras"
    model.save(model_export_path)
    joblib.dump(scaler, MODELS_V2_DIR / "gru_scaler.pkl")

    with open(MODELS_V2_DIR / "gru_train_medians.json", "w") as f:
        json.dump(medians, f, indent=2)
    with open(MODELS_V2_DIR / "gru_features.json", "w") as f:
        json.dump(feature_cols, f, indent=2)

    log.info("Successfully saved all GRU-v2 artifacts to %s", MODELS_V2_DIR)
    return model


if __name__ == "__main__":
    train_and_export()
