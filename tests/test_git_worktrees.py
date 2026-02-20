"""Tests for worktree-specific git operations."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from worktrees.git import (
    GitError,
    Worktree,
    add_worktree,
    clone_bare,
    create_environ_symlinks,
    delete_branch,
    delete_remote_branch,
    find_stale_environ_symlinks,
    get_main_worktree,
    get_untracked_gitignored_files,
    list_worktrees,
    merge_branch,
    migrate_to_dotgit,
    prune_worktrees,
    remove_worktree,
    run_setup_command,
)


class TestListWorktrees:
    """Tests for list_worktrees() function."""

    @patch("worktrees.git.run_git")
    def test_list_worktrees_single(self, mock_run_git):
        """Test listing single worktree."""
        mock_result = MagicMock()
        mock_result.stdout = (
            "worktree /home/user/project\n"
            "HEAD abc1234567890abcdef1234567890abcdef12\n"
            "branch refs/heads/main\n"
            "\n"
        )
        mock_run_git.return_value = mock_result

        worktrees = list_worktrees()
        assert len(worktrees) == 1
        assert worktrees[0].path == Path("/home/user/project")
        assert worktrees[0].commit == "abc1234"
        assert worktrees[0].branch == "main"

    @patch("worktrees.git.run_git")
    def test_list_worktrees_multiple(self, mock_run_git):
        """Test listing multiple worktrees."""
        mock_result = MagicMock()
        mock_result.stdout = (
            "worktree /home/user/project/.git\n"
            "HEAD abc1234567890abcdef1234567890abcdef12\n"
            "bare\n"
            "\n"
            "worktree /home/user/project/main\n"
            "HEAD def5678901234567890abcdef1234567890ab\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /home/user/project/feature\n"
            "HEAD 9876543210fedcba0123456789abcdef0123\n"
            "branch refs/heads/feature/test\n"
            "\n"
        )
        mock_run_git.return_value = mock_result

        worktrees = list_worktrees()
        assert len(worktrees) == 3
        assert worktrees[0].branch == "(bare)"
        assert worktrees[1].branch == "main"
        assert worktrees[2].branch == "feature/test"

    @patch("worktrees.git.run_git")
    def test_list_worktrees_detached(self, mock_run_git):
        """Test listing worktree in detached HEAD state."""
        mock_result = MagicMock()
        mock_result.stdout = (
            "worktree /home/user/project/detached\n"
            "HEAD abc1234567890abcdef1234567890abcdef12\n"
            "detached\n"
            "\n"
        )
        mock_run_git.return_value = mock_result

        worktrees = list_worktrees()
        assert len(worktrees) == 1
        assert worktrees[0].branch == "(detached)"


class TestAddWorktree:
    """Tests for add_worktree() function."""

    @patch("worktrees.git.branch_exists")
    @patch("worktrees.git.run_git")
    def test_add_worktree_existing_branch(self, mock_run_git, mock_branch_exists):
        """Test adding worktree for existing branch."""
        mock_branch_exists.return_value = (True, False)

        worktree_path = Path("/test/worktrees/feature")
        with patch.object(Path, "mkdir"):
            result = add_worktree(worktree_path, "feature")

        assert result == worktree_path
        mock_run_git.assert_called_once_with(
            "worktree", "add", str(worktree_path), "feature", cwd=None
        )

    @patch("worktrees.git.branch_exists")
    @patch("worktrees.git.run_git")
    def test_add_worktree_new_branch(self, mock_run_git, mock_branch_exists):
        """Test adding worktree with new branch creation."""
        mock_branch_exists.return_value = (False, False)

        worktree_path = Path("/test/worktrees/new-feature")
        with patch.object(Path, "mkdir"):
            result = add_worktree(
                worktree_path, "new-feature", create_branch=True, base_branch="main"
            )

        assert result == worktree_path
        mock_run_git.assert_called_once_with(
            "worktree", "add", "-b", "new-feature", str(worktree_path), "main", cwd=None
        )

    @patch("worktrees.git.run_git")
    def test_add_worktree_create_branch_no_base(self, mock_run_git):
        """Test adding worktree creating branch without base."""
        worktree_path = Path("/test/worktrees/feature")
        with patch.object(Path, "mkdir"):
            add_worktree(worktree_path, "feature", create_branch=True)

        mock_run_git.assert_called_once_with(
            "worktree", "add", "-b", "feature", str(worktree_path), cwd=None
        )


class TestRemoveWorktree:
    """Tests for remove_worktree() function."""

    @patch("worktrees.git.run_git")
    def test_remove_worktree_basic(self, mock_run_git):
        """Test removing worktree."""
        worktree_path = Path("/test/worktrees/feature")
        remove_worktree(worktree_path)

        mock_run_git.assert_called_once_with(
            "worktree", "remove", str(worktree_path), cwd=None
        )

    @patch("worktrees.git.run_git")
    def test_remove_worktree_force(self, mock_run_git):
        """Test removing worktree with force flag."""
        worktree_path = Path("/test/worktrees/feature")
        remove_worktree(worktree_path, force=True)

        mock_run_git.assert_called_once_with(
            "worktree", "remove", "--force", str(worktree_path), cwd=None
        )


class TestPruneWorktrees:
    """Tests for prune_worktrees() function."""

    @patch("worktrees.git.run_git")
    def test_prune_worktrees_with_output(self, mock_run_git):
        """Test pruning worktrees with output."""
        mock_result = MagicMock()
        mock_result.stdout = "Removing worktrees/old: gitdir file points to non-existent location\n"
        mock_result.stderr = ""
        mock_run_git.return_value = mock_result

        output = prune_worktrees()
        assert "Removing worktrees/old" in output

    @patch("worktrees.git.run_git")
    def test_prune_worktrees_no_output(self, mock_run_git):
        """Test pruning worktrees with no output."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run_git.return_value = mock_result

        output = prune_worktrees()
        assert output == ""


