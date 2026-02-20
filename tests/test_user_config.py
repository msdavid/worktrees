"""Tests for user_config module."""

import json
from unittest.mock import patch


from worktrees.user_config import (
    AIConfig,
    DEFAULT_PROMPT,
    GLOBAL_CONFIG_FILE,
    PROVIDER_DEFAULTS,
    UserConfig,
)


class TestAIConfig:
    """Tests for AIConfig dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = AIConfig()
        assert config.provider == "claude"
        assert config.command == ""
        assert config.prompt == DEFAULT_PROMPT

    def test_get_effective_command_with_custom(self):
        """Test get_effective_command returns custom command when set."""
        config = AIConfig(provider="claude", command="/custom/path/claude")
        assert config.get_effective_command() == "/custom/path/claude"

    def test_get_effective_command_with_default(self):
        """Test get_effective_command returns provider default when not set."""
        config = AIConfig(provider="claude", command="")
        assert config.get_effective_command() == PROVIDER_DEFAULTS["claude"]["command"]

    def test_get_effective_command_gemini(self):
        """Test get_effective_command for gemini provider."""
        config = AIConfig(provider="gemini", command="")
        assert config.get_effective_command() == PROVIDER_DEFAULTS["gemini"]["command"]

    def test_get_invocation_pattern_claude(self):
        """Test invocation pattern for claude."""
        config = AIConfig(provider="claude")
        assert config.get_invocation_pattern() == '{command} "{prompt}"'

    def test_get_invocation_pattern_gemini(self):
        """Test invocation pattern for gemini."""
        config = AIConfig(provider="gemini")
        assert config.get_invocation_pattern() == '{command} -i "{prompt}"'

    def test_build_command_substitutes_branches(self):
        """Test build_command substitutes branch placeholders."""
        config = AIConfig(
            provider="claude",
            command="/usr/bin/claude",
            prompt="merge <target-branch> into <current-branch>",
        )
        result = config.build_command("feature", "main")
        assert "feature" in result
        assert "main" in result
        assert "<target-branch>" not in result
        assert "<current-branch>" not in result

    def test_build_command_expands_tilde(self):
        """Test build_command expands ~ in path."""
        config = AIConfig(
            provider="claude",
            command="~/.claude/local/claude",
            prompt="test",
        )
        result = config.build_command("feature", "main")
        assert "~" not in result
        assert "/home" in result or "/Users" in result

    def test_build_command_uses_provider_pattern(self):
        """Test build_command uses correct invocation pattern."""
        config = AIConfig(provider="gemini", command="/usr/bin/gemini", prompt="test")
        result = config.build_command("feature", "main")
        assert "-i" in result  # Gemini uses -i flag

    def test_build_command_escapes_backticks(self):
        """Test build_command escapes backticks for shell safety."""
        config = AIConfig(
            provider="claude",
            command="/usr/bin/claude",
            prompt="run `worktrees mark merged into <current-branch>`",
        )
        result = config.build_command("feature", "main")
        # Backticks should be escaped to prevent shell command substitution
        assert "\\`worktrees" in result
        assert "\\`" in result

    def test_build_command_escapes_dollar_signs(self):
        """Test build_command escapes dollar signs for shell safety."""
        config = AIConfig(
            provider="claude",
            command="/usr/bin/claude",
            prompt="use $HOME variable",
        )
        result = config.build_command("feature", "main")
        assert "\\$HOME" in result

    def test_build_command_escapes_double_quotes(self):
        """Test build_command escapes double quotes for shell safety."""
        config = AIConfig(
            provider="claude",
            command="/usr/bin/claude",
            prompt='say "hello"',
        )
        result = config.build_command("feature", "main")
        assert '\\"hello\\"' in result

    def test_build_command_escapes_backslashes(self):
        """Test build_command escapes backslashes for shell safety."""
        config = AIConfig(
            provider="claude",
            command="/usr/bin/claude",
            prompt="path\\to\\file",
        )
        result = config.build_command("feature", "main")
        assert "path\\\\to\\\\file" in result


class TestUserConfig:
    """Tests for UserConfig dataclass."""

    def test_default_values(self):
        """Test default UserConfig has default AIConfig."""
        config = UserConfig()
        assert config.ai.provider == "claude"
        assert config.ai.command == ""
        assert config.ai.prompt == DEFAULT_PROMPT

    def test_load_returns_defaults_when_no_file(self, tmp_path):
        """Test load returns defaults when config file doesn't exist."""
        with patch.object(GLOBAL_CONFIG_FILE.__class__, "exists", return_value=False):
            config = UserConfig.load()
            assert config.ai.provider == "claude"

    def test_load_parses_existing_config(self, tmp_path):
        """Test load parses existing config file."""
        config_data = {
            "ai": {
                "provider": "gemini",
                "command": "/custom/gemini",
                "prompt": "custom prompt",
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
            config = UserConfig.load()
            assert config.ai.provider == "gemini"
            assert config.ai.command == "/custom/gemini"
            assert config.ai.prompt == "custom prompt"

    def test_load_handles_invalid_json(self, tmp_path):
        """Test load returns defaults on invalid JSON."""
        config_file = tmp_path / "config.json"
        config_file.write_text("invalid json{")

        with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
            config = UserConfig.load()
            assert config.ai.provider == "claude"

    def test_load_handles_missing_keys(self, tmp_path):
        """Test load handles partial config with missing keys."""
        config_data = {"ai": {"provider": "gemini"}}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
            config = UserConfig.load()
            assert config.ai.provider == "gemini"
            assert config.ai.command == ""
            assert config.ai.prompt == DEFAULT_PROMPT

    def test_save_creates_directory(self, tmp_path):
        """Test save creates config directory if needed."""
        config_dir = tmp_path / ".config" / "worktrees"
        config_file = config_dir / "config.json"

        with patch("worktrees.user_config.GLOBAL_CONFIG_DIR", config_dir):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                config = UserConfig(
                    ai=AIConfig(provider="gemini", command="/custom/gemini")
                )
                config.save()

                assert config_dir.exists()
                assert config_file.exists()

    def test_save_writes_correct_json(self, tmp_path):
        """Test save writes correct JSON structure."""
        config_dir = tmp_path / ".config" / "worktrees"
        config_file = config_dir / "config.json"

        with patch("worktrees.user_config.GLOBAL_CONFIG_DIR", config_dir):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                config = UserConfig(
                    ai=AIConfig(
                        provider="gemini",
                        command="/custom/gemini",
                        prompt="custom prompt",
                    )
                )
                config.save()

                data = json.loads(config_file.read_text())
                assert data["ai"]["provider"] == "gemini"
                assert data["ai"]["command"] == "/custom/gemini"
                assert data["ai"]["prompt"] == "custom prompt"

    def test_is_configured_false_when_no_file(self, tmp_path):
        """Test is_configured returns False when no config file."""
        config_file = tmp_path / "nonexistent.json"
        with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
            config = UserConfig()
            assert config.is_configured() is False

    def test_is_configured_true_when_file_exists(self, tmp_path):
        """Test is_configured returns True when config file exists."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
            config = UserConfig()
            assert config.is_configured() is True

    def test_roundtrip_save_load(self, tmp_path):
        """Test saving and loading preserves all data."""
        config_dir = tmp_path / ".config" / "worktrees"
        config_file = config_dir / "config.json"

        with patch("worktrees.user_config.GLOBAL_CONFIG_DIR", config_dir):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                original = UserConfig(
                    ai=AIConfig(
                        provider="gemini",
                        command="/custom/path",
                        prompt="custom prompt here",
                    )
                )
                original.save()

                loaded = UserConfig.load()
                assert loaded.ai.provider == original.ai.provider
                assert loaded.ai.command == original.ai.command
                assert loaded.ai.prompt == original.ai.prompt
