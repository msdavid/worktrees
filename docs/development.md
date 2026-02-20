# Development Guide

This guide covers the architecture and development workflow for contributing to `worktrees`.

## Architecture Overview

```
src/worktrees/
  __init__.py         # Package init, version
  __main__.py         # Entry point for `python -m worktrees`
  cli/
    __init__.py       # Main Typer app, shared utilities
    worktree.py       # add, remove, list, prune commands
    init_clone.py     # init, clone commands
    advanced.py       # convert-old, environ, merge commands
    status.py         # status command
    mark.py           # mark, unmark commands
    tmux.py           # tmux session management
    config_cmd.py     # config command (AI assistant setup)
  config.py           # Configuration classes and loading
  user_config.py      # Global user configuration (AI settings)
  git.py              # Git operations wrapper
  exclusions.py       # Ephemeral file patterns for ENVIRON migration
```

## Module Responsibilities

### cli/__init__.py

- Creates main `typer.Typer` app
- Defines shared utilities: `require_initialized()`, `show_worktree_list()`, `encode_branch_name()`, `decode_branch_name()`
- Defines questionary styling
- Imports and registers command modules

### cli/worktree.py

Core worktree management commands:
- `add`: Create worktrees with interactive branch selection
- `remove`: Remove worktrees with safeguards
- `list`: Display worktree table
- `prune`: Clean stale references

### cli/init_clone.py

Repository setup commands:
- `init`: Initialize existing repo for worktrees
- `clone`: Clone new repo as bare with worktrees support

### cli/advanced.py

Power user commands:
- `convert-old`: Migrate old bare repo structure
- `environ`: Sync ENVIRON symlinks
- `merge`: Merge branches with cleanup options

### cli/status.py

- `status`: Show current worktree and project info (including mark)

### cli/mark.py

Worktree labeling commands:
- `mark`: Set text label on a worktree (stored in `.worktrees.json`)
- `unmark`: Clear label from a worktree
- Helper functions: `get_current_worktree_name()`, `get_worktree_names()`

### cli/tmux.py

Tmux session management:
- `tmux`: Create/attach tmux session for a worktree
- Auto-activates `.venv` if present
- Supports multiple sessions per worktree with suffix naming (`name-2`, `name-3`)
- Detects if inside tmux (uses `switch-client` vs `attach`)

### cli/config_cmd.py

AI assistant configuration:
- `config`: Interactive wizard for setting up Claude or Gemini CLI
- Stores settings in `~/.config/worktrees/config.json`

### config.py

Configuration management:
- `WorktreesConfig`: Dataclass for `.worktrees.json` (includes marks)
- `find_project_root()`: Locate project root by finding `.worktrees.json`
- `DEFAULT_SETUP_COMMANDS`: Auto-detect mappings

### user_config.py

Global user configuration:
- `AIConfig`: Dataclass for AI assistant settings (provider, command, prompt)
- `UserConfig`: Wrapper stored at `~/.config/worktrees/config.json`
- Provider defaults for Claude and Gemini CLI
- Prompt template with `<target-branch>` and `<current-branch>` placeholders

### git.py

Git operations wrapper:
- All git command execution via `run_git()`
- `GitError` exception for failures
- Worktree operations: `add_worktree()`, `remove_worktree()`, `list_worktrees()`
- Branch operations: `branch_exists()`, `merge_branch()`, `delete_branch()`
- Repository operations: `clone_bare()`, `convert_to_bare()`, `migrate_to_dotgit()`
- ENVIRON operations: `create_environ_symlinks()`, `find_stale_environ_symlinks()`

### exclusions.py

Patterns for filtering ephemeral files during ENVIRON migration:
- `EXCLUDED_DIRS`: Directory patterns by category (python, javascript, etc.)
- `EXCLUDED_FILE_PATTERNS`: File patterns by category
- `is_ephemeral_file()`: Check if path should be excluded
- `filter_ephemeral_files()`: Filter list of paths

## Key Design Decisions

### Bare Repository with .git/ Subdirectory

Instead of having bare repo files (HEAD, objects/, refs/) at the project root, we store them in `.git/`:

```
project/
  .git/           # Bare repo internals here
    HEAD
    objects/
    refs/
    worktrees/
  main/           # Worktrees as siblings
  feature-x/
```

This keeps the project root clean and matches user expectations of `.git/` containing git data.

### ENVIRON Symlink Strategy

Symlinks are created at the highest possible level:

