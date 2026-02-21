"""Tests for tmux CLI command."""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from worktrees.cli import app
from worktrees.cli.tmux import get_next_session_name, get_tmux_sessions, is_inside_tmux
from worktrees.config import WORKTREES_JSON
from worktrees.git import Worktree

runner = CliRunner()


@pytest.fixture
def initialized_project(tmp_path):
    """Create an initialized worktrees project with mock worktrees."""
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


class TestGetTmuxSessions:
    """Tests for get_tmux_sessions helper."""

    def test_no_tmux_server(self):
        """Test when tmux server is not running."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = get_tmux_sessions("main")
            assert result == []

    def test_tmux_not_installed(self):
        """Test when tmux is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = get_tmux_sessions("main")
            assert result == []

    def test_matching_sessions(self):
        """Test filtering sessions by prefix."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "main\nmain-2\nmain-3\nfeature\nother-main\n"

        with patch("subprocess.run", return_value=mock_result):
            result = get_tmux_sessions("main")
            assert result == ["main", "main-2", "main-3"]

    def test_no_matching_sessions(self):
        """Test when no sessions match prefix."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "feature\ndev\n"

        with patch("subprocess.run", return_value=mock_result):
            result = get_tmux_sessions("main")
            assert result == []

    def test_empty_output(self):
        """Test handling empty output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = get_tmux_sessions("main")
            assert result == []


class TestGetNextSessionName:
    """Tests for get_next_session_name helper."""

    def test_no_existing_sessions(self):
        """Test when no sessions exist."""
        result = get_next_session_name("main", [])
        assert result == "main"

    def test_base_name_available(self):
        """Test when base name is available but suffixed exists."""
        result = get_next_session_name("main", ["main-2"])
        assert result == "main"

    def test_base_name_taken(self):
        """Test when base name is taken."""
        result = get_next_session_name("main", ["main"])
        assert result == "main-2"

    def test_multiple_suffixes(self):
        """Test finding next available suffix."""
        result = get_next_session_name("main", ["main", "main-2", "main-3"])
        assert result == "main-4"

    def test_gap_in_suffixes(self):
        """Test that gaps are not reused (uses max + 1)."""
        result = get_next_session_name("main", ["main", "main-5"])
        assert result == "main-6"


class TestGetCurrentWorktreeName:
    """Tests for get_current_worktree_name helper."""

    def test_returns_none_when_not_in_worktree(self, tmp_path):
        """Test returns None when not inside a worktree."""
        from worktrees.config import WorktreesConfig
        from worktrees.cli.tmux import get_current_worktree_name

        config = WorktreesConfig(project_root=tmp_path)
        mock_worktrees = [
            Worktree(path=tmp_path / "main", commit="abc123", branch="main"),
        ]

        with patch("worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees):
            with patch(
                "worktrees.cli.tmux.Path.cwd", return_value=tmp_path / "elsewhere"
            ):
                result = get_current_worktree_name(config)
                assert result is None

    def test_returns_worktree_name_when_inside(self, tmp_path):
        """Test returns worktree name when inside a worktree."""
        from worktrees.config import WorktreesConfig
        from worktrees.cli.tmux import get_current_worktree_name

        config = WorktreesConfig(project_root=tmp_path)
        mock_worktrees = [
            Worktree(path=tmp_path / "main", commit="abc123", branch="main"),
        ]

        with patch("worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees):
            with patch("worktrees.cli.tmux.Path.cwd", return_value=tmp_path / "main"):
                result = get_current_worktree_name(config)
                assert result == "main"

    def test_returns_none_on_git_error(self, tmp_path):
        """Test returns None when git error occurs."""
        from worktrees.config import WorktreesConfig
        from worktrees.cli.tmux import get_current_worktree_name
        from worktrees.git import GitError

        config = WorktreesConfig(project_root=tmp_path)

        with patch(
            "worktrees.cli.tmux.list_worktrees", side_effect=GitError("git failed")
        ):
            result = get_current_worktree_name(config)
            assert result is None

    def test_skips_bare_repo(self, tmp_path):
        """Test skips bare repository in worktree list."""
        from worktrees.config import WorktreesConfig
        from worktrees.cli.tmux import get_current_worktree_name

        config = WorktreesConfig(project_root=tmp_path)
        mock_worktrees = [
            Worktree(path=tmp_path / ".git", commit="abc123", branch="(bare)"),
            Worktree(path=tmp_path / "main", commit="abc123", branch="main"),
        ]

        with patch("worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees):
            with patch("worktrees.cli.tmux.Path.cwd", return_value=tmp_path / "main"):
                result = get_current_worktree_name(config)
                assert result == "main"

    def test_handles_value_error_on_relative_path(self, tmp_path):
        """Test handles ValueError from is_relative_to check."""
        from worktrees.config import WorktreesConfig
        from worktrees.cli.tmux import get_current_worktree_name

        config = WorktreesConfig(project_root=tmp_path)
        mock_worktrees = [
            Worktree(path=tmp_path / "main", commit="abc123", branch="main"),
        ]

        with patch("worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees):
            with patch("worktrees.cli.tmux.Path.cwd", return_value=tmp_path / "other"):
                # Mock is_relative_to to raise ValueError
                with patch.object(
                    tmp_path.__class__, "is_relative_to", side_effect=ValueError
                ):
                    result = get_current_worktree_name(config)
                    assert result is None

    def test_returns_deepest_match(self, tmp_path):
        """Test returns deepest matching worktree when nested."""
        from worktrees.config import WorktreesConfig
        from worktrees.cli.tmux import get_current_worktree_name

        config = WorktreesConfig(project_root=tmp_path)
        mock_worktrees = [
            Worktree(path=tmp_path / "main", commit="abc123", branch="main"),
            Worktree(path=tmp_path / "main" / "sub", commit="def456", branch="feature"),
        ]

        with patch("worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees):
            with patch(
                "worktrees.cli.tmux.Path.cwd", return_value=tmp_path / "main" / "sub"
            ):
                result = get_current_worktree_name(config)
                assert result == "sub"


class TestGetWorktreeNames:
    """Tests for get_worktree_names helper."""

    def test_returns_empty_on_git_error(self, tmp_path):
        """Test returns empty set when git error occurs."""
        from worktrees.config import WorktreesConfig
        from worktrees.cli.tmux import get_worktree_names
        from worktrees.git import GitError

        config = WorktreesConfig(project_root=tmp_path)

        with patch(
            "worktrees.cli.tmux.list_worktrees", side_effect=GitError("git failed")
        ):
            result = get_worktree_names(config)
            assert result == set()


class TestIsInsideTmux:
    """Tests for is_inside_tmux helper."""

    def test_inside_tmux(self):
        """Test detection when inside tmux."""
        with patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,12345,0"}):
            assert is_inside_tmux() is True

    def test_outside_tmux(self):
        """Test detection when outside tmux."""
        with patch.dict("os.environ", {}, clear=True):
            assert is_inside_tmux() is False

    def test_empty_tmux_var(self):
        """Test detection when TMUX var is empty."""
        with patch.dict("os.environ", {"TMUX": ""}):
            assert is_inside_tmux() is False


class TestCreateTmuxSession:
    """Tests for create_tmux_session helper."""

    def test_creates_session_without_venv(self, tmp_path):
        """Test creating tmux session without venv activation."""
        from worktrees.cli.tmux import create_tmux_session

        with patch("subprocess.run") as mock_run:
            create_tmux_session("test-session", tmp_path, activate_venv=False)

            mock_run.assert_called_once_with(
                [
                    "tmux",
                    "new-session",
                    "-d",
                    "-s",
                    "test-session",
                    "-c",
                    str(tmp_path),
                ],
                check=True,
            )

    def test_creates_session_with_venv(self, tmp_path):
        """Test creating tmux session with venv activation."""
        from worktrees.cli.tmux import create_tmux_session

        with patch("subprocess.run") as mock_run:
            create_tmux_session("test-session", tmp_path, activate_venv=True)

            assert mock_run.call_count == 2
            # First call: create session
            mock_run.assert_any_call(
                [
                    "tmux",
                    "new-session",
                    "-d",
                    "-s",
                    "test-session",
                    "-c",
                    str(tmp_path),
                ],
                check=True,
            )
            # Second call: activate venv
            mock_run.assert_any_call(
                [
                    "tmux",
                    "send-keys",
                    "-t",
                    "test-session",
                    "source .venv/bin/activate",
                    "Enter",
                ],
                check=True,
            )


class TestAttachOrSwitch:
    """Tests for attach_or_switch helper."""

    def test_switch_when_inside_tmux(self):
        """Test uses switch-client when inside tmux."""
        from worktrees.cli.tmux import attach_or_switch

        with patch("worktrees.cli.tmux.is_inside_tmux", return_value=True):
            with patch("subprocess.run") as mock_run:
                attach_or_switch("test-session")

                mock_run.assert_called_once_with(
                    ["tmux", "switch-client", "-t", "test-session"], check=True
                )

    def test_attach_when_outside_tmux(self):
        """Test uses attach when outside tmux."""
        from worktrees.cli.tmux import attach_or_switch

        with patch("worktrees.cli.tmux.is_inside_tmux", return_value=False):
            with patch("subprocess.run") as mock_run:
                attach_or_switch("test-session")

                mock_run.assert_called_once_with(
                    ["tmux", "attach", "-t", "test-session"], check=True
                )


class TestTmuxCommand:
    """Tests for the tmux command."""

    def test_requires_initialized(self, tmp_path):
        """Test tmux command requires initialized project."""
        with patch("worktrees.config.Path.cwd", return_value=tmp_path):
            result = runner.invoke(app, ["tmux"])
            assert result.exit_code == 1
            assert "not initialized" in result.output

    def test_outside_worktree_without_argument(self, initialized_project):
        """Test tmux command errors when outside worktree without argument."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.get_current_worktree_name", return_value=None
            ):
                result = runner.invoke(app, ["tmux"])
                assert result.exit_code == 1
                assert "not inside a worktree" in result.output

    def test_nonexistent_worktree(self, initialized_project):
        """Test tmux command errors for nonexistent worktree."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                result = runner.invoke(app, ["tmux", "nonexistent"])
                assert result.exit_code == 1
                assert "not found" in result.output
                assert "main" in result.output  # Shows available worktrees

    def test_creates_new_session(self, initialized_project):
        """Test creating a new tmux session."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        # Create the worktree directory
        (initialized_project / "main").mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                with patch("worktrees.cli.tmux.get_tmux_sessions", return_value=[]):
                    with patch("worktrees.cli.tmux.create_tmux_session") as mock_create:
                        with patch(
                            "worktrees.cli.tmux.attach_or_switch"
                        ) as mock_attach:
                            result = runner.invoke(app, ["tmux", "main"])
                            assert result.exit_code == 0
                            assert "Created session" in result.output
                            assert "main" in result.output
                            mock_create.assert_called_once()
                            mock_attach.assert_called_once_with("main")

    def test_creates_session_with_venv(self, initialized_project):
        """Test creating session activates venv if present."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        # Create the worktree directory with .venv
        worktree_path = initialized_project / "main"
        worktree_path.mkdir()
        (worktree_path / ".venv" / "bin").mkdir(parents=True)
        (worktree_path / ".venv" / "bin" / "activate").touch()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                with patch("worktrees.cli.tmux.get_tmux_sessions", return_value=[]):
                    with patch("worktrees.cli.tmux.create_tmux_session") as mock_create:
                        with patch("worktrees.cli.tmux.attach_or_switch"):
                            result = runner.invoke(app, ["tmux", "main"])
                            assert result.exit_code == 0
                            assert ".venv activated" in result.output
                            # Verify activate_venv=True was passed
                            mock_create.assert_called_once()
                            call_args = mock_create.call_args
                            assert call_args[0][2] is True  # activate_venv

    def test_tmux_not_found(self, initialized_project):
        """Test error handling when tmux is not installed."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        (initialized_project / "main").mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                with patch("worktrees.cli.tmux.get_tmux_sessions", return_value=[]):
                    with patch(
                        "worktrees.cli.tmux.create_tmux_session",
                        side_effect=FileNotFoundError,
                    ):
                        result = runner.invoke(app, ["tmux", "main"])
                        assert result.exit_code == 1
                        assert "tmux not found" in result.output

    def test_prompts_when_sessions_exist(self, initialized_project):
        """Test that user is prompted when sessions exist."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        (initialized_project / "main").mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                with patch(
                    "worktrees.cli.tmux.get_tmux_sessions",
                    return_value=["main", "main-2"],
                ):
                    with patch("questionary.select") as mock_select:
                        # Simulate user selecting to attach to existing session
                        mock_select.return_value.ask.return_value = ("attach", "main")
                        with patch(
                            "worktrees.cli.tmux.attach_or_switch"
                        ) as mock_attach:
                            result = runner.invoke(app, ["tmux", "main"])
                            assert result.exit_code == 0
                            assert "Existing sessions" in result.output
                            mock_attach.assert_called_once_with("main")

    def test_user_cancels_prompt(self, initialized_project):
        """Test graceful exit when user cancels prompt."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        (initialized_project / "main").mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                with patch(
                    "worktrees.cli.tmux.get_tmux_sessions", return_value=["main"]
                ):
                    with patch("questionary.select") as mock_select:
                        # Simulate user pressing Ctrl+C
                        mock_select.return_value.ask.return_value = None
                        result = runner.invoke(app, ["tmux", "main"])
                        assert result.exit_code == 0

    def test_uses_current_worktree(self, initialized_project):
        """Test that command uses current worktree when no argument given."""
        mock_worktrees = [
            Worktree(
                path=initialized_project / "feature", commit="abc123", branch="feature"
            )
        ]
        (initialized_project / "feature").mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.get_current_worktree_name", return_value="feature"
            ):
                with patch(
                    "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
                ):
                    with patch("worktrees.cli.tmux.get_tmux_sessions", return_value=[]):
                        with patch("worktrees.cli.tmux.create_tmux_session"):
                            with patch(
                                "worktrees.cli.tmux.attach_or_switch"
                            ) as mock_attach:
                                result = runner.invoke(app, ["tmux"])
                                assert result.exit_code == 0
                                mock_attach.assert_called_once_with("feature")

    def test_create_session_fails_with_called_process_error(self, initialized_project):
        """Test error handling when tmux session creation fails."""
        import subprocess

        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        (initialized_project / "main").mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                with patch("worktrees.cli.tmux.get_tmux_sessions", return_value=[]):
                    with patch(
                        "worktrees.cli.tmux.create_tmux_session",
                        side_effect=subprocess.CalledProcessError(1, "tmux"),
                    ):
                        result = runner.invoke(app, ["tmux", "main"])
                        assert result.exit_code == 1
                        assert "failed to create tmux session" in result.output

    def test_user_selects_new_session_with_venv(self, initialized_project):
        """Test creating new session from prompt with venv."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        # Create the worktree directory with .venv
        worktree_path = initialized_project / "main"
        worktree_path.mkdir()
        (worktree_path / ".venv" / "bin").mkdir(parents=True)
        (worktree_path / ".venv" / "bin" / "activate").touch()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                with patch(
                    "worktrees.cli.tmux.get_tmux_sessions", return_value=["main"]
                ):
                    with patch("questionary.select") as mock_select:
                        # Simulate user selecting to create new session
                        mock_select.return_value.ask.return_value = ("create", "main-2")
                        with patch(
                            "worktrees.cli.tmux.create_tmux_session"
                        ) as mock_create:
                            with patch(
                                "worktrees.cli.tmux.attach_or_switch"
                            ) as mock_attach:
                                result = runner.invoke(app, ["tmux", "main"])
                                assert result.exit_code == 0
                                assert "Created session" in result.output
                                assert "main-2" in result.output
                                # Verify activate_venv=True was passed
                                mock_create.assert_called_once()
                                call_args = mock_create.call_args
                                assert call_args[0][2] is True  # activate_venv
                                mock_attach.assert_called_once_with("main-2")

    def test_attach_fails_with_called_process_error(self, initialized_project):
        """Test error handling when attaching to session fails."""
        import subprocess

        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        (initialized_project / "main").mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                with patch(
                    "worktrees.cli.tmux.get_tmux_sessions", return_value=["main"]
                ):
                    with patch("questionary.select") as mock_select:
                        # Simulate user selecting to attach
                        mock_select.return_value.ask.return_value = ("attach", "main")
                        with patch(
                            "worktrees.cli.tmux.attach_or_switch",
                            side_effect=subprocess.CalledProcessError(1, "tmux"),
                        ):
                            result = runner.invoke(app, ["tmux", "main"])
                            assert result.exit_code == 1
                            assert "tmux operation failed" in result.output

    def test_attach_fails_with_file_not_found(self, initialized_project):
        """Test error handling when tmux not found during attach."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        (initialized_project / "main").mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                with patch(
                    "worktrees.cli.tmux.get_tmux_sessions", return_value=["main"]
                ):
                    with patch("questionary.select") as mock_select:
                        # Simulate user selecting to attach
                        mock_select.return_value.ask.return_value = ("attach", "main")
                        with patch(
                            "worktrees.cli.tmux.attach_or_switch",
                            side_effect=FileNotFoundError,
                        ):
                            result = runner.invoke(app, ["tmux", "main"])
                            assert result.exit_code == 1
                            assert "tmux not found" in result.output


