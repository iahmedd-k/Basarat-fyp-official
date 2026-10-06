import subprocess

import pytest

from app.tasks.refresh_fundamentals import _fetch_symbol_with_timeout


def test_fetch_symbol_runs_scraper_in_subprocess(monkeypatch):
    called = {}

    def run(args, **kwargs):
        called["args"] = args
        called["kwargs"] = kwargs
        return subprocess.CompletedProcess(args, 0, '{"symbol": "JDWS"}', "")

    monkeypatch.setattr("app.tasks.refresh_fundamentals.subprocess.run", run)

    result = _fetch_symbol_with_timeout("JDWS", 12)

    assert result == {"symbol": "JDWS"}
    assert called["args"][-1] == "JDWS"
    assert called["kwargs"]["timeout"] == 12
    assert called["kwargs"]["capture_output"] is True


def test_fetch_symbol_reports_scraper_timeout(monkeypatch):
    def run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("python", 12)

    monkeypatch.setattr("app.tasks.refresh_fundamentals.subprocess.run", run)

    with pytest.raises(TimeoutError, match="timed out for JDWS"):
        _fetch_symbol_with_timeout("JDWS", 12)


def test_fetch_symbol_reports_scraper_errors(monkeypatch):
    def run(args, **_kwargs):
        return subprocess.CompletedProcess(args, 1, "", "upstream unavailable")

    monkeypatch.setattr("app.tasks.refresh_fundamentals.subprocess.run", run)

    with pytest.raises(RuntimeError, match="upstream unavailable"):
        _fetch_symbol_with_timeout("JDWS", 12)
