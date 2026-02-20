"""Tests for status CLI command."""

import json
from pathlib import Path
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


class TestStatusCommand:
    """Tests for the status command."""

    def test_status_requires_initialized(self, tmp_path):
        """Test status command requires initialized project."""
        with patch("worktrees.config.Path.cwd", return_value=tmp_path):
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 1
            assert "not initialized" in result.output

    def test_status_handles_git_error(self, initialized_project):
        """Test status command handles GitError during list_worktrees."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.status.list_worktrees", side_effect=GitError("git error")
            ):
                result = runner.invoke(app, ["status"])
                assert result.exit_code == 1
                assert "git error" in result.output

    def test_status_not_in_worktree(self, initialized_project):
        """Test status command when not in a worktree."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.status.is_valid_worktree", return_value=False):
                with patch("worktrees.cli.status.list_worktrees") as mock_list:
                    mock_list.return_value = [
                        Worktree(
                            path=initialized_project / "main",
                            branch="main",
                            commit="abc123",
                        )
                    ]

                    result = runner.invoke(app, ["status"])
                    assert result.exit_code == 0
                    assert "not in a worktree" in result.output
                    assert "Project" in result.output
                    assert "worktrees:  1" in result.output

    def test_status_in_worktree_shows_info(self, initialized_project, tmp_path):
        """Test status command shows worktree info when inside one."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        with patch("worktrees.config.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.status.is_valid_worktree", return_value=True):
                with patch("worktrees.cli.status.list_worktrees") as mock_list:
                    mock_list.return_value = [
                        Worktree(path=worktree_path, branch="feature", commit="abc123")
                    ]

                    with patch(
                        "worktrees.cli.status.get_current_branch",
                        return_value="feature",
                    ):
                        with patch(
                            "worktrees.cli.status.has_uncommitted_changes",
                            return_value=False,
                        ):
                            result = runner.invoke(app, ["status"])
                            assert result.exit_code == 0
                            assert "feature" in result.output
                            assert "clean" in result.output
                            assert "worktrees:  1" in result.output

    def test_status_shows_uncommitted_changes(self, initialized_project):
        """Test status command shows uncommitted changes."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        with patch("worktrees.config.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.status.is_valid_worktree", return_value=True):
                with patch("worktrees.cli.status.list_worktrees") as mock_list:
                    mock_list.return_value = [
                        Worktree(path=worktree_path, branch="feature", commit="abc123")
                    ]

                    with patch(
                        "worktrees.cli.status.get_current_branch",
                        return_value="feature",
                    ):
                        with patch(
                            "worktrees.cli.status.has_uncommitted_changes",
                            return_value=True,
                        ):
                            result = runner.invoke(app, ["status"])
                            assert result.exit_code == 0
                            assert "uncommitted changes" in result.output

    def test_status_get_current_branch_error_shows_detached(self, initialized_project):
        """Test status command handles get_current_branch error gracefully."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        with patch("worktrees.config.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.status.is_valid_worktree", return_value=True):
                with patch("worktrees.cli.status.list_worktrees") as mock_list:
                    mock_list.return_value = [
                        Worktree(path=worktree_path, branch="feature", commit="abc123")
                    ]

                    with patch(
                        "worktrees.cli.status.get_current_branch",
                        side_effect=GitError("error"),
                    ):
                        with patch(
                            "worktrees.cli.status.has_uncommitted_changes",
                            return_value=False,
                        ):
                            result = runner.invoke(app, ["status"])
                            assert result.exit_code == 0
                            assert "feature" in result.output

    def test_status_shows_mark_if_present(self, initialized_project):
        """Test status command displays mark when set."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        # Add mark to config
        config_file = initialized_project / WORKTREES_JSON
        config_file.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "worktreesDir": ".",
                    "setup": {"autoDetect": True, "commands": []},
                    "marks": {"feature": "important"},
                }
            )
        )

        with patch("worktrees.config.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.status.is_valid_worktree", return_value=True):
                with patch("worktrees.cli.status.list_worktrees") as mock_list:
                    mock_list.return_value = [
                        Worktree(path=worktree_path, branch="feature", commit="abc123")
                    ]

                    with patch(
                        "worktrees.cli.status.get_current_branch",
                        return_value="feature",
                    ):
                        with patch(
                            "worktrees.cli.status.has_uncommitted_changes",
                            return_value=False,
                        ):
                            result = runner.invoke(app, ["status"])
                            assert result.exit_code == 0
                            assert "important" in result.output

    def test_status_excludes_bare_from_count(self, initialized_project):
        """Test status command excludes bare repo from worktree count."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        with patch("worktrees.config.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.status.is_valid_worktree", return_value=True):
                with patch("worktrees.cli.status.list_worktrees") as mock_list:
                    mock_list.return_value = [
                        Worktree(
                            path=initialized_project, branch="(bare)", commit="abc123"
                        ),
                        Worktree(path=worktree_path, branch="feature", commit="abc123"),
                    ]

                    with patch(
                        "worktrees.cli.status.get_current_branch",
                        return_value="feature",
                    ):
                        with patch(
                            "worktrees.cli.status.has_uncommitted_changes",
                            return_value=False,
                        ):
                            result = runner.invoke(app, ["status"])
                            assert result.exit_code == 0
                            assert "worktrees:  1" in result.output

    def test_status_in_nested_worktree_path(self, initialized_project):
        """Test status command finds worktree when in nested path."""
        worktree_path = initialized_project / "feature"
        nested_path = worktree_path / "src" / "nested"
        nested_path.mkdir(parents=True)

        with patch("worktrees.config.Path.cwd", return_value=nested_path):
            with patch("worktrees.cli.status.is_valid_worktree", return_value=True):
                with patch("worktrees.cli.status.list_worktrees") as mock_list:
                    mock_list.return_value = [
                        Worktree(path=worktree_path, branch="feature", commit="abc123")
                    ]

                    with patch(
                        "worktrees.cli.status.get_current_branch",
                        return_value="feature",
                    ):
                        with patch(
                            "worktrees.cli.status.has_uncommitted_changes",
                            return_value=False,
                        ):
                            result = runner.invoke(app, ["status"])
                            assert result.exit_code == 0
                            assert "feature" in result.output

    def test_status_shows_deepest_matching_worktree(self, initialized_project):
        """Test status command selects deepest matching worktree."""
        outer_path = initialized_project / "outer"
        inner_path = outer_path / "inner"
        nested_path = inner_path / "src"
        nested_path.mkdir(parents=True)

        with patch("worktrees.config.Path.cwd", return_value=nested_path):
            with patch("worktrees.cli.status.is_valid_worktree", return_value=True):
                with patch("worktrees.cli.status.list_worktrees") as mock_list:
                    mock_list.return_value = [
                        Worktree(path=outer_path, branch="outer", commit="abc123"),
                        Worktree(path=inner_path, branch="inner", commit="def456"),
                    ]

                    with patch(
                        "worktrees.cli.status.get_current_branch", return_value="inner"
                    ):
                        with patch(
                            "worktrees.cli.status.has_uncommitted_changes",
                            return_value=False,
                        ):
                            result = runner.invoke(app, ["status"])
                            assert result.exit_code == 0
                            assert "inner" in result.output

    def test_status_handles_value_error_on_relative_path(self, initialized_project):
        """Test status command handles ValueError when checking relative paths."""
        worktree_path = initialized_project / "feature"
        worktree_path.mkdir()

        with patch("worktrees.config.Path.cwd", return_value=worktree_path):
            with patch("worktrees.cli.status.is_valid_worktree", return_value=True):
                with patch("worktrees.cli.status.list_worktrees") as mock_list:
                    # Create a worktree that will raise ValueError on is_relative_to
                    mock_worktree = MagicMock()
                    mock_worktree.path = worktree_path
                    mock_worktree.branch = "feature"
                    mock_worktree.commit = "abc123"

                    # Mock is_relative_to to raise ValueError
                    def mock_relative_to(other):
                        if other == worktree_path:
                            return True
                        raise ValueError("path not relative")

                    with patch.object(
                        Path, "is_relative_to", side_effect=mock_relative_to
                    ):
                        mock_list.return_value = [mock_worktree]

                        with patch(
                            "worktrees.cli.status.get_current_branch",
                            return_value="feature",
                        ):
                            with patch(
                                "worktrees.cli.status.has_uncommitted_changes",
                                return_value=False,
                            ):
                                result = runner.invoke(app, ["status"])
                                assert result.exit_code == 0
