from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .agent_runner import (
    AITool,
    AgentConfig,
    ExecutionResult,
    execute_task,
    detect_available_tool,
)
from .config import OrchestratorConfig, create_default_config, load_config
from .state import append_ndjson, list_json_files, now_iso, read_json, write_json

ROLES = {"collector", "detection", "backend", "qa"}


def init_workspace(root: Path) -> None:
    for p in [
        root / "agents" / "collector",
        root / "agents" / "detection",
        root / "agents" / "backend",
        root / "agents" / "qa",
        root / "shared",
        root / "epics",
        root / "dist" / "collector",
        root / "dist" / "detection",
        root / "dist" / "backend",
        root / "dist" / "qa",
    ]:
        p.mkdir(parents=True, exist_ok=True)

    # 기본 설정 파일 생성
    config_path = root / "orchestrator.json"
    if not config_path.exists():
        create_default_config(root)


def next_epic_id(epics_dir: Path) -> str:
    n = 0
    for p in epics_dir.iterdir() if epics_dir.exists() else []:
        if p.is_dir() and p.name.startswith("epic-"):
            try:
                n = max(n, int(p.name.split("-")[-1]))
            except ValueError:
                pass
    return f"epic-{n + 1:03d}"


def new_epic(root: Path, title: str) -> str:
    epics_dir = root / "epics"
    epics_dir.mkdir(parents=True, exist_ok=True)
    epic_id = next_epic_id(epics_dir)
    epic_dir = epics_dir / epic_id
    epic_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        epic_dir / "epic.json",
        {"id": epic_id, "title": title, "created_at": now_iso(), "status": "open"},
    )
    (epic_dir / "tasks").mkdir(parents=True, exist_ok=True)
    return epic_id


def next_task_id(tasks_dir: Path) -> str:
    n = 0
    for p in list_json_files(tasks_dir):
        if p.stem.startswith("task-"):
            try:
                n = max(n, int(p.stem.split("-")[-1]))
            except ValueError:
                pass
    return f"task-{n + 1:03d}"


