# OctaVerse 오케스트레이터

파일시스템 상태 저장을 사용하는 최소 오케스트레이션 스켈레톤입니다.

## 명령어

```bash
python -m orchestrator init
python -m orchestrator new-epic "<title>"
python -m orchestrator add-task "<epic_id>" "<role>" "<title>"
python -m orchestrator add-role-tasks "<epic_id>" "<title>"
python -m orchestrator status "<epic_id>"
python -m orchestrator run "<epic_id>" --hours 8
```

## 기본 규칙

- `octaverse/` 디렉터리에서 명령을 실행합니다.
- 현재 작업 디렉터리를 상태 루트로 사용합니다.
- 에픽은 `epics/<epic_id>/`에 저장됩니다.
- 태스크는 `epics/<epic_id>/tasks/`의 JSON 파일 1개 단위입니다.
- 이벤트 로그는 `epics/<epic_id>/events.ndjson`에 누적됩니다.
- 역할은 `collector`, `detection`, `backend`, `qa`만 사용합니다.

## 동작 흐름

1. `init`: 필수 폴더를 생성합니다.
2. `new-epic`: `epic-XXX`와 메타데이터를 만듭니다.
3. `add-task`: 태스크 JSON 파일 1개를 추가합니다.
4. `add-role-tasks`: 역할 4개 태스크를 한 번에 추가합니다.
5. `run`: N시간 기준 라운드를 즉시 시뮬레이션합니다(대기 없음).
6. `status`: 에픽/태스크 상태를 출력합니다.
