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

REQUIRE_DIR=require
WORKSPACE_DIR=workspace
LOG_DIR=logs
STATE_DIR=state
PLAN_DIR=plans
LOCK_FILE=$STATE_DIR/lock

mkdir -p "$REQUIRE_DIR" "$WORKSPACE_DIR" "$LOG_DIR" "$STATE_DIR" "$PLAN_DIR"

cleanup() { rm -f "$LOCK_FILE"; }
acquire_lock() {
  if (set -C; : > "$LOCK_FILE") 2>/dev/null; then
    printf '%s\n' "$$" > "$LOCK_FILE"
  else
    echo "runner already active: $LOCK_FILE exists" >&2
    exit 1
  fi
}
extract_task_id() {
  base=${1##*/}
  printf '%s' "$base" | sed -n 's/^\([0-9][0-9]*\).*/\1/p'
}

task_hash() {
  cksum "$1" | awk '{print $1":"$2}'
}

find_next_task() {
  for task in "$REQUIRE_DIR"/*.md; do
    [ -f "$task" ] || continue
    id=$(extract_task_id "$task")
    [ -n "$id" ] || continue

    done_file=$STATE_DIR/$id.done
    hash_file=$STATE_DIR/$id.hash
    current_hash=$(task_hash "$task")

    if [ -f "$done_file" ]; then
      if [ -f "$hash_file" ]; then
        saved_hash=$(cat "$hash_file")
        [ "$saved_hash" = "$current_hash" ] && continue
      else
        printf '%s\n' "$current_hash" > "$hash_file"
        continue
      fi
    fi

    printf '%s|%s|%s\n' "$id" "$task" "$current_hash"
  done | sort -t '|' -k1,1n -k2,2 | while IFS='|' read -r id task hash; do
    [ -n "$id" ] || continue
    printf '%s|%s|%s\n' "$id" "$task" "$hash"
    break
  done
}
run_task() {
  id=$1
  task=$2
  hash=$3
  log=$LOG_DIR/$id.log
  { printf '== task %s start ==\n' "$id"; printf 'requirement: %s\n' "$task"; } > "$log"
  if sh "$ROOT_DIR/agent.sh" "$task" "$id" >> "$log" 2>&1; then
    date '+%Y-%m-%d %H:%M:%S' > "$STATE_DIR/$id.done"
    printf '%s\n' "$hash" > "$STATE_DIR/$id.hash"
    printf '== task %s success ==\n' "$id" >> "$log"
  else
    printf '== task %s failed ==\n' "$id" >> "$log"
    echo "task $id failed. see $log" >&2
    exit 1
  fi
}

trap cleanup EXIT HUP INT TERM
acquire_lock
while :; do
  next=$(find_next_task || true)
  [ -n "$next" ] || break
  id=${next%%|*}
  rest=${next#*|}
  task=${rest%%|*}
  hash=${rest#*|}
  run_task "$id" "$task" "$hash"
done

echo "queue empty. done."