def add_task(root: Path, epic_id: str, role: str, title: str) -> str:
    if role not in ROLES:
        raise ValueError(f"role must be one of: {', '.join(sorted(ROLES))}")
    epic_dir = root / "epics" / epic_id
    tasks_dir = epic_dir / "tasks"
    if not epic_dir.exists():
        raise ValueError(f"epic not found: {epic_id}")
    task_id = next_task_id(tasks_dir)
    task = {
        "id": task_id,
        "epic_id": epic_id,
        "role": role,
        "title": title,
        "status": "pending",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    write_json(tasks_dir / f"{task_id}.json", task)
    append_ndjson(
        epic_dir / "events.ndjson",
        {"ts": now_iso(), "type": "task_added", "task_id": task_id, "role": role, "title": title},
    )
    return task_id


def add_role_tasks(root: Path, epic_id: str, title: str) -> list[str]:
    ids = []
    for role in sorted(ROLES):
        ids.append(add_task(root, epic_id, role, f"{title} ({role})"))
    return ids


def load_tasks(epic_dir: Path) -> list[dict]:
    tasks = []
    for path in list_json_files(epic_dir / "tasks"):
        tasks.append(read_json(path))
    return tasks


def status(root: Path, epic_id: str) -> str:
    epic_dir = root / "epics" / epic_id
    if not epic_dir.exists():
        raise ValueError(f"epic not found: {epic_id}")
    epic = read_json(epic_dir / "epic.json")
    tasks = load_tasks(epic_dir)
    counts = {"pending": 0, "in_progress": 0, "done": 0, "failed": 0}
    for task in tasks:
        counts[task["status"]] = counts.get(task["status"], 0) + 1
    lines = [
        f"{epic['id']}: {epic['title']}",
        f"pending={counts.get('pending', 0)} in_progress={counts.get('in_progress', 0)} done={counts.get('done', 0)} failed={counts.get('failed', 0)} total={len(tasks)}",
    ]
    for task in tasks:
        lines.append(f"- {task['id']} [{task['role']}] {task['status']} {task['title']}")
    return "\n".join(lines)


def list_epics(root: Path) -> str:
    """모든 에픽 목록 조회"""
    epics_dir = root / "epics"
    if not epics_dir.exists():
        return "No epics found"

    epic_dirs = sorted(
        [p for p in epics_dir.iterdir() if p.is_dir() and p.name.startswith("epic-")]
    )

    if not epic_dirs:
        return "No epics found"

    lines = ["Epics:"]
    for epic_dir in epic_dirs:
        epic_file = epic_dir / "epic.json"
        if epic_file.exists():
            epic = read_json(epic_file)
            tasks = load_tasks(epic_dir)
            pending = sum(1 for t in tasks if t["status"] == "pending")
            done = sum(1 for t in tasks if t["status"] == "done")
            failed = sum(1 for t in tasks if t["status"] == "failed")
            status_str = f"pending={pending} done={done} failed={failed}"
            lines.append(f"  {epic['id']}: {epic['title']} ({status_str})")

    return "\n".join(lines)


def reset_task(root: Path, epic_id: str, task_id: str) -> str:
    """태스크 상태를 pending으로 초기화"""
    epic_dir = root / "epics" / epic_id
    if not epic_dir.exists():
        raise ValueError(f"epic not found: {epic_id}")

    task_file = epic_dir / "tasks" / f"{task_id}.json"
    if not task_file.exists():
        raise ValueError(f"task not found: {task_id}")

    task = read_json(task_file)
    old_status = task["status"]
    task["status"] = "pending"
    task["updated_at"] = now_iso()
    if "error" in task:
        del task["error"]
    write_json(task_file, task)

    append_ndjson(
        epic_dir / "events.ndjson",
        {
            "ts": now_iso(),
            "type": "task_reset",
            "task_id": task_id,
            "from_status": old_status,
            "to_status": "pending",
        },
    )

    return f"{task_id} reset from {old_status} to pending"


def retry_failed(root: Path, epic_id: str) -> str:
    """실패한 태스크를 모두 pending으로 변경"""
    epic_dir = root / "epics" / epic_id
    if not epic_dir.exists():
        raise ValueError(f"epic not found: {epic_id}")

    tasks = load_tasks(epic_dir)
    failed_tasks = [t for t in tasks if t["status"] == "failed"]

    if not failed_tasks:
        return "No failed tasks to retry"

    reset_ids = []
    for task in failed_tasks:
        task_id = task["id"]
        task_file = epic_dir / "tasks" / f"{task_id}.json"
        task["status"] = "pending"
        task["updated_at"] = now_iso()
        if "error" in task:
            del task["error"]
        write_json(task_file, task)
        reset_ids.append(task_id)

    append_ndjson(
        epic_dir / "events.ndjson",
        {
            "ts": now_iso(),
            "type": "retry_failed",
            "task_ids": reset_ids,
        },
    )

    return f"Reset {len(reset_ids)} failed tasks: {', '.join(reset_ids)}"


async def execute_single_task(
    root: Path,
    epic_dir: Path,
    task_file: Path,
    task: dict,
    config: OrchestratorConfig,
) -> ExecutionResult:
    """단일 태스크 실행"""
    epic = read_json(epic_dir / "epic.json")
    role = task["role"]

    # dist 디렉토리 준비
    dist_dir = root / config.dist_dir
    role_dist_dir = dist_dir / role
    role_dist_dir.mkdir(parents=True, exist_ok=True)

    # 에이전트 설정
    tool = config.get_tool_for_role(role)
    agent_config = AgentConfig(
        role=role,
        tool=tool,
        working_dir=root,
        dist_dir=dist_dir,
        timeout=config.task_timeout,
    )

    shared_dir = root / "shared"

    # 태스크 실행
    return await execute_task(task, epic, agent_config, shared_dir)


async def run_parallel(
    root: Path,
    epic_id: str,
    config: OrchestratorConfig,
) -> str:
    """태스크 병렬 실행"""
    epic_dir = root / "epics" / epic_id
    if not epic_dir.exists():
        raise ValueError(f"epic not found: {epic_id}")

    tasks_dir = epic_dir / "tasks"
    shared_dir = root / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)

    # 사용 가능한 AI 도구 확인
    available_tool = detect_available_tool()
    if available_tool is None:
        raise ValueError(
            "No AI CLI tool found. Please install 'claude' or 'codex' CLI."
        )

    # pending 태스크 수집
    pending_tasks = []
    for task_file in list_json_files(tasks_dir):
        task = read_json(task_file)
        if task["status"] == "pending":
            pending_tasks.append((task_file, task))

    if not pending_tasks:
        append_ndjson(
            epic_dir / "events.ndjson",
            {"ts": now_iso(), "type": "no_pending_tasks"},
        )
        return status(root, epic_id)

    append_ndjson(
        epic_dir / "events.ndjson",
        {
            "ts": now_iso(),
            "type": "run_start",
            "pending_count": len(pending_tasks),
            "max_parallel": config.max_parallel_tasks,
        },
    )

    # 세마포어로 동시 실행 수 제한
    semaphore = asyncio.Semaphore(config.max_parallel_tasks)

    async def run_with_semaphore(
        task_file: Path, task: dict
    ) -> tuple[dict, ExecutionResult]:
        async with semaphore:
            # 상태를 in_progress로 변경
            task["status"] = "in_progress"
            task["updated_at"] = now_iso()
            write_json(task_file, task)

            append_ndjson(
                epic_dir / "events.ndjson",
                {
                    "ts": now_iso(),
                    "type": "task_started",
                    "task_id": task["id"],
                    "role": task["role"],
                },
            )

            # 태스크 실행
            result = await execute_single_task(
                root, epic_dir, task_file, task, config
            )

            # 상태 업데이트
            new_status = "done" if result.success else "failed"
            task["status"] = new_status
            task["updated_at"] = now_iso()
            if not result.success:
                task["error"] = result.stderr
            write_json(task_file, task)

            append_ndjson(
                epic_dir / "events.ndjson",
                {
                    "ts": now_iso(),
                    "type": "task_done" if result.success else "task_failed",
                    "task_id": task["id"],
                    "role": task["role"],
                    "duration_seconds": result.duration_seconds,
                    "exit_code": result.exit_code,
                },
            )

            return task, result

    # 모든 pending 태스크 병렬 실행
    coroutines = [
        run_with_semaphore(task_file, task) for task_file, task in pending_tasks
    ]
    results = await asyncio.gather(*coroutines, return_exceptions=True)

    # 결과 요약
    success_count = sum(
        1 for r in results if isinstance(r, tuple) and r[1].success
    )
    failed_count = len(results) - success_count

    append_ndjson(
        epic_dir / "events.ndjson",
        {
            "ts": now_iso(),
            "type": "run_end",
            "success_count": success_count,
            "failed_count": failed_count,
        },
    )

    return status(root, epic_id)


