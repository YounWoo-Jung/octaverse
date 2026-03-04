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

ensure_require_repo() {
  if [ ! -d "$ROOT_DIR/require" ]; then
    [ -n "$REQUIRE_REPO" ] || {
      echo "error: require/ is missing and REQUIRE_REPO is empty" >&2
      return 1
    }
    git clone "$REQUIRE_REPO" "$ROOT_DIR/require"
    return 0
  fi

  if [ -d "$ROOT_DIR/require/.git" ]; then
    (cd "$ROOT_DIR/require" && git pull --ff-only)
    return 0
  fi

  if [ -n "$REQUIRE_REPO" ]; then
    echo "error: require/ exists but is not a git repository" >&2
    return 1
  fi

  echo "require/ is local (non-git). skip git pull."
  return 0
}

echo "[sync] start"
ensure_require_repo
sh "$ROOT_DIR/runner.sh"
echo "[sync] done"