class TestGetMainWorktree:
    """Tests for get_main_worktree() function."""

    @patch("worktrees.git.list_worktrees")
    def test_get_main_worktree_success(self, mock_list):
        """Test getting main worktree."""
        mock_list.return_value = [
            Worktree(Path("/test/.git"), "abc1234", "(bare)"),
            Worktree(Path("/test/main"), "def5678", "main"),
        ]

        main = get_main_worktree()
        assert main == Path("/test/.git")

    @patch("worktrees.git.list_worktrees")
    def test_get_main_worktree_no_worktrees(self, mock_list):
        """Test getting main worktree when none exist."""
        mock_list.return_value = []

        with pytest.raises(GitError, match="No worktrees found"):
            get_main_worktree()


class TestCloneBare:
    """Tests for clone_bare() function."""

    @patch("worktrees.git.run_git")
    def test_clone_bare_success(self, mock_run_git):
        """Test cloning bare repository."""
        url = "https://github.com/user/repo.git"
        dest = Path("/test/repo")

        with patch.object(Path, "mkdir"):
            result = clone_bare(url, dest)

        assert result == dest
        # Check that both clone and config commands were called
        assert mock_run_git.call_count == 2


class TestMergeBranch:
    """Tests for merge_branch() function."""

    @patch("worktrees.git.run_git")
    def test_merge_branch_success(self, mock_run_git):
        """Test merging branch."""
        merge_branch("feature")
        mock_run_git.assert_called_once_with("merge", "feature", cwd=None)

    @patch("worktrees.git.run_git")
    def test_merge_branch_with_path(self, mock_run_git):
        """Test merging branch with custom path."""
        custom_path = Path("/test/worktree")
        merge_branch("feature", cwd=custom_path)
        mock_run_git.assert_called_once_with("merge", "feature", cwd=custom_path)


