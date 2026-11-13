#!/bin/sh
# Remove Docker Desktop's hyperkit.pid when it does not name a running HyperKit.
# RyzenHV 0.7.8 cleans it only at boot; a stale file makes the next HyperKit exit with "Failed to set up pidfile".
for f in "$HOME"/Library/Containers/com.docker.docker/Data/vms/*/hyperkit.pid; do
  [ -f "$f" ] || continue
  pid="$(tr -dc '0-9' < "$f")"
  if [ -n "$pid" ] && ps -p "$pid" -o comm= 2>/dev/null | grep -q hyperkit; then continue; fi
  rm -f "$f" && echo "$(date '+%F %T') removed stale $f (pid ${pid:-none})"
done