async def run_sequential(
    root: Path,
    epic_id: str,
    hours: int,
    config: OrchestratorConfig,
) -> str:
    """태스크 순차 실행 (실제 AI CLI 호출)"""
    epic_dir = root / "epics" / epic_id
    if not epic_dir.exists():
        raise ValueError(f"epic not found: {epic_id}")
    tasks_dir = epic_dir / "tasks"
    shared_dir = root / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)

    # 사용 가능한 AI 도구 확인
    available_tool = detect_available_tool()
    if available_tool is None:
        raise ValueError(
            "No AI CLI tool found. Please install 'claude' or 'codex' CLI."
        )

    rounds = max(1, hours)
    for r in range(1, rounds + 1):
        append_ndjson(epic_dir / "events.ndjson", {"ts": now_iso(), "type": "round_start", "round": r})
        task_files = list_json_files(tasks_dir)
        pending = None
        for file in task_files:
            task = read_json(file)
            if task["status"] == "pending":
                pending = (file, task)
                break
        if pending:
            file, task = pending
            task["status"] = "in_progress"
            task["updated_at"] = now_iso()
            write_json(file, task)
            append_ndjson(
                epic_dir / "events.ndjson",
                {"ts": now_iso(), "type": "task_started", "round": r, "task_id": task["id"], "role": task["role"]},
            )

            # 실제 태스크 실행
            result = await execute_single_task(root, epic_dir, file, task, config)

            # 상태 업데이트
            new_status = "done" if result.success else "failed"
            task["status"] = new_status
            task["updated_at"] = now_iso()
            if not result.success:
                task["error"] = result.stderr
            write_json(file, task)

            append_ndjson(
                epic_dir / "events.ndjson",
                {
                    "ts": now_iso(),
                    "type": "task_done" if result.success else "task_failed",
                    "round": r,
                    "task_id": task["id"],
                    "role": task["role"],
                    "duration_seconds": result.duration_seconds,
                    "exit_code": result.exit_code,
                },
            )
        else:
            append_ndjson(epic_dir / "events.ndjson", {"ts": now_iso(), "type": "idle", "round": r})
        append_ndjson(epic_dir / "events.ndjson", {"ts": now_iso(), "type": "round_end", "round": r})
    return status(root, epic_id)


