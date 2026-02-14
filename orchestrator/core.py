from __future__ import annotations

import argparse
from pathlib import Path

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
    ]:
        p.mkdir(parents=True, exist_ok=True)


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
    counts = {"pending": 0, "in_progress": 0, "done": 0}
    for task in tasks:
        counts[task["status"]] = counts.get(task["status"], 0) + 1
    lines = [
        f"{epic['id']}: {epic['title']}",
        f"pending={counts.get('pending', 0)} in_progress={counts.get('in_progress', 0)} done={counts.get('done', 0)} total={len(tasks)}",
    ]
    for task in tasks:
        lines.append(f"- {task['id']} [{task['role']}] {task['status']} {task['title']}")
    return "\n".join(lines)


def run(root: Path, epic_id: str, hours: int) -> str:
    epic_dir = root / "epics" / epic_id
    if not epic_dir.exists():
        raise ValueError(f"epic not found: {epic_id}")
    tasks_dir = epic_dir / "tasks"
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
                {"ts": now_iso(), "type": "task_started", "round": r, "task_id": task["id"]},
            )
            task["status"] = "done"
            task["updated_at"] = now_iso()
            write_json(file, task)
            append_ndjson(
                epic_dir / "events.ndjson",
                {"ts": now_iso(), "type": "task_done", "round": r, "task_id": task["id"]},
            )
        else:
            append_ndjson(epic_dir / "events.ndjson", {"ts": now_iso(), "type": "idle", "round": r})
        append_ndjson(epic_dir / "events.ndjson", {"ts": now_iso(), "type": "round_end", "round": r})
    return status(root, epic_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orchestrator")
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

    p_run = sub.add_parser("run")
    p_run.add_argument("epic_id")
    p_run.add_argument("--hours", type=int, default=8)

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
        elif args.cmd == "run":
            print(run(root, args.epic_id, args.hours))
    except ValueError as e:
        print(f"error: {e}")
        return 2
    return 0
