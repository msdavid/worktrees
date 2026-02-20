"""Global user configuration for worktrees.

Stored at ~/.config/worktrees/config.json, separate from project-level config.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

GLOBAL_CONFIG_DIR = Path.home() / ".config" / "worktrees"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.json"

DEFAULT_PROMPT = (
    "merge <target-branch> into <current-branch>. "
    "If there are conflicts work interactively with me to resolve "
    "by presenting the conflicts, the options and your suggestion. "
    "if merge is successful run `worktrees mark merged into <current-branch>`"
)

PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "claude": {
        "command": "~/.claude/local/claude",
        "invocation": '{command} "{prompt}"',
    },
    "gemini": {
        "command": "/home/mauro/.npm-global/bin/gemini",
        "invocation": '{command} -i "{prompt}"',
    },
}


@dataclass
class AIConfig:
    """AI assistant configuration."""

    provider: str = "claude"
    command: str = ""
    prompt: str = field(default_factory=lambda: DEFAULT_PROMPT)

    def get_effective_command(self) -> str:
        """Get the command, using provider default if not set."""
        if self.command:
            return self.command
        return PROVIDER_DEFAULTS.get(self.provider, {}).get("command", "")

    def get_invocation_pattern(self) -> str:
        """Get the invocation pattern for this provider."""
        return PROVIDER_DEFAULTS.get(self.provider, {}).get(
            "invocation", '{command} "{prompt}"'
        )

    def build_command(self, target_branch: str, current_branch: str) -> str:
        """Build the full command with substituted prompt."""
        # Substitute branch placeholders in prompt
        prompt = self.prompt.replace("<target-branch>", target_branch)
        prompt = prompt.replace("<current-branch>", current_branch)

        # Escape shell-sensitive characters for double-quoted strings
        # Order matters: escape backslashes first, then others
        prompt = prompt.replace("\\", "\\\\")
        prompt = prompt.replace('"', '\\"')
        prompt = prompt.replace("$", "\\$")
        prompt = prompt.replace("`", "\\`")

        # Expand ~ in command path
        command = str(Path(self.get_effective_command()).expanduser())

        # Build full invocation
        pattern = self.get_invocation_pattern()
        return pattern.format(command=command, prompt=prompt)


@dataclass
class UserConfig:
    """Global user configuration."""

    ai: AIConfig = field(default_factory=AIConfig)

    @classmethod
    def load(cls) -> "UserConfig":
        """Load config from ~/.config/worktrees/config.json.

        Returns default config if file doesn't exist.
        """
        if not GLOBAL_CONFIG_FILE.exists():
            return cls()

        try:
            with open(GLOBAL_CONFIG_FILE) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return cls()

        ai_data = data.get("ai", {})
        ai_config = AIConfig(
            provider=ai_data.get("provider", "claude"),
            command=ai_data.get("command", ""),
            prompt=ai_data.get("prompt", DEFAULT_PROMPT),
        )

        return cls(ai=ai_config)

    def save(self) -> None:
        """Save config to ~/.config/worktrees/config.json."""
        GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        data = {
            "ai": {
                "provider": self.ai.provider,
                "command": self.ai.command,
                "prompt": self.ai.prompt,
            }
        }

        with open(GLOBAL_CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    def is_configured(self) -> bool:
        """Check if AI config has been explicitly set."""
        return GLOBAL_CONFIG_FILE.exists()
