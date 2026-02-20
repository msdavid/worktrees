"""Git operations wrapper for worktree management."""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Worktree:
    """Represents a git worktree."""

    path: Path
    commit: str
    branch: str | None


class GitError(Exception):
    """Raised when a git command fails."""


def run_git(
    *args: str, check: bool = True, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the result."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if check and result.returncode != 0:
        raise GitError(result.stderr.strip() or result.stdout.strip())
    return result


def is_bare_repo(path: Path | None = None) -> bool:
    """Check if the current or specified directory is a bare git repository."""
    result = run_git("rev-parse", "--is-bare-repository", check=False, cwd=path)
    return result.stdout.strip() == "true"


def get_remote_url(remote: str = "origin", cwd: Path | None = None) -> str | None:
    """Get the URL for a remote.

    Args:
        remote: Name of the remote (default: "origin")
        cwd: Working directory (default: current directory)

    Returns:
        The remote URL, or None if the remote doesn't exist
    """
    result = run_git("config", "--get", f"remote.{remote}.url", check=False, cwd=cwd)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def is_git_repo(path: Path | None = None) -> bool:
    """Check if the current or specified directory is a git repository."""
    result = run_git("rev-parse", "--git-dir", check=False, cwd=path)
    return result.returncode == 0


def has_uncommitted_changes(path: Path | None = None) -> bool:
    """Check if working directory has uncommitted changes."""
    result = run_git("status", "--porcelain", check=False, cwd=path)
    return bool(result.stdout.strip())


def get_current_branch(path: Path | None = None) -> str:
    """Get the current branch name."""
    result = run_git("branch", "--show-current", cwd=path)
    return result.stdout.strip()


def get_default_branch(path: Path | None = None) -> str:
    """Get the default branch name (main/master).

    Tries to detect from remote HEAD, then falls back to common names.
    """
    # Try to get from remote HEAD
    result = run_git("symbolic-ref", "refs/remotes/origin/HEAD", check=False, cwd=path)
    if result.returncode == 0:
        ref = result.stdout.strip()
        return ref.replace("refs/remotes/origin/", "")

    # Try common branch names
    for branch in ["main", "master"]:
        result = run_git(
            "rev-parse", "--verify", f"refs/heads/{branch}", check=False, cwd=path
        )
        if result.returncode == 0:
            return branch

    # Fall back to current branch or first branch
    result = run_git("branch", "--format=%(refname:short)", check=False, cwd=path)
    branches = [b.strip() for b in result.stdout.strip().split("\n") if b.strip()]
    if branches:
        return branches[0]

    return "main"


def list_local_branches(path: Path | None = None) -> list[str]:
    """List all local branches, with current branch first."""
    result = run_git("branch", "--format=%(refname:short)", check=False, cwd=path)
    branches = [b.strip() for b in result.stdout.strip().split("\n") if b.strip()]

    # Move current branch to front
    try:
        current = get_current_branch(path)
        if current in branches:
            branches.remove(current)
            branches.insert(0, current)
    except GitError:
        pass

    return branches


def branch_exists(branch: str, path: Path | None = None) -> tuple[bool, bool]:
    """Check if branch exists locally and/or remotely.

    Returns:
        Tuple of (exists_locally, exists_remotely)
    """
    result = run_git("branch", "-a", check=False, cwd=path)
    branches = result.stdout.strip().split("\n")
    branches = [b.strip().lstrip("* ") for b in branches]

    local = branch in branches
    remote = f"remotes/origin/{branch}" in branches or f"origin/{branch}" in branches

    return local, remote


def list_worktrees(path: Path | None = None) -> list[Worktree]:
    """List all worktrees."""
    result = run_git("worktree", "list", "--porcelain", cwd=path)

    worktrees = []
    current: dict[str, str] = {}

    for line in result.stdout.strip().split("\n"):
        if not line:
            if current:
                worktrees.append(
                    Worktree(
                        path=Path(current.get("worktree", "")),
                        commit=current.get("HEAD", "")[:7],
                        branch=current.get("branch", "").replace("refs/heads/", "")
                        or None,
                    )
                )
                current = {}
            continue

        if line.startswith("worktree "):
            current["worktree"] = line[9:]
        elif line.startswith("HEAD "):
            current["HEAD"] = line[5:]
        elif line.startswith("branch "):
            current["branch"] = line[7:]
        elif line == "detached":
            current["branch"] = "(detached)"
        elif line == "bare":
            current["branch"] = "(bare)"

    if current:
        worktrees.append(
            Worktree(
                path=Path(current.get("worktree", "")),
                commit=current.get("HEAD", "")[:7],
                branch=current.get("branch", "").replace("refs/heads/", "") or None,
            )
        )

    return worktrees


def add_worktree(
    worktree_path: Path,
    branch: str,
    create_branch: bool = False,
    base_branch: str | None = None,
    cwd: Path | None = None,
) -> Path:
    """Create a new worktree.

    Args:
        worktree_path: Full path for the worktree directory
        branch: Branch name to checkout
        create_branch: Whether to create a new branch
        base_branch: Base branch for new branch (only used with create_branch=True)
        cwd: Directory to run git commands from (project root)

    Returns:
        Path to the created worktree
    """
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    if create_branch:
        if base_branch:
            run_git(
                "worktree",
                "add",
                "-b",
                branch,
                str(worktree_path),
                base_branch,
                cwd=cwd,
            )
        else:
            run_git("worktree", "add", "-b", branch, str(worktree_path), cwd=cwd)
    else:
        local, remote = branch_exists(branch, cwd)
        if local or remote:
            run_git("worktree", "add", str(worktree_path), branch, cwd=cwd)
        else:
            run_git("worktree", "add", "-b", branch, str(worktree_path), cwd=cwd)

    return worktree_path


def remove_worktree(
    worktree_path: Path, force: bool = False, cwd: Path | None = None
) -> None:
    """Remove a worktree.

    Args:
        worktree_path: Full path to the worktree to remove
        force: Force removal even if there are uncommitted changes
        cwd: Directory to run git commands from (project root)
    """
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(worktree_path))

    run_git(*args, cwd=cwd)


