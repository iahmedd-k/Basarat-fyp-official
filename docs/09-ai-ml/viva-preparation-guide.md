# Basarat ML/DL Viva Preparation Guide

**Purpose:** A plain-language, project-specific study guide for explaining the machine-learning, deep-learning, NLP, and AI-related parts of Basarat in a viva.  
**Scope:** Based on the code, saved artifacts, configuration, and ML documentation in this repository as inspected on 4 October 2026.

> **How to use this guide:** Learn the short answers first, then use the follow-up details to handle examiner questions. Be clear about the difference between what the documents claim, what the runtime code does, and what still needs verification. This is a research prototype for decision support, not a promise of investment returns.

## 1. Project answer in one minute

**Q: What does the ML part of Basarat do?**  
**A:** Basarat is a PSX stock-analysis application. Its forecasting service loads a recurrent neural network called an Attention-BiGRU and an XGBoost classifier. It prepares market features, obtains each model's bullish/bearish probabilities, combines them, and can mark an unclear result as neutral or uncertain. The project also has a separate financial-news sentiment service using FinBERT through the Hugging Face Inference API when configured, with a keyword heuristic as a fallback. A separate Groq-hosted language model powers the chat assistant. Recommendations combine the forecast with deterministic technical, fundamental, and sentiment signals. These are separate components: the chat LLM is not the stock forecaster, and FinBERT sentiment is not automatically one of the forecaster's learned inputs.

**Q: What is the main forecasting task?**  
**A:** The newer `final_v3` model package is documented as a two-class, five-trading-day, cross-sectional direction task. It estimates whether a stock will be relatively stronger or weaker than a reference market/universe. The package manifest says `down = 0` and `up = 1`; the detailed feature-engineering source also contains a top-30% Buy, bottom-30% Avoid, middle-40% Neutral target, plus a binary target. This distinction matters: the exact label definition for the deployed binary artifacts must be confirmed from the canonical training run before claiming one precise target formulation.

## 2. What AI/ML-related components are in the project?

| Component | What it does | Is it a trained model? | Where it is used |
|---|---|---|---|
| Attention-BiGRU | Reads a sequence of daily market features and returns an up probability | Yes; TensorFlow/Keras | Forecast inference and the documented final model package |
| XGBoost | Uses a tabular feature row to estimate direction | Yes; XGBoost | Forecast inference and recommendation ML component |
| Recommendation technical signal | Turns indicators such as RSI, MACD, Bollinger Bands, and moving-average crosses into a hand-built score | No; deterministic rules | Recommendation ranking |
| Recommendation fundamental signal | Applies hand-coded valuation/momentum heuristics to available market/fundamental data | No; deterministic rules | Recommendation ranking |
| Financial-news sentiment | Classifies news text as positive/neutral/negative and aggregates scores | Pretrained FinBERT through a remote API if configured; otherwise a local keyword heuristic | Sentiment API and optional recommendation input |
| Stock chat assistant | Generates natural-language responses using a configured hosted model, with app context and safety logic | Yes, but hosted and not trained by this project | Assistant/chat interface; Groq API client |
| Technical indicators and risk statistics | Computes market indicators and portfolio/risk summaries | No; mathematical/statistical calculations | Features, recommendations, and risk services |

The project does **not** define a locally trained transformer, computer-vision model, or reinforcement-learning agent in the inspected application code. Avoid naming one in a viva unless a separate experiment or artifact outside this repository is actually part of your work.

## 3. Forecasting pipeline: explain it from data to output

### 3.1 Input data

The forecast feature pipeline starts with daily PSX OHLCV data: **open, high, low, close, and volume**. It derives technical indicators and joins macroeconomic series such as PKR/USD and SBP policy rate. The newer documented research pipeline additionally describes financial statement fundamentals and PSX company-disclosure events. The features include:

- Price/trend: returns, distance from moving averages, EMA/SMA crosses, VWAP distance, and distance from a 52-week high.
- Momentum: RSI, MACD, stochastic oscillator, MFI, and CCI.
- Volatility/range: ATR, rolling volatility, Bollinger/Keltner positions, and high-low/open-close ranges.
- Volume/liquidity: volume z-scores, relative volume, turnover-related measures, and Amihud illiquidity.
- Relative context: index/market and sector returns/ranks.
- Macro/event/fundamental inputs in the documented newer model: interest-rate and FX changes, disclosure-event flags/timing, and selected dividend/EPS/fundamental ratios.

**Viva wording:** “We transform historical market observations into numerical features. Indicators summarize trend, momentum, volatility, liquidity, and market context; they are inputs, not guaranteed causes of future returns.”

### 3.2 Labels and prediction horizon

The older three-class experiments label the forward five-day return as bullish, bearish, or sideways, using a threshold around ±1%. The experiment log says a neutral-class collapse made this formulation unhelpful in real-stock evaluation.

