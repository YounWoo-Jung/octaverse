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

[ "$#" -ge 1 ] || { echo "usage: ./agent.sh <requirement.md> [task-id]" >&2; exit 1; }
TASK_FILE=$1
[ -f "$TASK_FILE" ] || { echo "error: requirement file not found: $TASK_FILE" >&2; exit 1; }
TASK_ID=${2:-$(basename "$TASK_FILE" | sed -n 's/^\([0-9][0-9]*\).*/\1/p')}
[ -n "$TASK_ID" ] || { echo "error: cannot infer task id from $TASK_FILE" >&2; exit 1; }

MAX_ITERATIONS=${MAX_ITERATIONS:-6}
WORKSPACE_DIR=$ROOT_DIR/workspace
PLAN_FILE=$ROOT_DIR/plans/${TASK_ID}-plan.md
mkdir -p "$WORKSPACE_DIR" "$ROOT_DIR/plans" "$ROOT_DIR/logs" "$ROOT_DIR/state"

ENGINE=
ENGINE_MODE=
read_requirement() { cat "$TASK_FILE"; }

detect_engine() {
  if command -v claude >/dev/null 2>&1; then
    ENGINE=claude
    if claude --help 2>&1 | grep -q -- '--print'; then ENGINE_MODE=print
    elif claude --help 2>&1 | grep -q -- ' -p'; then ENGINE_MODE=prompt
    else ENGINE_MODE=plain; fi
    return 0
  fi
  if command -v codex >/dev/null 2>&1; then
    ENGINE=codex
    if codex --help 2>&1 | grep -q -- ' exec'; then ENGINE_MODE=exec
    elif codex --help 2>&1 | grep -q -- ' -p'; then ENGINE_MODE=prompt
    else ENGINE_MODE=plain; fi
    return 0
  fi
  echo "error: no AI engine found. install claude or codex." >&2
  exit 1
}

run_ai() {
  prompt=$1
  case "$ENGINE:$ENGINE_MODE" in
    claude:print) claude --print "$prompt" ;;
    claude:prompt) claude -p "$prompt" ;;
    claude:plain) claude "$prompt" ;;
    codex:exec) codex exec "$prompt" ;;
    codex:prompt) codex -p "$prompt" ;;
    codex:plain) codex "$prompt" ;;
    *) echo "error: unknown engine mode: $ENGINE:$ENGINE_MODE" >&2; return 1 ;;
  esac
}

create_fallback_plan() {
  cat > "$PLAN_FILE" <<EOF
## Architecture Outline
- \`$TASK_FILE\` 분석 후 \`workspace/\` 내부에서만 구현합니다.
- 최소 변경으로 테스트 통과를 목표로 반복합니다.

## Files to Create
- workspace/ 하위 구현 파일
- workspace/ 하위 테스트 파일

## Tests to Implement
- 프로젝트 성격에 맞는 테스트를 추가/수정합니다.

## Potential Risks
- 테스트 도구 부재 시 검증이 제한될 수 있습니다.
- AI CLI 호출 옵션 차이로 실패할 수 있습니다.
EOF
}

create_plan() {
  tmp_plan=$(mktemp)
  prompt=$(cat <<EOF
Create markdown plan for task $TASK_ID.
Use sections exactly:
## Architecture Outline
## Files to Create
## Tests to Implement
## Potential Risks
Rules: concise, actionable, minimal edits, code changes only in workspace/.

Requirement:
$(read_requirement)
EOF
)
  if run_ai "$prompt" > "$tmp_plan" 2>/dev/null && [ -s "$tmp_plan" ]; then
    mv "$tmp_plan" "$PLAN_FILE"
  else
    rm -f "$tmp_plan"
    create_fallback_plan
  fi
}

run_tests() {
  if command -v npm >/dev/null 2>&1 && [ -f "$WORKSPACE_DIR/package.json" ]; then
    (cd "$WORKSPACE_DIR" && npm test); return $?
  fi
  if command -v pytest >/dev/null 2>&1 && [ -d "$WORKSPACE_DIR/tests" ]; then
    (cd "$WORKSPACE_DIR" && pytest); return $?
  fi
  if command -v go >/dev/null 2>&1 && [ -f "$WORKSPACE_DIR/go.mod" ]; then
    (cd "$WORKSPACE_DIR" && go test ./...); return $?
  fi
  if command -v make >/dev/null 2>&1 && [ -f "$WORKSPACE_DIR/Makefile" ]; then
    (cd "$WORKSPACE_DIR" && make test); return $?
  fi
  echo "No runnable test command detected in workspace/; treating as pass."
  return 0
}

detect_engine
echo "engine: $ENGINE ($ENGINE_MODE)"
create_plan
echo "plan: $PLAN_FILE"

iteration=1
last_test_output=
while [ "$iteration" -le "$MAX_ITERATIONS" ]; do
  echo "== iteration $iteration/$MAX_ITERATIONS =="

  reason_prompt=$(cat <<EOF
REASON step for task $TASK_ID.
Summarize next changes in <=8 bullets.

Requirement:
$(read_requirement)

Plan:
$(cat "$PLAN_FILE")
EOF
)
  run_ai "$reason_prompt" || true

  act_prompt=$(cat <<EOF
ACT step for task $TASK_ID.
Implement now.
Rules:
- edit only workspace/
- minimal edits
- do not touch require/, state/, logs/, plans/
- add/update tests if needed

Requirement:
$(read_requirement)

Plan:
$(cat "$PLAN_FILE")

Previous test feedback:
$last_test_output
EOF
)
  run_ai "$act_prompt"

  test_output_file=$(mktemp)
  if run_tests > "$test_output_file" 2>&1; then
    cat "$test_output_file"
    rm -f "$test_output_file"
    echo "tests passed."
    exit 0
  fi

  cat "$test_output_file"
  last_test_output=$(sed -n '1,200p' "$test_output_file")
  rm -f "$test_output_file"

  if [ "$iteration" -lt "$MAX_ITERATIONS" ]; then
    feedback_prompt=$(cat <<EOF
FEEDBACK step for task $TASK_ID.
Tests failed. Fix with minimal edits in workspace/ only.

Requirement:
$(read_requirement)

Plan:
$(cat "$PLAN_FILE")

Test output:
$last_test_output
EOF
)
    run_ai "$feedback_prompt" || true
  fi

  iteration=$((iteration + 1))
done

echo "error: max iteration reached ($MAX_ITERATIONS) without passing tests" >&2
exit 1
