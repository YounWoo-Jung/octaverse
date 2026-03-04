## AI Work Summary (2026-03-05)

### What was done
- daemon 실행용 `octaverse.sh`를 추가했다.
- 동기화 실행용 `sync.sh`를 추가했다.
- 설정 파일 `conf/octaverse.conf`를 추가했다.
- `runner.sh`에 설정 로드와 task hash 추적(`state/<id>.hash`)을 반영했다.
- `agent.sh`에 설정 로드 루틴을 반영했다.
- `README.md`를 daemon/config/sync/git push 정책 기준으로 업데이트했다.

### Key Decisions
- 기존 구조(`runner.sh` 중심 처리)는 유지하고 daemon/sync만 외곽에 추가했다.
- POSIX sh 호환을 위해 `cksum`, `awk`, 표준 쉘 문법만 사용했다.
- REQUIRE_REPO 미설정 상태의 로컬 `require/`는 sync에서 pull을 생략하고 runner를 실행하도록 처리했다.

### Modified Files
- README.md
- runner.sh
- agent.sh
- sync.sh
- octaverse.sh
- conf/octaverse.conf
- MEMORY.md
- MISTAKE.md
- SUMMARY.md

### Notes
- daemon 로그는 `./octaverse.sh >> daemon.log 2>&1` 형태로 리다이렉트 가능하다.
- 자동 push는 수행하지 않는다.

## AI Work Summary (2026-03-05)

### What was done
- 저장소 루트에 `.gitignore`를 추가했다.
- 런타임/생성 산출물(`logs/`, `state/`, `workspace/`, `*.log`)이 추적되지 않도록 설정했다.

### Key Decisions
- 현재 스크립트 동작에 영향 없는 최소 ignore 규칙만 추가했다.
- 소스/설정 파일(`*.sh`, `conf/`, `require/`, `plans/`)은 ignore 대상에 포함하지 않았다.

### Modified Files
- .gitignore
- SUMMARY.md

### Notes
- 기존 실행 방식(`./octaverse.sh >> daemon.log 2>&1`)과 호환되도록 `*.log`를 함께 무시한다.
