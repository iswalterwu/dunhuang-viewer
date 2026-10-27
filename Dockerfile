FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIPS_CONCURRENCY=2 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app

# libvips：流式解码超大 TIFF，限制解码内存占用
# 软件源镜像用于构建网络兼容；如需更换，由部署方调整
RUN set -eux; \
    for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list; do \
        if [ -f "$f" ]; then sed -i 's|deb.debian.org|mirrors.aliyun.com|g' "$f"; fi; \
    done; \
    apt-get update; \
    apt-get install -y --no-install-recommends libvips42; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .
COPY pyramid_worker.py .
COPY static ./static

ENV DATA_DIR=/data \
    CACHE_DIR=/cache \
    CACHE_MAX_GB=600 \
    TILE_SIZE=512 \
    TILE_QUALITY=82

VOLUME ["/data", "/cache"]
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "75"]