The newer research code computes a forward five-day stock return, subtracts an index return, and ranks excess returns across stocks on each date. It assigns the top 30% to Buy/outperform, bottom 30% to Avoid/underperform, and the middle 40% to Neutral. It also constructs a median-split binary target. The production manifest instead describes two classes, down/up, on a five-day horizon. Do not conflate the three-class training experiment with the binary deployed manifest.

**Q: What is a label?**  
**A:** It is the known answer used during training. For example, after the next five trading sessions have happened, a stock's observed return can be converted into an up/down or Buy/Avoid class.

**Q: What does “excess return” mean?**  
**A:** A stock's return minus a reference market return over the same period. It asks whether the stock did better or worse than that reference, not simply whether its price rose in absolute terms.

### 3.3 Train, validation, and test

The older GRU pipeline splits samples chronologically by the date at the end of each input window. Its default cutoffs are:

- Training: before 1 July 2024.
- Validation: 1 July 2024 through 30 June 2025.
- Test: from 1 July 2025 onwards.

This is preferable to random row splitting for time-series data because a random split can let future market regimes influence training while older observations appear in the test set.

**Q: Why have three sets?**  
**A:** Training fits the model parameters; validation helps select settings and stop training; the test set should estimate performance on data not used to make those choices.

**Q: What is data leakage?**  
**A:** Information that would not have been available at prediction time accidentally enters training or evaluation. Examples include calculating a feature from a future close, fitting a scaler on test data, or using a future announcement before its publication.

**Q: How does the project try to prevent leakage?**  
**A:** It has time-based splitting, a leakage-checking module, training-only scaler fitting in the older GRU pipeline, and backward as-of joins for macro data. The newer feature code uses rolling and lagged calculations, but the canonical production artifact lineage and publication-time correctness still need to be verified end-to-end.

### 3.4 The GRU and Attention-BiGRU

The older `build_model` function defines a simpler three-class GRU: a GRU with 64 units, dropout, a 32-unit dense layer, and a softmax output. The `final_v3` serving loader instead constructs a newer Attention-BiGRU with input shape documented as **45 timesteps × 79 features**:

1. Spatial dropout.
2. A one-dimensional convolution to learn local patterns across adjacent time steps.
3. Two bidirectional GRU layers that return a representation at each time step.
4. Temporal attention that assigns weights to time steps and sums the weighted representations.
5. Dense layers and a sigmoid output representing the up probability.

**Q: What is a GRU?**  
**A:** A Gated Recurrent Unit is a recurrent neural-network layer. Its gates help it retain useful information and discard less useful information as it processes a sequence. It is designed for ordered data such as daily market observations.

**Q: Why use 45 days?**  
**A:** The model receives a medium-term historical window. The experiment documentation reports that 45 days performed better than the 30- and 60-day candidates in the earlier 36-feature experiments. That experiment does not by itself prove 45 days is optimal for every future dataset.

**Q: Why bidirectional?**  
**A:** Within the already observed input window, a bidirectional GRU processes the sequence in both temporal directions. It can learn context from both earlier and later points inside that historical window. It must never see observations after the prediction date; “bidirectional” does not mean that future market data is allowed.

**Q: What does attention do here?**  
**A:** The network calculates a weight for each time step and combines the time-step representations into a context vector. It provides a learned way to emphasize parts of the input sequence. It is not automatically a human-readable explanation of why a stock will move.

**Q: Why sigmoid rather than softmax?**  
**A:** A single sigmoid output represents the probability-like score for one of two classes, here “up.” The other class can be represented as `1 - p_up`. Softmax is commonly used when a model outputs one score for each of multiple mutually exclusive classes.

### 3.5 XGBoost

XGBoost is a gradient-boosted decision-tree method. It adds trees iteratively, where later trees improve on errors made by the current ensemble. In this project it uses a tabular feature row, not a time sequence. The newer manifest lists 70 XGBoost features; the feature list contains price/technical, relative-performance, event, macro, and selected fundamental features.

The project’s older multi-class training defaults include 300 estimators, depth 6, learning rate 0.05, row subsampling 0.8, and column subsampling 0.8. The separate `v3` experiment code uses a more heavily regularized setup (for example depth 4 and `min_child_weight=100`). Do not claim those experiment hyperparameters are necessarily the exact settings of the saved production artifact.

**Q: Why XGBoost as well as a GRU?**  
**A:** They represent the data differently. XGBoost handles nonlinear interactions in a fixed feature row; the GRU learns patterns across an ordered history. A combination may provide complementary information, but it only helps if both models and their outputs are validated correctly.

**Q: Does XGBoost need StandardScaler?**  
**A:** Usually not. Tree split decisions compare values to thresholds, so a monotonic rescaling normally does not require a standard scaler. The sequence network is more sensitive to input scales, so its inference path uses a saved scaler.

### 3.6 Ensembling and abstention

The runtime inference code can weight GRU and XGBoost probabilities according to the requested horizon, then make a decision. Its current source has a 5-percentage-point near-tie rule and horizon weights of 65/35 for `1D`, 50/50 for `1W`, and 35/65 for `1M`. If one model is unavailable, the code can use the other. The API also labels a requested output date for 1D, 1W, or 1M.

