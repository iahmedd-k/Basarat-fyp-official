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

### 5.1 Historical experiments

The experiment documentation reports:

- Earlier three-class GRU-45 + XGBoost candidate: around 47.14% test accuracy and 0.4286 validation macro-F1 in its stated experiment.
- The newer `final_v3` manifest: 33,730 XGBoost and 33,686 BiGRU test samples; XGBoost sealed-test accuracy about 53.24%; BiGRU sealed-test accuracy about 51.34%.
- The same manifest/documentation describes thresholded accuracy ranges and mean Spearman rank information coefficients. These are results for particular evaluation slices and thresholds, not guaranteed live results.
- A separate older real-stock walk-forward report concerns `final_v1`, has a three-class target, and reports only 34.23% broad-universe accuracy. It is not a result for the current binary `final_v3` package.

Do not compare scores without saying which model version, target, sample population, dates, threshold, and test protocol they refer to. Thresholding can increase accuracy among retained predictions while reducing coverage. In the saved JSON, the XGBoost sealed-test record reports roughly 53.24% all-sample accuracy; its high-threshold subsets have low coverage. A score from a validation set or selected confidence subset must not be presented as all-sample test accuracy.

### 5.2 Metrics to explain simply

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

1. **Feature-count mismatch:** The saved `final_v3` artifacts list 79 GRU features and 70 XGBoost features. The currently scheduled `run_features` path uses a versioned 36-feature GRU list. The inference helper fills missing GRU features with 0.0; XGBoost inference also has a 0.50 fallback for a missing value. This means exact feature parity depends on the deployed parquet and should be checked, not assumed.
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
- Deployed package metadata/results: `../models/final/final_v3/model_manifest.json`, `../models/final/final_v3/gru_metrics.json`, and `../models/final/final_v3/xgb_metrics.json`.

## 10. Final 20-second closing answer

“Basarat uses an Attention-BiGRU for ordered daily market sequences and XGBoost for tabular market features, with an ensemble and an uncertainty gate for short-term PSX direction. It separately offers FinBERT-based financial-news sentiment, rule-based recommendation synthesis, and a hosted generative chat assistant. The core research challenge is noisy, changing market data, so chronological evaluation, leakage prevention, probability calibration, cost-aware backtesting, and exact training-serving feature consistency are essential. The current output is decision support, not guaranteed investment performance.”
