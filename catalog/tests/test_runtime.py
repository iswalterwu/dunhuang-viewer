"""Small source contracts only: not a YAML parser, image build or runtime proof."""

import re
from pathlib import Path

from dh_catalog.db import MIGRATIONS

CATALOG = Path(__file__).resolve().parents[1]
DOCKERFILE = (CATALOG / "Dockerfile").read_text(encoding="utf-8")
COMPOSE = (CATALOG / "docker-compose.yml").read_text(encoding="utf-8")
DB, _, API = COMPOSE.partition("  catalog-api:\n")


def test_image_layout_keeps_migrations_and_real_tests():
    assert DOCKERFILE.startswith("FROM python:3.12-slim\n")
    assert "WORKDIR /app\n" in DOCKERFILE
    assert "PYTHONPATH=/app/src" in DOCKERFILE
    assert "PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple" in DOCKERFILE
    assert "RUN python -m pip install -r requirements.txt" in DOCKERFILE
    for directory in ("src", "migrations", "tests", "acceptance"):
        assert f"COPY {directory} ./{directory}\n" in DOCKERFILE
    assert "COPY pytest.ini ./\n" in DOCKERFILE
    assert "COPY Dockerfile docker-compose.yml .dockerignore .env.example ./\n" in DOCKERFILE
    assert MIGRATIONS == CATALOG / "migrations"
    assert list(MIGRATIONS.glob("*.sql"))
    assert "pytest==" in (CATALOG / "requirements.txt").read_text(encoding="utf-8")
    assert "apt-get" not in DOCKERFILE
    assert "libvips" not in DOCKERFILE


def test_startup_migrates_before_factory_and_health_uses_cli():
    assert 'CMD ["sh", "-c", "python -m dh_catalog migrate && exec python -m uvicorn dh_catalog.api:create_app --factory --host 0.0.0.0 --port 8000"]' in DOCKERFILE
    assert 'CMD ["python", "-m", "dh_catalog", "health"]' in DOCKERFILE
    assert "ARG DH_CODE_VERSION\n" in DOCKERFILE
    assert 'RUN test -n "$DH_CODE_VERSION"' in DOCKERFILE
    assert "ENV DH_CODE_VERSION=${DH_CODE_VERSION}" in DOCKERFILE
    assert "DH_CODE_VERSION:?" in API
    assert "POSTGRES_PASSWORD:?" in DB and "POSTGRES_PASSWORD:?" in API
    # Configuration is passed as environment, never interpolated into shell code.
    assert "command:" not in API
    assert "entrypoint:" not in API
    assert "AUTH_SECRET:" not in COMPOSE


def test_independent_services_and_memory_limits():
    assert re.findall(r"^  ([\w-]+):$", COMPOSE, re.MULTILINE) == ["catalog-db", "catalog-api"]
    assert "image: postgres:17.4-alpine3.21" in DB
    for setting in ("shared_buffers=64MB", "max_connections=20", "work_mem=4MB"):
        assert setting in DB
    assert "ports:" not in DB
    assert "mem_limit: 384m\n" in DB and "memswap_limit: 384m\n" in DB
    assert "mem_limit: 512m\n" in API and "memswap_limit: 512m\n" in API
    assert "condition: service_healthy" in API


def test_read_only_inputs_and_external_pgdata():
    assert re.findall(r'^      - "(.*:/var/lib/postgresql/data)"$', DB, re.MULTILINE) == [
        "${DH_HOST_PGDATA_DIR:?Set DH_HOST_PGDATA_DIR in catalog/.env}:/var/lib/postgresql/data",
    ]
    assert re.findall(r'^      - "(.*:ro)"$', API, re.MULTILINE) == [
        "${DH_HOST_DATA_DIR:?Set DH_HOST_DATA_DIR in catalog/.env}:/data:ro",
        "${DH_HOST_BACKUP_DIR:?Set DH_HOST_BACKUP_DIR in catalog/.env}:/backup:ro",
        "${DH_HOST_CACHE_DIR:?Set DH_HOST_CACHE_DIR in catalog/.env}:/v0cache:ro",
        "${DH_HOST_V0_ENV_FILE:?Set DH_HOST_V0_ENV_FILE in catalog/.env}:/run/v0.env:ro",
    ]
    assert "DH_DATA_DIR: /data" in API and "DH_BACKUP_DIR: /backup" in API
    assert "DH_V0_CACHE_DIR: /v0cache" in API
    assert "user: root\n" in API
    assert "DH_V0_ENV_FILE: /run/v0.env" in API
    assert "      - ./.env\n" in API


def test_host_bindings_are_explicit_lan_and_tailscale():
    assert re.findall(r'^      - "(.*:8504:8000)"$', API, re.MULTILINE) == [
        "${CATALOG_LAN_IP:?Set CATALOG_LAN_IP in catalog/.env}:8504:8000",
        "${CATALOG_TAILSCALE_IP:?Set CATALOG_TAILSCALE_IP in catalog/.env}:8504:8000",
    ]
    assert "0.0.0.0" not in COMPOSE
    assert "[::]" not in COMPOSE


def test_production_v0_url_required_and_optional_values_come_from_env_file():
    assert 'DH_V0_URL: "${DH_V0_URL:?Set DH_V0_URL in catalog/.env}"' in API
    assert "DH_V0_PUBLIC_URL:" not in API
    assert "DH_RECORD_DATA_ROOT:" not in API and "DH_RECORD_BACKUP_ROOT:" not in API
    assert "      - ./.env\n" in API
    assert "${DH_V0_PUBLIC_URL" not in COMPOSE  # No nested Compose interpolation.


def test_build_context_excludes_secrets_and_host_artifacts():
    patterns = (CATALOG / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for pattern in ("**/.env", "**/.env.*", "**/*.env", "!.env.example", "**/.venv",
                    "**/venv", "**/cache", "**/logs", "**/*.log", "**/__pycache__", "**/*.py[cod]"):
        assert pattern in patterns
    # No catch-all exclusion or blanket source/data-format exclusions.
    for pattern in ("*", "**", "src", "tests", "acceptance", "**/*.json", "**/*.tif"):
        assert pattern not in patterns
    example = (CATALOG / ".env.example").read_text(encoding="utf-8")
    for name in ("POSTGRES_PASSWORD", "DH_CODE_VERSION", "CATALOG_LAN_IP", "CATALOG_TAILSCALE_IP",
                 "DH_V0_URL", "DH_V0_PUBLIC_URL", "DH_HOST_DATA_DIR", "DH_HOST_BACKUP_DIR",
                 "DH_HOST_CACHE_DIR", "DH_HOST_V0_ENV_FILE", "DH_HOST_PGDATA_DIR",
                 "DH_RECORD_DATA_ROOT", "DH_RECORD_BACKUP_ROOT"):
        assert re.search(rf"^{name}=$", example, re.MULTILINE), name
    assert not re.search(r"^AUTH_\w+=", example, re.MULTILINE)


def test_runtime_sources_are_utf8_lf():
    for name in ("Dockerfile", "docker-compose.yml", ".env.example", ".dockerignore", "tests/test_runtime.py"):
        raw = (CATALOG / name).read_bytes()
        raw.decode("utf-8")
        assert not raw.startswith(b"\xef\xbb\xbf")
        assert b"\r" not in raw
