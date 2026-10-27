#!/bin/sh
# 监听拼接输出 + 图块重建队列（每 20 秒检查）
export PATH="/usr/local/bin:/usr/syno/bin:/usr/bin:/bin:$PATH"
while true; do
  python3 /srv/example/viewer/stitch_apply.py >> /srv/example/cache/auto_huge.log 2>&1
  python3 - <<'PY'
import json, sys
try:
    d = json.load(open('/srv/example/cache/pyramid_build_state.json'))
except Exception:
    sys.exit(1)
sys.exit(0 if d.get('deferred') else 1)
PY
  if [ $? -eq 0 ]; then
    if ! /usr/local/bin/docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^dunhuang-pyramid-huge$'; then
      cd /srv/example/viewer && /usr/local/bin/docker-compose up -d pyramid-huge >/dev/null 2>&1
    fi
  fi
  sleep 20
done