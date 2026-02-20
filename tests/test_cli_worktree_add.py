"""Tests for worktree add CLI command with tmux integration."""

import json
import subprocess
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from worktrees.cli import app
from worktrees.config import WORKTREES_JSON
from worktrees.git import GitError

runner = CliRunner()


@pytest.fixture
def initialized_project(tmp_path):
    """Create an initialized worktrees project."""
    config_file = tmp_path / WORKTREES_JSON
    config_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "worktreesDir": ".",
                "setup": {"autoDetect": True, "commands": []},
                "marks": {},
            }
        )
    )
    return tmp_path


class TestWorktreeAddCommand:
    """Tests for the 'worktrees add' command."""

    def test_add_requires_initialized(self, tmp_path):
        """Test add command requires initialized project."""
        with patch("worktrees.config.Path.cwd", return_value=tmp_path):
            result = runner.invoke(app, ["add", "feature"])
            assert result.exit_code == 1
            assert "not initialized" in result.output

    def test_add_with_explicit_branch_success(self, initialized_project):
        """Test adding worktree with explicitly provided branch."""
        worktree_path = initialized_project / "feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.add_worktree") as mock_add:
                mock_add.return_value = worktree_path
                with patch(
                    "worktrees.cli.worktree.create_environ_symlinks", return_value=[]
                ):
                    with patch("questionary.confirm") as mock_confirm:
                        # User says no to tmux
                        mock_confirm.return_value.ask.return_value = False

                        result = runner.invoke(app, ["add", "feature"])

                        assert result.exit_code == 0
                        assert "Created" in result.output
                        assert "feature" in result.output
                        mock_add.assert_called_once()

    def test_add_worktree_already_exists_use_existing(self, initialized_project):
        """Test adding worktree when directory already exists and user chooses to use it."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("questionary.select") as mock_select:
                mock_select.return_value.ask.return_value = "use"

                result = runner.invoke(app, ["add", "feature"])

                assert result.exit_code == 0
                assert "already exists" in result.output

    def test_add_worktree_already_exists_cancel(self, initialized_project):
        """Test adding worktree when directory exists and user cancels."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("questionary.select") as mock_select:
                mock_select.return_value.ask.return_value = "cancel"

                result = runner.invoke(app, ["add", "feature"])

                assert result.exit_code == 0

    def test_add_creates_environ_symlinks(self, initialized_project):
        """Test add command creates symlinks from ENVIRON directory."""
        worktree_path = initialized_project / "feature"
        environ_dir = initialized_project / "ENVIRON"
        environ_dir.mkdir()
        (environ_dir / ".env").write_text("TEST=value")

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.add_worktree") as mock_add:
                mock_add.return_value = worktree_path
                with patch(
                    "worktrees.cli.worktree.create_environ_symlinks"
                ) as mock_link:
                    mock_link.return_value = [".env"]
                    with patch("questionary.confirm") as mock_confirm:
                        mock_confirm.return_value.ask.return_value = False

                        result = runner.invoke(app, ["add", "feature"])

                        assert result.exit_code == 0
                        assert "Linked" in result.output
                        assert ".env" in result.output

    def test_add_runs_setup_commands(self, initialized_project):
        """Test add command runs setup commands from config."""
        config_file = initialized_project / WORKTREES_JSON
        config_file.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "worktreesDir": ".",
                    "setup": {
                        "autoDetect": False,
                        "commands": ["python -m venv .venv"],
                    },
                    "marks": {},
                }
            )
        )
        worktree_path = initialized_project / "feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.add_worktree") as mock_add:
                mock_add.return_value = worktree_path
                with patch(
                    "worktrees.cli.worktree.create_environ_symlinks", return_value=[]
                ):
                    with patch(
                        "worktrees.cli.worktree.run_setup_command"
                    ) as mock_setup:
                        mock_setup.return_value = (True, "")
                        with patch("questionary.confirm") as mock_confirm:
                            mock_confirm.return_value.ask.return_value = False

                            result = runner.invoke(app, ["add", "feature"])

                            assert result.exit_code == 0
                            assert "Setup" in result.output
                            mock_setup.assert_called_once()

    def test_add_skip_setup_commands_with_flag(self, initialized_project):
        """Test add command skips setup commands with --no-setup flag."""
        config_file = initialized_project / WORKTREES_JSON
        config_file.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "worktreesDir": ".",
                    "setup": {
                        "autoDetect": False,
                        "commands": ["python -m venv .venv"],
                    },
                    "marks": {},
                }
            )
        )
        worktree_path = initialized_project / "feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.add_worktree") as mock_add:
                mock_add.return_value = worktree_path
                with patch(
                    "worktrees.cli.worktree.create_environ_symlinks", return_value=[]
                ):
                    with patch(
                        "worktrees.cli.worktree.run_setup_command"
                    ) as mock_setup:
                        with patch("questionary.confirm") as mock_confirm:
                            mock_confirm.return_value.ask.return_value = False

                            result = runner.invoke(
                                app, ["add", "feature", "--no-setup"]
                            )

                            assert result.exit_code == 0
                            mock_setup.assert_not_called()

    def test_add_handles_git_error(self, initialized_project):
        """Test add command handles GitError during worktree creation."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.worktree.add_worktree",
                side_effect=GitError("branch does not exist"),
            ):
                result = runner.invoke(app, ["add", "feature"])

                assert result.exit_code == 1
                assert "branch does not exist" in result.output


class TestWorktreeAddTmuxIntegration:
    """Tests for tmux integration in the add command."""

    def test_add_prompts_for_tmux_session(self, initialized_project):
        """Test add command prompts user about starting tmux session."""
        worktree_path = initialized_project / "feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.add_worktree") as mock_add:
                mock_add.return_value = worktree_path
                with patch(
                    "worktrees.cli.worktree.create_environ_symlinks", return_value=[]
                ):
                    with patch("questionary.confirm") as mock_confirm:
                        mock_confirm.return_value.ask.return_value = False

                        result = runner.invoke(app, ["add", "feature"])

                        assert result.exit_code == 0
                        # Verify confirm was called with tmux question
                        mock_confirm.assert_called_once()
                        call_args = mock_confirm.call_args[0]
                        assert "tmux session" in call_args[0]

    def test_add_starts_tmux_session_without_venv(self, initialized_project):
        """Test add command creates tmux session without venv activation."""
        worktree_path = initialized_project / "feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.add_worktree") as mock_add:
                mock_add.return_value = worktree_path
                with patch(
                    "worktrees.cli.worktree.create_environ_symlinks", return_value=[]
                ):
                    with patch("questionary.confirm") as mock_confirm:
                        # User says yes to tmux
                        mock_confirm.return_value.ask.return_value = True
                        with patch(
                            "worktrees.cli.worktree.get_tmux_sessions"
                        ) as mock_sessions:
                            mock_sessions.return_value = []
                            with patch(
                                "worktrees.cli.worktree.create_tmux_session"
                            ) as mock_create:
                                with patch(
                                    "worktrees.cli.worktree.attach_or_switch"
                                ) as mock_attach:
                                    result = runner.invoke(app, ["add", "feature"])

                                    assert result.exit_code == 0
                                    assert "Created session" in result.output
                                    # Verify session was created without venv
                                    mock_create.assert_called_once_with(
                                        "feature", worktree_path, False
                                    )
                                    mock_attach.assert_called_once_with("feature")

    def test_add_starts_tmux_session_with_venv(self, initialized_project):
        """Test add command creates tmux session with venv activation."""
        worktree_path = initialized_project / "feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.add_worktree") as mock_add:
                # Create venv after add_worktree is called to simulate setup command creating it
                def create_venv_side_effect(path, *args, **kwargs):
                    venv_activate = path / ".venv" / "bin" / "activate"
                    venv_activate.parent.mkdir(parents=True)
                    venv_activate.touch()
                    return path

                mock_add.side_effect = create_venv_side_effect
                with patch(
                    "worktrees.cli.worktree.create_environ_symlinks", return_value=[]
                ):
                    with patch("questionary.confirm") as mock_confirm:
                        # User says yes to tmux
                        mock_confirm.return_value.ask.return_value = True
                        with patch(
                            "worktrees.cli.worktree.get_tmux_sessions"
                        ) as mock_sessions:
                            mock_sessions.return_value = []
                            with patch(
                                "worktrees.cli.worktree.create_tmux_session"
                            ) as mock_create:
                                with patch(
                                    "worktrees.cli.worktree.attach_or_switch"
                                ) as mock_attach:
                                    result = runner.invoke(app, ["add", "feature"])

                                    assert result.exit_code == 0
                                    assert "Created session" in result.output
                                    assert ".venv activated" in result.output
                                    # Verify session was created with venv=True
                                    mock_create.assert_called_once_with(
                                        "feature", worktree_path, True
                                    )
                                    mock_attach.assert_called_once_with("feature")

    def test_add_handles_existing_tmux_sessions(self, initialized_project):
        """Test add command handles existing tmux sessions with same name."""
        worktree_path = initialized_project / "feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.add_worktree") as mock_add:
                mock_add.return_value = worktree_path
                with patch(
                    "worktrees.cli.worktree.create_environ_symlinks", return_value=[]
                ):
                    with patch("questionary.confirm") as mock_confirm:
                        # User says yes to tmux
                        mock_confirm.return_value.ask.return_value = True
                        with patch(
                            "worktrees.cli.worktree.get_tmux_sessions"
                        ) as mock_sessions:
                            # Simulate existing sessions
                            mock_sessions.return_value = ["feature", "feature-2"]
                            with patch(
                                "worktrees.cli.worktree.create_tmux_session"
                            ) as mock_create:
                                with patch("worktrees.cli.worktree.attach_or_switch"):
                                    result = runner.invoke(app, ["add", "feature"])

                                    assert result.exit_code == 0
                                    # Should create session with suffix
                                    mock_create.assert_called_once()
                                    call_args = mock_create.call_args[0]
                                    assert call_args[0] == "feature-3"

    def test_add_shows_manual_instructions_when_no_tmux(self, initialized_project):
        """Test add command shows manual instructions when user declines tmux."""
        worktree_path = initialized_project / "feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.add_worktree") as mock_add:
                mock_add.return_value = worktree_path
                with patch(
                    "worktrees.cli.worktree.create_environ_symlinks", return_value=[]
                ):
                    with patch("questionary.confirm") as mock_confirm:
                        # User says no to tmux
                        mock_confirm.return_value.ask.return_value = False

                        result = runner.invoke(app, ["add", "feature"])

                        assert result.exit_code == 0
                        assert "Next" in result.output
                        assert f"cd {worktree_path}" in result.output

    def test_add_shows_manual_instructions_with_venv(self, initialized_project):
        """Test add command shows venv activation in manual instructions."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.add_worktree") as mock_add:
                # Create venv after add_worktree is called
                def create_venv_side_effect(path, *args, **kwargs):
                    venv_activate = path / ".venv" / "bin" / "activate"
                    venv_activate.parent.mkdir(parents=True)
                    venv_activate.touch()
                    return path

                mock_add.side_effect = create_venv_side_effect
                with patch(
                    "worktrees.cli.worktree.create_environ_symlinks", return_value=[]
                ):
                    with patch("questionary.confirm") as mock_confirm:
                        # User says no to tmux
                        mock_confirm.return_value.ask.return_value = False

                        result = runner.invoke(app, ["add", "feature"])

                        assert result.exit_code == 0
                        assert "source .venv/bin/activate" in result.output

    def test_add_handles_tmux_not_found(self, initialized_project):
        """Test add command handles tmux not being installed."""
        worktree_path = initialized_project / "feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.add_worktree") as mock_add:
                mock_add.return_value = worktree_path
                with patch(
                    "worktrees.cli.worktree.create_environ_symlinks", return_value=[]
                ):
                    with patch("questionary.confirm") as mock_confirm:
                        # User says yes to tmux
                        mock_confirm.return_value.ask.return_value = True
                        with patch(
                            "worktrees.cli.worktree.get_tmux_sessions", return_value=[]
                        ):
                            with patch(
                                "worktrees.cli.worktree.create_tmux_session",
                                side_effect=FileNotFoundError,
                            ):
                                result = runner.invoke(app, ["add", "feature"])

                                assert result.exit_code == 1
                                assert "tmux not found" in result.output

    def test_add_handles_tmux_creation_error(self, initialized_project):
        """Test add command handles tmux session creation failure."""
        worktree_path = initialized_project / "feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.add_worktree") as mock_add:
                mock_add.return_value = worktree_path
                with patch(
                    "worktrees.cli.worktree.create_environ_symlinks", return_value=[]
                ):
                    with patch("questionary.confirm") as mock_confirm:
                        # User says yes to tmux
                        mock_confirm.return_value.ask.return_value = True
                        with patch(
                            "worktrees.cli.worktree.get_tmux_sessions", return_value=[]
                        ):
                            with patch(
                                "worktrees.cli.worktree.create_tmux_session",
                                side_effect=subprocess.CalledProcessError(1, "tmux"),
                            ):
                                result = runner.invoke(app, ["add", "feature"])

                                assert result.exit_code == 1
                                assert "failed to create tmux session" in result.output

    def test_add_with_custom_name(self, initialized_project):
        """Test add command with custom worktree name."""
        worktree_path = initialized_project / "custom-name"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.add_worktree") as mock_add:
                mock_add.return_value = worktree_path
                with patch(
                    "worktrees.cli.worktree.create_environ_symlinks", return_value=[]
                ):
                    with patch("questionary.confirm") as mock_confirm:
                        mock_confirm.return_value.ask.return_value = False

                        result = runner.invoke(
                            app, ["add", "feature", "--name", "custom-name"]
                        )

                        assert result.exit_code == 0
                        assert "custom-name" in result.output
                        # Verify add_worktree was called with custom path
                        call_args = mock_add.call_args[0]
                        assert call_args[0] == worktree_path


