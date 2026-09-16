"""XGBoost baseline pipeline — parallel track to the GRU models.

This module provides a complete XGBoost training pipeline for the same
PSX direction-classification problem, using flat tabular features instead
of 30-day sequences. It reuses the same labels, splits, and evaluation
format as the GRU pipeline for direct, apples-to-apples comparison.

Usage::

    python -m app.ml.training_xgb.run_training_xgb
"""
