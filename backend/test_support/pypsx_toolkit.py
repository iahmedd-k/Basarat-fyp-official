"""Block live PSX calls in the lightweight unit-test container."""


def get_historical(*args, **kwargs):
    raise AssertionError("Live PSX access is disabled in the lightweight test container")


def market_watch(*args, **kwargs):
    raise AssertionError("Live PSX access is disabled in the lightweight test container")


def index_constituents(*args, **kwargs):
    raise AssertionError("Live PSX access is disabled in the lightweight test container")


class Ticker:
    def __init__(self, *args, **kwargs):
        raise AssertionError("Live PSX access is disabled in the lightweight test container")
