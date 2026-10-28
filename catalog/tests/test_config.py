import secrets
from pathlib import Path

import pytest

from dh_catalog.config import load_settings


def test_paths_urls_and_private_fields(tmp_path):
    secret = secrets.token_urlsafe(32)
    config = tmp_path / "v0.env"
    config.write_text(f'AUTH_SECRET = "{secret}"\nAUTH_PASS=unused\n', encoding="utf-8")
    settings = load_settings({
        "DH_DATA_DIR": str(tmp_path / "影像"),
        "DH_BACKUP_DIR": str(tmp_path / "备份"),
        "DH_V0_CACHE_DIR": str(tmp_path / "cache"),
        "DH_V0_ENV_FILE": str(config),
        "DH_V0_URL": "http://localhost:8503/",
        "DH_V0_PUBLIC_URL": "https://example.test/",
        "DH_DATABASE_URL": "postgresql://test@localhost/test_catalog",
    })
    assert settings.data_dir == tmp_path / "影像"
    assert settings.backup_dir == tmp_path / "备份"
    assert settings.v0_cache_dir == tmp_path / "cache"
    assert settings.auth_secret == secret
    assert settings.v0_url == "http://localhost:8503"
    assert settings.v0_public_url == "https://example.test"
    assert secret not in repr(settings)
    assert "postgresql://" not in repr(settings)


@pytest.mark.parametrize("content", ["", "AUTH_SECRET=\n", "AUTH_SECRET=''\n", "AUTH_USER=someone\n"])
def test_missing_secret_has_no_fallback(tmp_path, content):
    config = tmp_path / "v0.env"
    config.write_text(content, encoding="utf-8")
    settings = load_settings({"DH_V0_ENV_FILE": str(config), "AUTH_SECRET": "ignored"})
    assert settings.auth_secret is None
    assert settings.database_url is None


def test_absent_v0_env_is_unavailable(tmp_path):
    settings = load_settings({"DH_V0_ENV_FILE": str(tmp_path / "absent.env")})
    assert settings.auth_secret is None
    assert settings.v0_public_url == settings.v0_url
    assert settings.data_dir == Path("/data")


@pytest.mark.parametrize("quote", ["'", '"', ""])
def test_secret_quotes_whitespace_and_no_interpolation(tmp_path, quote):
    secret = secrets.token_urlsafe(32) + "${NOT_AN_ENV_LOOKUP}"
    config = tmp_path / "v0.env"
    config.write_text(f"AUTH_SECRET = {quote}{secret}{quote}  \n", encoding="utf-8-sig")
    assert load_settings({"DH_V0_ENV_FILE": str(config)}).auth_secret == secret


@pytest.mark.parametrize("value", ["localhost:8503", "file:///tmp/index", "https://"])
def test_invalid_v0_url_rejected_at_config_boundary(value):
    with pytest.raises(ValueError, match="HTTP"):
        load_settings({"DH_V0_URL": value})