```python
# If ENVIRON has:
ENVIRON/
  .env
  config/
    a.json
    b.json

# And worktree has no config/ directory, we symlink:
worktree/
  .env -> ../ENVIRON/.env
  config -> ../ENVIRON/config   # Whole directory!

# But if worktree already has config/:
worktree/
  .env -> ../ENVIRON/.env
  config/
    a.json -> ../../ENVIRON/config/a.json
    b.json -> ../../ENVIRON/config/b.json
```

This minimizes symlink count and automatically includes new files added to symlinked directories.

### stderr for Status Messages

The CLI writes status messages to stderr, keeping stdout clean for potential scripting:

```python
err = Console(stderr=True)
err.print("[bold]Created[/bold]")
```

### Interactive Selection

When arguments are optional, the CLI falls back to interactive selection using `questionary`:

```python
@app.command()
def add(
    branch: Annotated[
        Optional[str],
        typer.Argument(help="Branch to checkout (interactive if omitted)"),
    ] = None,
):
    if not branch:
        branch = questionary.select("Select branch:", choices=...).ask()
```

## Development Setup

### Prerequisites

- Python 3.10+
- uv (recommended) or pip

### Setup

```bash
# Clone
git clone https://github.com/msdavid/worktrees.git
cd worktrees

# Create virtual environment and install
uv sync

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_git.py

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_git.py::test_is_bare_repo
```

### Running the CLI

```bash
# From project directory with venv activated
worktrees --help

# Or via Python module
python -m worktrees --help
```

## Testing Strategy

### Test Files

```
tests/
  __init__.py
  test_git.py               # Core git operations
  test_git_worktrees.py     # Worktree-specific git operations
  test_config.py            # Project configuration loading/saving
  test_user_config.py       # Global user/AI configuration
  test_exclusions.py        # Ephemeral file filtering
  test_cli_init.py          # init/clone commands and CLI utilities
  test_cli_worktree_add.py  # add command with tmux integration
  test_cli_advanced.py      # convert-old, environ, merge commands
  test_cli_status.py        # status command
  test_cli_mark.py          # mark/unmark commands
  test_cli_tmux.py          # tmux session management
  test_cli_config.py        # config command (AI setup)
```

### Test Patterns

Tests use `pytest` with temporary directories:

```python
def test_is_bare_repo(tmp_path):
    # Create a bare repo
    subprocess.run(["git", "init", "--bare"], cwd=tmp_path)

    assert is_bare_repo(tmp_path) is True
```

### Coverage

Coverage is configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "--verbose --cov=worktrees --cov-report=term-missing"
```

## Code Style

### Type Hints

All functions use type hints:

```python
def add_worktree(
    worktree_path: Path,
    branch: str,
    create_branch: bool = False,
    base_branch: str | None = None,
    cwd: Path | None = None,
) -> Path:
```

### Docstrings

Functions include docstrings with Args/Returns:

```python
def branch_exists(branch: str, path: Path | None = None) -> tuple[bool, bool]:
    """Check if branch exists locally and/or remotely.

    Args:
        branch: Branch name to check
        path: Repository path (default: current directory)

    Returns:
        Tuple of (exists_locally, exists_remotely)
    """
```

### Error Handling

Git errors are wrapped in `GitError`:

```python
class GitError(Exception):
    """Raised when a git command fails."""

def run_git(*args: str, check: bool = True, cwd: Path | None = None):
    result = subprocess.run(["git", *args], ...)
    if check and result.returncode != 0:
        raise GitError(result.stderr.strip() or result.stdout.strip())
    return result
```

CLI commands catch `GitError` and display user-friendly messages:

```python
try:
    add_worktree(...)
except GitError as e:
    err.print(f"[red]error:[/red] {e}")
    raise typer.Exit(1)
```

## Adding New Commands

1. Create command in appropriate CLI module or create new module
2. Register with `@app.command()` decorator
3. Import in `cli/__init__.py` if in new module
4. Add tests
5. Update documentation

Example:

```python
# cli/worktree.py
@app.command()
def new_command(
    arg: Annotated[str, typer.Argument(help="Description")],
    option: Annotated[bool, typer.Option("--flag", "-f", help="Description")] = False,
) -> None:
    """Brief description of command.

    Longer description with details.
    """
    config = require_initialized()
    # Implementation...
```

## Release Process

1. Update version in `src/worktrees/__init__.py`
2. Update CHANGELOG (if exists)
3. Create git tag:

```bash
git tag -a v0.x.0 -m "Release v0.x.0"
git push origin v0.x.0
```

This project is installed directly from GitHub (not published on PyPI):

```bash
uv tool install git+https://github.com/msdavid/worktrees.git
```
