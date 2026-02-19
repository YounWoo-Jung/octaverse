"""오케스트레이터 설정 관리"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .agent_runner import AITool


@dataclass
class OrchestratorConfig:
    """오케스트레이터 전역 설정"""

    # 기본 AI 도구 (claude 또는 codex)
    default_tool: AITool = AITool.CLAUDE

    # 역할별 도구 매핑 (지정하지 않으면 default_tool 사용)
    role_tools: dict[str, AITool] = field(default_factory=dict)

    # 병렬 실행 시 최대 동시 작업 수
    max_parallel_tasks: int = 4

    # 태스크 타임아웃 (초)
    task_timeout: int = 600

    # 결과물 출력 디렉토리
    dist_dir: str = "dist"

    @classmethod
    def from_dict(cls, data: dict) -> "OrchestratorConfig":
        """딕셔너리에서 설정 생성"""
        default_tool = AITool(data.get("default_tool", "claude"))

        role_tools = {}
        for role, tool_name in data.get("role_tools", {}).items():
            role_tools[role] = AITool(tool_name)

        return cls(
            default_tool=default_tool,
            role_tools=role_tools,
            max_parallel_tasks=data.get("max_parallel_tasks", 4),
            task_timeout=data.get("task_timeout", 600),
            dist_dir=data.get("dist_dir", "dist"),
        )

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            "default_tool": self.default_tool.value,
            "role_tools": {k: v.value for k, v in self.role_tools.items()},
            "max_parallel_tasks": self.max_parallel_tasks,
            "task_timeout": self.task_timeout,
            "dist_dir": self.dist_dir,
        }

    def get_tool_for_role(self, role: str) -> AITool:
        """역할에 맞는 도구 반환"""
        return self.role_tools.get(role, self.default_tool)


def load_config(root: Path) -> OrchestratorConfig:
    """프로젝트 루트에서 설정 로드"""
    import json

    config_path = root / "orchestrator.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            return OrchestratorConfig.from_dict(data)
        except Exception:
            pass

    return OrchestratorConfig()


def save_config(root: Path, config: OrchestratorConfig) -> None:
    """설정 저장"""
    import json

    config_path = root / "orchestrator.json"
    config_path.write_text(
        json.dumps(config.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )


def create_default_config(root: Path) -> None:
    """기본 설정 파일 생성"""
    config = OrchestratorConfig(
        default_tool=AITool.CLAUDE,
        role_tools={},
        max_parallel_tasks=4,
        task_timeout=600,
        dist_dir="dist",
    )
    save_config(root, config)