**Q: What is an ensemble?**  
**A:** A method that combines predictions from multiple models. A soft-voting ensemble averages or weights probabilities; hard voting combines class decisions.

**Q: What does abstention/rejection mean?**  
**A:** The system declines to make an actionable directional call when its score is too close to the decision boundary. It trades prediction coverage for the possibility of higher accuracy among the smaller number of retained predictions.

**Q: Does a 60% score mean a 60% chance of profit?**  
**A:** No. It is a model output, not necessarily a calibrated probability of profit. The target is a label, and trading outcomes also depend on costs, execution, liquidity, and market changes. Calibration and realistic strategy testing are required before interpreting it as a true probability.

## 4. Separate NLP and recommendation components

### 4.1 FinBERT news sentiment

The source code sends article text to the Hugging Face Inference API for `ProsusAI/finbert` when an `HF_API_TOKEN` is configured. Its continuous score is:

`sentiment_score = P(positive) - P(negative)`

The score is between -1 and +1. Values at or above +0.15 are labeled positive, at or below -0.15 negative, and intermediate values neutral. If the API is unavailable or not configured, the service uses a locally coded financial keyword/phrase heuristic with a limited negation window. Scores can be aggregated over a recent period with exponential time decay (the synchronous task uses a 3-day half-life).

**Q: What is FinBERT?**  
**A:** A BERT-family language model adapted for financial text sentiment. This application uses it as an external pretrained inference service; the repository does not show this project fine-tuning FinBERT.

**Q: Is the keyword fallback equivalent to FinBERT?**  
**A:** No. It is a simpler, less context-sensitive backup. It matches selected financial words and phrases and attempts limited negation handling. It can miss sarcasm, context, company-specific meanings, and complex language.

**Q: Does FinBERT feed the stock-direction model?**  
**A:** The inspected production GRU/XGBoost feature lists do not contain a text-sentiment score. Sentiment is a separate service and may be used by the recommendation composite when available. Do not say the forecasting models are trained on article text unless a new training feature pipeline demonstrates that.

### 4.2 Recommendation score

The recommendation engine combines four possible normalized signals: the ML forecast, technical rules, a fundamental heuristic, and news sentiment. It renormalizes weights over available components. The documented defaults are 30% ML, 25% technical, 25% fundamental, and 20% sentiment; user preferences may supply weights. A composite above +0.15 yields BUY, below -0.15 SELL, otherwise HOLD.

This is a **rules-based score**, not a separate learned model, a calibrated expected return, or personalized financial advice. The fundamental component is explicitly described in project notes as exploratory and relatively simple. ATR-derived target/stop bands are volatility distances, not predicted prices or execution guarantees.

**Q: What is the difference between forecast and recommendation?**  
**A:** Forecast is the ML service’s estimate of market direction. Recommendation is a separate layer that combines that signal with hand-built indicator, fundamental, and potentially sentiment scores to produce BUY/SELL/HOLD.

### 4.3 Groq-hosted chat assistant

The assistant calls a Groq-compatible chat-completions API. The configured model names are settings, not locally stored model artifacts; current defaults are `openai/gpt-oss-20b` and a configured Qwen fallback. The assistant adds application context, limits conversation history, and applies intent/prompt/output-safety checks. It is a generative language model component, not the forecaster, and its generated text should not be treated as ground truth.

## 5. What the checked results say—and do not say

### 5.1 `final_v3` artifact package and reported evaluation protocol

The `final_v3` package manifest calls the model `final_v3_institutional_ensemble`, gives it a five-trading-day (`5D`) horizon, and maps `down=0`, `up=1`. The saved metric files report separate train, validation, and sealed-test rows. Their split metadata gives these date ranges:

| Split | Dates in artifact metadata | XGBoost rows | Attention-BiGRU rows |
|---|---|---:|---:|
| Train | 2020-01-01 to 2024-09-09 | 104,963 | 94,826 |
| Validation | 2024-09-18 to 2025-05-12 | 16,605 | 16,560 |
| Sealed test | 2025-05-20 to 2026-09-11 | 33,730 | 33,686 |

The validation and sealed test each report 162 and 328 evaluated dates, respectively. The training metrics report 1,159 dates for XGBoost and 1,115 for BiGRU. Rows are stock/date observations, not unique companies. The date ranges show gaps between splits; the metric JSON does not, by itself, establish the precise reason for each gap or prove that all overlapping five-day label windows were embargoed.

**Q: What does “sealed test” mean?**
**A:** It means a set documented as held out for final evaluation. To trust that interpretation, we still need the exact training/threshold-selection lineage and to confirm the test set was not repeatedly used to choose models or thresholds.

