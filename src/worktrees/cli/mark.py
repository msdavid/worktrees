"""Mark commands: mark and unmark worktrees."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from worktrees.cli import app, err, require_initialized
from worktrees.config import WorktreesConfig
from worktrees.git import GitError, list_worktrees


def get_current_worktree_name(config: WorktreesConfig) -> str | None:
    """Get the name of the current worktree if inside one."""
    cwd = Path.cwd()
    try:
        worktrees = list_worktrees(config.project_root)
        # Find most specific match (longest path wins)
        best_match = None
        for wt in worktrees:
            if wt.branch == "(bare)":
                continue
            try:
                if cwd == wt.path or cwd.is_relative_to(wt.path):
                    if best_match is None or len(wt.path.parts) > len(best_match.parts):
                        best_match = wt.path
            except ValueError:
                continue
        return best_match.name if best_match else None
    except GitError:
        pass
    return None


def get_worktree_names(config: WorktreesConfig) -> set[str]:
    """Get set of all worktree names (excluding bare repo)."""
    try:
        worktrees = list_worktrees(config.project_root)
        return {wt.path.name for wt in worktrees if wt.branch != "(bare)"}
    except GitError:
        return set()


@app.command()
def mark(
    text: Annotated[
        Optional[list[str]],
        typer.Argument(help="Mark text (replaces existing mark)"),
    ] = None,
    worktree: Annotated[
        Optional[str],
        typer.Option("--worktree", "-w", help="Target worktree (default: current)"),
    ] = None,
) -> None:
    """Set a mark on a worktree.

    Marks are simple text labels for organizing worktrees.
    Each worktree can have one mark (setting a new mark replaces the old one).

    Examples:
        worktrees mark done              # Mark current worktree
        worktrees mark done -w feature   # Mark specific worktree
        worktrees mark ready for review  # Multi-word mark
    """
    config = require_initialized()

    # Determine target worktree
    if worktree:
        target_name = worktree
    else:
        target_name = get_current_worktree_name(config)
        if target_name is None:
            err.print("[red]error:[/red] not inside a worktree")
            err.print("  use [dim]-w <name>[/dim] to specify a worktree")
            raise typer.Exit(1)

    # Validate worktree exists
    worktree_names = get_worktree_names(config)
    if target_name not in worktree_names:
        err.print(f"[red]error:[/red] worktree '{target_name}' not found")
        raise typer.Exit(1)

    if not text:
        # Show current mark if no text provided
        mark_text = config.get_mark(target_name)
        if mark_text:
            err.print(f"[bold]{target_name}:[/bold] [cyan]{mark_text}[/cyan]")
        else:
            err.print(f"[dim]No mark on {target_name}[/dim]")
        return

    # Join all arguments into a single mark
    mark_text = " ".join(text)

    config.set_mark(target_name, mark_text)
    config.save()

    err.print(
        f"[green]Marked[/green] [bold]{target_name}[/bold]: [cyan]{mark_text}[/cyan]"
    )


@app.command()
def unmark(
    worktree: Annotated[
        Optional[str],
        typer.Option("--worktree", "-w", help="Target worktree (default: current)"),
    ] = None,
) -> None:
    """Clear the mark from a worktree.

    Examples:
        worktrees unmark              # Clear mark from current worktree
        worktrees unmark -w feature   # Clear mark from specific worktree
    """
    config = require_initialized()

    # Determine target worktree
    if worktree:
        target_name = worktree
    else:
        target_name = get_current_worktree_name(config)
        if target_name is None:
            err.print("[red]error:[/red] not inside a worktree")
            err.print("  use [dim]-w <name>[/dim] to specify a worktree")
            raise typer.Exit(1)

    # Validate worktree exists
    worktree_names = get_worktree_names(config)
    if target_name not in worktree_names:
        err.print(f"[red]error:[/red] worktree '{target_name}' not found")
        raise typer.Exit(1)

    if config.clear_mark(target_name):
        config.save()
        err.print(f"[green]Cleared mark from[/green] [bold]{target_name}[/bold]")
    else:
        err.print(f"[dim]No mark on {target_name}[/dim]")
