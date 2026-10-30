#!/bin/sh
: "${DH_DEPLOY_DIR:?Set DH_DEPLOY_DIR}"
: "${DH_HOST_DATA_DIR:?Set DH_HOST_DATA_DIR}"
: "${DH_HOST_CACHE_DIR:?Set DH_HOST_CACHE_DIR}"
case "$1" in
  start)
    if ! ps -ef 2>/dev/null | grep -v grep | grep -q auto_huge_daemon.sh; then
      nohup "$DH_DEPLOY_DIR/auto_huge_daemon.sh" >/dev/null 2>&1 &
    fi
    ;;
  stop)
    for p in $(ps -ef 2>/dev/null | grep -v grep | grep auto_huge_daemon.sh | awk '{print $2}'); do kill $p 2>/dev/null; done
    ;;
esac
exit 0