The result tables below transcribe the saved `gru_metrics.json` and `xgb_metrics.json`. Accuracy, precision, recall, F1, IC, and return-spread values are percentages where shown with `%`; log loss and Brier score are shown as unitless values. “Top-minus-bottom 20% excess return” and “long-short alpha spread” are the values named in the artifact files; the files do not fully specify portfolio weighting, transaction costs, or execution assumptions, so do not describe these as net realized trading profit.

### 5.2 All-sample train, validation, and sealed-test metrics

| Model / split | Rows | Directional accuracy | Balanced accuracy | Macro F1 | Log loss | Brier | Mean daily Spearman IC | Median daily Spearman IC | Mean top-minus-bottom 20% excess return |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| XGBoost — train | 104,963 | 59.54% | 59.54% | 0.5954 | 0.67575 | 0.24136 | 0.2409 | 0.2533 | +2.564% |
| XGBoost — validation | 16,605 | 52.02% | 52.02% | 0.5196 | 0.69111 | 0.24898 | 0.0636 | 0.0465 | +0.489% |
| **XGBoost — sealed test** | **33,730** | **53.24%** | **53.24%** | **0.5324** | **0.69061** | **0.24873** | **0.0800** | **0.0856** | **+0.375%** |
| Attention-BiGRU — train | 94,826 | 53.77% | 53.77% | 0.5376 | 0.68806 | 0.24748 | 0.0932 | 0.0988 | +0.733% |
| Attention-BiGRU — validation | 16,560 | 52.05% | 52.05% | 0.5202 | 0.69188 | 0.24936 | 0.0329 | 0.0556 | -0.275% |
| **Attention-BiGRU — sealed test** | **33,686** | **51.34%** | **51.35%** | **0.5124** | **0.69305** | **0.24994** | **0.0438** | **0.0610** | **+0.354%** |

These are model-level results, not the accuracy of a combined ensemble on a separately tested live trading strategy. The metric files evaluate the components individually. The near-balanced up/down supports explain why accuracy and balanced accuracy are nearly the same.

**Sealed-test class report:**

| Model | Class | Precision | Recall | F1 | Support |
|---|---|---:|---:|---:|---:|
| XGBoost | Down | 53.18% | 53.75% | 53.46% | 16,855 |
| XGBoost | Up | 53.31% | 52.74% | 53.02% | 16,875 |
| Attention-BiGRU | Down | 51.19% | 56.01% | 53.49% | 16,827 |
| Attention-BiGRU | Up | 51.54% | 46.69% | 48.99% | 16,859 |

**Validation class report:**

| Model | Class | Precision | Recall | F1 | Support |
|---|---|---:|---:|---:|---:|
| XGBoost | Down | 52.18% | 48.58% | 50.31% | 8,304 |
| XGBoost | Up | 51.88% | 55.46% | 53.61% | 8,301 |
| Attention-BiGRU | Down | 52.15% | 49.48% | 50.78% | 8,278 |
| Attention-BiGRU | Up | 51.96% | 54.61% | 53.25% | 8,282 |

**Interpretation:** On this sealed sample, XGBoost is 1.90 percentage points more accurate than the BiGRU (53.24% vs 51.34%). The BiGRU has higher recall for Down than Up (56.01% vs 46.69%), so its overall accuracy alone hides a class-specific weakness. The accuracy results are modest; small gains above a roughly balanced binary baseline need uncertainty estimates, repeated/regime-aware evaluation, and cost-aware strategy tests before they support strong claims.

### 5.3 Confidence threshold, accuracy, and coverage

For a binary classifier, the artifact's rejection report evaluates confidence thresholds `τ`: retain a prediction only if the higher class probability reaches the selected threshold; otherwise count it as “no signal.” **Coverage is the fraction retained.** Higher selective accuracy is not a free improvement: fewer predictions are made. These are component-level results, not a combined-ensemble result.

**XGBoost — validation (16,605 rows):**

| Threshold τ | Accuracy on retained rows | Coverage | Signals / no signal | Reported long-short spread |
|---:|---:|---:|---:|---:|
| 0.50 | 52.02% | 100.00% | 16,605 / 0 | +0.197% |
| 0.52 | 53.16% | 64.55% | 10,718 / 5,887 | +0.266% |
| 0.54 | 55.43% | 35.13% | 5,833 / 10,772 | +0.712% |
| 0.55 | 56.55% | 23.44% | 3,892 / 12,713 | +0.883% |
| 0.56 | 58.41% | 14.97% | 2,486 / 14,119 | +1.239% |
| 0.58 | 58.12% | 4.60% | 764 / 15,841 | +1.283% |
| 0.60 | 59.49% | 1.17% | 195 / 16,410 | +1.220% |

**XGBoost — sealed test (33,730 rows):**

