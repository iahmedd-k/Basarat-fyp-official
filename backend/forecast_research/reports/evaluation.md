# Forecast model evaluation

Version: `psx-volband-xgb-v1`  
Train through: 2024-12-31  
Calibration: 2025-01-01 through 2025-12-31  
Historical test: 2026-01-01 onward

Macro-F1 and balanced accuracy are the primary metrics. Multiclass probabilities are temperature-scaled using the separate 2025 calibration period. Majority-class probabilities provide the baseline. Per-class precision/recall and confusion matrices are in `evaluation.json`.

| Horizon | Train n | Cal n | Test n | XGB macro-F1 | Majority macro-F1 | XGB balanced accuracy | Majority balanced accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1d | 92871 | 23337 | 17200 | 0.3500 | 0.2127 | 0.3816 | 0.3333 |
| 3d | 92245 | 23083 | 17167 | 0.3335 | 0.2060 | 0.3705 | 0.3333 |
| 7d | 91028 | 22584 | 17103 | 0.3443 | 0.2103 | 0.3642 | 0.3333 |

Rows: 161271; symbols: 103; flagged anomaly/jump rows: 1190.

## Limitations

The holdout period has appeared in prior repository research, so it is not a virgin holdout. Raw PSX OHLCV lacks verified corporate-action adjusted total returns and historic constituents. Reported classification metrics do not establish a profitable strategy, calibrated confidence, or future performance. Use shadow forecasts and collect forward outcomes before considering integration.
