"""Status command for showing current worktree information."""

from pathlib import Path

import typer

from worktrees.cli import app, err, require_initialized
from worktrees.git import (
    GitError,
    get_current_branch,
    has_uncommitted_changes,
    is_valid_worktree,
    list_worktrees,
)


@app.command()
def status() -> None:
    """Show current worktree status.

    Displays the current worktree, branch, and whether there are
    uncommitted changes. Also shows the total number of worktrees.
    """
    config = require_initialized()
    project_root = config.project_root
    cwd = Path.cwd()

    # Check if we're in a worktree
    in_worktree = is_valid_worktree(cwd)

    # Get worktree info
    try:
        worktrees = list_worktrees(project_root)
    except GitError as e:
        err.print(f"[red]error:[/red] {e}")
        raise typer.Exit(1)

    # Filter to managed worktrees (exclude bare)
    managed = [w for w in worktrees if w.branch != "(bare)"]

    err.print()
    err.print("[bold]Status[/bold]")

    if in_worktree:
        # Find current worktree (most specific match - longest path wins)
        current_wt = None
        for wt in worktrees:
            try:
                if cwd == wt.path or cwd.is_relative_to(wt.path):
                    if current_wt is None or len(wt.path.parts) > len(
                        current_wt.path.parts
                    ):
                        current_wt = wt
            except ValueError:
                continue

        if current_wt:
            err.print(f"  worktree: [cyan]{current_wt.path.name}[/cyan]")
            try:
                branch = get_current_branch(cwd)
                err.print(f"  branch:   [green]{branch}[/green]")
            except GitError:
                err.print(f"  branch:   [dim]{current_wt.branch or 'detached'}[/dim]")

            # Check for uncommitted changes
            if has_uncommitted_changes(cwd):
                err.print("  changes:  [yellow]uncommitted changes[/yellow]")
            else:
                err.print("  changes:  [dim]clean[/dim]")

            # Show mark
            mark = config.get_mark(current_wt.path.name)
            if mark:
                err.print(f"  mark:     [cyan]{mark}[/cyan]")
        else:
            err.print("  worktree: [dim]unknown[/dim]")
    else:
        err.print("  worktree: [dim]not in a worktree[/dim]")

    err.print()
    err.print("[bold]Project[/bold]")
    err.print(f"  root:       [cyan]{project_root}[/cyan]")
    err.print(f"  worktrees:  {len(managed)}")
    err.print()
