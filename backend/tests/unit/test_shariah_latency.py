from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.models.stock import Stock
from app.services.shariah_service import (
    KMI30_MEMBERSHIP_CACHE_KEY,
    STOCK_METADATA_CACHE_TTL_SECONDS,
    ShariahService,
)
from app.tasks import refresh_shariah_cache


@pytest.mark.asyncio
async def test_stock_metadata_warm_cache_avoids_database_query(monkeypatch):
    cached_stock = {
        "id": "stock-id",
        "symbol": "OGDC",
        "name": "Oil & Gas Development Company",
        "sector": "Oil & Gas Exploration Companies",
        "market": "PSX",
        "is_active": True,
    }
    cache_get = AsyncMock(return_value=cached_stock)
    cache_set = AsyncMock()
    db = Mock()
    db.execute = AsyncMock()
    monkeypatch.setattr("app.services.shariah_service.cache_get", cache_get)
    monkeypatch.setattr("app.services.shariah_service.cache_set", cache_set)

    stock = await ShariahService(db).get_stock_by_symbol("ogdc")

    assert isinstance(stock, Stock)
    assert stock.id == "stock-id"
    assert stock.sector == cached_stock["sector"]
    db.execute.assert_not_awaited()
    cache_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_stock_metadata_cold_cache_queries_once_and_sets_one_hour_ttl(monkeypatch):
    stock = SimpleNamespace(
        id="stock-id",
        symbol="OGDC",
        name="Oil & Gas Development Company",
        sector="Oil & Gas Exploration Companies",
        market="PSX",
        is_active=True,
    )
    result = Mock()
    result.scalars.return_value.first.return_value = stock
    db = Mock()
    db.execute = AsyncMock(return_value=result)
    cache_get = AsyncMock(return_value=None)
    cache_set = AsyncMock()
    monkeypatch.setattr("app.services.shariah_service.cache_get", cache_get)
    monkeypatch.setattr("app.services.shariah_service.cache_set", cache_set)

    service = ShariahService(db)
    first = await service.get_stock_by_symbol("ogdc")
    second = await service.get_stock_by_symbol("OGDC")

    assert first is second
    db.execute.assert_awaited_once()
    cache_set.assert_awaited_once()
    assert cache_set.await_args.args[0] == "stock:OGDC"
    assert cache_set.await_args.kwargs["ttl_seconds"] == STOCK_METADATA_CACHE_TTL_SECONDS == 3600


@pytest.mark.asyncio
async def test_screening_returns_the_stock_loaded_for_it(monkeypatch):
    stock = SimpleNamespace(
        id="stock-id",
        symbol="OGDC",
        name="Oil & Gas Development Company",
        sector="Oil & Gas Exploration Companies",
        market="PSX",
        is_active=True,
    )
    result = Mock()
    result.scalars.return_value.first.return_value = stock
    db = Mock()
    db.execute = AsyncMock(return_value=result)
    monkeypatch.setattr(
        "app.services.shariah_service.cache_get",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr("app.services.shariah_service.cache_set", AsyncMock())

    screening, resolved_stock = await ShariahService(db).get_screening_with_stock("OGDC")

    assert screening is not None
    assert resolved_stock is stock
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_kmi_membership_checks_only_cached_snapshots(monkeypatch):
    cache_get = AsyncMock(
        side_effect=[
            ["OGDC", "LUCK"],
        ]
    )
    monkeypatch.setattr("app.services.shariah_service.cache_get", cache_get)

    async def external_fetch(*args, **kwargs):
        raise AssertionError("request path must not call the external KMI-30 API")

    monkeypatch.setattr(
        "app.services.market_service.MarketService.get_index_constituents",
        external_fetch,
    )
    service = ShariahService(None)

    assert await service._is_current_kmi30_member("OGDC") is True
    assert await service._is_current_kmi30_member("HBL") is False
    assert cache_get.await_args_list[0].args == (KMI30_MEMBERSHIP_CACHE_KEY,)


@pytest.mark.asyncio
async def test_membership_uses_shared_market_snapshot_when_dedicated_cache_is_cold(monkeypatch):
    cache_get = AsyncMock(
        side_effect=[
            None,
            datetime.now(timezone.utc).isoformat(),
            [{"symbol": "OGDC"}],
        ]
    )
    monkeypatch.setattr("app.services.shariah_service.cache_get", cache_get)

    assert await ShariahService(None)._is_current_kmi30_member("OGDC") is True
    assert cache_get.await_args_list[1].args == (
        "market:constituents:KMI30:fetched_at",
    )
    assert cache_get.await_args_list[2].args == ("market:constituents:KMI30",)


@pytest.mark.asyncio
async def test_stale_shared_constituents_are_not_used_for_current_membership(monkeypatch):
    cache_get = AsyncMock(side_effect=[None, "2020-01-01T00:00:00+00:00"])
    monkeypatch.setattr("app.services.shariah_service.cache_get", cache_get)

    assert await ShariahService(None)._is_current_kmi30_member("OGDC") is False
    assert [call.args[0] for call in cache_get.await_args_list] == [
        KMI30_MEMBERSHIP_CACHE_KEY,
        "market:constituents:KMI30:fetched_at",
    ]


@pytest.mark.asyncio
async def test_background_refresh_warms_kmi_response_and_fresh_membership(monkeypatch):
    import json

    from app.services.market_service import MarketService

    published = {}

    async def persist_cache(key, value, ttl_seconds):
        published[key] = json.dumps(value)

    monkeypatch.setattr(
        refresh_shariah_cache,
        "get_sync_redis_client",
        lambda: SimpleNamespace(get=published.get),
    )
    monkeypatch.setattr(
        refresh_shariah_cache, "set_dataset_status_sync", lambda *_args, **_kwargs: None
    )
    cache_set = AsyncMock(side_effect=persist_cache)
    monkeypatch.setattr(
        refresh_shariah_cache,
        "cache_set",
        cache_set,
    )

    async def refreshed_constituents(self, index_code, force_refresh, read_only):
        assert index_code == "KMI30"
        assert force_refresh is True
        assert read_only is False
        return [{"symbol": "OGDC"}, {"symbol": "LUCK"}]

    monkeypatch.setattr(MarketService, "get_index_constituents", refreshed_constituents)
    monkeypatch.setattr(
        MarketService,
        "constituents_freshness",
        classmethod(
            lambda cls, index_code: {
                "as_of": datetime.now(timezone.utc).isoformat(),
                "is_stale": False,
            }
        ),
    )

    result = await refresh_shariah_cache._refresh_shariah_cache()

    assert result["market_constituents"] == 2
    cached_values = {call.args[0]: call for call in cache_set.await_args_list}
    assert cached_values["shariah:kmi30:constituents"].kwargs["ttl_seconds"] == 3600
    assert cached_values[KMI30_MEMBERSHIP_CACHE_KEY].args[1] == ["LUCK", "OGDC"]
    assert cached_values[KMI30_MEMBERSHIP_CACHE_KEY].kwargs["ttl_seconds"] == 86400


def test_shariah_cache_refresh_is_scheduled_on_weekday_mornings():
    from app.celery_app import celery

    schedule = celery.conf.beat_schedule["refresh-shariah-cache"]["schedule"]
    assert schedule.minute == {5}
    assert schedule.hour == {9}
    assert schedule.day_of_week == {1, 2, 3, 4, 5}
    assert (
        "app.tasks.refresh_shariah_cache"
        in celery.conf.include
    )
