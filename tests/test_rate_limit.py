from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core import rate_limit


@pytest.fixture(autouse=True)
def _reset_rate_counters():
    rate_limit._rate_counters.clear()
    yield
    rate_limit._rate_counters.clear()


def _request(ip: str) -> MagicMock:
    req = MagicMock()
    req.client.host = ip
    return req


def test_requests_within_limit_succeed():
    req = _request("10.0.0.1")
    for _ in range(rate_limit._RATE_LIMIT):
        rate_limit.check_rate_limit(req)


def test_request_over_limit_raises_429():
    req = _request("10.0.0.2")
    for _ in range(rate_limit._RATE_LIMIT):
        rate_limit.check_rate_limit(req)

    with pytest.raises(HTTPException) as exc_info:
        rate_limit.check_rate_limit(req)
    assert exc_info.value.status_code == 429


def test_different_ips_tracked_separately():
    req_a = _request("10.0.0.3")
    req_b = _request("10.0.0.4")

    for _ in range(rate_limit._RATE_LIMIT):
        rate_limit.check_rate_limit(req_a)

    # req_a is now at its limit, but req_b has an independent counter.
    rate_limit.check_rate_limit(req_b)

    with pytest.raises(HTTPException):
        rate_limit.check_rate_limit(req_a)
