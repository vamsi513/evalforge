import pytest

from app.core import rate_limit
from app.core.config import settings
from app.db.session import init_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_database() -> None:
    init_db()


@pytest.fixture(scope="session", autouse=True)
def _dev_mode_admin_role():
    """In test runs with no platform_api_key, default callers to admin so
    tests that don't set X-User-Role can still exercise write endpoints."""
    original = settings.default_user_role
    settings.default_user_role = "admin"
    yield
    settings.default_user_role = original


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """TestClient uses a fixed synthetic IP for every request, so without a
    reset the eval-creation rate limit added in app/core/rate_limit.py would
    accumulate across the whole test session (many files collectively make
    far more than 20 calls) and start failing unrelated tests with 429s."""
    rate_limit._rate_counters.clear()
    yield
    rate_limit._rate_counters.clear()