class TestWorktreeAddInteractive:
    """Tests for interactive branch selection in add command."""

    def test_add_interactive_branch_selection(self, initialized_project):
        """Test add command with interactive branch selection."""
        worktree_path = initialized_project / "feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.list_local_branches") as mock_branches:
                mock_branches.return_value = ["main", "feature", "develop"]
                with patch("worktrees.cli.worktree.get_current_branch") as mock_current:
                    mock_current.return_value = "main"
                    with patch("questionary.select") as mock_select:
                        # User selects 'feature' branch
                        mock_select.return_value.ask.return_value = "feature"
                        with patch("worktrees.cli.worktree.add_worktree") as mock_add:
                            mock_add.return_value = worktree_path
                            with patch(
                                "worktrees.cli.worktree.create_environ_symlinks",
                                return_value=[],
                            ):
                                with patch("questionary.confirm") as mock_confirm:
                                    mock_confirm.return_value.ask.return_value = False

                                    # No branch argument - interactive mode
                                    result = runner.invoke(app, ["add"])

                                    assert result.exit_code == 0
                                    mock_select.assert_called_once()

    def test_add_interactive_user_cancels(self, initialized_project):
        """Test add command when user cancels interactive selection."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.list_local_branches") as mock_branches:
                mock_branches.return_value = ["main", "feature"]
                with patch(
                    "worktrees.cli.worktree.get_current_branch", return_value="main"
                ):
                    with patch("questionary.select") as mock_select:
                        # User cancels
                        mock_select.return_value.ask.return_value = None

                        result = runner.invoke(app, ["add"])

                        assert result.exit_code == 0

    def test_add_interactive_new_branch_creation(self, initialized_project):
        """Test add command creates new branch in interactive mode."""
        worktree_path = initialized_project / "new-feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.list_local_branches") as mock_branches:
                mock_branches.return_value = ["main", "develop"]
                with patch(
                    "worktrees.cli.worktree.get_current_branch", return_value="main"
                ):
                    with patch("questionary.select") as mock_select:
                        # First call: user selects "+ new branch"
                        # Second call: user selects base branch "main"
                        mock_select.return_value.ask.side_effect = ["__new__", "main"]
                        with patch("questionary.text") as mock_text:
                            # User enters new branch name
                            mock_text.return_value.ask.return_value = "new-feature"
                            with patch(
                                "worktrees.cli.worktree.branch_exists"
                            ) as mock_exists:
                                # Branch doesn't exist yet
                                mock_exists.return_value = (False, False)
                                with patch(
                                    "worktrees.cli.worktree.add_worktree"
                                ) as mock_add:
                                    mock_add.return_value = worktree_path
                                    with patch(
                                        "worktrees.cli.worktree.create_environ_symlinks",
                                        return_value=[],
                                    ):
                                        with patch(
                                            "questionary.confirm"
                                        ) as mock_confirm:
                                            mock_confirm.return_value.ask.return_value = False

                                            result = runner.invoke(app, ["add"])

                                            assert result.exit_code == 0
                                            # Verify add_worktree was called with create_branch=True
                                            assert (
                                                mock_add.call_args[1]["create_branch"]
                                                is True
                                            )
                                            assert (
                                                mock_add.call_args[1]["base_branch"]
                                                == "main"
                                            )

    def test_add_interactive_handles_git_error(self, initialized_project):
        """Test add command handles git errors during interactive mode."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.worktree.list_local_branches",
                side_effect=GitError("git error"),
            ):
                result = runner.invoke(app, ["add"])

                assert result.exit_code == 1
                assert "git error" in result.output
