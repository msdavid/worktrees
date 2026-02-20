"""Tests for config CLI command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from worktrees.cli import app
from worktrees.user_config import DEFAULT_PROMPT, PROVIDER_DEFAULTS

runner = CliRunner()


class TestConfigCommand:
    """Tests for the config command."""

    def test_config_creates_new_config(self, tmp_path):
        """Test config command creates new config file."""
        config_dir = tmp_path / ".config" / "worktrees"
        config_file = config_dir / "config.json"

        with patch("worktrees.user_config.GLOBAL_CONFIG_DIR", config_dir):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.cli.config_cmd.UserConfig") as mock_config_cls:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = False
                    mock_config.ai.provider = "claude"
                    mock_config.ai.command = ""
                    mock_config.ai.prompt = DEFAULT_PROMPT
                    mock_config.ai.get_effective_command.return_value = (
                        PROVIDER_DEFAULTS["claude"]["command"]
                    )
                    mock_config_cls.load.return_value = mock_config

                    with patch("questionary.select") as mock_select:
                        with patch("questionary.text") as mock_text:
                            with patch("questionary.confirm") as mock_confirm:
                                mock_select.return_value.ask.return_value = "claude"
                                mock_text.return_value.ask.return_value = ""
                                mock_confirm.return_value.ask.return_value = (
                                    True  # Use default prompt
                                )

                                result = runner.invoke(app, ["config"])
                                assert result.exit_code == 0
                                assert "Configuration saved" in result.output

    def test_config_shows_current_settings(self, tmp_path):
        """Test config command shows current settings when configured."""
        config_dir = tmp_path / ".config" / "worktrees"
        config_file = config_dir / "config.json"

        with patch("worktrees.user_config.GLOBAL_CONFIG_DIR", config_dir):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.cli.config_cmd.UserConfig") as mock_config_cls:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_config.ai.provider = "gemini"
                    mock_config.ai.command = "/custom/gemini"
                    mock_config.ai.prompt = "custom prompt"
                    mock_config.ai.get_effective_command.return_value = "/custom/gemini"
                    mock_config_cls.load.return_value = mock_config

                    with patch("questionary.select") as mock_select:
                        with patch("questionary.text") as mock_text:
                            with patch("questionary.confirm") as mock_confirm:
                                mock_select.return_value.ask.return_value = "gemini"
                                mock_text.return_value.ask.return_value = ""
                                mock_confirm.return_value.ask.return_value = (
                                    True  # Use default prompt
                                )

                                result = runner.invoke(app, ["config"])
                                assert result.exit_code == 0
                                assert "Current configuration" in result.output
                                assert "gemini" in result.output

    def test_config_user_cancels_provider(self, tmp_path):
        """Test config command exits gracefully when user cancels provider selection."""
        config_dir = tmp_path / ".config" / "worktrees"
        config_file = config_dir / "config.json"

        with patch("worktrees.user_config.GLOBAL_CONFIG_DIR", config_dir):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.cli.config_cmd.UserConfig") as mock_config_cls:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = False
                    mock_config_cls.load.return_value = mock_config

                    with patch("questionary.select") as mock_select:
                        mock_select.return_value.ask.return_value = None

                        result = runner.invoke(app, ["config"])
                        assert result.exit_code == 0
                        assert "Configuration saved" not in result.output

    def test_config_user_cancels_command(self, tmp_path):
        """Test config command exits when user cancels command input."""
        config_dir = tmp_path / ".config" / "worktrees"
        config_file = config_dir / "config.json"

        with patch("worktrees.user_config.GLOBAL_CONFIG_DIR", config_dir):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.cli.config_cmd.UserConfig") as mock_config_cls:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = False
                    mock_config.ai.provider = "claude"
                    mock_config.ai.command = ""
                    mock_config_cls.load.return_value = mock_config

                    with patch("questionary.select") as mock_select:
                        with patch("questionary.text") as mock_text:
                            mock_select.return_value.ask.return_value = "claude"
                            mock_text.return_value.ask.return_value = None

                            result = runner.invoke(app, ["config"])
                            assert result.exit_code == 0

    def test_config_custom_prompt(self, tmp_path):
        """Test config command with custom prompt."""
        config_dir = tmp_path / ".config" / "worktrees"
        config_file = config_dir / "config.json"

        with patch("worktrees.user_config.GLOBAL_CONFIG_DIR", config_dir):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.cli.config_cmd.UserConfig") as mock_config_cls:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = False
                    mock_config.ai.provider = "claude"
                    mock_config.ai.command = ""
                    mock_config.ai.prompt = DEFAULT_PROMPT
                    mock_config.ai.get_effective_command.return_value = (
                        PROVIDER_DEFAULTS["claude"]["command"]
                    )
                    mock_config_cls.load.return_value = mock_config

                    with patch("questionary.select") as mock_select:
                        with patch("questionary.text") as mock_text:
                            with patch("questionary.confirm") as mock_confirm:
                                with patch("click.edit") as mock_edit:
                                    mock_select.return_value.ask.return_value = "claude"
                                    mock_text.return_value.ask.return_value = (
                                        ""  # Command
                                    )
                                    mock_confirm.return_value.ask.return_value = (
                                        False  # Don't use default prompt
                                    )
                                    mock_edit.return_value = "my custom prompt"

                                    result = runner.invoke(app, ["config"])
                                    assert result.exit_code == 0
                                    mock_config.save.assert_called_once()

    def test_config_user_cancels_custom_prompt_confirm(self, tmp_path):
        """Test config command exits when user cancels custom prompt confirmation."""
        config_dir = tmp_path / ".config" / "worktrees"
        config_file = config_dir / "config.json"

        with patch("worktrees.user_config.GLOBAL_CONFIG_DIR", config_dir):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.cli.config_cmd.UserConfig") as mock_config_cls:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = False
                    mock_config.ai.provider = "claude"
                    mock_config.ai.command = ""
                    mock_config_cls.load.return_value = mock_config

                    with patch("questionary.select") as mock_select:
                        with patch("questionary.text") as mock_text:
                            with patch("questionary.confirm") as mock_confirm:
                                mock_select.return_value.ask.return_value = "claude"
                                mock_text.return_value.ask.return_value = ""
                                mock_confirm.return_value.ask.return_value = None

                                result = runner.invoke(app, ["config"])
                                assert result.exit_code == 0

    def test_config_user_cancels_custom_prompt_editor(self, tmp_path):
        """Test config command keeps existing prompt when user cancels editor."""
        config_dir = tmp_path / ".config" / "worktrees"
        config_file = config_dir / "config.json"

        with patch("worktrees.user_config.GLOBAL_CONFIG_DIR", config_dir):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.cli.config_cmd.UserConfig") as mock_config_cls:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = False
                    mock_config.ai.provider = "claude"
                    mock_config.ai.command = ""
                    mock_config.ai.prompt = DEFAULT_PROMPT
                    mock_config.ai.get_effective_command.return_value = (
                        PROVIDER_DEFAULTS["claude"]["command"]
                    )
                    mock_config_cls.load.return_value = mock_config

                    with patch("questionary.select") as mock_select:
                        with patch("questionary.text") as mock_text:
                            with patch("questionary.confirm") as mock_confirm:
                                with patch("click.edit") as mock_edit:
                                    mock_select.return_value.ask.return_value = "claude"
                                    mock_text.return_value.ask.return_value = (
                                        ""  # Command
                                    )
                                    mock_confirm.return_value.ask.return_value = (
                                        False  # Don't use default
                                    )
                                    mock_edit.return_value = None  # Editor cancelled

                                    result = runner.invoke(app, ["config"])
                                    assert result.exit_code == 0
                                    assert "Keeping existing prompt" in result.output

    def test_config_custom_prompt_empty_falls_back_to_default(self, tmp_path):
        """Test config command falls back to default prompt when user provides empty text."""
        config_dir = tmp_path / ".config" / "worktrees"
        config_file = config_dir / "config.json"

        with patch("worktrees.user_config.GLOBAL_CONFIG_DIR", config_dir):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.cli.config_cmd.UserConfig") as mock_config_cls:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = False
                    mock_config.ai.provider = "claude"
                    mock_config.ai.command = ""
                    mock_config.ai.prompt = DEFAULT_PROMPT
                    mock_config.ai.get_effective_command.return_value = (
                        PROVIDER_DEFAULTS["claude"]["command"]
                    )
                    mock_config_cls.load.return_value = mock_config

                    with patch("questionary.select") as mock_select:
                        with patch("questionary.text") as mock_text:
                            with patch("questionary.confirm") as mock_confirm:
                                with patch("click.edit") as mock_edit:
                                    mock_select.return_value.ask.return_value = "claude"
                                    mock_text.return_value.ask.return_value = (
                                        ""  # Command
                                    )
                                    mock_confirm.return_value.ask.return_value = (
                                        False  # Don't use default
                                    )
                                    mock_edit.return_value = (
                                        "   \n\n   "  # Empty/whitespace
                                    )

                                    result = runner.invoke(app, ["config"])
                                    assert result.exit_code == 0
                                    # Verify it saved the default prompt when empty was provided
                                    assert mock_config.ai.prompt == DEFAULT_PROMPT
                                    mock_config.save.assert_called_once()
