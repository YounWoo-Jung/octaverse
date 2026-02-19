# Octaverse

AI Orchestration CLI Tool - Parallel execution with Claude Code CLI or Codex CLI.

## Installation

```bash
pip install octaverse
```

## Usage

```bash
# Initialize workspace
octaverse init

# Create a new epic
octaverse new-epic "My Project"

# Add tasks
octaverse add-task epic-001 collector "Data collection task"
octaverse add-role-tasks epic-001 "Feature implementation"

# Check status
octaverse status epic-001

# Run tasks (parallel mode)
octaverse run epic-001

# Run tasks (sequential mode)
octaverse run epic-001 --sequential

# Configure
octaverse config --show
octaverse config --tool claude --max-parallel 4
```

## License

MIT