| Threshold τ | Accuracy on retained rows | Coverage | Signals / no signal | Reported long-short spread |
|---:|---:|---:|---:|---:|
| 0.50 | 53.24% | 100.00% | 33,730 / 0 | +0.250% |
| 0.52 | 54.41% | 68.98% | 23,268 / 10,462 | +0.350% |
| 0.54 | 54.95% | 40.55% | 13,679 / 20,051 | +0.424% |
| 0.55 | 55.30% | 29.01% | 9,784 / 23,946 | +0.358% |
| 0.56 | 55.37% | 20.06% | 6,765 / 26,965 | +0.427% |
| 0.58 | 56.44% | 8.15% | 2,750 / 30,980 | +0.668% |
| 0.60 | 59.70% | 2.57% | 866 / 32,864 | +1.643% |

**Attention-BiGRU — validation (16,560 rows):**

| Threshold τ | Accuracy on retained rows | Coverage | Signals / no signal | Reported long-short spread |
|---:|---:|---:|---:|---:|
| 0.50 | 52.05% | 100.00% | 16,560 / 0 | -0.118% |
| 0.52 | 53.00% | 44.16% | 7,313 / 9,247 | -0.284% |
| 0.54 | 55.06% | 19.38% | 3,209 / 13,351 | -0.556% |
| 0.55 | 56.15% | 13.25% | 2,194 / 14,366 | -0.155% |
| 0.56 | 59.29% | 8.68% | 1,437 / 15,123 | -0.206% |
| 0.58 | 61.11% | 3.91% | 648 / 15,912 | +1.335% |
| 0.60 | 58.06% | 1.87% | 310 / 16,250 | +1.985% |

**Attention-BiGRU — sealed test (33,686 rows):**

| Threshold τ | Accuracy on retained rows | Coverage | Signals / no signal | Reported long-short spread |
|---:|---:|---:|---:|---:|
| 0.50 | 51.34% | 100.00% | 33,686 / 0 | +0.103% |
| 0.52 | 52.48% | 23.44% | 7,896 / 25,790 | +0.210% |
| 0.54 | 51.26% | 7.87% | 2,651 / 31,035 | -0.543% |
| 0.55 | 52.37% | 4.76% | 1,604 / 32,082 | -0.402% |
| 0.56 | 50.30% | 2.92% | 984 / 32,702 | -0.604% |
| 0.58 | 38.95% | 1.07% | 362 / 33,324 | -3.102% |
| 0.60 | 47.58% | 0.37% | 124 / 33,562 | -2.188% |

**What this comparison tells us:** The XGBoost sealed-test selective accuracy rises from 53.24% at full coverage to 59.70% at 2.57% coverage. But the BiGRU's held-out threshold results are not monotonic: at `τ=0.58`, it retains only 1.07% and accuracy falls to 38.95%. Thus the documentation's headline “up to 65.22%” validation figure must not be quoted as sealed-test or all-sample performance. Choosing a threshold after looking at test performance would also contaminate the test set; select it on validation, freeze it, then evaluate once on test.

### 5.4 Evaluation checks and audit evidence

There are two different kinds of evidence in this repository. Do not present them as the same audit:

1. **`final_v3` saved component metrics:** the train/validation/sealed-test tables above, 328 sealed-test dates, classification reports, threshold curves, Brier/log-loss, and daily rank-IC/return-spread summaries. These are the direct metric-file evidence for the newer binary model package.
2. **`model-final-evaluation.md` audit:** this is explicitly for the older `final_v1` three-class candidate, not `final_v3`. It reports a separate real-stock walk-forward evaluation and ten integrity checks:

| Recorded audit check (`final_v1` report) | What it checked | Reported result |
|---|---|---|
| Feature warmup | Required 60-day indicators had enough prior rows | Minimum 693 rows available |
| Non-overlapping horizon | Predictions stepped by five trading days | 0 overlap violations in 5,875 predictions |
| Point-in-time features | Features/scalers did not use data after prediction date | Report says all features were `<= T` |
| Symbol encoding | Deterministic symbol IDs | Alphabetical deterministic mapping |
| Label integrity | Recomputed close-to-close `T+5` labels | 0 mismatches / 5,875 |
| Prediction schedule | Weekly dates not chosen using outcomes | Report says 61 uniform weekly dates across 106 date stamps |
| Metric recomputation | Independent recomputation matched stored reports | Report says 100% match |
| Confidence buckets | Accuracy by confidence band | 33.87% below 50%; 49.48% at/above 70% |
| Dataset sanity | Nulls, duplicates, probability sums | Report says 0 nulls/duplicates and sums within `1e-5` |
| Methodology comparison | Compared rolling offline vs walk-forward testing | Autocorrelation/sample-protocol differences documented |

The report's counts are retained as the report states them; for example, it gives 5,875 predictions and also describes 61 uniform weekly dates across 106 unique date stamps. Treat these as legacy audit claims, not independently re-run `final_v3` test results.

**`final_v1` real-stock results (separate, older protocol):** It reports 5,875 predictions across a broad 98-stock universe from 2025-07-01 to 2026-09-07, sampled every five trading days, with a three-class ±1% label. Broad-universe accuracy was 34.23%, macro F1 0.3398, weighted F1 0.3309, and balanced accuracy 37.84%. Core 15 liquid stocks had 29.44% accuracy, macro F1 0.2828, and balanced accuracy 34.69%. This must not be described as the binary `final_v3` score.

