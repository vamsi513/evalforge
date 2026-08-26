import pytest

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
