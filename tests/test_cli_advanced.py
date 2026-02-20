"""Tests for advanced CLI commands (convert-old, environ, merge)."""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from worktrees.cli import app
from worktrees.config import WORKTREES_JSON
from worktrees.git import GitError, Worktree

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


class TestConvertOldCommand:
    """Tests for the convert-old command."""

    def test_convert_old_requires_worktrees_json(self, tmp_path):
        """Test convert-old requires .worktrees.json file."""
        with patch("worktrees.cli.advanced.Path.cwd", return_value=tmp_path):
            result = runner.invoke(app, ["convert-old"])
            assert result.exit_code == 1
            assert "not a worktrees project" in result.output

    def test_convert_old_already_migrated(self, initialized_project):
        """Test convert-old exits when .git/ directory already exists."""
        gitdir = initialized_project / ".git"
        gitdir.mkdir()

        with patch("worktrees.cli.advanced.Path.cwd", return_value=initialized_project):
            result = runner.invoke(app, ["convert-old"])
            assert result.exit_code == 0
            assert "already migrated" in result.output

    def test_convert_old_no_bare_repo(self, initialized_project):
        """Test convert-old exits when no bare repository at root."""
        with patch("worktrees.cli.advanced.Path.cwd", return_value=initialized_project):
            result = runner.invoke(app, ["convert-old"])
            assert result.exit_code == 0
            assert "nothing to migrate" in result.output

    def test_convert_old_success(self, initialized_project):
        """Test convert-old successfully migrates bare repo."""
        # Create bare repo files
        head_file = initialized_project / "HEAD"
        head_file.write_text("ref: refs/heads/main\n")

        with patch("worktrees.cli.advanced.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.advanced.migrate_to_dotgit") as mock_migrate:
                with patch("worktrees.cli.advanced.list_worktrees") as mock_list:
                    mock_list.return_value = [
                        Worktree(
                            path=initialized_project / "main",
                            branch="main",
                            commit="abc123",
                        )
                    ]

                    result = runner.invoke(app, ["convert-old"])
                    assert result.exit_code == 0
                    assert "Migrated" in result.output
                    assert "main" in result.output
                    mock_migrate.assert_called_once_with(initialized_project)

    def test_convert_old_git_error(self, initialized_project):
        """Test convert-old handles GitError."""
        head_file = initialized_project / "HEAD"
        head_file.write_text("ref: refs/heads/main\n")

        with patch("worktrees.cli.advanced.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.advanced.migrate_to_dotgit",
                side_effect=GitError("migration failed"),
            ):
                result = runner.invoke(app, ["convert-old"])
                assert result.exit_code == 1
                assert "migration failed" in result.output

    def test_convert_old_excludes_bare_from_output(self, initialized_project):
        """Test convert-old does not list bare repo in output."""
        head_file = initialized_project / "HEAD"
        head_file.write_text("ref: refs/heads/main\n")

        with patch("worktrees.cli.advanced.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.advanced.migrate_to_dotgit"):
                with patch("worktrees.cli.advanced.list_worktrees") as mock_list:
                    mock_list.return_value = [
                        Worktree(
                            path=initialized_project, branch="(bare)", commit="abc123"
                        ),
                        Worktree(
                            path=initialized_project / "main",
                            branch="main",
                            commit="abc123",
                        ),
                    ]

                    result = runner.invoke(app, ["convert-old"])
                    assert result.exit_code == 0
                    # Should show "main" but not "(bare)"
                    assert "main" in result.output


