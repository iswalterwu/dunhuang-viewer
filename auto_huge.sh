#!/bin/sh
: "${DH_DEPLOY_DIR:?Set DH_DEPLOY_DIR}"
: "${DH_HOST_DATA_DIR:?Set DH_HOST_DATA_DIR}"
: "${DH_HOST_CACHE_DIR:?Set DH_HOST_CACHE_DIR}"
export PATH=/usr/local/bin:/usr/bin:/bin:/usr/syno/bin
python3 - "$DH_HOST_CACHE_DIR/pyramid_build_state.json" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
sys.exit(0 if d.get('deferred') else 1)
PY
if [ $? -ne 0 ]; then exit 0; fi
if /usr/local/bin/docker ps --format '{{.Names}}' | grep -q '^dunhuang-pyramid-huge$'; then exit 0; fi
cd "$DH_DEPLOY_DIR" && /usr/local/bin/docker-compose up -d pyramid-huge >/dev/null 2>&1