**Automated software tests present in the repository (separate from evaluation metrics):**

| Test case / behavior | What it checks | What it does not prove |
|---|---|---|
| Missing/NaN label handling | Invalid forward-return labels are rejected or dropped | Forecast accuracy |
| Explicit GRU feature-list validation | Feature names/order/count match a declared legacy contract | Parity with all 79 production artifact features |
| Class-weight computation | Weights are derived from training labels | That weighting improves unseen performance |
| Confidence and probability-gap helpers | Probability summary calculations | Calibration |
| Chronological split and target validation | Split dates and expected labels satisfy checks | Absence of every possible pipeline leak |
| Technical feature construction | Expected normalized and market-relative columns are calculated | Predictive value of those features |
| Comprehensive metric calculation | Expected evaluation metrics are produced | Correctness of the stored production metrics on independent data |
| Ensemble agreement logic | Agreement/reason handling for model outputs | Live ensemble performance |
| Reproducibility seed setup | Random seeds/configuration are set | Bit-for-bit reproducibility across hardware/software |
| XGBoost sample weights | Per-class sample weights are computed | Model quality after weighting |
| Missing inference feature behavior | Current GRU path's missing-feature handling (zero fill) | Correctness of the fallback or artifact-feature parity |
| Recommendation component behavior | Shared forecast use, available-weight renormalization, neutral ATR handling | That the recommendation score predicts profitable trades |
| Forecast API/history behavior | Endpoint response and history contract | Generalization or profitability |

These test names are present in `tests/unit/test_ml_fixes.py`, `tests/unit/test_recommendation_engine.py`, and `tests/api/test_forecast_api.py`. They are software behavior tests, not proof that every `final_v3` metric has been independently reproduced. This report update did not run the test suite.

**Q: What is the main message from the evaluation?**
**A:** “On the saved newer binary sealed test, XGBoost reached 53.24% all-sample accuracy and the BiGRU 51.34%, across about 33.7 thousand observations each. Thresholding XGBoost to 0.60 increased retained-sample accuracy to 59.70%, but coverage dropped to 2.57%. BiGRU did not show the same threshold behavior. The separate older three-class walk-forward report scored much lower, so the versions and evaluation protocols must not be mixed. No result establishes net profitability after trading costs.”

### 5.5 Metric terms to explain simply

| Metric | Easy explanation | Viva note |
|---|---|---|
| Accuracy | Fraction of all predictions that are correct | Can look good when one class dominates |
| Precision | Of predictions made for a class, how many were right? | Useful when false positive calls are costly |
| Recall | Of real examples of a class, how many did the model find? | Useful when missing a class is costly |
| F1 | Harmonic balance of precision and recall | Macro F1 gives each class equal weight |
| Balanced accuracy | Average recall over classes | Helps with class imbalance |
| Log loss | Penalizes wrong probability assignments, especially confident mistakes | Lower is better |
| Brier score | Mean squared error of probability estimates | Lower is better; can assess probability quality |
| Spearman rank IC | Rank correlation between model scores and outcomes | Measures ordering quality, not directly a trade return |
| Coverage | Portion of examples receiving an actionable signal after the gate | Must be reported with selective accuracy |
| Alpha spread | Return difference between selected long/short or ranked groups under a specified definition | Needs exact portfolio construction, costs, and dates |

**Q: What is the baseline for a balanced binary problem?**  
**A:** A naive random or constant prediction has about 50% accuracy only under a balanced setup and suitable assumptions. Always compare against a simple baseline using the same labels, data dates, and sample population. A 53% result alone does not prove profitability.

## 6. Viva-critical implementation caveats

The following are source-audit observations, not claims that the models cannot run. They are important questions to resolve before stating that the exact documented final model can be reproduced identically from the current repository.

1. **Feature-count mismatch:** The `final_v3` manifest claims 70 XGBoost features, but the checked `xgb_features.json` array and `xgb_metrics.json` each report 69; the GRU artifacts consistently report 79. The currently scheduled `run_features` path uses a versioned 36-feature GRU list. The inference helper fills missing GRU features with 0.0; XGBoost inference also has a 0.50 fallback for a missing value. This means exact feature parity depends on the deployed parquet and should be checked, not assumed.
2. **Model-generation mismatch:** The `v3` feature engineer and trainer write experiment-style outputs and their feature/label logic does not by itself reproduce every field in the checked 70-feature production list. The ordinary weekly candidate-retraining task builds the older three-class GRU/XGBoost candidates and stores them separately; it does not directly overwrite the final_v3 artifact directory. Weekly scheduling therefore should not be described as automatically retraining and deploying the current final_v3 binary models.
3. **Class mapping/label lineage:** The `final_v3` manifest says `down=0, up=1`. The separate checked v3 experiment script uses `buy=0, avoid=1` and a different target construction. Those names and class IDs must be tied to the exact saved artifact training run. Verify model class order and feature metadata before explaining the deployed probability as “up.”
4. **Threshold performance:** Documentation numbers come from different versions, splits, and threshold settings. The model recommendation review itself says not to call the thresholds decision-grade without a chronological point-in-time evaluation of the complete API rule, an untouched holdout, calibration checks, transaction costs, slippage, liquidity and market-impact constraints.
5. **Horizon labels versus API options:** The manifest says the trained target horizon is 5D, while the forecast API accepts 1D, 1W, and 1M. Runtime blending weights and output dates differ by requested horizon, but the manifest alone does not establish separate models trained for each horizon. Say this distinction explicitly.
6. **Probability calibration:** The inference docstring explicitly describes top-class probability as raw model probability when calibration is not active. Do not equate model confidence with real-world calibrated likelihood.
7. **Fundamental/news quality:** The recommendation review characterizes the fundamental screen as heuristic. External FinBERT API use also depends on token/service availability; the fallback is lexical, not a transformer.

