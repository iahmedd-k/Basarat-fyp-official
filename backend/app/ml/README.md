# Machine Learning Package

The ML code lives under `app/ml`; persisted production artifacts live separately under `models/production`. Keep these distinct from `app/models`, which contains SQLAlchemy database models.

## Package map

| Directory | Purpose |
|---|---|
| `serving/` | Production artifact loading, inference, forecast persistence, and evaluation utilities |
| `v3/` | Current cross-sectional feature engineering and multi-horizon training pipeline |
| `v2/` | Previous versioned feature engineering and training code |
| `training/` | GRU training, evaluation, and experiment utilities |
| `training_xgb/` | XGBoost training, feature preparation, and evaluation utilities |

## Production model lifecycle

- The active model bundle is stored in [`../../models/production/v3/`](../../models/production/v3/).
- `serving/model_loader.py` loads that bundle at application startup.
- The current multi-horizon trainer in `v3/train_all_horizons.py` writes its artifacts to the same versioned production directory.
- Historical or experimental artifacts should not be mixed into the active bundle; keep them under an appropriately named archive or experiment directory.

Run the main versioned trainer from the backend directory with:

```powershell
python -m app.ml.v3.train_all_horizons
```
