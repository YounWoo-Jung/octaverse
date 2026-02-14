# OctaVerse 사용법

## 1. 위치와 실행 환경

작업 루트:

```bash
cd /home/hanul/workspace/python/octaverse
```

가상환경 활성화:

```bash
source .venv/bin/activate
```

가상환경 없이 실행할 때:

```bash
.venv/bin/python -m orchestrator --help
```

## 2. 기본 명령어

초기 폴더 구조 보장:

```bash
python -m orchestrator init
```

에픽 생성:

```bash
python -m orchestrator new-epic "에픽 제목"
```

단일 태스크 추가:

```bash
python -m orchestrator add-task "epic-001" "collector" "요구사항 수집"
```

역할 4개 태스크 일괄 추가:

```bash
python -m orchestrator add-role-tasks "epic-001" "구현 작업"
```

에픽 상태 확인:

```bash
python -m orchestrator status "epic-001"
```

라운드 실행(대기 없이 즉시 시뮬레이션):

```bash
python -m orchestrator run "epic-001" --hours 8
```

## 3. 역할(role) 규칙

허용 role:

- `collector`
- `detection`
- `backend`
- `qa`

이 외 role 입력 시 에러가 발생합니다.

## 4. 상태 파일 구조

에픽 디렉터리:

```text
epics/<epic_id>/
```

에픽 메타데이터:

```text
epics/<epic_id>/epic.json
```

태스크 파일(태스크 1개 = JSON 1개):

```text
epics/<epic_id>/tasks/task-XXX.json
```

이벤트 로그(NDJSON):

```text
epics/<epic_id>/events.ndjson
```

## 5. 권장 작업 순서

1. `init` 실행
2. `new-epic`으로 에픽 생성
3. `add-role-tasks` 또는 `add-task`로 태스크 등록
4. `run --hours N` 실행
5. `status`로 결과 확인
6. 필요 시 3~5 반복

## 6. 빠른 시작 예시

```bash
cd /home/hanul/workspace/python/octaverse
source .venv/bin/activate

python -m orchestrator init
python -m orchestrator new-epic "로그인 기능 개발"
python -m orchestrator add-role-tasks epic-002 "1차 구현"
python -m orchestrator run epic-002 --hours 4
python -m orchestrator status epic-002
```

## 7. 로그 확인

최근 이벤트 20줄:

```bash
tail -n 20 epics/epic-001/events.ndjson
```

태스크 파일 목록:

```bash
ls -1 epics/epic-001/tasks
```

## 8. 오류 처리 기준

- 에픽이 없으면 `epic not found` 에러를 반환합니다.
- role이 잘못되면 허용 role 목록과 함께 에러를 반환합니다.
- `run`은 최소 1라운드 실행됩니다.
