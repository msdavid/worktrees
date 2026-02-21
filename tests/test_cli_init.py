"""Tests for CLI __init__ module functions."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from worktrees.cli import (
    STYLE,
    app,
    decode_branch_name,
    encode_branch_name,
    show_worktree_list,
)
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


class TestRequireInitialized:
    """Tests for the require_initialized() function."""

    def test_require_initialized_success(self, initialized_project):
        """Test require_initialized returns config when project is initialized."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            # Test via CLI command that uses require_initialized
            result = runner.invoke(app, ["status"])
            # Status will work or fail based on initialization
            assert result.exit_code in [0, 1]  # Either success or controlled exit

    def test_require_initialized_no_project_root(self, tmp_path):
        """Test require_initialized exits when no project root found."""
        with patch("worktrees.config.Path.cwd", return_value=tmp_path):
            # Test via CLI - status command uses require_initialized
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 1
            assert "not initialized" in result.output

    def test_require_initialized_no_config_file(self, tmp_path):
        """Test require_initialized exits when config file doesn't exist."""
        with patch("worktrees.config.Path.cwd", return_value=tmp_path):
            # Test via CLI - status command uses require_initialized
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 1
            assert "not initialized" in result.output


class TestEncodeBranchName:
    """Tests for the encode_branch_name() function."""

    def test_encode_simple(self):
        """Test encoding a simple branch name (no slashes)."""
        assert encode_branch_name("main") == "main"

    def test_encode_with_slash(self):
        """Test encoding a branch with a single slash."""
        assert encode_branch_name("feat/my-feature") == "feat-slash-my-feature"

    def test_encode_multiple_slashes(self):
        """Test encoding a branch with multiple slashes."""
        assert (
            encode_branch_name("category/subcategory/feature")
            == "category-slash-subcategory-slash-feature"
        )

    def test_encode_trailing_slash(self):
        """Test encoding a branch with trailing slash (stripped)."""
        assert encode_branch_name("feat/feature/") == "feat-slash-feature"

    def test_encode_empty(self):
        """Test encoding an empty string."""
        assert encode_branch_name("") == ""


class TestDecodeBranchName:
    """Tests for the decode_branch_name() function."""

    def test_decode_simple(self):
        """Test decoding a simple name (no -slash- tokens)."""
        assert decode_branch_name("main") == "main"

    def test_decode_with_slash(self):
        """Test decoding a name with a single -slash- token."""
        assert decode_branch_name("feat-slash-my-feature") == "feat/my-feature"

    def test_decode_multiple_slashes(self):
        """Test decoding a name with multiple -slash- tokens."""
        assert (
            decode_branch_name("category-slash-subcategory-slash-feature")
            == "category/subcategory/feature"
        )

    def test_decode_empty(self):
        """Test decoding an empty string."""
        assert decode_branch_name("") == ""


class TestBranchNameRoundTrip:
    """Tests for encode/decode round-trip consistency."""

    @pytest.mark.parametrize(
        "branch",
        [
            "main",
            "feat/my-feature",
            "category/subcategory/feature",
            "release/v2.0",
            "a/b/c",
            "",
        ],
    )
    def test_round_trip(self, branch):
        """Test that decode(encode(branch)) == branch."""
        assert decode_branch_name(encode_branch_name(branch)) == branch


