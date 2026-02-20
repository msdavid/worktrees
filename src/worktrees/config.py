"""Configuration constants and project config for worktree CLI."""

import json
from dataclasses import dataclass, field
from pathlib import Path

WORKTREES_JSON = ".worktrees.json"

# Default setup commands to run based on project detection
DEFAULT_SETUP_COMMANDS: dict[str, list[str]] = {
    "pyproject.toml": ["uv sync"],
    "package.json": ["npm install"],
    "Cargo.toml": ["cargo build"],
    "go.mod": ["go mod download"],
}


@dataclass
class WorktreesConfig:
    """Project-level worktrees configuration from .worktrees.json."""

    version: str = "1.0"
    worktrees_dir: Path = field(default_factory=lambda: Path("."))
    setup_auto_detect: bool = True
    setup_commands: list[str] = field(default_factory=list)
    project_root: Path = field(default_factory=Path.cwd)
    marks: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, project_root: Path) -> "WorktreesConfig | None":
        """Load from .worktrees.json, return None if not found."""
        config_path = project_root / WORKTREES_JSON

        if not config_path.exists():
            return None

        with open(config_path) as f:
            data = json.load(f)

        worktrees_dir_str = data.get("worktreesDir", ".")
        if worktrees_dir_str == ".":
            worktrees_dir = project_root
        else:
            worktrees_dir = Path(worktrees_dir_str).expanduser()

        setup = data.get("setup", {})
        marks = data.get("marks", {})

        return cls(
            version=data.get("version", "1.0"),
            worktrees_dir=worktrees_dir,
            setup_auto_detect=setup.get("autoDetect", True),
            setup_commands=setup.get("commands", []),
            project_root=project_root,
            marks=marks,
        )

    def save(self, project_root: Path | None = None) -> None:
        """Save to .worktrees.json."""
        root = project_root or self.project_root
        config_path = root / WORKTREES_JSON

        # Determine worktreesDir value for JSON
        if self.worktrees_dir == root:
            worktrees_dir_str = "."
        else:
            worktrees_dir_str = str(self.worktrees_dir)

        data = {
            "version": self.version,
            "worktreesDir": worktrees_dir_str,
            "setup": {
                "autoDetect": self.setup_auto_detect,
                "commands": self.setup_commands,
            },
            "marks": self.marks,
        }

        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    def get_worktree_path(self, name: str) -> Path:
        """Get absolute path for a worktree directory."""
        return self.worktrees_dir / name

    def get_setup_commands(self, worktree_path: Path) -> list[str]:
        """Get setup commands, auto-detecting if enabled."""
        if self.setup_commands:
            return self.setup_commands

        if not self.setup_auto_detect:
            return []

        commands = []
        for marker_file, cmds in DEFAULT_SETUP_COMMANDS.items():
            if (worktree_path / marker_file).exists():
                commands.extend(cmds)

        return commands

    def get_mark(self, worktree_name: str) -> str | None:
        """Get mark for a worktree."""
        mark = self.marks.get(worktree_name)
        # Handle legacy list format (convert to string)
        if isinstance(mark, list):
            return ", ".join(mark) if mark else None
        return mark

    def set_mark(self, worktree_name: str, mark: str) -> None:
        """Set the mark for a worktree (replaces any existing mark)."""
        self.marks[worktree_name] = mark

    def clear_mark(self, worktree_name: str) -> bool:
        """Clear mark from a worktree. Returns True if had a mark."""
        if worktree_name in self.marks:
            del self.marks[worktree_name]
            return True
        return False


def find_project_root() -> Path | None:
    """Find project root by looking for .worktrees.json.

    Search order:
    1. Current directory for .worktrees.json
    2. Parent directories for .worktrees.json
    3. Return None if not found (not initialized)
    """
    cwd = Path.cwd()

    # Check current directory
    if (cwd / WORKTREES_JSON).exists():
        return cwd

    # Check parent directories
    for parent in cwd.parents:
        if (parent / WORKTREES_JSON).exists():
            return parent

    return None


@dataclass
class WorktreeConfig:
    """Legacy configuration for worktree creation (deprecated)."""

    setup_commands: list[str] = field(default_factory=list)
    auto_detect_setup: bool = True

    def get_setup_commands(self, repo_root: Path) -> list[str]:
        """Get setup commands, auto-detecting if enabled."""
        if self.setup_commands:
            return self.setup_commands

        if not self.auto_detect_setup:
            return []

        commands = []
        for marker_file, cmds in DEFAULT_SETUP_COMMANDS.items():
            if (repo_root / marker_file).exists():
                commands.extend(cmds)

        return commands