class TestEnvironCommand:
    """Tests for the environ command."""

    def test_environ_requires_valid_worktree(self, tmp_path):
        """Test environ command must be run from inside a worktree."""
        with patch("worktrees.cli.advanced.Path.cwd", return_value=tmp_path):
            with patch("worktrees.cli.advanced.is_valid_worktree", return_value=False):
                result = runner.invoke(app, ["environ"])
                assert result.exit_code == 1
                assert "not inside a worktree" in result.output

    def test_environ_requires_project_root(self, tmp_path):
        """Test environ command requires project root."""
        with patch("worktrees.cli.advanced.Path.cwd", return_value=tmp_path):
            with patch("worktrees.cli.advanced.is_valid_worktree", return_value=True):
                with patch(
                    "worktrees.cli.advanced.find_project_root", return_value=None
                ):
                    result = runner.invoke(app, ["environ"])
                    assert result.exit_code == 1
                    assert "cannot find project root" in result.output

    def test_environ_no_environ_directory(self, initialized_project, tmp_path):
        """Test environ command when ENVIRON directory doesn't exist."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        with patch("worktrees.cli.advanced.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.advanced.is_valid_worktree", return_value=True):
                with patch(
                    "worktrees.cli.advanced.find_project_root",
                    return_value=initialized_project,
                ):
                    result = runner.invoke(app, ["environ"])
                    assert result.exit_code == 0
                    assert "no ENVIRON directory" in result.output

    def test_environ_empty_environ_directory(self, initialized_project):
        """Test environ command with empty ENVIRON directory."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        environ_dir = initialized_project / "ENVIRON"
        environ_dir.mkdir()

        with patch("worktrees.cli.advanced.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.advanced.is_valid_worktree", return_value=True):
                with patch(
                    "worktrees.cli.advanced.find_project_root",
                    return_value=initialized_project,
                ):
                    result = runner.invoke(app, ["environ"])
                    assert result.exit_code == 0
                    assert "empty" in result.output

    def test_environ_creates_symlinks(self, initialized_project):
        """Test environ command creates symlinks."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        environ_dir = initialized_project / "ENVIRON"
        environ_dir.mkdir()
        (environ_dir / ".env").write_text("TEST=value")

        with patch("worktrees.cli.advanced.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.advanced.is_valid_worktree", return_value=True):
                with patch(
                    "worktrees.cli.advanced.find_project_root",
                    return_value=initialized_project,
                ):
                    with patch(
                        "worktrees.cli.advanced.find_stale_environ_symlinks",
                        return_value=[],
                    ):
                        with patch(
                            "worktrees.cli.advanced.create_environ_symlinks",
                            return_value=[".env"],
                        ):
                            result = runner.invoke(app, ["environ"])
                            assert result.exit_code == 0
                            assert "Linked" in result.output
                            assert ".env" in result.output

    def test_environ_no_new_symlinks(self, initialized_project):
        """Test environ command when all symlinks already exist."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        environ_dir = initialized_project / "ENVIRON"
        environ_dir.mkdir()
        (environ_dir / ".env").write_text("TEST=value")

        with patch("worktrees.cli.advanced.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.advanced.is_valid_worktree", return_value=True):
                with patch(
                    "worktrees.cli.advanced.find_project_root",
                    return_value=initialized_project,
                ):
                    with patch(
                        "worktrees.cli.advanced.find_stale_environ_symlinks",
                        return_value=[],
                    ):
                        with patch(
                            "worktrees.cli.advanced.create_environ_symlinks",
                            return_value=[],
                        ):
                            result = runner.invoke(app, ["environ"])
                            assert result.exit_code == 0
                            assert "no new symlinks" in result.output

    def test_environ_handles_git_error(self, initialized_project):
        """Test environ command handles GitError."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        environ_dir = initialized_project / "ENVIRON"
        environ_dir.mkdir()
        (environ_dir / ".env").write_text("TEST=value")

        with patch("worktrees.cli.advanced.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.advanced.is_valid_worktree", return_value=True):
                with patch(
                    "worktrees.cli.advanced.find_project_root",
                    return_value=initialized_project,
                ):
                    with patch(
                        "worktrees.cli.advanced.find_stale_environ_symlinks",
                        return_value=[],
                    ):
                        with patch(
                            "worktrees.cli.advanced.create_environ_symlinks",
                            side_effect=GitError("link error"),
                        ):
                            result = runner.invoke(app, ["environ"])
                            assert result.exit_code == 1
                            assert "link error" in result.output

    def test_environ_finds_stale_symlinks(self, initialized_project):
        """Test environ command finds and reports stale symlinks."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        environ_dir = initialized_project / "ENVIRON"
        environ_dir.mkdir()
        (environ_dir / ".env").write_text("TEST=value")

        stale_link = worktree_path / ".old_env"
        stale_link.write_text("")  # Create file so it exists

        with patch("worktrees.cli.advanced.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.advanced.is_valid_worktree", return_value=True):
                with patch(
                    "worktrees.cli.advanced.find_project_root",
                    return_value=initialized_project,
                ):
                    with patch(
                        "worktrees.cli.advanced.find_stale_environ_symlinks",
                        return_value=[stale_link],
                    ):
                        with patch(
                            "worktrees.cli.advanced.create_environ_symlinks",
                            return_value=[],
                        ):
                            # Use --remove-stale flag to avoid interactive prompt
                            result = runner.invoke(app, ["environ", "--remove-stale"])
                            assert result.exit_code == 0
                            assert "Stale symlinks" in result.output

    def test_environ_removes_stale_symlinks_with_flag(self, initialized_project):
        """Test environ command removes stale symlinks with --remove-stale flag."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        environ_dir = initialized_project / "ENVIRON"
        environ_dir.mkdir()
        (environ_dir / ".env").write_text("TEST=value")

        stale_link = worktree_path / ".old_env"
        stale_link.write_text("")  # Create file to be "removed"

        with patch("worktrees.cli.advanced.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.advanced.is_valid_worktree", return_value=True):
                with patch(
                    "worktrees.cli.advanced.find_project_root",
                    return_value=initialized_project,
                ):
                    with patch(
                        "worktrees.cli.advanced.find_stale_environ_symlinks",
                        return_value=[stale_link],
                    ):
                        with patch(
                            "worktrees.cli.advanced.create_environ_symlinks",
                            return_value=[],
                        ):
                            result = runner.invoke(app, ["environ", "--remove-stale"])
                            assert result.exit_code == 0
                            assert "removed" in result.output

    def test_environ_prompts_for_stale_removal(self, initialized_project):
        """Test environ command prompts for stale symlink removal."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        environ_dir = initialized_project / "ENVIRON"
        environ_dir.mkdir()
        (environ_dir / ".env").write_text("TEST=value")

        stale_link = worktree_path / ".old_env"

        with patch("worktrees.cli.advanced.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.advanced.is_valid_worktree", return_value=True):
                with patch(
                    "worktrees.cli.advanced.find_project_root",
                    return_value=initialized_project,
                ):
                    with patch(
                        "worktrees.cli.advanced.find_stale_environ_symlinks",
                        return_value=[stale_link],
                    ):
                        with patch(
                            "worktrees.cli.advanced.create_environ_symlinks",
                            return_value=[],
                        ):
                            with patch("questionary.confirm") as mock_confirm:
                                mock_confirm.return_value.ask.return_value = False

                                result = runner.invoke(app, ["environ"])
                                assert result.exit_code == 0
                                assert "skipped" in result.output
                                mock_confirm.assert_called_once()

    def test_environ_user_confirms_stale_removal(self, initialized_project):
        """Test environ command removes stale when user confirms."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        environ_dir = initialized_project / "ENVIRON"
        environ_dir.mkdir()
        (environ_dir / ".env").write_text("TEST=value")

        stale_link = worktree_path / ".old_env"
        stale_link.write_text("")

        with patch("worktrees.cli.advanced.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.advanced.is_valid_worktree", return_value=True):
                with patch(
                    "worktrees.cli.advanced.find_project_root",
                    return_value=initialized_project,
                ):
                    with patch(
                        "worktrees.cli.advanced.find_stale_environ_symlinks",
                        return_value=[stale_link],
                    ):
                        with patch(
                            "worktrees.cli.advanced.create_environ_symlinks",
                            return_value=[],
                        ):
                            with patch("questionary.confirm") as mock_confirm:
                                mock_confirm.return_value.ask.return_value = True

                                result = runner.invoke(app, ["environ"])
                                assert result.exit_code == 0
                                assert "removed" in result.output


class TestMergeCommand:
    """Tests for the merge command."""

    def test_merge_requires_initialized(self, tmp_path):
        """Test merge command requires initialized project."""
        with patch("worktrees.config.Path.cwd", return_value=tmp_path):
            result = runner.invoke(app, ["merge", "feature"])
            assert result.exit_code == 1
            assert "not initialized" in result.output

    def test_merge_requires_user_config(self, initialized_project, tmp_path):
        """Test merge command requires AI configuration."""
        nonexistent_config = tmp_path / "nonexistent.json"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", nonexistent_config):
                with patch(
                    "worktrees.cli.advanced.is_valid_worktree", return_value=True
                ):
                    result = runner.invoke(app, ["merge", "feature"])
                    assert result.exit_code == 1
                    assert "not configured" in result.output
                    assert "worktrees config" in result.output

    def test_merge_requires_worktree(self, initialized_project, tmp_path):
        """Test merge command must be run from inside a worktree."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=False
                    ):
                        result = runner.invoke(app, ["merge", "feature"])
                        assert result.exit_code == 1
                        assert "inside a worktree" in result.output

    def test_merge_get_current_branch_error(self, initialized_project, tmp_path):
        """Test merge command handles get_current_branch errors."""
        from worktrees.git import GitError

        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=True
                    ):
                        with patch(
                            "worktrees.cli.advanced.get_current_branch",
                            side_effect=GitError("test error"),
                        ):
                            result = runner.invoke(app, ["merge", "feature"])
                            assert result.exit_code == 1
                            assert "test error" in result.output

    def test_merge_cannot_merge_into_self(self, initialized_project, tmp_path):
        """Test merge command prevents merging branch into itself."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=True
                    ):
                        with patch(
                            "worktrees.cli.advanced.get_current_branch",
                            return_value="main",
                        ):
                            result = runner.invoke(app, ["merge", "main"])
                            assert result.exit_code == 1
                            assert "cannot merge branch into itself" in result.output

    def test_merge_with_explicit_branch(self, initialized_project, tmp_path):
        """Test merge command with explicitly provided branch."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_config.ai.provider = "claude"
                    mock_config.ai.build_command.return_value = "echo merging"
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=True
                    ):
                        with patch(
                            "worktrees.cli.advanced.get_current_branch",
                            return_value="main",
                        ):
                            with patch("subprocess.run") as mock_run:
                                mock_run.return_value = MagicMock(returncode=0)

                                result = runner.invoke(app, ["merge", "feature"])
                                assert result.exit_code == 0
                                assert "Merging" in result.output
                                assert "feature" in result.output
                                assert "main" in result.output

                                # Verify AI command was built correctly
                                mock_config.ai.build_command.assert_called_once_with(
                                    target_branch="feature", current_branch="main"
                                )

                                # Verify subprocess.run was called
                                assert mock_run.called

    def test_merge_interactive_branch_selection_no_branches(
        self, initialized_project, tmp_path
    ):
        """Test merge command interactive mode with no branches to merge."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=True
                    ):
                        with patch(
                            "worktrees.cli.advanced.get_current_branch",
                            return_value="main",
                        ):
                            with patch(
                                "worktrees.cli.advanced.list_local_branches",
                                return_value=["main"],
                            ):
                                result = runner.invoke(app, ["merge"])
                                assert result.exit_code == 0
                                assert "no branches to merge" in result.output

    def test_merge_interactive_branch_selection_git_error(
        self, initialized_project, tmp_path
    ):
        """Test merge command handles git errors during branch listing."""
        from worktrees.git import GitError

        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=True
                    ):
                        with patch(
                            "worktrees.cli.advanced.get_current_branch",
                            return_value="main",
                        ):
                            with patch(
                                "worktrees.cli.advanced.list_local_branches",
                                side_effect=GitError("branch error"),
                            ):
                                result = runner.invoke(app, ["merge"])
                                assert result.exit_code == 1
                                assert "branch error" in result.output

    def test_merge_interactive_branch_selection_user_cancels(
        self, initialized_project, tmp_path
    ):
        """Test merge command handles user canceling branch selection."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=True
                    ):
                        with patch(
                            "worktrees.cli.advanced.get_current_branch",
                            return_value="main",
                        ):
                            with patch(
                                "worktrees.cli.advanced.list_local_branches",
                                return_value=["main", "feature"],
                            ):
                                with patch("questionary.select") as mock_select:
                                    mock_select.return_value.ask.return_value = None

                                    result = runner.invoke(app, ["merge"])
                                    assert result.exit_code == 0

    def test_merge_interactive_branch_selection_success(
        self, initialized_project, tmp_path
    ):
        """Test merge command with successful interactive branch selection."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_config.ai.provider = "claude"
                    mock_config.ai.build_command.return_value = "echo merging"
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=True
                    ):
                        with patch(
                            "worktrees.cli.advanced.get_current_branch",
                            return_value="main",
                        ):
                            with patch(
                                "worktrees.cli.advanced.list_local_branches",
                                return_value=["main", "feature", "develop"],
                            ):
                                with patch("questionary.select") as mock_select:
                                    mock_select.return_value.ask.return_value = (
                                        "feature"
                                    )

                                    with patch("subprocess.run") as mock_run:
                                        mock_run.return_value = MagicMock(returncode=0)

                                        result = runner.invoke(app, ["merge"])
                                        assert result.exit_code == 0
                                        assert "Merging" in result.output
                                        assert "feature" in result.output

                                        # Verify branch was used
                                        mock_config.ai.build_command.assert_called_once_with(
                                            target_branch="feature",
                                            current_branch="main",
                                        )

    def test_merge_subprocess_nonzero_exit(self, initialized_project, tmp_path):
        """Test merge command propagates subprocess exit code."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_config.ai.provider = "claude"
                    mock_config.ai.build_command.return_value = "exit 42"
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=True
                    ):
                        with patch(
                            "worktrees.cli.advanced.get_current_branch",
                            return_value="main",
                        ):
                            with patch(
                                "worktrees.cli.advanced.list_worktrees", return_value=[]
                            ):
                                with patch("subprocess.run") as mock_run:
                                    mock_run.return_value = MagicMock(returncode=42)

                                    result = runner.invoke(app, ["merge", "feature"])
                                    assert result.exit_code == 42

    def test_merge_command_not_found(self, initialized_project, tmp_path):
        """Test merge command handles AI command not found."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_config.ai.provider = "claude"
                    mock_config.ai.build_command.return_value = "/nonexistent/command"
                    mock_config.ai.get_effective_command.return_value = (
                        "/nonexistent/command"
                    )
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=True
                    ):
                        with patch(
                            "worktrees.cli.advanced.get_current_branch",
                            return_value="main",
                        ):
                            with patch(
                                "worktrees.cli.advanced.list_worktrees", return_value=[]
                            ):
                                with patch(
                                    "subprocess.run", side_effect=FileNotFoundError()
                                ):
                                    result = runner.invoke(app, ["merge", "feature"])
                                    assert result.exit_code == 1
                                    assert "command not found" in result.output

    def test_merge_filters_current_branch_from_selection(
        self, initialized_project, tmp_path
    ):
        """Test merge interactive selection excludes current branch."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_config.ai.provider = "gemini"
                    mock_config.ai.build_command.return_value = (
                        "gemini -i 'merge feature'"
                    )
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=True
                    ):
                        with patch(
                            "worktrees.cli.advanced.get_current_branch",
                            return_value="main",
                        ):
                            with patch(
                                "worktrees.cli.advanced.list_local_branches",
                                return_value=["main", "feature", "develop"],
                            ):
                                with patch("questionary.select") as mock_select:
                                    mock_select.return_value.ask.return_value = (
                                        "develop"
                                    )

                                    with patch("subprocess.run") as mock_run:
                                        mock_run.return_value = MagicMock(returncode=0)

                                        result = runner.invoke(app, ["merge"])
                                        assert result.exit_code == 0

                                        # Verify the select was called with choices that don't include "main"
                                        call_args = mock_select.call_args
                                        choices = call_args[1]["choices"]
                                        choice_values = [c.value for c in choices]
                                        assert "feature" in choice_values
                                        assert "develop" in choice_values
                                        assert "main" not in choice_values

    def test_merge_uses_gemini_provider(self, initialized_project, tmp_path):
        """Test merge command works with gemini provider."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_config.ai.provider = "gemini"
                    mock_config.ai.build_command.return_value = (
                        "/usr/bin/gemini -i 'merge feature'"
                    )
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=True
                    ):
                        with patch(
                            "worktrees.cli.advanced.get_current_branch",
                            return_value="main",
                        ):
                            with patch("subprocess.run") as mock_run:
                                mock_run.return_value = MagicMock(returncode=0)

                                result = runner.invoke(app, ["merge", "feature"])
                                assert result.exit_code == 0
                                assert "gemini" in result.output

    def test_merge_fails_if_source_has_uncommitted_changes(
        self, initialized_project, tmp_path
    ):
        """Test merge fails when source branch worktree has uncommitted changes."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        feature_worktree = initialized_project / "feature"
        feature_worktree.mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=True
                    ):
                        with patch(
                            "worktrees.cli.advanced.get_current_branch",
                            return_value="main",
                        ):
                            with patch(
                                "worktrees.cli.advanced.list_worktrees"
                            ) as mock_list_wt:
                                mock_list_wt.return_value = [
                                    Worktree(
                                        path=initialized_project / "main",
                                        branch="main",
                                        commit="abc123",
                                    ),
                                    Worktree(
                                        path=feature_worktree,
                                        branch="feature",
                                        commit="def456",
                                    ),
                                ]
                                with patch(
                                    "worktrees.cli.advanced.has_uncommitted_changes",
                                    return_value=True,
                                ):
                                    result = runner.invoke(app, ["merge", "feature"])
                                    assert result.exit_code == 1
                                    assert "uncommitted changes" in result.output
                                    assert "feature" in result.output

    def test_merge_succeeds_if_source_has_no_uncommitted_changes(
        self, initialized_project, tmp_path
    ):
        """Test merge succeeds when source branch worktree is clean."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        feature_worktree = initialized_project / "feature"
        feature_worktree.mkdir()

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_config.ai.provider = "claude"
                    mock_config.ai.build_command.return_value = "echo merging"
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=True
                    ):
                        with patch(
                            "worktrees.cli.advanced.get_current_branch",
                            return_value="main",
                        ):
                            with patch(
                                "worktrees.cli.advanced.list_worktrees"
                            ) as mock_list_wt:
                                mock_list_wt.return_value = [
                                    Worktree(
                                        path=initialized_project / "main",
                                        branch="main",
                                        commit="abc123",
                                    ),
                                    Worktree(
                                        path=feature_worktree,
                                        branch="feature",
                                        commit="def456",
                                    ),
                                ]
                                with patch(
                                    "worktrees.cli.advanced.has_uncommitted_changes",
                                    return_value=False,
                                ):
                                    with patch("subprocess.run") as mock_run:
                                        mock_run.return_value = MagicMock(returncode=0)

                                        result = runner.invoke(
                                            app, ["merge", "feature"]
                                        )
                                        assert result.exit_code == 0
                                        assert "Merging" in result.output

    def test_merge_proceeds_if_source_branch_has_no_worktree(
        self, initialized_project, tmp_path
    ):
        """Test merge proceeds when source branch has no worktree (remote only)."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.user_config.GLOBAL_CONFIG_FILE", config_file):
                with patch("worktrees.user_config.UserConfig.load") as mock_load:
                    mock_config = MagicMock()
                    mock_config.is_configured.return_value = True
                    mock_config.ai.provider = "claude"
                    mock_config.ai.build_command.return_value = "echo merging"
                    mock_load.return_value = mock_config

                    with patch(
                        "worktrees.cli.advanced.is_valid_worktree", return_value=True
                    ):
                        with patch(
                            "worktrees.cli.advanced.get_current_branch",
                            return_value="main",
                        ):
                            with patch(
                                "worktrees.cli.advanced.list_worktrees"
                            ) as mock_list_wt:
                                # Only main worktree exists, feature branch has no worktree
                                mock_list_wt.return_value = [
                                    Worktree(
                                        path=initialized_project / "main",
                                        branch="main",
                                        commit="abc123",
                                    ),
                                ]
                                with patch("subprocess.run") as mock_run:
                                    mock_run.return_value = MagicMock(returncode=0)

                                    result = runner.invoke(app, ["merge", "feature"])
                                    assert result.exit_code == 0
                                    assert "Merging" in result.output
