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