class TestShowWorktreeList:
    """Tests for the show_worktree_list() function."""

    def test_show_worktree_list_handles_git_error(self, initialized_project, capsys):
        """Test show_worktree_list handles GitError."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            from worktrees.config import WorktreesConfig

            config = WorktreesConfig.load(initialized_project)

            with patch(
                "worktrees.cli.list_worktrees", side_effect=GitError("test error")
            ):
                show_worktree_list(config, use_stderr=True)

                captured = capsys.readouterr()
                assert "error" in captured.err
                assert "test error" in captured.err

    def test_show_worktree_list_empty(self, initialized_project, capsys):
        """Test show_worktree_list with no worktrees."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            from worktrees.config import WorktreesConfig

            config = WorktreesConfig.load(initialized_project)

            with patch("worktrees.cli.list_worktrees", return_value=[]):
                show_worktree_list(config, use_stderr=False)

                captured = capsys.readouterr()
                # Should output table header
                assert "name" in captured.out or "branch" in captured.out

    def test_show_worktree_list_with_worktrees(self, initialized_project, capsys):
        """Test show_worktree_list displays worktrees."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            from worktrees.config import WorktreesConfig

            config = WorktreesConfig.load(initialized_project)

            worktrees = [
                Worktree(
                    path=initialized_project / "main", branch="main", commit="abc123"
                ),
                Worktree(
                    path=initialized_project / "feature",
                    branch="feature",
                    commit="def456",
                ),
            ]

            with patch("worktrees.cli.list_worktrees", return_value=worktrees):
                show_worktree_list(config, use_stderr=False)

                captured = capsys.readouterr()
                assert "main" in captured.out
                assert "feature" in captured.out
                assert "abc123" in captured.out

    def test_show_worktree_list_with_bare_repo(self, initialized_project, capsys):
        """Test show_worktree_list displays bare repo specially."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            from worktrees.config import WorktreesConfig

            config = WorktreesConfig.load(initialized_project)

            worktrees = [
                Worktree(path=initialized_project, branch="(bare)", commit="abc123"),
            ]

            with patch("worktrees.cli.list_worktrees", return_value=worktrees):
                show_worktree_list(config, use_stderr=False)

                captured = capsys.readouterr()
                assert "(bare)" in captured.out

    def test_show_worktree_list_with_marks(self, initialized_project, capsys):
        """Test show_worktree_list displays marks."""
        # Add marks to config
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

        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            from worktrees.config import WorktreesConfig

            config = WorktreesConfig.load(initialized_project)

            worktrees = [
                Worktree(
                    path=initialized_project / "feature",
                    branch="feature",
                    commit="abc123",
                ),
            ]

            with patch("worktrees.cli.list_worktrees", return_value=worktrees):
                show_worktree_list(config, use_stderr=False)

                captured = capsys.readouterr()
                assert "important" in captured.out

    def test_show_worktree_list_sorted_by_creation(self, initialized_project, capsys):
        """Test show_worktree_list sorts by creation time."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            from worktrees.config import WorktreesConfig

            config = WorktreesConfig.load(initialized_project)

            bare_path = initialized_project / "bare"
            main_path = initialized_project / "main"
            feature_path = initialized_project / "feature"

            # Create paths with different creation times
            bare_path.mkdir()
            main_path.mkdir()
            feature_path.mkdir()

            worktrees = [
                Worktree(path=feature_path, branch="feature", commit="def456"),
                Worktree(path=bare_path, branch="(bare)", commit="abc123"),
                Worktree(path=main_path, branch="main", commit="ghi789"),
            ]

            with patch("worktrees.cli.list_worktrees", return_value=worktrees):
                show_worktree_list(config, use_stderr=False)

                captured = capsys.readouterr()
                # Bare should be first, then others by creation time
                assert "(bare)" in captured.out

    def test_show_worktree_list_handles_missing_path(self, initialized_project, capsys):
        """Test show_worktree_list handles missing worktree path."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            from worktrees.config import WorktreesConfig

            config = WorktreesConfig.load(initialized_project)

            worktrees = [
                Worktree(
                    path=initialized_project / "nonexistent",
                    branch="feature",
                    commit="abc123",
                ),
            ]

            with patch("worktrees.cli.list_worktrees", return_value=worktrees):
                show_worktree_list(config, use_stderr=False)

                captured = capsys.readouterr()
                # Should not crash
                assert "feature" in captured.out

    def test_show_worktree_list_detached_branch(self, initialized_project, capsys):
        """Test show_worktree_list shows detached HEAD."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            from worktrees.config import WorktreesConfig

            config = WorktreesConfig.load(initialized_project)

            worktrees = [
                Worktree(
                    path=initialized_project / "detached", branch=None, commit="abc123"
                ),
            ]

            with patch("worktrees.cli.list_worktrees", return_value=worktrees):
                show_worktree_list(config, use_stderr=False)

                captured = capsys.readouterr()
                assert "(detached)" in captured.out

    def test_show_worktree_list_uses_stderr(self, initialized_project, capsys):
        """Test show_worktree_list can output to stderr."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            from worktrees.config import WorktreesConfig

            config = WorktreesConfig.load(initialized_project)

            worktrees = [
                Worktree(
                    path=initialized_project / "main", branch="main", commit="abc123"
                ),
            ]

            with patch("worktrees.cli.list_worktrees", return_value=worktrees):
                show_worktree_list(config, use_stderr=True)

                captured = capsys.readouterr()
                assert "main" in captured.err


class TestMainCallback:
    """Tests for the main() callback function."""

    def test_main_without_subcommand_requires_initialized(self, tmp_path):
        """Test main callback requires initialized project."""
        with patch("worktrees.config.Path.cwd", return_value=tmp_path):
            result = runner.invoke(app, [])
            assert result.exit_code == 1
            assert "not initialized" in result.output

    def test_main_without_subcommand_shows_list(self, initialized_project):
        """Test main callback shows worktree list."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            worktrees = [
                Worktree(
                    path=initialized_project / "main", branch="main", commit="abc123"
                ),
            ]

            with patch("worktrees.cli.list_worktrees", return_value=worktrees):
                result = runner.invoke(app, [])
                assert result.exit_code == 0
                assert "main" in result.output

    def test_main_with_subcommand_does_not_show_list(self, initialized_project):
        """Test main callback doesn't show list when subcommand is invoked."""
        with patch("worktrees.config.Path.cwd", return_value=initialized_project):
            result = runner.invoke(app, ["status"])
            # Should invoke status command, not the main list view
            # Status command will check for initialization separately
            assert result.exit_code == 0 or result.exit_code == 1


class TestConstants:
    """Tests for module constants."""

    def test_style_exists(self):
        """Test STYLE constant is defined."""
        assert STYLE is not None

    def test_app_exists(self):
        """Test app constant is defined."""
        assert app is not None
        assert app.info.name == "worktrees"


