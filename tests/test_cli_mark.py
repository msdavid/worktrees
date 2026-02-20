"""Tests for mark CLI commands."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from worktrees.cli import app
from worktrees.cli.mark import get_current_worktree_name, get_worktree_names
from worktrees.config import WORKTREES_JSON, WorktreesConfig
from worktrees.git import GitError, Worktree

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


class TestMarkCommand:
    """Tests for the mark command."""

    def test_mark_requires_initialized(self, tmp_path):
        """Test mark command requires initialized project."""
        with patch("worktrees.config.Path.cwd", return_value=tmp_path):
            result = runner.invoke(app, ["mark", "done"])
            assert result.exit_code == 1
            assert "not initialized" in result.output

    def test_mark_outside_worktree_without_w_flag(self, initialized_project):
        """Test mark command errors when outside worktree without -w."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.mark.get_current_worktree_name", return_value=None
            ):
                result = runner.invoke(app, ["mark", "done"])
                assert result.exit_code == 1
                assert "not inside a worktree" in result.output

    def test_mark_nonexistent_worktree(self, initialized_project):
        """Test mark command errors for nonexistent worktree."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.mark.list_worktrees", return_value=mock_worktrees
            ):
                result = runner.invoke(app, ["mark", "done", "-w", "nonexistent"])
                assert result.exit_code == 1
                assert "not found" in result.output

    def test_mark_sets_mark(self, initialized_project):
        """Test mark command sets mark on worktree."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.mark.list_worktrees", return_value=mock_worktrees
            ):
                result = runner.invoke(app, ["mark", "done", "-w", "main"])
                assert result.exit_code == 0
                assert "Marked" in result.output
                assert "done" in result.output

                # Verify mark was saved
                config_data = json.loads(
                    (initialized_project / WORKTREES_JSON).read_text()
                )
                assert config_data["marks"]["main"] == "done"

    def test_mark_replaces_existing(self, initialized_project):
        """Test mark command replaces existing mark."""
        # Set up existing mark
        config_file = initialized_project / WORKTREES_JSON
        config_file.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "worktreesDir": ".",
                    "setup": {"autoDetect": True, "commands": []},
                    "marks": {"main": "old mark"},
                }
            )
        )

        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.mark.list_worktrees", return_value=mock_worktrees
            ):
                result = runner.invoke(app, ["mark", "new", "mark", "-w", "main"])
                assert result.exit_code == 0

                # Verify mark was replaced
                config_data = json.loads(
                    (initialized_project / WORKTREES_JSON).read_text()
                )
                assert config_data["marks"]["main"] == "new mark"

    def test_mark_multiword(self, initialized_project):
        """Test mark command with multi-word mark."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.mark.list_worktrees", return_value=mock_worktrees
            ):
                result = runner.invoke(
                    app, ["mark", "ready", "for", "review", "-w", "main"]
                )
                assert result.exit_code == 0
                assert "ready for review" in result.output

                # Verify mark was saved
                config_data = json.loads(
                    (initialized_project / WORKTREES_JSON).read_text()
                )
                assert config_data["marks"]["main"] == "ready for review"

    def test_mark_show_without_text(self, initialized_project):
        """Test mark command shows mark when no text provided."""
        # Set up existing mark
        config_file = initialized_project / WORKTREES_JSON
        config_file.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "worktreesDir": ".",
                    "setup": {"autoDetect": True, "commands": []},
                    "marks": {"main": "done"},
                }
            )
        )

        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.mark.list_worktrees", return_value=mock_worktrees
            ):
                result = runner.invoke(app, ["mark", "-w", "main"])
                assert result.exit_code == 0
                assert "done" in result.output

    def test_mark_show_no_mark_without_text(self, initialized_project):
        """Test mark command shows no mark message when no mark exists."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.mark.list_worktrees", return_value=mock_worktrees
            ):
                result = runner.invoke(app, ["mark", "-w", "main"])
                assert result.exit_code == 0
                assert "No mark" in result.output


class TestUnmarkCommand:
    """Tests for the unmark command."""

    def test_unmark_requires_initialized(self, tmp_path):
        """Test unmark command requires initialized project."""
        with patch("worktrees.config.Path.cwd", return_value=tmp_path):
            result = runner.invoke(app, ["unmark"])
            assert result.exit_code == 1
            assert "not initialized" in result.output

    def test_unmark_clears_mark(self, initialized_project):
        """Test unmark command clears mark."""
        # Set up existing mark
        config_file = initialized_project / WORKTREES_JSON
        config_file.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "worktreesDir": ".",
                    "setup": {"autoDetect": True, "commands": []},
                    "marks": {"main": "done"},
                }
            )
        )

        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.mark.list_worktrees", return_value=mock_worktrees
            ):
                result = runner.invoke(app, ["unmark", "-w", "main"])
                assert result.exit_code == 0
                assert "Cleared mark" in result.output

                # Verify mark was cleared
                config_data = json.loads(
                    (initialized_project / WORKTREES_JSON).read_text()
                )
                assert "main" not in config_data["marks"]

    def test_unmark_no_mark(self, initialized_project):
        """Test unmark command handles no mark gracefully."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.mark.list_worktrees", return_value=mock_worktrees
            ):
                result = runner.invoke(app, ["unmark", "-w", "main"])
                assert result.exit_code == 0
                assert "No mark" in result.output

    def test_unmark_outside_worktree_without_w_flag(self, initialized_project):
        """Test unmark command errors when outside worktree without -w."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.mark.get_current_worktree_name", return_value=None
            ):
                result = runner.invoke(app, ["unmark"])
                assert result.exit_code == 1
                assert "not inside a worktree" in result.output

    def test_unmark_nonexistent_worktree(self, initialized_project):
        """Test unmark command errors for nonexistent worktree."""
        mock_worktrees = [
            Worktree(path=initialized_project / "main", commit="abc123", branch="main")
        ]
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.mark.list_worktrees", return_value=mock_worktrees
            ):
                result = runner.invoke(app, ["unmark", "-w", "nonexistent"])
                assert result.exit_code == 1
                assert "not found" in result.output


