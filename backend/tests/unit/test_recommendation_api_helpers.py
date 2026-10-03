from datetime import date

from app.api.v1.recommendations import _apply_freshness_guard, _risk_payload


def test_missing_risk_inputs_are_not_replaced_with_fabricated_defaults():
    payload = _risk_payload({
        "signal": "hold",
        "current_price": 100.0,
        "target_price": None,
        "stop_loss": None,
        "atr_14": None,
    })

    assert payload["atr_14"] is None
    assert payload["expected_range"] is None
    assert payload["upside_pct"] is None
    assert payload["downside_pct"] is None
    assert payload["risk_reward_ratio"] is None


def test_missing_analysis_date_suppresses_actionable_signal():
    result = _apply_freshness_guard(
        {
            "signal": "buy",
            "confidence": 0.8,
            "target_price": 110.0,
            "stop_loss": 95.0,
            "data_as_of": None,
        },
        today=date(2026, 10, 3),
    )

    assert result["signal"] == "hold"
    assert result["signal_suppressed"] is True
    assert result["confidence"] == 0.0
    assert result["target_price"] is None
    assert result["stop_loss"] is None
