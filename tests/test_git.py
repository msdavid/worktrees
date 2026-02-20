"""Tests for git operations module.

This test suite covers:
- get_remote_url() function (NEW)
- convert_to_bare() function (MODIFIED to preserve remote URLs)
- Core git operations
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from worktrees.git import (
    GitError,
    convert_to_bare,
    get_remote_url,
    is_bare_repo,
    is_git_repo,
    run_git,
)


class TestGetRemoteUrl:
    """Tests for the get_remote_url() function."""

    def test_get_remote_url_success(self):
        """Test retrieving a remote URL successfully."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/user/repo.git\n"

        with patch("worktrees.git.run_git", return_value=mock_result) as mock_run:
            url = get_remote_url("origin", cwd=Path("/test/path"))

            assert url == "https://github.com/user/repo.git"
            mock_run.assert_called_once_with(
                "config",
                "--get",
                "remote.origin.url",
                check=False,
                cwd=Path("/test/path"),
            )

    def test_get_remote_url_default_remote(self):
        """Test get_remote_url uses 'origin' as default remote."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "git@github.com:user/repo.git\n"

        with patch("worktrees.git.run_git", return_value=mock_result) as mock_run:
            url = get_remote_url()

            assert url == "git@github.com:user/repo.git"
            mock_run.assert_called_once_with(
                "config", "--get", "remote.origin.url", check=False, cwd=None
            )

    def test_get_remote_url_nonexistent_remote(self):
        """Test get_remote_url returns None when remote doesn't exist."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("worktrees.git.run_git", return_value=mock_result):
            url = get_remote_url("nonexistent")

            assert url is None

    def test_get_remote_url_custom_remote(self):
        """Test retrieving URL from a custom remote name."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "https://gitlab.com/user/repo.git\n"

        with patch("worktrees.git.run_git", return_value=mock_result) as mock_run:
            url = get_remote_url("upstream")

            assert url == "https://gitlab.com/user/repo.git"
            mock_run.assert_called_once_with(
                "config", "--get", "remote.upstream.url", check=False, cwd=None
            )

    def test_get_remote_url_empty_output(self):
        """Test get_remote_url returns None when output is empty."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "\n"

        with patch("worktrees.git.run_git", return_value=mock_result):
            url = get_remote_url()

            assert url is None

    def test_get_remote_url_whitespace_trimmed(self):
        """Test that whitespace is properly trimmed from URL."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  https://example.com/repo.git  \n"

        with patch("worktrees.git.run_git", return_value=mock_result):
            url = get_remote_url()

            assert url == "https://example.com/repo.git"

    def test_get_remote_url_with_custom_cwd(self):
        """Test get_remote_url with custom working directory."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/test/repo.git\n"

        custom_path = Path("/custom/repo/path")
        with patch("worktrees.git.run_git", return_value=mock_result) as mock_run:
            url = get_remote_url(cwd=custom_path)

            assert url == "https://github.com/test/repo.git"
            mock_run.assert_called_once_with(
                "config", "--get", "remote.origin.url", check=False, cwd=custom_path
            )