def prune_worktrees(cwd: Path | None = None) -> str:
    """Prune stale worktree information.

    Returns:
        Output from git worktree prune
    """
    result = run_git("worktree", "prune", "-v", cwd=cwd)
    return result.stdout.strip() or result.stderr.strip()


def get_repo_root(path: Path | None = None) -> Path:
    """Get the root directory of the current git repository."""
    result = run_git("rev-parse", "--show-toplevel", cwd=path)
    return Path(result.stdout.strip())


def get_git_dir(path: Path | None = None) -> Path:
    """Get the .git directory (or bare repo root)."""
    result = run_git("rev-parse", "--git-dir", cwd=path)
    git_dir = Path(result.stdout.strip())
    if git_dir.is_absolute():
        return git_dir
    return (path or Path.cwd()) / git_dir


def get_main_worktree(path: Path | None = None) -> Path:
    """Get the path to the main (original) worktree."""
    worktrees = list_worktrees(path)
    if worktrees:
        # First worktree in the list is always the main one
        return worktrees[0].path
    raise GitError("No worktrees found")


def clone_bare(url: str, dest: Path) -> Path:
    """Clone a repository as a bare repository into .git/ subdirectory.

    Args:
        url: Repository URL to clone
        dest: Destination directory (project root)

    Returns:
        Path to the project root (dest), with bare repo in dest/.git/
    """
    # Create destination directory if it doesn't exist
    dest.mkdir(parents=True, exist_ok=True)

    git_dir = dest / ".git"
    run_git("clone", "--bare", url, str(git_dir))

    # Set up remote tracking for fetches
    run_git(
        "config",
        "remote.origin.fetch",
        "+refs/heads/*:refs/remotes/origin/*",
        cwd=git_dir,
    )

    return dest


def convert_to_bare(repo_path: Path) -> tuple[Path, str]:
    """Convert a normal repository to a bare repository.

    The bare repo internals are stored in .git/ subdirectory, keeping the
    project root clean for worktrees and ENVIRON.

    Args:
        repo_path: Path to the repository to convert

    Returns:
        Tuple of (project_root_path, default_branch)

    Note:
        Caller is responsible for checking uncommitted changes before calling
        (e.g., ENVIRON migration may create untracked files before conversion).
    """
    # Get current branch before conversion
    default_branch = get_current_branch(repo_path) or get_default_branch(repo_path)

    # Capture original remote URL before conversion (clone --bare loses it)
    original_remote_url = get_remote_url("origin", cwd=repo_path)

    # Create temp directory for bare clone
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_bare = Path(temp_dir) / "bare.git"

        # Clone as bare to temp location
        run_git("clone", "--bare", str(repo_path), str(temp_bare))

        # Set up remote tracking
        run_git(
            "config",
            "remote.origin.fetch",
            "+refs/heads/*:refs/remotes/origin/*",
            cwd=temp_bare,
        )

        # Restore original remote URL (clone --bare sets it to the local path)
        if original_remote_url:
            run_git(
                "config",
                "remote.origin.url",
                original_remote_url,
                cwd=temp_bare,
            )

        # Backup ENVIRON if it exists
        environ_backup = None
        if (repo_path / "ENVIRON").exists():
            environ_backup = Path(temp_dir) / "environ_backup"
            shutil.move(str(repo_path / "ENVIRON"), str(environ_backup))

        # Remove everything in repo_path (including old .git)
        for item in repo_path.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        # Create .git directory and move bare contents into it
        git_dir = repo_path / ".git"
        git_dir.mkdir()
        for item in temp_bare.iterdir():
            shutil.move(str(item), str(git_dir / item.name))

        # Restore ENVIRON if it was backed up
        if environ_backup:
            shutil.move(str(environ_backup), str(repo_path / "ENVIRON"))

    return repo_path, default_branch


