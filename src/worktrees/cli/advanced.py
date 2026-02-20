"""Advanced commands: convert-old, environ, merge."""

import subprocess
from pathlib import Path
from typing import Annotated, Optional

import questionary
import typer
from rich import print as rprint

from worktrees.cli import STYLE, app, err, require_initialized
from worktrees.config import WORKTREES_JSON, find_project_root
from worktrees.git import (
    GitError,
    create_environ_symlinks,
    find_stale_environ_symlinks,
    get_current_branch,
    has_uncommitted_changes,
    is_valid_worktree,
    list_local_branches,
    list_worktrees,
    migrate_to_dotgit,
)
from worktrees.user_config import UserConfig


@app.command("convert-old")
def convert_old() -> None:
    """Migrate existing bare repository to .git/ structure.

    For worktrees projects created with older versions that have bare repo
    files (HEAD, objects/, refs/, etc.) at the project root, this command
    moves them into a .git/ subdirectory for a cleaner structure.
    """
    cwd = Path.cwd()

    # Validate: has .worktrees.json
    if not (cwd / WORKTREES_JSON).exists():
        err.print("[red]error:[/red] not a worktrees project")
        err.print("  run this command from a worktrees project root")
        raise typer.Exit(1)

    # Check if already using .git/ structure
    if (cwd / ".git").exists():
        err.print("[yellow]already migrated:[/yellow] .git/ directory exists")
        raise typer.Exit(0)

    # Check if this is a bare repo at root
    if not (cwd / "HEAD").exists():
        err.print("[yellow]warning:[/yellow] no bare repository files at root")
        err.print("  nothing to migrate")
        raise typer.Exit(0)

    try:
        migrate_to_dotgit(cwd)

        # Verify worktrees still work
        worktrees = list_worktrees(cwd)

        err.print()
        err.print("[bold]Migrated[/bold]")
        err.print("  bare repository internals moved to .git/")
        err.print()
        err.print("[bold]Worktrees[/bold]")
        for wt in worktrees:
            if wt.branch != "(bare)":
                err.print(f"  [dim]{wt.path.name}[/dim] ({wt.branch})")
        err.print()

    except GitError as e:
        err.print(f"[red]error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def environ(
    remove_stale: Annotated[
        bool,
        typer.Option(
            "--remove-stale", "-s", help="Remove symlinks to deleted ENVIRON files"
        ),
    ] = False,
) -> None:
    """Sync ENVIRON symlinks in the current worktree.

    ENVIRON is a directory at the project root containing shared files
    (like .env, credentials) that are symlinked into each worktree.
    Must be run from inside a worktree.
    """
    cwd = Path.cwd()

    # Validate we're in a worktree
    if not is_valid_worktree(cwd):
        err.print("[red]error:[/red] not inside a worktree")
        err.print("  run this command from inside a worktree directory")
        raise typer.Exit(1)

    # Find project root
    project_root = find_project_root()
    if project_root is None:
        err.print("[red]error:[/red] cannot find project root")
        raise typer.Exit(1)

    environ_dir = project_root / "ENVIRON"
    if not environ_dir.is_dir():
        err.print("[yellow]warning:[/yellow] no ENVIRON directory found")
        err.print(f"  expected: [dim]{environ_dir}[/dim]")
        raise typer.Exit(0)

    if not any(environ_dir.iterdir()):
        err.print("[yellow]warning:[/yellow] ENVIRON directory is empty")
        raise typer.Exit(0)

    # Find stale symlinks
    stale = find_stale_environ_symlinks(cwd, environ_dir)
    if stale:
        rprint()
        rprint("[bold]Stale symlinks[/bold]")
        for s in stale:
            rprint(f"  [dim]{s.relative_to(cwd)}[/dim]")

        if remove_stale:
            for s in stale:
                s.unlink()
            rprint("  [green]removed[/green]")
        else:
            # Prompt with default skip
            if questionary.confirm(
                "Remove stale symlinks?", default=False, style=STYLE
            ).ask():
                for s in stale:
                    s.unlink()
                rprint("  [green]removed[/green]")
            else:
                rprint("  [dim]skipped[/dim]")

    # Create symlinks
    try:
        linked = create_environ_symlinks(environ_dir, cwd)
        if linked:
            rprint()
            rprint("[bold]Linked[/bold]")
            for f in linked:
                rprint(f"  [dim]{f}[/dim]")
            rprint()
        else:
            rprint()
            rprint("[dim]no new symlinks created (all files already exist)[/dim]")
            rprint()
    except GitError as e:
        err.print(f"[red]error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def merge(
    branch: Annotated[
        Optional[str],
        typer.Argument(help="Branch to merge (interactive if omitted)"),
    ] = None,
) -> None:
    """AI-assisted merge using configured assistant.

    Invokes the configured AI assistant (claude or gemini) to perform
    the merge interactively. The AI will handle conflicts and guide
    you through resolution.

    Must be run from inside a worktree. If BRANCH is omitted, shows
    an interactive branch selector.

    Run 'worktrees config' first to configure your AI assistant.

    Examples:
        worktrees merge feature-branch    # Merge feature-branch into current
        worktrees merge                   # Interactive branch selection
    """
    config = require_initialized()
    project_root = config.project_root
    cwd = Path.cwd()

    # Load user config
    user_config = UserConfig.load()
    if not user_config.is_configured():
        err.print("[red]error:[/red] AI assistant not configured")
        err.print("  run: [dim]worktrees config[/dim]")
        raise typer.Exit(1)

    # Validate: must be run from inside a worktree
    if not is_valid_worktree(cwd):
        err.print("[red]error:[/red] must be run from inside a worktree")
        raise typer.Exit(1)

    # Get current branch
    try:
        current = get_current_branch(cwd)
    except GitError as e:
        err.print(f"[red]error:[/red] {e}")
        raise typer.Exit(1)

    # Interactive branch selection if not provided
    if not branch:
        try:
            branches = list_local_branches(project_root)
            # Filter out current branch - can't merge into itself
            mergeable = [b for b in branches if b != current]

            if not mergeable:
                err.print("[yellow]warning:[/yellow] no branches to merge")
                raise typer.Exit(0)

            choices = [questionary.Choice(b, value=b) for b in mergeable]

            branch = questionary.select(
                "Select branch to merge:",
                choices=choices,
                style=STYLE,
            ).ask()

            if branch is None:
                raise typer.Exit(0)

        except GitError as e:
            err.print(f"[red]error:[/red] {e}")
            raise typer.Exit(1)

    # Validate branch
    if branch == current:
        err.print("[red]error:[/red] cannot merge branch into itself")
        raise typer.Exit(1)

    # Check if source branch worktree has uncommitted changes
    worktrees = list_worktrees(project_root)
    source_worktree = next((wt for wt in worktrees if wt.branch == branch), None)
    if source_worktree and has_uncommitted_changes(source_worktree.path):
        err.print("[red]error:[/red] source branch has uncommitted changes")
        err.print(f"  commit or stash changes in [bold]{branch}[/bold] before merging")
        raise typer.Exit(1)

    # Build and execute AI command
    ai_command = user_config.ai.build_command(
        target_branch=branch,
        current_branch=current,
    )

    err.print()
    err.print(
        f"[bold]Merging[/bold] [green]{branch}[/green] → [green]{current}[/green]"
    )
    err.print(f"[dim]Using {user_config.ai.provider}...[/dim]")
    err.print()

    # Run AI command interactively (not captured)
    try:
        result = subprocess.run(ai_command, shell=True, cwd=cwd)
        if result.returncode != 0:
            raise typer.Exit(result.returncode)
    except FileNotFoundError:
        err.print("[red]error:[/red] AI command not found")
        err.print(f"  command: [dim]{user_config.ai.get_effective_command()}[/dim]")
        err.print("  run: [dim]worktrees config[/dim] to update")
        raise typer.Exit(1)
