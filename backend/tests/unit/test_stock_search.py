import pandas as pd

from app.services.stock_service import StockService


def test_search_symbols_resolves_known_company_name_alias(monkeypatch):
    service = object.__new__(StockService)
    monkeypatch.setattr(
        service,
        "_get_market_frame",
        lambda: pd.DataFrame({"sector": ["COMMERCIAL BANKS"]}, index=["HBL"]),
    )
    monkeypatch.setattr(service, "_sector_of", lambda symbol: "COMMERCIAL BANKS")

    result = service.search_symbols("Habib", limit=10)

    assert result == [{"symbol": "HBL", "name": "Habib Bank", "sector": "COMMERCIAL BANKS"}]


def test_company_name_falls_back_to_stockanalysis_when_psx_returns_ticker(monkeypatch):
    monkeypatch.setattr("app.services.stock_service.cache_get_sync", lambda key: None)
    monkeypatch.setattr("app.services.stock_service.cache_set_sync", lambda *args: None)
    monkeypatch.setattr(
        "app.services.stock_service.pypsx_toolkit.Ticker",
        lambda symbol: type("Ticker", (), {"info": {"name": "HBL"}})(),
    )
    monkeypatch.setattr(
        "app.services.stock_service.fetch_stockanalysis_fundamentals",
        lambda symbol: {"company_profile": {"name": "Habib Bank Limited"}},
    )

    assert StockService._company_name("HBL") == "Habib Bank Limited"