class TestConvertToBare:
    """Tests for the convert_to_bare() function with remote URL preservation."""

    @patch("worktrees.git.get_current_branch")
    @patch("worktrees.git.get_remote_url")
    @patch("worktrees.git.run_git")
    @patch("worktrees.git.shutil")
    @patch("worktrees.git.tempfile")
    def test_convert_to_bare_preserves_remote_url(
        self,
        mock_tempfile,
        mock_shutil,
        mock_run_git,
        mock_get_remote_url,
        mock_get_current_branch,
    ):
        """Test that convert_to_bare preserves the original remote URL."""
        # Set up mocks
        repo_path = Path("/test/repo")
        temp_dir = Path("/tmp/test123")
        temp_bare = temp_dir / "bare.git"

        mock_get_current_branch.return_value = "main"
        mock_get_remote_url.return_value = "https://github.com/user/repo.git"
        mock_tempfile.TemporaryDirectory.return_value.__enter__.return_value = str(
            temp_dir
        )

        # Mock file system
        with patch.object(Path, "exists", return_value=False):
            with patch.object(Path, "iterdir", return_value=[]):
                with patch.object(Path, "mkdir"):
                    result_path, branch = convert_to_bare(repo_path)

        # Verify remote URL was captured
        mock_get_remote_url.assert_called_once_with("origin", cwd=repo_path)

        # Verify git operations were called with correct parameters
        git_calls = mock_run_git.call_args_list

        # Check that clone --bare was called
        assert any("clone" in str(call) and "--bare" in str(call) for call in git_calls)

        # Check that remote.origin.url was set to restore the original URL
        config_url_call = call(
            "config",
            "remote.origin.url",
            "https://github.com/user/repo.git",
            cwd=temp_bare,
        )
        assert config_url_call in git_calls

        # Verify return values
        assert result_path == repo_path
        assert branch == "main"

    @patch("worktrees.git.get_current_branch")
    @patch("worktrees.git.get_remote_url")
    @patch("worktrees.git.run_git")
    @patch("worktrees.git.shutil")
    @patch("worktrees.git.tempfile")
    def test_convert_to_bare_no_remote_url(
        self,
        mock_tempfile,
        mock_shutil,
        mock_run_git,
        mock_get_remote_url,
        mock_get_current_branch,
    ):
        """Test convert_to_bare when repository has no remote URL."""
        repo_path = Path("/test/repo")
        temp_dir = Path("/tmp/test456")

        mock_get_current_branch.return_value = "main"
        mock_get_remote_url.return_value = None  # No remote URL
        mock_tempfile.TemporaryDirectory.return_value.__enter__.return_value = str(
            temp_dir
        )

        with patch.object(Path, "exists", return_value=False):
            with patch.object(Path, "iterdir", return_value=[]):
                with patch.object(Path, "mkdir"):
                    result_path, branch = convert_to_bare(repo_path)

        # Verify remote URL was checked
        mock_get_remote_url.assert_called_once_with("origin", cwd=repo_path)

        # Verify that remote.origin.url was NOT set (since there was no original URL)
        git_calls = mock_run_git.call_args_list
        config_url_calls = [
            c
            for c in git_calls
            if len(c[0]) >= 2 and c[0][0] == "config" and "remote.origin.url" in c[0]
        ]
        # Should only have the fetch config, not the URL config
        assert len(config_url_calls) == 0

        assert result_path == repo_path
        assert branch == "main"

    @patch("worktrees.git.get_current_branch")
    @patch("worktrees.git.get_remote_url")
    @patch("worktrees.git.run_git")
    @patch("worktrees.git.shutil")
    @patch("worktrees.git.tempfile")
    def test_convert_to_bare_with_environ(
        self,
        mock_tempfile,
        mock_shutil,
        mock_run_git,
        mock_get_remote_url,
        mock_get_current_branch,
    ):
        """Test convert_to_bare preserves ENVIRON directory."""
        repo_path = Path("/test/repo")
        temp_dir = Path("/tmp/test789")
        environ_path = repo_path / "ENVIRON"
        environ_backup = temp_dir / "environ_backup"

        mock_get_current_branch.return_value = "main"
        mock_get_remote_url.return_value = "git@github.com:user/repo.git"
        mock_tempfile.TemporaryDirectory.return_value.__enter__.return_value = str(
            temp_dir
        )

        def mock_exists(self):
            return self == environ_path

        with patch.object(Path, "exists", mock_exists):
            with patch.object(Path, "iterdir", return_value=[]):
                with patch.object(Path, "mkdir"):
                    result_path, branch = convert_to_bare(repo_path)

        # Verify ENVIRON was backed up and restored
        move_calls = mock_shutil.move.call_args_list
        assert call(str(environ_path), str(environ_backup)) in move_calls
        assert call(str(environ_backup), str(environ_path)) in move_calls

        assert result_path == repo_path
        assert branch == "main"

    @patch("worktrees.git.get_default_branch")
    @patch("worktrees.git.get_current_branch")
    @patch("worktrees.git.get_remote_url")
    @patch("worktrees.git.run_git")
    @patch("worktrees.git.shutil")
    @patch("worktrees.git.tempfile")
    def test_convert_to_bare_fallback_to_default_branch(
        self,
        mock_tempfile,
        mock_shutil,
        mock_run_git,
        mock_get_remote_url,
        mock_get_current_branch,
        mock_get_default_branch,
    ):
        """Test convert_to_bare falls back to default branch when current is None."""
        repo_path = Path("/test/repo")
        temp_dir = Path("/tmp/test999")

        mock_get_current_branch.return_value = None
        mock_get_default_branch.return_value = "master"
        mock_get_remote_url.return_value = "https://gitlab.com/user/repo.git"
        mock_tempfile.TemporaryDirectory.return_value.__enter__.return_value = str(
            temp_dir
        )

        with patch.object(Path, "exists", return_value=False):
            with patch.object(Path, "iterdir", return_value=[]):
                with patch.object(Path, "mkdir"):
                    result_path, branch = convert_to_bare(repo_path)

        mock_get_default_branch.assert_called_once_with(repo_path)
        assert branch == "master"


