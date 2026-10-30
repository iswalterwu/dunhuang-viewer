import os
import secrets
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from dh_catalog.config import Settings, load_settings


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
        "DH_CODE_VERSION": "synthetic-commit",
    })
    assert settings.data_dir == tmp_path / "影像"
    assert settings.backup_dir == tmp_path / "备份"
    assert settings.v0_cache_dir == tmp_path / "cache"
    assert settings.auth_secret == secret
    assert settings.v0_url == "http://localhost:8503"
    assert settings.v0_public_url == "https://example.test"
    assert settings.code_version == "synthetic-commit"
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
    assert settings.v0_public_url == settings.v0_url == "http://localhost:8503"
    assert settings.record_roots == {}
    assert settings.data_dir == Path("/data")
    assert settings.code_version == "development"


@pytest.mark.parametrize("public_url", ["", " \t "])
def test_empty_optional_public_url_reuses_explicit_v0_url(tmp_path, public_url):
    settings = load_settings({
        "DH_V0_ENV_FILE": str(tmp_path / "absent.env"),
        "DH_V0_URL": "https://viewer.example.test/",
        "DH_V0_PUBLIC_URL": public_url,
    })
    assert settings.v0_public_url == settings.v0_url == "https://viewer.example.test"


def test_record_roots_are_posix_strings_independent_of_host_and_scan_roots(tmp_path):
    settings = load_settings({
        "DH_V0_ENV_FILE": str(tmp_path / "absent.env"),
        "DH_DATA_DIR": str(tmp_path / "data"),
        "DH_BACKUP_DIR": str(tmp_path / "backup"),
        "DH_HOST_DATA_DIR": "/srv/current/images",
        "DH_HOST_BACKUP_DIR": "/srv/current/segments",
        "DH_RECORD_DATA_ROOT": "  /srv/legacy/images  ",
        "DH_RECORD_BACKUP_ROOT": "\t/srv/legacy/segments/\n",
    })
    assert settings.record_roots == {"data": "/srv/legacy/images/", "backup": "/srv/legacy/segments/"}
    assert all(isinstance(value, str) and "\\" not in value for value in settings.record_roots.values())
    assert settings.data_dir == tmp_path / "data" and settings.backup_dir == tmp_path / "backup"
    assert replace(settings, code_version="new").record_roots == settings.record_roots


@pytest.mark.parametrize("role", ["DATA", "BACKUP"])
@pytest.mark.parametrize("value", ["", " \t "])
def test_empty_record_roots_are_omitted(tmp_path, role, value):
    settings = load_settings({"DH_V0_ENV_FILE": str(tmp_path / "absent.env"),
                              f"DH_RECORD_{role}_ROOT": value})
    assert settings.record_roots == {}


@pytest.mark.parametrize("role", ["DATA", "BACKUP"])
@pytest.mark.parametrize("value", ["relative/images", "/", " /// ", "C:\\synthetic\\images", "/srv\\images"])
def test_record_roots_reject_non_posix_absolute_prefixes(tmp_path, role, value):
    name = f"DH_RECORD_{role}_ROOT"
    with pytest.raises(ValueError, match=name):
        load_settings({"DH_V0_ENV_FILE": str(tmp_path / "absent.env"), name: value})


def test_existing_settings_constructor_and_replace_keep_empty_mapping_defaults(tmp_path):
    args = (tmp_path, tmp_path, tmp_path, tmp_path / "v0.env",
            "http://localhost:8503", "http://localhost:8503", None, None)
    first, second = Settings(*args), Settings(*args, "synthetic-code")
    assert first.record_roots == second.record_roots == {}
    assert first.record_roots is not second.record_roots
    assert replace(first, code_version="synthetic-code") == second


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


@pytest.mark.parametrize("command", ["import", "migrate"])
def test_cli_has_no_import_entry_or_database_fallback(tmp_path, command):
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    env.pop("DH_DATABASE_URL", None)
    env["DH_V0_ENV_FILE"] = str(tmp_path / "absent.env")
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "dh_catalog", command], env=env,
        capture_output=True, encoding="utf-8", check=False,
    )
    assert result.returncode == 2
    expected = "invalid choice" if command == "import" else "DH_DATABASE_URL"
    assert expected in result.stderr


@pytest.mark.parametrize("case", ["secret", "database", "run", "config"])
def test_health_configuration_errors_without_importer_or_scan(tmp_path, case):
    config = tmp_path / "v0.env"
    config.write_text("" if case == "secret" else "AUTH_SECRET=" + secrets.token_urlsafe(32), encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"),
               DH_V0_ENV_FILE=str(config), DH_V0_CACHE_DIR=str(tmp_path / "must-not-read"),
               DH_DATA_DIR=str(tmp_path / "must-not-read"), DH_BACKUP_DIR=str(tmp_path / "must-not-read"),
               DH_V0_URL="invalid-url" if case == "config" else "http://v0.test")
    env.pop("DH_DATABASE_URL", None)
    env.pop("DH_V0_PUBLIC_URL", None)
    argv = ["dh_catalog", "health", "--run", "1"] if case == "run" else ["dh_catalog", "health"]
    code = (
        "import runpy, sys\n"
        f"sys.argv = {argv!r}\n"
        "try:\n    runpy.run_module('dh_catalog', run_name='__main__')\n"
        "except SystemExit as error:\n"
        "    assert 'dh_catalog.importer' not in sys.modules\n"
        "    assert 'dh_catalog.scan' not in sys.modules\n"
        "    raise\n"
    )
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", code], env=env,
                            capture_output=True, encoding="utf-8", check=False)
    assert result.returncode == (2 if case in {"run", "database"} else 1)
    assert {"secret": "AUTH_SECRET", "database": "DH_DATABASE_URL", "run": "--run", "config": "运行配置无效"}[case] in result.stderr
