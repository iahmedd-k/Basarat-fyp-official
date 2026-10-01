from app.tasks.stock_data_pipeline import _clean, _merge_dict
from app.services.psx_company_tables import _page_source_info
from app.services.technical_calculator import calculate_recent_indicators
from bs4 import BeautifulSoup
import pandas as pd


def test_clean_removes_null_and_non_finite_values_but_keeps_real_zero_and_false():
    assert _clean({
        "null": None,
        "blank": "  ",
        "nan": float("nan"),
        "zero": 0,
        "false": False,
        "nested": {"keep": 1, "drop": None},
    }) == {
        "zero": 0,
        "false": False,
        "nested": {"keep": 1},
    }


def test_merge_keeps_saved_values_when_refresh_is_missing_or_null():
    saved = {"profile": {"name": "Example Co", "sector": "Banks"}, "eps": 12.5}
    refreshed = {"profile": {"name": None, "website": "https://example.test"}, "eps": None}

    assert _merge_dict(saved, refreshed) == {
        "profile": {
            "name": "Example Co",
            "sector": "Banks",
            "website": "https://example.test",
        },
        "eps": 12.5,
    }


def test_psx_quote_parser_keeps_official_change_metrics():
    soup = BeautifulSoup('''
        <div class="tabs__panel" data-name="REG">
          <span class="stats_label">1-Year Change * ^</span><span class="stats_value">9.65%</span>
          <span class="stats_label">YTD Change * ^</span><span class="stats_value">-5.70%</span>
          <span class="stats_label">P/E Ratio (TTM) **</span><span class="stats_value">6.92</span>
        </div>
    ''', "html.parser")

    market_data = _page_source_info(soup, "HBL")["Market Data"]

    assert market_data["year_change_pct"] == 9.65
    assert market_data["ytd_change_pct"] == -5.7
    assert market_data["pe_ratio_ttm"] == 6.92


def test_manual_indicators_use_a_maximum_45_day_window():
    dates = pd.bdate_range("2026-08-17", periods=33)
    close = pd.Series(range(100, 133), dtype=float)
    frame = pd.DataFrame({
        "date": dates,
        "high": close + 1,
        "low": close - 1,
        "close": close,
    })

    result = calculate_recent_indicators(frame)

    assert set(result["latest"]) == {
        "rsi_14", "macd", "macd_signal", "macd_histogram", "sma_14", "adx_14",
    }
    assert len(result["history"]) <= 45