class TestRunGit:
    """Tests for the run_git() helper function."""

    @patch("worktrees.git.subprocess.run")
    def test_run_git_success(self, mock_subprocess_run):
        """Test run_git with successful command."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "success output"
        mock_result.stderr = ""
        mock_subprocess_run.return_value = mock_result

        result = run_git("status")

        assert result.returncode == 0
        assert result.stdout == "success output"
        mock_subprocess_run.assert_called_once_with(
            ["git", "status"],
            capture_output=True,
            text=True,
            cwd=None,
        )

    @patch("worktrees.git.subprocess.run")
    def test_run_git_failure_with_check(self, mock_subprocess_run):
        """Test run_git raises GitError on failure when check=True."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "fatal: not a git repository"
        mock_subprocess_run.return_value = mock_result

        with pytest.raises(GitError, match="fatal: not a git repository"):
            run_git("status", check=True)

    @patch("worktrees.git.subprocess.run")
    def test_run_git_failure_without_check(self, mock_subprocess_run):
        """Test run_git returns result without raising when check=False."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error message"
        mock_subprocess_run.return_value = mock_result

        result = run_git("status", check=False)

        assert result.returncode == 1
        assert result.stderr == "error message"

    @patch("worktrees.git.subprocess.run")
    def test_run_git_with_cwd(self, mock_subprocess_run):
        """Test run_git with custom working directory."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_subprocess_run.return_value = mock_result

        custom_path = Path("/custom/path")
        run_git("status", cwd=custom_path)

        mock_subprocess_run.assert_called_once_with(
            ["git", "status"],
            capture_output=True,
            text=True,
            cwd=custom_path,
        )


