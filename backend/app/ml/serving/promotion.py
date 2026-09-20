"""Champion vs Challenger — promotion logic for model replacement."""

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.ml.serving.model_registry import (
    get_production_model,
    promote_model,
    reject_model,
)

log = logging.getLogger(__name__)


def compare_models(production_metrics: dict, candidate_metrics: dict, config: dict) -> dict:
    """Compare production vs candidate model metrics.

    Parameters
    ----------
    production_metrics : metrics dict from the production model
    candidate_metrics : metrics dict from the candidate model
    config : dict with keys MIN_ACCURACY_IMPROVEMENT, MIN_F1_IMPROVEMENT, MAX_ABSTENTION_INCREASE

    Returns
    -------
    dict with keys: decision, reason, details
    """
    min_acc_imp = config.get("MIN_ACCURACY_IMPROVEMENT", 0.01)
    min_f1_imp = config.get("MIN_F1_IMPROVEMENT", 0.01)
    max_abstention = config.get("MAX_ABSTENTION_INCREASE", 0.05)

    prod_acc = production_metrics.get("test_accuracy", 0)
    cand_acc = candidate_metrics.get("test_accuracy", 0)
    prod_f1 = production_metrics.get("weighted_avg_f1", 0)
    cand_f1 = candidate_metrics.get("weighted_avg_f1", 0)
    prod_abstention = production_metrics.get("abstention_rate", 0)
    cand_abstention = candidate_metrics.get("abstention_rate", 0)

    acc_diff = cand_acc - prod_acc
    f1_diff = cand_f1 - prod_f1
    abstention_diff = cand_abstention - prod_abstention

    details = {
        "production_accuracy": prod_acc,
        "candidate_accuracy": cand_acc,
        "accuracy_improvement": round(acc_diff, 4),
        "production_f1": prod_f1,
        "candidate_f1": cand_f1,
        "f1_improvement": round(f1_diff, 4),
        "production_abstention_rate": prod_abstention,
        "candidate_abstention_rate": cand_abstention,
        "abstention_change": round(abstention_diff, 4),
    }

    # Check if candidate is materially worse
    if acc_diff < -min_acc_imp:
        return {
            "decision": "rejected",
            "reason": f"Accuracy degradation {acc_diff:+.4f} exceeds threshold -{min_acc_imp}",
            "details": details,
        }

    if f1_diff < -min_f1_imp:
        return {
            "decision": "rejected",
            "reason": f"F1 degradation {f1_diff:+.4f} exceeds threshold -{min_f1_imp}",
            "details": details,
        }

    if abstention_diff > max_abstention:
        return {
            "decision": "rejected",
            "reason": f"Abstention increase {abstention_diff:+.4f} exceeds threshold {max_abstention}",
            "details": details,
        }

    # Candidate must show improvement to be promoted
    if acc_diff >= min_acc_imp or f1_diff >= min_f1_imp:
        return {
            "decision": "promoted",
            "reason": f"Meets improvement criteria (acc={acc_diff:+.4f}, f1={f1_diff:+.4f})",
            "details": details,
        }

    # Marginal improvement — reject (be conservative)
    return {
        "decision": "rejected",
        "reason": f"Insufficient improvement (acc={acc_diff:+.4f}, f1={f1_diff:+.4f}) — below thresholds",
        "details": details,
    }


def evaluate_and_promote(
    session: Session,
    gru_candidate_version: str,
    xgb_candidate_version: str,
    gru_production_metrics: dict,
    gru_candidate_metrics: dict,
    xgb_production_metrics: dict,
    xgb_candidate_metrics: dict,
    config: dict,
) -> dict:
    """Evaluate both GRU and XGB candidates against production, then promote if better.

    Returns a dict with the promotion decision for each model type.
    """
    results = {}

    # Compare GRU
    gru_decision = compare_models(gru_production_metrics, gru_candidate_metrics, config)
    results["gru"] = gru_decision

    if gru_decision["decision"] == "promoted":
        promote_model(session, gru_candidate_version)
        log.info("[PROMOTION] GRU candidate %s promoted to production", gru_candidate_version)
    else:
        reject_model(session, gru_candidate_version, gru_decision["reason"])
        log.info("[PROMOTION] GRU candidate %s rejected: %s", gru_candidate_version, gru_decision["reason"])

    # Compare XGB
    xgb_decision = compare_models(xgb_production_metrics, xgb_candidate_metrics, config)
    results["xgb"] = xgb_decision

    if xgb_decision["decision"] == "promoted":
        promote_model(session, xgb_candidate_version)
        log.info("[PROMOTION] XGB candidate %s promoted to production", xgb_candidate_version)
    else:
        reject_model(session, xgb_candidate_version, xgb_decision["reason"])
        log.info("[PROMOTION] XGB candidate %s rejected: %s", xgb_candidate_version, xgb_decision["reason"])

    return results