class TestTmuxNonInteractive:
    """Tests for --new and --attach non-interactive options."""

    def test_new_creates_session_no_existing(self, initialized_project):
        """Test --new creates session when no existing sessions."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        (initialized_project / "main").mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                with patch("worktrees.cli.tmux.get_tmux_sessions", return_value=[]):
                    with patch("worktrees.cli.tmux.create_tmux_session") as mock_create:
                        with patch(
                            "worktrees.cli.tmux.attach_or_switch"
                        ) as mock_attach:
                            result = runner.invoke(app, ["tmux", "main", "--new"])
                            assert result.exit_code == 0
                            assert "Created session" in result.output
                            assert "main" in result.output
                            mock_create.assert_called_once()
                            assert mock_create.call_args[0][0] == "main"
                            mock_attach.assert_called_once_with("main")

    def test_new_creates_next_session_with_existing(self, initialized_project):
        """Test --new creates next session name when sessions already exist."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        (initialized_project / "main").mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                with patch(
                    "worktrees.cli.tmux.get_tmux_sessions",
                    return_value=["main", "main-2"],
                ):
                    with patch("worktrees.cli.tmux.create_tmux_session") as mock_create:
                        with patch(
                            "worktrees.cli.tmux.attach_or_switch"
                        ) as mock_attach:
                            result = runner.invoke(app, ["tmux", "main", "--new"])
                            assert result.exit_code == 0
                            assert "Created session" in result.output
                            assert "main-3" in result.output
                            mock_create.assert_called_once()
                            assert mock_create.call_args[0][0] == "main-3"
                            mock_attach.assert_called_once_with("main-3")

    def test_new_and_attach_mutually_exclusive(self, initialized_project):
        """Test --new and --attach cannot be used together."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        (initialized_project / "main").mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                result = runner.invoke(
                    app, ["tmux", "main", "--new", "--attach", "main"]
                )
                assert result.exit_code == 1
                assert "mutually exclusive" in result.output

    def test_attach_to_existing_session(self, initialized_project):
        """Test --attach attaches to an existing session."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        (initialized_project / "main").mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                with patch(
                    "worktrees.cli.tmux.get_tmux_sessions", return_value=["main"]
                ):
                    with patch(
                        "worktrees.cli.tmux.attach_or_switch"
                    ) as mock_attach:
                        result = runner.invoke(
                            app, ["tmux", "main", "--attach", "main"]
                        )
                        assert result.exit_code == 0
                        mock_attach.assert_called_once_with("main")

    def test_attach_to_nonexistent_session(self, initialized_project):
        """Test --attach errors when session does not exist."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        (initialized_project / "main").mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                with patch("worktrees.cli.tmux.get_tmux_sessions", return_value=[]):
                    result = runner.invoke(
                        app, ["tmux", "main", "--attach", "nonexistent"]
                    )
                    assert result.exit_code == 1
                    assert "not found" in result.output

    def test_attach_shows_available_sessions(self, initialized_project):
        """Test --attach error includes available sessions."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        (initialized_project / "main").mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.tmux.list_worktrees", return_value=mock_worktrees
            ):
                with patch(
                    "worktrees.cli.tmux.get_tmux_sessions",
                    return_value=["main", "main-2"],
                ):
                    result = runner.invoke(
                        app, ["tmux", "main", "--attach", "nonexistent"]
                    )
                    assert result.exit_code == 1
                    assert "not found" in result.output
                    assert "available: main, main-2" in result.output
