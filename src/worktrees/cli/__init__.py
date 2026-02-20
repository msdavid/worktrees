"""CLI commands for worktree management."""

import typer
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.table import Table

from worktrees.config import WorktreesConfig, find_project_root
from worktrees.git import GitError, Worktree, list_worktrees

# Use stderr for status messages so stdout can be used for shell commands
err = Console(stderr=True)

# Custom questionary style with orange cursor
STYLE = Style(
    [
        ("pointer", "fg:#ff8c00 bold"),  # orange pointer/cursor
        ("highlighted", "fg:#ff8c00 bold"),  # highlighted choice
        ("selected", "fg:#ff8c00"),  # selected items
        ("question", "bold"),
        ("answer", "fg:#ff8c00 bold"),
    ]
)

app = typer.Typer(
    name="worktrees",
    help="Modern CLI for managing git worktrees with project-local configuration",
    invoke_without_command=True,
)


def require_initialized() -> WorktreesConfig:
    """Check for .worktrees.json and return config, or prompt to init.

    Returns:
        WorktreesConfig if initialized

    Raises:
        typer.Exit: If not initialized
    """
    project_root = find_project_root()
    if project_root is None:
        err.print("[red]error:[/red] not initialized for worktrees")
        err.print("  run: [dim]worktrees init[/dim]")
        raise typer.Exit(1)

    config = WorktreesConfig.load(project_root)
    if config is None:
        err.print("[red]error:[/red] not initialized for worktrees")
        err.print("  run: [dim]worktrees init[/dim]")
        raise typer.Exit(1)

    return config


def encode_branch_name(branch: str) -> str:
    """Encode branch name for use as a directory name.

    Replaces ``/`` with ``-slash-`` so that branch names like ``feat/menu-add``
    become flat directory names (``feat-slash-menu-add``) instead of nested paths.

    The encoding is reversible via :func:`decode_branch_name`.
    """
    return branch.strip("/").replace("/", "-slash-")


def decode_branch_name(encoded: str) -> str:
    """Decode a directory name back to the original branch name.

    Reverses the encoding performed by :func:`encode_branch_name`.
    """
    return encoded.replace("-slash-", "/")


def show_worktree_list(config: WorktreesConfig, use_stderr: bool = False) -> None:
    """Display worktrees in a clean format."""
    console = err if use_stderr else Console()

    try:
        worktrees = list_worktrees(config.project_root)
    except GitError as e:
        err.print(f"[red]error:[/red] {e}")
        return

    # Sort by creation time (oldest first), bare repo always first
    def sort_key(w: Worktree) -> tuple[int, float]:
        is_bare = 0 if w.branch == "(bare)" else 1
        try:
            ctime = w.path.stat().st_ctime
        except OSError:
            ctime = 0
        return (is_bare, ctime)

    worktrees = sorted(worktrees, key=sort_key)

    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("name")
    table.add_column("branch")
    table.add_column("commit", style="dim")
    table.add_column("mark", style="cyan")

    for w in worktrees:
        is_bare = w.branch == "(bare)"
        if is_bare:
            name_display = f"{w.path.name} [dim](bare)[/dim]"
        else:
            name_display = w.path.name

        # Get mark for this worktree
        worktree_mark = config.get_mark(w.path.name) or ""

        table.add_row(name_display, w.branch or "(detached)", w.commit, worktree_mark)

    console.print(table)


@app.callback()
def main(ctx: typer.Context) -> None:
    """Modern CLI for managing git worktrees with project-local configuration."""
    if ctx.invoked_subcommand is None:
        config = require_initialized()
        show_worktree_list(config)


# Import and register commands from submodules
from worktrees.cli import advanced, config_cmd, init_clone, mark, status, tmux, worktree  # noqa: E402, F401