**Strong viva answer if asked about these issues:**  
“The project has a newer final_v3 artifact package and a live inference path, but source inspection shows version drift between the documented artifact features and the scheduled legacy feature builder/training jobs. I would verify the exact training run, ordered feature list, class mapping, and inference inputs before claiming full reproducibility. The project’s own evaluation notes also require calibration and cost-aware walk-forward testing before calling the signals decision-grade.”

## 7. Common examiner questions and short answers

### Foundations

**Q: What is machine learning?**  
**A:** A way for a computer to learn patterns from examples and use those patterns to make predictions on new examples.

**Q: What is deep learning?**  
**A:** Machine learning based on neural networks with multiple layers. The GRU is the deep-learning model in the forecasting ensemble.

**Q: Is every AI feature in the app machine learning?**  
**A:** No. Technical indicators, thresholds, recommendation formulas, and risk calculations are deterministic math or rules. FinBERT, GRU, XGBoost, and the chat LLM are learned models.

**Q: What is supervised learning?**  
**A:** Training with examples that include both input features and a target label. Our forecast models learn from historical features paired with a later outcome label.

**Q: Is this classification or regression?**  
**A:** The documented active forecast is classification into direction classes. Returns may be used to construct the labels and evaluate rank/return spread, but the core model output is a class probability rather than a direct predicted price.

**Q: What is a feature?**  
**A:** A numeric input supplied to a model, such as a recent return, volatility, RSI, or event flag.

**Q: What is a parameter versus a hyperparameter?**  
**A:** Parameters are learned during training, such as neural weights. Hyperparameters are selected before/during training, such as GRU units, tree depth, learning rate, and dropout.

**Q: What is overfitting?**  
**A:** When a model learns accidental details of its training sample and performs worse on genuinely new periods.

**Q: What is regularization?**  
**A:** Techniques that limit unnecessary model complexity to reduce overfitting. Examples here include dropout in the neural net and tree depth/subsampling/regularization controls in XGBoost experiments.

### Data and evaluation

**Q: Why is time ordering essential in stock prediction?**  
**A:** Markets change over time, and future observations must not be used to predict earlier dates. A chronological test better imitates deployment.

**Q: Why not use only accuracy?**  
**A:** Accuracy hides class imbalance and error type. We should also report per-class precision/recall, macro F1, balanced accuracy, probability loss/calibration, signal coverage, and realistic strategy outcomes.

**Q: What is class imbalance?**  
**A:** One label occurs much more often than another. A model can then achieve apparently good accuracy by mostly predicting the common class.

**Q: What is a confusion matrix?**  
**A:** A table counting correct and incorrect predictions for each actual/predicted class. It reveals which classes are being confused.

**Q: What is a validation set versus a test set?**  
**A:** Validation helps choose models and thresholds. The test set should remain untouched until the choices are fixed and is used for final evaluation.

**Q: What is look-ahead bias?**  
**A:** A form of leakage where information from after the forecast timestamp influences a feature or decision.

**Q: What is an embargo/gap in time-series testing?**  
**A:** A buffer between training and validation/test periods to reduce leakage from labels whose forward-return windows overlap the boundary.

### Model details

**Q: What does the GRU's gate do intuitively?**  
**A:** It controls what information to keep from earlier steps, what to forget, and what new information to add.

**Q: What does dropout do?**  
**A:** During training it randomly disables some activations, discouraging the network from relying too heavily on a small set of pathways. It is normally disabled during inference.

**Q: What is a convolution doing before the GRU?**  
**A:** It learns short local patterns across nearby time steps before the recurrent layers process longer sequence context.

**Q: What is gradient boosting?**  
**A:** Building a sequence of weak learners, such as shallow trees, where each new learner helps correct errors from earlier learners.

**Q: What does learning rate mean in XGBoost?**  
**A:** It scales each new tree's contribution. A smaller value usually needs more trees but can make updates more gradual.