# Items that should NOT be moved to .git/ during migration
# (worktree directories are detected dynamically)
NON_GIT_ITEMS = {".worktrees.json", "ENVIRON"}


def migrate_to_dotgit(project_root: Path) -> None:
    """Migrate bare repo internals from root to .git/ directory.

    For existing worktrees projects that have bare repo files at the root level,
    this moves them into a .git/ subdirectory for a cleaner structure.

    Uses a blacklist approach: moves everything except worktree directories
    and known non-git items (.worktrees.json, ENVIRON).

    Args:
        project_root: Path to the project root with bare repo at root level

    Raises:
        GitError: If migration fails or structure is invalid
    """
    git_dir = project_root / ".git"

    if git_dir.exists():
        raise GitError(
            ".git already exists - already migrated or not a bare repo at root"
        )

    # Verify this looks like a bare repo at root
    if not (project_root / "HEAD").exists():
        raise GitError("Not a bare repository (no HEAD file at root)")

    # Identify worktree directories (they have .git files, not directories)
    worktree_dirs: set[str] = set()
    for item in project_root.iterdir():
        if item.is_dir():
            git_file = item / ".git"
            if git_file.is_file():
                worktree_dirs.add(item.name)

    # Create .git directory
    git_dir.mkdir()

    # Move everything that's not a worktree or known non-git item
    # This includes: HEAD, objects/, refs/, config, hooks/, info/, logs/,
    # worktrees/, packed-refs, shallow, modules/, and any other git internals
    for item in project_root.iterdir():
        if item.name == ".git":
            continue  # Skip the .git dir we just created
        if item.name in NON_GIT_ITEMS:
            continue  # Skip known non-git items
        if item.name in worktree_dirs:
            continue  # Skip worktree directories

        # Move to .git/
        shutil.move(str(item), str(git_dir / item.name))

    # Update worktree .git files to point to new location
    # The content is like "gitdir: ../worktrees/main" or "gitdir: /abs/path/worktrees/main"
    project_root_str = str(project_root)
    for wt_name in worktree_dirs:
        git_file = project_root / wt_name / ".git"
        content = git_file.read_text().strip()

        if not content.startswith("gitdir: "):
            continue

        old_gitdir = content[8:]  # Remove "gitdir: " prefix

        if old_gitdir.startswith("/"):
            # Absolute path like /home/user/project/worktrees/main
            # Needs to become /home/user/project/.git/worktrees/main
            if old_gitdir.startswith(project_root_str + "/"):
                relative_part = old_gitdir[len(project_root_str) + 1 :]
                new_gitdir = str(git_dir / relative_part)
                git_file.write_text(f"gitdir: {new_gitdir}\n")
        elif old_gitdir.startswith("../"):
            # Relative path like ../worktrees/main
            # Needs to become ../.git/worktrees/main
            rest = old_gitdir[3:]  # Remove "../" prefix
            new_gitdir = f"../.git/{rest}"
            git_file.write_text(f"gitdir: {new_gitdir}\n")


def is_valid_worktree(path: Path) -> bool:
    """Check if path is a valid git worktree.

    A worktree has a .git file (not directory) containing a gitdir reference.

    Args:
        path: Path to check

    Returns:
        True if path is a valid worktree
    """
    git_file = path / ".git"
    if not git_file.is_file():
        return False

    try:
        content = git_file.read_text().strip()
        return content.startswith("gitdir:")
    except OSError:
        return False


def get_untracked_gitignored_files(repo_path: Path) -> list[Path]:
    """Get files that are both untracked AND in .gitignore.

    Args:
        repo_path: Path to git repository

    Returns:
        List of file paths relative to repo root
    """
    result = run_git(
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        check=False,
        cwd=repo_path,
    )
    if result.returncode != 0:
        return []

    files = []
    for line in result.stdout.strip().split("\n"):
        if line:
            files.append(Path(line))
    return files