class TestDeleteBranch:
    """Tests for delete_branch() function."""

    @patch("worktrees.git.run_git")
    def test_delete_branch_normal(self, mock_run_git):
        """Test deleting merged branch."""
        delete_branch("feature")
        mock_run_git.assert_called_once_with("branch", "-d", "feature", cwd=None)

    @patch("worktrees.git.run_git")
    def test_delete_branch_force(self, mock_run_git):
        """Test force deleting branch."""
        delete_branch("feature", force=True)
        mock_run_git.assert_called_once_with("branch", "-D", "feature", cwd=None)


class TestDeleteRemoteBranch:
    """Tests for delete_remote_branch() function."""

    @patch("worktrees.git.run_git")
    def test_delete_remote_branch_default(self, mock_run_git):
        """Test deleting remote branch on origin."""
        delete_remote_branch("feature")
        mock_run_git.assert_called_once_with(
            "push", "origin", "--delete", "feature", cwd=None
        )

    @patch("worktrees.git.run_git")
    def test_delete_remote_branch_custom_remote(self, mock_run_git):
        """Test deleting remote branch on custom remote."""
        delete_remote_branch("feature", remote="upstream")
        mock_run_git.assert_called_once_with(
            "push", "upstream", "--delete", "feature", cwd=None
        )


class TestGetUntrackedGitIgnoredFiles:
    """Tests for get_untracked_gitignored_files() function."""

    @patch("worktrees.git.run_git")
    def test_get_untracked_gitignored_files_some_files(self, mock_run_git):
        """Test getting untracked gitignored files."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ".env\n.env.local\nnode_modules/\n"
        mock_run_git.return_value = mock_result

        files = get_untracked_gitignored_files(Path("/test"))
        assert files == [Path(".env"), Path(".env.local"), Path("node_modules/")]

    @patch("worktrees.git.run_git")
    def test_get_untracked_gitignored_files_empty(self, mock_run_git):
        """Test getting untracked gitignored files when none exist."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run_git.return_value = mock_result

        files = get_untracked_gitignored_files(Path("/test"))
        assert files == []

    @patch("worktrees.git.run_git")
    def test_get_untracked_gitignored_files_error(self, mock_run_git):
        """Test getting untracked gitignored files on error."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run_git.return_value = mock_result

        files = get_untracked_gitignored_files(Path("/test"))
        assert files == []


class TestCreateEnvironSymlinks:
    """Tests for create_environ_symlinks() function."""

    def test_create_environ_symlinks_nonexistent_dir(self, tmp_path):
        """Test creating symlinks when ENVIRON doesn't exist."""
        environ_dir = tmp_path / "ENVIRON"
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        created = create_environ_symlinks(environ_dir, worktree_path)
        assert created == []

    def test_create_environ_symlinks_files(self, tmp_path):
        """Test creating symlinks for files."""
        environ_dir = tmp_path / "ENVIRON"
        environ_dir.mkdir()
        (environ_dir / ".env").write_text("SECRET=value")
        (environ_dir / "credentials.json").write_text("{}")

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        created = create_environ_symlinks(environ_dir, worktree_path)
        assert len(created) == 2
        assert ".env" in created
        assert "credentials.json" in created

        # Verify symlinks were created
        assert (worktree_path / ".env").is_symlink()
        assert (worktree_path / "credentials.json").is_symlink()

    def test_create_environ_symlinks_directory(self, tmp_path):
        """Test creating symlink for entire directory."""
        environ_dir = tmp_path / "ENVIRON"
        environ_dir.mkdir()
        config_dir = environ_dir / "config"
        config_dir.mkdir()
        (config_dir / "app.yml").write_text("settings")

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        created = create_environ_symlinks(environ_dir, worktree_path)
        assert "config/" in created

        # Verify directory symlink was created
        assert (worktree_path / "config").is_symlink()

    def test_create_environ_symlinks_skip_existing(self, tmp_path):
        """Test skipping existing files when skip_existing=True."""
        environ_dir = tmp_path / "ENVIRON"
        environ_dir.mkdir()
        (environ_dir / ".env").write_text("SECRET=value")

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()
        (worktree_path / ".env").write_text("existing")

        created = create_environ_symlinks(environ_dir, worktree_path, skip_existing=True)
        assert created == []

    def test_create_environ_symlinks_error_on_existing(self, tmp_path):
        """Test error when file exists and skip_existing=False."""
        environ_dir = tmp_path / "ENVIRON"
        environ_dir.mkdir()
        (environ_dir / ".env").write_text("SECRET=value")

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()
        (worktree_path / ".env").write_text("existing")

        with pytest.raises(GitError, match="File already exists"):
            create_environ_symlinks(environ_dir, worktree_path, skip_existing=False)


