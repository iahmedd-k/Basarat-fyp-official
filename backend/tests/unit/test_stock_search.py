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


def test_company_name_uses_known_alias_without_on_demand_scrape(monkeypatch):
    monkeypatch.setattr("app.services.stock_service.cache_get_sync", lambda key: None)
    class Result:
        def scalar_one_or_none(self):
            return None

    class Session:
        def execute(self, *_args):
            return Result()

        def close(self):
            pass

    monkeypatch.setattr("app.db.base.get_sync_session_factory", lambda: lambda: Session())
    monkeypatch.setattr(
        "app.services.stock_service.pypsx_toolkit.Ticker",
        lambda symbol: (_ for _ in ()).throw(AssertionError("profile APIs must not scrape on demand")),
    )
    assert StockService._company_name("HBL") == "Habib Bank"