def create_environ_symlinks(
    environ_dir: Path,
    worktree_path: Path,
    skip_existing: bool = True,
) -> list[str]:
    """Create symlinks from ENVIRON directory to worktree.

    Symlinks at the highest possible level: tries to symlink directories first,
    only descending into a directory if it already exists in the worktree.
    This results in fewer symlinks and automatic inclusion of new files.

    Args:
        environ_dir: Path to ENVIRON directory
        worktree_path: Path to target worktree
        skip_existing: If True, skip files/dirs that already exist in worktree

    Returns:
        List of created symlink paths (relative to worktree)

    Raises:
        GitError: If symlink creation fails
    """
    if not environ_dir.is_dir():
        return []

    created: list[str] = []

    def _symlink_recursive(src_dir: Path, dst_dir: Path, rel_base: Path) -> None:
        """Recursively symlink items, preferring directory-level symlinks."""
        for item in src_dir.iterdir():
            rel_path = rel_base / item.name
            link_path = dst_dir / item.name

            if item.is_file():
                # File: symlink if target doesn't exist
                if link_path.exists() or link_path.is_symlink():
                    if skip_existing:
                        continue
                    raise GitError(f"File already exists: {link_path}")

                link_path.parent.mkdir(parents=True, exist_ok=True)
                rel_target = os.path.relpath(item, link_path.parent)
                try:
                    os.symlink(rel_target, link_path)
                    created.append(str(rel_path))
                except OSError as e:
                    raise GitError(f"Failed to create symlink {link_path}: {e}")

            elif item.is_dir():
                # Directory: symlink whole dir if target doesn't exist,
                # otherwise recurse into it
                if link_path.is_symlink():
                    # Already a symlink, skip
                    if skip_existing:
                        continue
                    raise GitError(f"Directory already exists: {link_path}")

                if not link_path.exists():
                    # Target doesn't exist: symlink the whole directory
                    link_path.parent.mkdir(parents=True, exist_ok=True)
                    rel_target = os.path.relpath(item, link_path.parent)
                    try:
                        os.symlink(rel_target, link_path)
                        created.append(str(rel_path) + "/")
                    except OSError as e:
                        raise GitError(f"Failed to create symlink {link_path}: {e}")

                elif link_path.is_dir():
                    # Target exists as directory: recurse into it
                    _symlink_recursive(item, link_path, rel_path)

    _symlink_recursive(environ_dir, worktree_path, Path("."))
    return created


def find_stale_environ_symlinks(worktree_path: Path, environ_dir: Path) -> list[Path]:
    """Find symlinks in worktree that point to non-existent ENVIRON files.

    Args:
        worktree_path: Path to worktree to scan
        environ_dir: Path to ENVIRON directory

    Returns:
        List of stale symlink paths (absolute)
    """
    stale = []

    for item in worktree_path.rglob("*"):
        if item.is_symlink():
            target = item.resolve()
            # Check if this symlink was supposed to point into ENVIRON
            try:
                target.relative_to(environ_dir)
                # It's an ENVIRON symlink - check if target exists
                if not target.exists():
                    stale.append(item)
            except ValueError:
                # Not an ENVIRON symlink, ignore
                pass

    return stale


def run_setup_command(worktree_path: Path, command: str) -> tuple[bool, str]:
    """Run a setup command in the worktree directory.

    Args:
        worktree_path: Path to the worktree
        command: Command to run

    Returns:
        Tuple of (success, output)
    """
    result = subprocess.run(
        command,
        shell=True,
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip() or result.stderr.strip()
    return result.returncode == 0, output


def get_repo_name_from_url(url: str) -> str:
    """Extract repository name from a git URL.

    Args:
        url: Git repository URL

    Returns:
        Repository name (without .git suffix)
    """
    # Handle various URL formats
    # https://github.com/user/repo.git
    # git@github.com:user/repo.git
    # /path/to/repo.git
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def merge_branch(branch: str, cwd: Path | None = None) -> None:
    """Merge a branch into the current HEAD.

    Args:
        branch: Branch name to merge
        cwd: Directory to run git commands from

    Raises:
        GitError: If merge fails (conflicts, etc.)
    """
    run_git("merge", branch, cwd=cwd)


def delete_branch(branch: str, force: bool = False, cwd: Path | None = None) -> None:
    """Delete a local branch.

    Args:
        branch: Branch name to delete
        force: Force delete even if not fully merged
        cwd: Directory to run git commands from

    Raises:
        GitError: If deletion fails
    """
    flag = "-D" if force else "-d"
    run_git("branch", flag, branch, cwd=cwd)


def delete_remote_branch(
    branch: str, remote: str = "origin", cwd: Path | None = None
) -> None:
    """Delete a remote branch.

    Args:
        branch: Branch name to delete
        remote: Remote name (default: origin)
        cwd: Directory to run git commands from

    Raises:
        GitError: If deletion fails
    """
    run_git("push", remote, "--delete", branch, cwd=cwd)
