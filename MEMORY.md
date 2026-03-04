# Project Memory

## Core Principles
- Convention over Configuration
- Simple is Best
- POSIX sh only
- Linux/macOS portable scripts

## Architecture Decisions
- runner.sh는 require/*.md를 숫자 ID 순서로 순차 처리한다.
- agent.sh는 AI CLI(claude 우선, codex 차순) 기반 반복 루프를 수행한다.
- sync.sh는 설정 로드 후 require 저장소 동기화와 runner 실행을 담당한다.
- octaverse.sh는 sync.sh를 주기적으로 호출하는 daemon 루프를 담당한다.

## Constraints
- 코드 자동 push 금지(수동 검토/commit/push).
- 작업 코드 변경은 workspace/ 중심으로 수행한다.
- state/lock으로 동시 runner 실행을 방지한다.

## Important State
- 설정 파일: conf/octaverse.conf
- 기본 SYNC_INTERVAL=60
- REQUIRE_REPO 미설정 시 sync.sh는 로컬 non-git require/에서 pull을 생략한다.

## Open Threads
- 없음
