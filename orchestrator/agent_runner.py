"""AI CLI 도구 실행기 - Claude Code CLI, Codex CLI 등을 실행"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class AITool(Enum):
    CLAUDE = "claude"
    CODEX = "codex"


@dataclass
class AgentConfig:
    """에이전트 설정"""

    role: str
    tool: AITool
    working_dir: Path  # 프로젝트 루트
    dist_dir: Path  # 결과물 출력 디렉토리 (dist/)
    timeout: int = 600  # 10분 기본 타임아웃

    @property
    def output_dir(self) -> Path:
        """역할별 출력 디렉토리 (dist/{role}/)"""
        return self.dist_dir / self.role


@dataclass
class ExecutionResult:
    """실행 결과"""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float


def detect_available_tool() -> AITool | None:
    """사용 가능한 AI CLI 도구 감지"""
    if shutil.which("claude"):
        return AITool.CLAUDE
    if shutil.which("codex"):
        return AITool.CODEX
    return None


def build_prompt(task: dict, epic: dict, output_dir: Path, shared_dir: Path | None = None) -> str:
    """태스크 실행을 위한 프롬프트 생성"""
    role = task["role"]
    title = task["title"]
    epic_title = epic.get("title", "")

    role_contexts = {
        "collector": """당신은 데이터 수집 및 분석 전문가입니다.
- 시장 조사, 경쟁사 분석, 요구사항 수집을 담당
- 체계적인 문서화와 명확한 정리가 필요""",
        "detection": """당신은 보안 탐지 규칙 및 위협 탐지 전문가입니다.
- 탐지 로직, 규칙 작성, MITRE ATT&CK 매핑을 담당
- SIEM/EDR/XDR 탐지 규칙 개발""",
        "backend": """당신은 백엔드 시스템 설계 및 개발 전문가입니다.
- 시스템 아키텍처, API 설계, 데이터베이스 설계를 담당
- 확장 가능하고 유지보수가 쉬운 코드 작성""",
        "qa": """당신은 QA 및 테스트 전문가입니다.
- 테스트 계획, 품질 기준 정의, 리스크 분석을 담당
- DoD(Definition of Done) 및 검증 체크리스트 작성""",
    }

    context = role_contexts.get(role, "")
    prompt_parts = [
        f"# 에픽: {epic_title}",
        f"# 당신의 역할: {role}",
        "",
        context,
        "",
        f"## 수행할 작업: {title}",
        "",
        f"## 결과물 출력 디렉토리: {output_dir}",
        "모든 결과물은 위 디렉토리에 저장하세요.",
        "",
    ]

    if shared_dir and shared_dir.exists():
        prompt_parts.append("## 공유 자료 (shared/ 디렉토리의 관련 파일들을 참고하세요)")
        prompt_parts.append(f"공유 디렉토리 경로: {shared_dir}")
        prompt_parts.append("")

    prompt_parts.extend([
        "## 작업 지시",
        "위 작업을 수행하고 결과를 지정된 출력 디렉토리에 저장하세요.",
        "필요한 경우 shared/ 디렉토리에 공유할 자료를 작성하세요.",
        "",
        "완료 후 간단한 요약을 출력하세요.",
    ])

    return "\n".join(prompt_parts)


async def run_claude_cli(
    prompt: str,
    working_dir: Path,
    timeout: int = 600,
) -> ExecutionResult:
    """Claude Code CLI 실행"""
    import time

    start = time.time()
    cmd = ["claude"]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(working_dir),
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=prompt.encode("utf-8")),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Timeout after {timeout} seconds",
                duration_seconds=time.time() - start,
            )

        duration = time.time() - start
        return ExecutionResult(
            success=proc.returncode == 0,
            exit_code=proc.returncode or 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            duration_seconds=duration,
        )
    except Exception as e:
        return ExecutionResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr=str(e),
            duration_seconds=time.time() - start,
        )


async def run_codex_cli(
    prompt: str,
    working_dir: Path,
    timeout: int = 600,
) -> ExecutionResult:
    """Codex CLI 실행"""
    import time

    start = time.time()
    cmd = ["codex", prompt]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(working_dir),
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Timeout after {timeout} seconds",
                duration_seconds=time.time() - start,
            )

        duration = time.time() - start
        return ExecutionResult(
            success=proc.returncode == 0,
            exit_code=proc.returncode or 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            duration_seconds=duration,
        )
    except Exception as e:
        return ExecutionResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr=str(e),
            duration_seconds=time.time() - start,
        )


async def execute_task(
    task: dict,
    epic: dict,
    config: AgentConfig,
    shared_dir: Path,
) -> ExecutionResult:
    """태스크 실행"""
    # 출력 디렉토리 준비
    config.output_dir.mkdir(parents=True, exist_ok=True)

    prompt = build_prompt(task, epic, config.output_dir, shared_dir)

    if config.tool == AITool.CLAUDE:
        return await run_claude_cli(prompt, config.working_dir, config.timeout)
    elif config.tool == AITool.CODEX:
        return await run_codex_cli(prompt, config.working_dir, config.timeout)
    else:
        return ExecutionResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr=f"Unsupported tool: {config.tool}",
            duration_seconds=0,
        )