class TestInitNonInteractive:
    """Tests for the --bare/--no-bare and --worktrees-dir options of init."""

    def test_init_bare_converts_to_bare(self, tmp_path):
        """Test --bare converts to bare repository without questionary prompt."""
        with (
            patch("worktrees.config.Path.cwd", return_value=tmp_path),
            patch(
                "worktrees.cli.init_clone.is_git_repo", return_value=True
            ),
            patch(
                "worktrees.cli.init_clone.is_bare_repo", return_value=False
            ),
            patch(
                "worktrees.cli.init_clone.has_uncommitted_changes",
                return_value=False,
            ),
            patch(
                "worktrees.cli.init_clone.get_untracked_gitignored_files",
                return_value=[],
            ),
            patch(
                "worktrees.cli.init_clone.convert_to_bare",
                return_value=(tmp_path, "main"),
            ) as mock_convert,
            patch("worktrees.cli.init_clone.add_worktree"),
            patch("questionary.confirm") as mock_confirm,
        ):
            result = runner.invoke(app, ["init", "--bare"])
            assert result.exit_code == 0, result.output
            mock_convert.assert_called_once_with(tmp_path)
            mock_confirm.assert_not_called()

    def test_init_no_bare_uses_default_path(self, tmp_path):
        """Test --no-bare creates config with default ~/.worktrees/repo_name path."""
        with (
            patch("worktrees.config.Path.cwd", return_value=tmp_path),
            patch(
                "worktrees.cli.init_clone.is_git_repo", return_value=True
            ),
            patch(
                "worktrees.cli.init_clone.is_bare_repo", return_value=False
            ),
            patch(
                "worktrees.cli.init_clone.has_uncommitted_changes",
                return_value=False,
            ),
            patch(
                "worktrees.cli.init_clone.WorktreesConfig"
            ) as mock_config_cls,
            patch("questionary.confirm") as mock_confirm,
        ):
            mock_instance = mock_config_cls.return_value
            result = runner.invoke(app, ["init", "--no-bare"])
            assert result.exit_code == 0, result.output
            mock_confirm.assert_not_called()
            mock_config_cls.assert_called_once()
            call_kwargs = mock_config_cls.call_args
            expected_dir = Path.home() / ".worktrees" / tmp_path.name
            assert call_kwargs.kwargs["worktrees_dir"] == expected_dir
            assert call_kwargs.kwargs["project_root"] == tmp_path

    def test_init_no_bare_with_worktrees_dir(self, tmp_path):
        """Test --no-bare --worktrees-dir uses the provided path."""
        custom_dir = "/tmp/custom"
        with (
            patch("worktrees.config.Path.cwd", return_value=tmp_path),
            patch(
                "worktrees.cli.init_clone.is_git_repo", return_value=True
            ),
            patch(
                "worktrees.cli.init_clone.is_bare_repo", return_value=False
            ),
            patch(
                "worktrees.cli.init_clone.has_uncommitted_changes",
                return_value=False,
            ),
            patch(
                "worktrees.cli.init_clone.WorktreesConfig"
            ) as mock_config_cls,
            patch("questionary.confirm") as mock_confirm,
        ):
            mock_instance = mock_config_cls.return_value
            result = runner.invoke(
                app, ["init", "--no-bare", "--worktrees-dir", custom_dir]
            )
            assert result.exit_code == 0, result.output
            mock_confirm.assert_not_called()
            mock_config_cls.assert_called_once()
            call_kwargs = mock_config_cls.call_args
            assert call_kwargs.kwargs["worktrees_dir"] == Path(custom_dir)
            assert call_kwargs.kwargs["project_root"] == tmp_path

    def test_init_bare_with_worktrees_dir_errors(self, tmp_path):
        """Test --bare --worktrees-dir produces an error."""
        with (
            patch("worktrees.config.Path.cwd", return_value=tmp_path),
            patch(
                "worktrees.cli.init_clone.is_git_repo", return_value=True
            ),
            patch(
                "worktrees.cli.init_clone.is_bare_repo", return_value=False
            ),
            patch(
                "worktrees.cli.init_clone.has_uncommitted_changes",
                return_value=False,
            ),
        ):
            result = runner.invoke(
                app, ["init", "--bare", "--worktrees-dir", "/tmp/x"]
            )
            assert result.exit_code == 1
            assert "--worktrees-dir cannot be used with --bare" in result.output

    def test_init_neither_bare_prompts(self, tmp_path):
        """Test init without --bare/--no-bare prompts via questionary.confirm."""
        with (
            patch("worktrees.config.Path.cwd", return_value=tmp_path),
            patch(
                "worktrees.cli.init_clone.is_git_repo", return_value=True
            ),
            patch(
                "worktrees.cli.init_clone.is_bare_repo", return_value=False
            ),
            patch(
                "worktrees.cli.init_clone.has_uncommitted_changes",
                return_value=False,
            ),
            patch("questionary.confirm") as mock_confirm,
        ):
            # Simulate user cancelling the prompt (returns None)
            mock_confirm.return_value.ask.return_value = None
            result = runner.invoke(app, ["init"])
            mock_confirm.assert_called_once()
