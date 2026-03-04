# octaverse v1

octaverse는 `require/`의 마크다운 요구사항 파일을 순차 처리하는 최소 자율 개발 러너입니다.

## 목적
- 요구사항 큐를 파일시스템 기준으로 순차 실행
- AI CLI(claude/codex) 기반 코드 생성 루프 실행
- 테스트 통과 시 완료 마킹

## 디렉터리 구조
```
octaverse/
├── conf/
│   └── octaverse.conf    # 런타임 설정(REQUIRE_REPO, SYNC_INTERVAL)
├── require/              # 작업 큐: <id>-*.md
├── workspace/            # 실제 코드 작업 디렉터리
├── logs/                 # 실행 로그: logs/<id>.log
├── state/                # 상태 파일: <id>.done, <id>.hash, lock
├── plans/                # 계획 파일: plans/<id>-plan.md
├── runner.sh             # 순차 실행 러너
├── sync.sh               # require 동기화 + runner 실행
├── octaverse.sh          # 데몬 실행 루프
├── agent.sh              # 단일 작업 처리 에이전트
└── README.md
```

## 실행 방법
1. `require/`에 요구사항 파일을 추가합니다. (예: `001-auth.md`, `002-user-api.md`)
2. 실행 권한을 설정합니다.
   ```sh
   chmod +x runner.sh agent.sh sync.sh octaverse.sh
   ```
3. 단발 실행:
   ```sh
   ./runner.sh
   ```

## 동작 규칙
- 실행 순서: 파일명 숫자 ID 오름차순 (`001`, `002`, `010`)
- 완료 마킹: `state/<id>.done`
- 중복 실행 방지: `state/lock`
- 요구사항 변경 추적: `state/<id>.hash` (동일 해시 재실행 방지)
- 로그 기록: `logs/<id>.log`
- 계획 파일 생성: `plans/<id>-plan.md`

## Daemon Mode
cron 없이 상시 실행하려면 아래 명령을 사용합니다.
```sh
./octaverse.sh
```

출력은 표준 출력/표준 에러로 나오므로 파일로 리다이렉트할 수 있습니다.
```sh
./octaverse.sh >> daemon.log 2>&1
```

루프 동작:
1. `sync.sh` 실행
2. `SYNC_INTERVAL` 초 sleep
3. 반복

## 설정 파일
설정 파일 경로:
- `conf/octaverse.conf`

기본 예시:
```sh
REQUIRE_REPO=https://github.com/org/octaverse-require.git
SYNC_INTERVAL=60
```

- `REQUIRE_REPO`: requirement 저장소 Git URL
- `SYNC_INTERVAL`: daemon 폴링 주기(초), 기본 60

`sync.sh` 동작:
1. 설정 로드
2. `require/` 확인 (없으면 `REQUIRE_REPO`로 clone)
3. git 저장소인 경우 `require/`에서 `git pull --ff-only` 수행
4. `runner.sh` 실행

`REQUIRE_REPO`를 사용하지 않고 수동으로 `require/`를 관리하려면 `sync.sh` 대신 `runner.sh`를 직접 실행합니다.

## agent 루프
`agent.sh`는 다음 단계를 반복합니다.
1. Reason: 요구사항 분석
2. Plan: 계획 파일 생성
3. Act: 코드 생성/수정
4. Learn: 테스트 실행
5. Feedback: 실패 시 수정

종료 조건:
- 테스트 통과
- 최대 반복 수 도달 (기본 6회)

## 테스트 명령 탐지 순서
`workspace/` 기준으로 아래 순서로 시도합니다.
1. `npm test`
2. `pytest`
3. `go test ./...`
4. `make test`

실행 가능한 테스트가 없으면 통과로 처리합니다.

## Git Push 정책
octaverse는 코드 변경을 자동 push 하지 않습니다.

개발자가 직접 검토 후 수동으로 실행해야 합니다.
```sh
git add .
git commit -m "..."
git push
```

## 예시 워크플로
1. `require/001-auth.md` 작성 또는 `REQUIRE_REPO` 설정
2. `./octaverse.sh` 또는 `./sync.sh` 실행
3. `logs/001.log`, `plans/001-plan.md`, `state/001.done` 확인
4. 변경 검토 후 수동으로 commit/push
