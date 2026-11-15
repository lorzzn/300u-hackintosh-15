#!/bin/sh
# Docker's system helper creates this link before the user socket starts listening.
socket_link="${DOCKER_SOCKET_LINK:-/var/run/docker.sock}"
expected_target="$HOME/.docker/run/docker.sock"
waited=0

until [ -L "$socket_link" ] &&
      [ "$(readlink "$socket_link" 2>/dev/null)" = "$expected_target" ]; do
  if [ $((waited % 60)) -eq 0 ]; then
    printf '%s waiting for %s -> %s\n' \
      "$(date '+%F %T')" "$socket_link" "$expected_target"
  fi
  sleep 2
  waited=$((waited + 2))
done

printf '%s default Docker socket link ready, opening Docker\n' "$(date '+%F %T')"
exec open -g -a Docker