class TestGitIntegration:
    """Integration tests using real git repositories."""

    def test_get_remote_url_real_repo(self, tmp_path):
        """Test get_remote_url with a real temporary git repository."""
        # Create a real git repo
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        # Initialize repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)

        # Test when no remote exists
        url = get_remote_url(cwd=repo_path)
        assert url is None

        # Add a remote
        test_url = "https://github.com/test/repo.git"
        subprocess.run(
            ["git", "remote", "add", "origin", test_url],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Test retrieving the remote
        url = get_remote_url(cwd=repo_path)
        assert url == test_url

        # Test custom remote
        subprocess.run(
            ["git", "remote", "add", "upstream", "https://example.com/upstream.git"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        upstream_url = get_remote_url("upstream", cwd=repo_path)
        assert upstream_url == "https://example.com/upstream.git"

    def test_convert_to_bare_real_repo(self, tmp_path):
        """Test convert_to_bare with a real repository."""
        # Create a real git repo with content
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        # Initialize repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)

        # Configure git user for commits
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Add a remote
        original_url = "https://github.com/test/original.git"
        subprocess.run(
            ["git", "remote", "add", "origin", original_url],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Create a file and commit
        test_file = repo_path / "test.txt"
        test_file.write_text("test content")
        subprocess.run(
            ["git", "add", "test.txt"], cwd=repo_path, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Convert to bare
        result_path, branch = convert_to_bare(repo_path)

        # Verify conversion
        assert result_path == repo_path
        assert branch in ["main", "master"]  # Depends on git version

        # Verify it's now a bare repo in .git subdirectory
        git_dir = repo_path / ".git"
        assert git_dir.exists()
        assert is_bare_repo(git_dir)

        # Verify remote URL was preserved
        restored_url = get_remote_url(cwd=git_dir)
        assert restored_url == original_url

    def test_convert_to_bare_with_environ_real(self, tmp_path):
        """Test convert_to_bare preserves ENVIRON directory with real files."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        # Initialize repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Create ENVIRON directory with content
        environ_dir = repo_path / "ENVIRON"
        environ_dir.mkdir()
        (environ_dir / ".env").write_text("SECRET=value")

        # Create and commit a file (required for conversion)
        (repo_path / "README.md").write_text("# Test")
        subprocess.run(
            ["git", "add", "README.md"], cwd=repo_path, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Convert to bare
        convert_to_bare(repo_path)

        # Verify ENVIRON was preserved
        assert (repo_path / "ENVIRON").exists()
        assert (repo_path / "ENVIRON" / ".env").exists()
        assert (repo_path / "ENVIRON" / ".env").read_text() == "SECRET=value"


class TestIsBareRepo:
    """Tests for is_bare_repo() function."""

    @patch("worktrees.git.run_git")
    def test_is_bare_repo_true(self, mock_run_git):
        """Test is_bare_repo returns True for bare repository."""
        mock_result = MagicMock()
        mock_result.stdout = "true\n"
        mock_run_git.return_value = mock_result

        assert is_bare_repo() is True

    @patch("worktrees.git.run_git")
    def test_is_bare_repo_false(self, mock_run_git):
        """Test is_bare_repo returns False for normal repository."""
        mock_result = MagicMock()
        mock_result.stdout = "false\n"
        mock_run_git.return_value = mock_result

        assert is_bare_repo() is False

    @patch("worktrees.git.run_git")
    def test_is_bare_repo_with_path(self, mock_run_git):
        """Test is_bare_repo with custom path."""
        mock_result = MagicMock()
        mock_result.stdout = "true\n"
        mock_run_git.return_value = mock_result

        custom_path = Path("/custom/repo")
        is_bare_repo(custom_path)

        mock_run_git.assert_called_once_with(
            "rev-parse", "--is-bare-repository", check=False, cwd=custom_path
        )


class TestIsGitRepo:
    """Tests for is_git_repo() function."""

    @patch("worktrees.git.run_git")
    def test_is_git_repo_true(self, mock_run_git):
        """Test is_git_repo returns True for git repository."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run_git.return_value = mock_result

        assert is_git_repo() is True

    @patch("worktrees.git.run_git")
    def test_is_git_repo_false(self, mock_run_git):
        """Test is_git_repo returns False for non-git directory."""
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_run_git.return_value = mock_result

        assert is_git_repo() is False


class TestHasUncommittedChanges:
    """Tests for has_uncommitted_changes() function."""

    @patch("worktrees.git.run_git")
    def test_has_uncommitted_changes_true(self, mock_run_git):
        """Test has_uncommitted_changes returns True when changes exist."""
        mock_result = MagicMock()
        mock_result.stdout = "M file.txt\n"
        mock_run_git.return_value = mock_result

        from worktrees.git import has_uncommitted_changes

        assert has_uncommitted_changes() is True

    @patch("worktrees.git.run_git")
    def test_has_uncommitted_changes_false(self, mock_run_git):
        """Test has_uncommitted_changes returns False when clean."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_run_git.return_value = mock_result

        from worktrees.git import has_uncommitted_changes

        assert has_uncommitted_changes() is False


class TestGetCurrentBranch:
    """Tests for get_current_branch() function."""

    @patch("worktrees.git.run_git")
    def test_get_current_branch_success(self, mock_run_git):
        """Test get_current_branch returns branch name."""
        mock_result = MagicMock()
        mock_result.stdout = "main\n"
        mock_run_git.return_value = mock_result

        from worktrees.git import get_current_branch

        branch = get_current_branch()
        assert branch == "main"

    @patch("worktrees.git.run_git")
    def test_get_current_branch_with_path(self, mock_run_git):
        """Test get_current_branch with custom path."""
        mock_result = MagicMock()
        mock_result.stdout = "feature/test\n"
        mock_run_git.return_value = mock_result

        from worktrees.git import get_current_branch

        custom_path = Path("/test/path")
        branch = get_current_branch(custom_path)
        assert branch == "feature/test"
        mock_run_git.assert_called_once_with(
            "branch", "--show-current", cwd=custom_path
        )


class TestGetDefaultBranch:
    """Tests for get_default_branch() function."""

    @patch("worktrees.git.run_git")
    def test_get_default_branch_from_remote(self, mock_run_git):
        """Test get_default_branch from remote HEAD."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "refs/remotes/origin/main\n"
        mock_run_git.return_value = mock_result

        from worktrees.git import get_default_branch

        branch = get_default_branch()
        assert branch == "main"

    @patch("worktrees.git.run_git")
    def test_get_default_branch_fallback_main(self, mock_run_git):
        """Test get_default_branch falls back to main."""

        def side_effect(*args, **kwargs):
            result = MagicMock()
            if args[0] == "symbolic-ref":
                result.returncode = 1
                return result
            elif args[0] == "rev-parse" and "main" in args[2]:
                result.returncode = 0
                return result
            else:
                result.returncode = 1
                return result

        mock_run_git.side_effect = side_effect

        from worktrees.git import get_default_branch

        branch = get_default_branch()
        assert branch == "main"

    @patch("worktrees.git.run_git")
    def test_get_default_branch_fallback_master(self, mock_run_git):
        """Test get_default_branch falls back to master."""

        def side_effect(*args, **kwargs):
            result = MagicMock()
            if args[0] == "symbolic-ref":
                result.returncode = 1
                return result
            elif args[0] == "rev-parse" and "master" in args[2]:
                result.returncode = 0
                return result
            else:
                result.returncode = 1
                return result

        mock_run_git.side_effect = side_effect

        from worktrees.git import get_default_branch

        branch = get_default_branch()
        assert branch == "master"


class TestListLocalBranches:
    """Tests for list_local_branches() function."""

    @patch("worktrees.git.get_current_branch")
    @patch("worktrees.git.run_git")
    def test_list_local_branches_with_current_first(
        self, mock_run_git, mock_get_current
    ):
        """Test list_local_branches puts current branch first."""
        mock_result = MagicMock()
        mock_result.stdout = "feature\nmain\ndev\n"
        mock_run_git.return_value = mock_result
        mock_get_current.return_value = "dev"

        from worktrees.git import list_local_branches

        branches = list_local_branches()
        assert branches == ["dev", "feature", "main"]

    @patch("worktrees.git.get_current_branch")
    @patch("worktrees.git.run_git")
    def test_list_local_branches_no_current(self, mock_run_git, mock_get_current):
        """Test list_local_branches when get_current_branch fails."""
        mock_result = MagicMock()
        mock_result.stdout = "main\nfeature\n"
        mock_run_git.return_value = mock_result
        mock_get_current.side_effect = GitError("detached")

        from worktrees.git import list_local_branches

        branches = list_local_branches()
        assert branches == ["main", "feature"]


class TestBranchExists:
    """Tests for branch_exists() function."""

    @patch("worktrees.git.run_git")
    def test_branch_exists_local_only(self, mock_run_git):
        """Test branch_exists when branch exists locally."""
        mock_result = MagicMock()
        mock_result.stdout = "* main\n  feature\n  remotes/origin/main\n"
        mock_run_git.return_value = mock_result

        from worktrees.git import branch_exists

        local, remote = branch_exists("feature")
        assert local is True
        assert remote is False

    @patch("worktrees.git.run_git")
    def test_branch_exists_remote_only(self, mock_run_git):
        """Test branch_exists when branch exists on remote."""
        mock_result = MagicMock()
        mock_result.stdout = "  main\n  remotes/origin/feature\n"
        mock_run_git.return_value = mock_result

        from worktrees.git import branch_exists

        local, remote = branch_exists("feature")
        assert local is False
        assert remote is True

    @patch("worktrees.git.run_git")
    def test_branch_exists_both(self, mock_run_git):
        """Test branch_exists when branch exists both locally and remotely."""
        mock_result = MagicMock()
        mock_result.stdout = "  feature\n  remotes/origin/feature\n"
        mock_run_git.return_value = mock_result

        from worktrees.git import branch_exists

        local, remote = branch_exists("feature")
        assert local is True
        assert remote is True


class TestGetRepoRoot:
    """Tests for get_repo_root() function."""

    @patch("worktrees.git.run_git")
    def test_get_repo_root_success(self, mock_run_git):
        """Test get_repo_root returns repository root."""
        mock_result = MagicMock()
        mock_result.stdout = "/home/user/project\n"
        mock_run_git.return_value = mock_result

        from worktrees.git import get_repo_root

        root = get_repo_root()
        assert root == Path("/home/user/project")


class TestGetGitDir:
    """Tests for get_git_dir() function."""

    @patch("worktrees.git.run_git")
    def test_get_git_dir_absolute(self, mock_run_git):
        """Test get_git_dir with absolute path."""
        mock_result = MagicMock()
        mock_result.stdout = "/home/user/project/.git\n"
        mock_run_git.return_value = mock_result

        from worktrees.git import get_git_dir

        git_dir = get_git_dir()
        assert git_dir == Path("/home/user/project/.git")

    @patch("worktrees.git.run_git")
    def test_get_git_dir_relative(self, mock_run_git):
        """Test get_git_dir with relative path."""
        mock_result = MagicMock()
        mock_result.stdout = ".git\n"
        mock_run_git.return_value = mock_result

        from worktrees.git import get_git_dir

        with patch("worktrees.git.Path.cwd", return_value=Path("/test/path")):
            git_dir = get_git_dir()
            assert git_dir == Path("/test/path/.git")


class TestGetRepoNameFromUrl:
    """Tests for get_repo_name_from_url() function."""

    def test_get_repo_name_from_url_https(self):
        """Test extracting repo name from HTTPS URL."""
        from worktrees.git import get_repo_name_from_url

        name = get_repo_name_from_url("https://github.com/user/repo.git")
        assert name == "repo"

    def test_get_repo_name_from_url_ssh(self):
        """Test extracting repo name from SSH URL."""
        from worktrees.git import get_repo_name_from_url

        name = get_repo_name_from_url("git@github.com:user/repo.git")
        assert name == "repo"

    def test_get_repo_name_from_url_local_path(self):
        """Test extracting repo name from local path."""
        from worktrees.git import get_repo_name_from_url

        name = get_repo_name_from_url("/path/to/repo.git")
        assert name == "repo"

    def test_get_repo_name_from_url_no_git_suffix(self):
        """Test extracting repo name without .git suffix."""
        from worktrees.git import get_repo_name_from_url

        name = get_repo_name_from_url("https://github.com/user/repo")
        assert name == "repo"


class TestIsValidWorktree:
    """Tests for is_valid_worktree() function."""

    def test_is_valid_worktree_true(self, tmp_path):
        """Test is_valid_worktree returns True for valid worktree."""
        git_file = tmp_path / ".git"
        git_file.write_text("gitdir: /path/to/.git/worktrees/main")

        from worktrees.git import is_valid_worktree

        assert is_valid_worktree(tmp_path) is True

    def test_is_valid_worktree_false_no_git_file(self, tmp_path):
        """Test is_valid_worktree returns False when .git doesn't exist."""
        from worktrees.git import is_valid_worktree

        assert is_valid_worktree(tmp_path) is False

    def test_is_valid_worktree_false_git_is_directory(self, tmp_path):
        """Test is_valid_worktree returns False when .git is directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        from worktrees.git import is_valid_worktree

        assert is_valid_worktree(tmp_path) is False
