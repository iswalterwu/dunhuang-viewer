#!/bin/sh
export PATH=/usr/local/bin:/usr/bin:/bin:/usr/syno/bin
STATE=/srv/example/cache/pyramid_build_state.json
python3 - <<'PY'
import json, sys
try:
    d = json.load(open('/srv/example/cache/pyramid_build_state.json'))
except Exception:
    sys.exit(1)
sys.exit(0 if d.get('deferred') else 1)
PY
if [ $? -ne 0 ]; then exit 0; fi
if /usr/local/bin/docker ps --format '{{.Names}}' | grep -q '^dunhuang-pyramid-huge$'; then exit 0; fi
cd /srv/example/viewer && /usr/local/bin/docker-compose up -d pyramid-huge >/dev/null 2>&1