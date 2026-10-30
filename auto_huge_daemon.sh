#!/bin/sh
# 监听拼接输出 + 图块重建队列（每 20 秒检查）
: "${DH_DEPLOY_DIR:?Set DH_DEPLOY_DIR}"
: "${DH_HOST_DATA_DIR:?Set DH_HOST_DATA_DIR}"
: "${DH_HOST_CACHE_DIR:?Set DH_HOST_CACHE_DIR}"
export PATH="/usr/local/bin:/usr/syno/bin:/usr/bin:/bin:$PATH"
while true; do
  DATA_DIR="$DH_HOST_DATA_DIR" CACHE_DIR="$DH_HOST_CACHE_DIR" python3 "$DH_DEPLOY_DIR/stitch_apply.py" >> "$DH_HOST_CACHE_DIR/auto_huge.log" 2>&1
  python3 - "$DH_HOST_CACHE_DIR/pyramid_build_state.json" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
sys.exit(0 if d.get('deferred') else 1)
PY
  if [ $? -eq 0 ]; then
    if ! /usr/local/bin/docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^dunhuang-pyramid-huge$'; then
      cd "$DH_DEPLOY_DIR" && /usr/local/bin/docker-compose up -d pyramid-huge >/dev/null 2>&1
    fi
  fi
  sleep 20
done