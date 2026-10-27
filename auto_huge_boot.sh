#!/bin/sh
case "$1" in
  start)
    if ! ps -ef 2>/dev/null | grep -v grep | grep -q auto_huge_daemon.sh; then
      nohup /srv/example/viewer/auto_huge_daemon.sh >/dev/null 2>&1 &
    fi
    ;;
  stop)
    for p in $(ps -ef 2>/dev/null | grep -v grep | grep auto_huge_daemon.sh | awk '{print $2}'); do kill $p 2>/dev/null; done
    ;;
esac
exit 0