class TestFindStaleEnvironSymlinks:
    """Tests for find_stale_environ_symlinks() function."""

    def test_find_stale_environ_symlinks_none(self, tmp_path):
        """Test finding stale symlinks when none exist."""
        environ_dir = tmp_path / "ENVIRON"
        environ_dir.mkdir()

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        stale = find_stale_environ_symlinks(worktree_path, environ_dir)
        assert stale == []

    def test_find_stale_environ_symlinks_valid(self, tmp_path):
        """Test finding stale symlinks with valid symlinks."""
        environ_dir = tmp_path / "ENVIRON"
        environ_dir.mkdir()
        (environ_dir / ".env").write_text("SECRET=value")

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        # Create valid symlink
        env_link = worktree_path / ".env"
        env_link.symlink_to(environ_dir / ".env")

        stale = find_stale_environ_symlinks(worktree_path, environ_dir)
        assert stale == []

    def test_find_stale_environ_symlinks_stale(self, tmp_path):
        """Test finding stale symlinks when target is deleted."""
        environ_dir = tmp_path / "ENVIRON"
        environ_dir.mkdir()

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        # Create symlink to non-existent file
        env_link = worktree_path / ".env"
        env_link.symlink_to(environ_dir / ".env")

        stale = find_stale_environ_symlinks(worktree_path, environ_dir)
        assert len(stale) == 1
        assert stale[0] == env_link


class TestRunSetupCommand:
    """Tests for run_setup_command() function."""

    def test_run_setup_command_success(self, tmp_path):
        """Test running successful setup command."""
        success, output = run_setup_command(tmp_path, "echo test")
        assert success is True
        assert "test" in output

    def test_run_setup_command_failure(self, tmp_path):
        """Test running failing setup command."""
        success, output = run_setup_command(tmp_path, "false")
        assert success is False


class TestMigrateToDotgit:
    """Tests for migrate_to_dotgit() function."""

    def test_migrate_to_dotgit_already_exists(self, tmp_path):
        """Test migration when .git already exists."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        with pytest.raises(GitError, match="already exists"):
            migrate_to_dotgit(tmp_path)

    def test_migrate_to_dotgit_not_bare(self, tmp_path):
        """Test migration when not a bare repo."""
        with pytest.raises(GitError, match="Not a bare repository"):
            migrate_to_dotgit(tmp_path)

    def test_migrate_to_dotgit_success(self, tmp_path):
        """Test successful migration to .git/ structure."""
        # Create bare repo structure
        (tmp_path / "HEAD").write_text("ref: refs/heads/main")
        objects_dir = tmp_path / "objects"
        objects_dir.mkdir()
        refs_dir = tmp_path / "refs"
        refs_dir.mkdir()
        config_file = tmp_path / "config"
        config_file.write_text("[core]\n")

        # Create a worktree
        worktree_dir = tmp_path / "main"
        worktree_dir.mkdir()
        git_file = worktree_dir / ".git"
        git_file.write_text("gitdir: ../worktrees/main")

        # Create worktrees dir
        worktrees_dir = tmp_path / "worktrees"
        worktrees_dir.mkdir()

        # Migrate
        migrate_to_dotgit(tmp_path)

        # Verify .git directory was created
        git_dir = tmp_path / ".git"
        assert git_dir.exists()
        assert (git_dir / "HEAD").exists()
        assert (git_dir / "objects").exists()
        assert (git_dir / "refs").exists()

        # Verify worktree .git file was updated
        assert git_file.read_text().strip() == "gitdir: ../.git/worktrees/main"