def run(root: Path, epic_id: str, hours: int, parallel: bool = True) -> str:
    """태스크 실행 (기존 동기 인터페이스 유지)"""
    config = load_config(root)

    if parallel:
        return asyncio.run(run_parallel(root, epic_id, config))
    else:
        return asyncio.run(run_sequential(root, epic_id, hours, config))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="octaverse")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")

    p_new = sub.add_parser("new-epic")
    p_new.add_argument("title")

    p_task = sub.add_parser("add-task")
    p_task.add_argument("epic_id")
    p_task.add_argument("role")
    p_task.add_argument("title")

    p_role_tasks = sub.add_parser("add-role-tasks")
    p_role_tasks.add_argument("epic_id")
    p_role_tasks.add_argument("title")

    p_status = sub.add_parser("status")
    p_status.add_argument("epic_id")

    sub.add_parser("list-epics")

    p_reset = sub.add_parser("reset-task")
    p_reset.add_argument("epic_id")
    p_reset.add_argument("task_id")

    p_retry = sub.add_parser("retry-failed")
    p_retry.add_argument("epic_id")

    p_run = sub.add_parser("run")
    p_run.add_argument("epic_id")
    p_run.add_argument("--hours", type=int, default=8, help="Hours for sequential mode (default: 8)")
    p_run.add_argument("--parallel", action="store_true", default=True, help="Run tasks in parallel (default)")
    p_run.add_argument("--sequential", action="store_true", help="Run tasks sequentially")

    p_config = sub.add_parser("config")
    p_config.add_argument("--tool", choices=["claude", "codex"], help="Default AI tool")
    p_config.add_argument("--max-parallel", type=int, help="Max parallel tasks")
    p_config.add_argument("--timeout", type=int, help="Task timeout in seconds")
    p_config.add_argument("--role-tool", nargs=2, metavar=("ROLE", "TOOL"), action="append", help="Set tool for specific role (e.g., --role-tool collector codex)")
    p_config.add_argument("--show", action="store_true", help="Show current config")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path.cwd()
    try:
        if args.cmd == "init":
            init_workspace(root)
            print("initialized")
        elif args.cmd == "new-epic":
            print(new_epic(root, args.title))
        elif args.cmd == "add-task":
            print(add_task(root, args.epic_id, args.role, args.title))
        elif args.cmd == "add-role-tasks":
            print("\n".join(add_role_tasks(root, args.epic_id, args.title)))
        elif args.cmd == "status":
            print(status(root, args.epic_id))
        elif args.cmd == "list-epics":
            print(list_epics(root))
        elif args.cmd == "reset-task":
            print(reset_task(root, args.epic_id, args.task_id))
        elif args.cmd == "retry-failed":
            print(retry_failed(root, args.epic_id))
        elif args.cmd == "run":
            parallel = not args.sequential
            print(run(root, args.epic_id, args.hours, parallel=parallel))
        elif args.cmd == "config":
            if args.show:
                config = load_config(root)
                print("Current configuration:")
                for k, v in config.to_dict().items():
                    print(f"  {k}: {v}")
            else:
                config = load_config(root)
                if args.tool:
                    config.default_tool = AITool(args.tool)
                if args.max_parallel:
                    config.max_parallel_tasks = args.max_parallel
                if args.timeout:
                    config.task_timeout = args.timeout
                if args.role_tool:
                    for role, tool in args.role_tool:
                        if role not in ROLES:
                            print(f"error: invalid role '{role}'. Must be one of: {', '.join(sorted(ROLES))}")
                            return 2
                        config.role_tools[role] = AITool(tool)
                from .config import save_config
                save_config(root, config)
                print("Configuration updated")
    except ValueError as e:
        print(f"error: {e}")
        return 2
    return 0