**Q: What is feature scaling, and why save the scaler?**  
**A:** Scaling puts numeric features on comparable ranges. The saved training scaler must be reused at inference; fitting a different scaler at serving time changes the model inputs.

**Q: What is a cross-sectional rank feature?**  
**A:** It expresses a stock's relative position versus other stocks on the same date, often on a 0-to-1 scale, rather than using only its raw value.

**Q: What is a stationary or normalized feature?**  
**A:** A transformation intended to make values more comparable across time or stocks, for example return or distance-from-moving-average instead of absolute price. It may reduce scale effects but does not guarantee statistical stationarity.

### Product and limitations

**Q: Why can we return “no signal”?**  
**A:** Financial predictions are uncertain. Abstaining avoids forcing a directional decision when the score is ambiguous, at the cost of lower coverage.

**Q: Is the output financial advice?**  
**A:** No. It is decision-support information from a prototype, not a guarantee, suitability assessment, or promise of profit.

**Q: What would you improve next?**  
**A:** First lock down reproducibility: align production features, labels, class IDs, and artifacts; add checks that fail loudly on missing or reordered features; then conduct point-in-time walk-forward testing with an embargo, calibrated probabilities, realistic trading costs, liquidity constraints, and simple benchmark strategies.

**Q: How would you monitor the model after deployment?**  
**A:** Track input freshness and missingness, prediction and class distributions, calibration and realized performance after outcomes mature, data drift, model version, and failures. Retraining should produce a separate candidate that passes pre-defined validation gates before manual deployment.

## 8. Terms to memorize

| Term | Plain-language meaning |
|---|---|
| OHLCV | Open, high, low, close, and traded volume |
| Time series | Data ordered by time |
| Lookback/window | Number of earlier time steps given to a sequence model |
| Horizon | How far ahead the target outcome is measured |
| Label/target | The answer the supervised model is trained to predict |
| Return | Percentage change in price over a period |
| Excess return | Asset return minus a reference-market return |
| Cross-sectional | Comparing assets with one another at the same time |
| Imputation | Replacing missing input values according to a defined rule |
| StandardScaler | Transformation using training mean and standard deviation |
| Early stopping | Stop training when validation performance stops improving |
| Soft voting | Combining probability outputs from multiple models |
| Calibration | Whether predicted probabilities match observed frequencies |
| Selective prediction | Predict only on cases passing a confidence/decision rule |
| Coverage | Fraction of examples for which the system gives an actionable output |
| Data drift | Change over time in input-data distributions |
| Model drift | Decline/change in relationship between inputs and outcomes |
| Inference | Using a trained model to produce an output |
| Artifact | Saved model weights, scaler, feature list, or metadata |
| Point-in-time data | Data known at the exact time a prediction would have been made |
| Slippage | Difference between intended and actual execution price |
| Liquidity | How readily an asset can be traded without materially moving its price |

## 9. Source map for follow-up study

- Forecasting and model design: [model-training.md](./model-training.md), [model-experiments.md](./model-experiments.md), [ADR-005-ml-architecture.md](../../docs/02-architecture/decisions/ADR-005-ml-architecture.md).
- Historical evaluation (older final_v1): [model-final-evaluation.md](./model-final-evaluation.md).
- Training/serving caveats and validation requirements: [recommendation-engine-review.md](./recommendation-engine-review.md).
- Runtime inference and ensemble: [inference.py](../app/ml/serving/inference.py), [model_loader.py](../app/ml/serving/model_loader.py).
- Current candidate training and feature generation: [weekly_retraining.py](../app/tasks/weekly_retraining.py), [daily_workflow.py](../app/tasks/daily_workflow.py), [run_features.py](../app/data/features/run_features.py).
- Newer research feature engineering and XGBoost experiment: [feature_engineer_v3.py](../app/ml/v3/feature_engineer_v3.py), [train_xgb_v3.py](../app/ml/v3/train_xgb_v3.py).
- Financial sentiment: [sentiment_service.py](../app/services/sentiment_service.py), [sentiment_tasks.py](../app/tasks/sentiment_tasks.py).
- Recommendation score: [recommendation_service.py](../app/services/recommendation_service.py).
- Hosted chat model: [groq_client.py](../app/services/groq_client.py), [assistant_service.py](../app/services/assistant_service.py).
- Deployed package metadata/results: [model_manifest.json](../models/production/v3/model_manifest.json), [gru_metrics.json](../models/production/v3/gru_metrics.json), and [xgb_metrics.json](../models/production/v3/xgb_metrics.json).

## 10. Final 20-second closing answer

“Basarat uses an Attention-BiGRU for ordered daily market sequences and XGBoost for tabular market features, with an ensemble and an uncertainty gate for short-term PSX direction. It separately offers FinBERT-based financial-news sentiment, rule-based recommendation synthesis, and a hosted generative chat assistant. The core research challenge is noisy, changing market data, so chronological evaluation, leakage prevention, probability calibration, cost-aware backtesting, and exact training-serving feature consistency are essential. The current output is decision support, not guaranteed investment performance.”
