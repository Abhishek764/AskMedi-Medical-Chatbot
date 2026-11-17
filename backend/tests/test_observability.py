from app.core.config import Settings
from app.core.observability import _scrub, init_sentry


def test_sentry_off_without_dsn():
    assert init_sentry(Settings(_env_file=None, env="test")) is False


def test_scrub_removes_bodies_and_secrets():
    event = {
        "request": {
            "data": {"question": "I have HIV", "password": "x"},
            "cookies": {"askmedi_refresh": "t"},
            "query_string": "email=a@b.c",
            "headers": {"Authorization": "Bearer abc", "User-Agent": "ua"},
        },
        "user": {"email": "a@b.c"},
    }
    out = _scrub(event, {})
    assert "data" not in out["request"] and "cookies" not in out["request"]
    assert out["request"]["headers"]["Authorization"] == "[scrubbed]"
    assert out["request"]["headers"]["User-Agent"] == "ua"
    assert "user" not in out
