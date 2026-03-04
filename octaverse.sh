#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
cd "$ROOT_DIR"

CONF_FILE=$ROOT_DIR/conf/octaverse.conf
SYNC_INTERVAL=${SYNC_INTERVAL:-60}
REQUIRE_REPO=${REQUIRE_REPO:-}
[ -f "$CONF_FILE" ] && . "$CONF_FILE"
SYNC_INTERVAL=${SYNC_INTERVAL:-60}
REQUIRE_REPO=${REQUIRE_REPO:-}

while :; do
  if ! sh "$ROOT_DIR/sync.sh"; then
    echo "[daemon] sync failed"
  fi
  sleep "$SYNC_INTERVAL"
done
