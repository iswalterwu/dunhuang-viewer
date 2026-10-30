FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install -r requirements.txt

ARG DH_CODE_VERSION
RUN test -n "$DH_CODE_VERSION"
ENV DH_CODE_VERSION=${DH_CODE_VERSION}

COPY src ./src
COPY migrations ./migrations
COPY tests ./tests
COPY pytest.ini ./
# T-23 supplies the real baseline and comparison tests before T-24 builds.
COPY acceptance ./acceptance
# Static runtime contracts must also run inside this same candidate image.
COPY Dockerfile docker-compose.yml .dockerignore .env.example ./

# The existing v0 users.json is root:600; all v0 mounts remain read-only.
USER root
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ["python", "-m", "dh_catalog", "health"]
CMD ["sh", "-c", "python -m dh_catalog migrate && exec python -m uvicorn dh_catalog.api:create_app --factory --host 0.0.0.0 --port 8000"]