class TestGetCurrentWorktreeName:
    """Tests for get_current_worktree_name helper."""

    def test_returns_none_when_not_in_worktree(self, tmp_path):
        """Test returns None when not inside a worktree."""
        config = WorktreesConfig(project_root=tmp_path)
        mock_worktrees = [
            Worktree(path=tmp_path / "main", commit="abc123", branch="main"),
        ]

        with patch("worktrees.cli.mark.list_worktrees", return_value=mock_worktrees):
            with patch(
                "worktrees.cli.mark.Path.cwd", return_value=tmp_path / "elsewhere"
            ):
                result = get_current_worktree_name(config)
                assert result is None

    def test_returns_worktree_name_when_inside(self, tmp_path):
        """Test returns worktree name when inside a worktree."""
        config = WorktreesConfig(project_root=tmp_path)
        mock_worktrees = [
            Worktree(path=tmp_path / "main", commit="abc123", branch="main"),
        ]

        with patch("worktrees.cli.mark.list_worktrees", return_value=mock_worktrees):
            with patch("worktrees.cli.mark.Path.cwd", return_value=tmp_path / "main"):
                result = get_current_worktree_name(config)
                assert result == "main"

    def test_returns_none_on_git_error(self, tmp_path):
        """Test returns None when git error occurs."""
        config = WorktreesConfig(project_root=tmp_path)

        with patch(
            "worktrees.cli.mark.list_worktrees", side_effect=GitError("git failed")
        ):
            result = get_current_worktree_name(config)
            assert result is None

    def test_skips_bare_repo(self, tmp_path):
        """Test skips bare repository in worktree list."""
        config = WorktreesConfig(project_root=tmp_path)
        mock_worktrees = [
            Worktree(path=tmp_path / ".git", commit="abc123", branch="(bare)"),
            Worktree(path=tmp_path / "main", commit="abc123", branch="main"),
        ]

        with patch("worktrees.cli.mark.list_worktrees", return_value=mock_worktrees):
            with patch("worktrees.cli.mark.Path.cwd", return_value=tmp_path / "main"):
                result = get_current_worktree_name(config)
                assert result == "main"

    def test_handles_value_error_on_relative_path(self, tmp_path):
        """Test handles ValueError from is_relative_to check."""
        config = WorktreesConfig(project_root=tmp_path)
        mock_worktrees = [
            Worktree(path=tmp_path / "main", commit="abc123", branch="main"),
        ]

        with patch("worktrees.cli.mark.list_worktrees", return_value=mock_worktrees):
            with patch("worktrees.cli.mark.Path.cwd", return_value=tmp_path / "other"):
                # Mock is_relative_to to raise ValueError
                with patch.object(
                    tmp_path.__class__, "is_relative_to", side_effect=ValueError
                ):
                    result = get_current_worktree_name(config)
                    assert result is None

    def test_returns_deepest_match(self, tmp_path):
        """Test returns deepest matching worktree when nested."""
        config = WorktreesConfig(project_root=tmp_path)
        mock_worktrees = [
            Worktree(path=tmp_path / "main", commit="abc123", branch="main"),
            Worktree(path=tmp_path / "main" / "sub", commit="def456", branch="feature"),
        ]

        with patch("worktrees.cli.mark.list_worktrees", return_value=mock_worktrees):
            with patch(
                "worktrees.cli.mark.Path.cwd", return_value=tmp_path / "main" / "sub"
            ):
                result = get_current_worktree_name(config)
                assert result == "sub"


class TestGetWorktreeNames:
    """Tests for get_worktree_names helper."""

    def test_returns_worktree_names(self, tmp_path):
        """Test returns set of worktree names."""
        config = WorktreesConfig(project_root=tmp_path)
        mock_worktrees = [
            Worktree(path=tmp_path / "main", commit="abc123", branch="main"),
            Worktree(path=tmp_path / "feature", commit="def456", branch="feature"),
        ]

        with patch("worktrees.cli.mark.list_worktrees", return_value=mock_worktrees):
            result = get_worktree_names(config)
            assert result == {"main", "feature"}

    def test_excludes_bare_repo(self, tmp_path):
        """Test excludes bare repository from results."""
        config = WorktreesConfig(project_root=tmp_path)
        mock_worktrees = [
            Worktree(path=tmp_path / ".git", commit="abc123", branch="(bare)"),
            Worktree(path=tmp_path / "main", commit="abc123", branch="main"),
        ]

        with patch("worktrees.cli.mark.list_worktrees", return_value=mock_worktrees):
            result = get_worktree_names(config)
            assert result == {"main"}

    def test_returns_empty_on_git_error(self, tmp_path):
        """Test returns empty set when git error occurs."""
        config = WorktreesConfig(project_root=tmp_path)

        with patch(
            "worktrees.cli.mark.list_worktrees", side_effect=GitError("git failed")
        ):
            result = get_worktree_names(config)
            assert result == set()
