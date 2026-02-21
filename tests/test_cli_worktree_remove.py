"""Tests for worktree remove CLI command with --delete-remaining option."""

import json
from pathlib import Path
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


class TestWorktreeRemoveDeleteRemaining:
    """Tests for the --delete-remaining option on the 'worktrees remove' command."""

    def test_remove_delete_remaining_auto_deletes(self, initialized_project):
        """Test --delete-remaining auto-deletes directory without prompting when not empty."""
        worktree_path = initialized_project / "feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.worktree.remove_worktree",
                side_effect=GitError("directory not empty"),
            ):
                with patch(
                    "worktrees.cli.worktree.list_worktrees", return_value=[]
                ):
                    with patch("questionary.confirm") as mock_confirm:
                        with patch("shutil.rmtree") as mock_rmtree:
                            result = runner.invoke(
                                app, ["remove", "feature", "--delete-remaining"]
                            )

                            assert result.exit_code == 0
                            mock_rmtree.assert_called_once_with(worktree_path)
                            mock_confirm.assert_not_called()

    def test_remove_without_flag_prompts(self, initialized_project):
        """Test without --delete-remaining, user is prompted when directory not empty."""
        worktree_path = initialized_project / "feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.worktree.remove_worktree",
                side_effect=GitError("directory not empty"),
            ):
                with patch(
                    "worktrees.cli.worktree.list_worktrees", return_value=[]
                ):
                    with patch("questionary.confirm") as mock_confirm:
                        mock_confirm.return_value.ask.return_value = True
                        with patch("shutil.rmtree") as mock_rmtree:
                            result = runner.invoke(
                                app, ["remove", "feature"]
                            )

                            assert result.exit_code == 0
                            mock_confirm.assert_called_once()
                            assert "Delete remaining files?" in mock_confirm.call_args[0][0]
                            mock_rmtree.assert_called_once_with(worktree_path)

    def test_remove_force_delete_remaining(self, initialized_project):
        """Test --force --delete-remaining handles uncommitted changes then directory not empty."""
        worktree_path = initialized_project / "feature"

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch(
                "worktrees.cli.worktree.remove_worktree",
            ) as mock_remove:
                # First call: raises "uncommitted changes" (initial non-force attempt)
                # Second call: raises "directory not empty" (force retry)
                mock_remove.side_effect = [
                    GitError("uncommitted changes"),
                    GitError("directory not empty"),
                ]
                with patch(
                    "worktrees.cli.worktree.list_worktrees", return_value=[]
                ):
                    with patch("questionary.confirm") as mock_confirm:
                        # The confirm prompt for "Force remove?" when uncommitted changes
                        mock_confirm.return_value.ask.return_value = True
                        with patch("shutil.rmtree") as mock_rmtree:
                            result = runner.invoke(
                                app,
                                ["remove", "feature", "--force", "--delete-remaining"],
                            )

                            assert result.exit_code == 0
                            # remove_worktree called twice: first with force=True
                            # (from CLI flag), then with force=True (from retry)
                            assert mock_remove.call_count == 2
                            mock_rmtree.assert_called_once_with(worktree_path)

    def test_remove_basic_success(self, initialized_project):
        """Test basic remove works without prompts when no errors occur."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            with patch("worktrees.cli.worktree.remove_worktree") as mock_remove:
                mock_remove.return_value = None
                with patch(
                    "worktrees.cli.worktree.list_worktrees", return_value=[]
                ):
                    with patch("questionary.confirm") as mock_confirm:
                        with patch("shutil.rmtree") as mock_rmtree:
                            result = runner.invoke(app, ["remove", "feature"])

                            assert result.exit_code == 0
                            assert "Removed" in result.output
                            mock_remove.assert_called_once()
                            mock_confirm.assert_not_called()
                            mock_rmtree.assert_not_called()
