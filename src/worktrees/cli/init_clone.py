"""Init and clone commands for repository setup."""

import shutil
from pathlib import Path
from typing import Annotated, Optional

import questionary
import typer

from worktrees.cli import STYLE, app, encode_branch_name, err
from worktrees.config import WORKTREES_JSON, WorktreesConfig
from worktrees.exclusions import filter_ephemeral_files
from worktrees.git import (
    GitError,
    add_worktree,
    clone_bare,
    convert_to_bare,
    get_default_branch,
    get_repo_name_from_url,
    get_untracked_gitignored_files,
    has_uncommitted_changes,
    is_bare_repo,
    is_git_repo,
)


@app.command()
def init() -> None:
    """Initialize worktrees for this repository."""
    cwd = Path.cwd()

    # Check if already initialized
    if (cwd / WORKTREES_JSON).exists():
        err.print("[yellow]warning:[/yellow] already initialized")
        err.print(f"  config: [cyan]{cwd / WORKTREES_JSON}[/cyan]")
        raise typer.Exit(0)

    # Check if this is a git repository
    if not is_git_repo(cwd):
        err.print("[red]error:[/red] not a git repository")
        raise typer.Exit(1)

    # Check if already a bare repo
    if is_bare_repo(cwd):
        # Already bare, just create config
        config = WorktreesConfig(
            worktrees_dir=cwd,
            project_root=cwd,
        )
        config.save(cwd)

        # Get default branch and create worktree
        default_branch = get_default_branch(cwd)
        worktree_path = cwd / encode_branch_name(default_branch)

        if not worktree_path.exists():
            add_worktree(worktree_path, default_branch, cwd=cwd)

            err.print()
            err.print("[bold]Initialized[/bold]")
            err.print(f"  config: [cyan]{WORKTREES_JSON}[/cyan]")
            err.print("  mode:   bare repository")
            err.print()
            err.print("[bold]Created[/bold]")
            err.print(f"  path:   [cyan]{worktree_path}[/cyan]")
            err.print(f"  branch: [green]{default_branch}[/green]")
            err.print()
            err.print("[bold]Next[/bold]")
            err.print(f"  [dim]cd {worktree_path}[/dim]")
            err.print()
        else:
            err.print()
            err.print("[bold]Initialized[/bold]")
            err.print(f"  config: [cyan]{WORKTREES_JSON}[/cyan]")
            err.print("  mode:   bare repository")
            err.print()

        return

    # Normal repo - check for uncommitted changes
    if has_uncommitted_changes(cwd):
        err.print("[red]error:[/red] uncommitted changes detected")
        err.print("  commit or stash changes before converting to bare")
        raise typer.Exit(1)

    # Ask if user wants to convert to bare
    err.print()
    convert = questionary.confirm(
        "Convert to bare repository? (recommended for worktrees)",
        default=False,
        style=STYLE,
    ).ask()

    if convert is None:
        raise typer.Exit(0)

    if convert:
        # Convert to bare repository
        try:
            # Migrate untracked+gitignored files to ENVIRON before conversion
            # (excluding ephemeral caches and build artifacts)
            untracked = get_untracked_gitignored_files(cwd)
            untracked = filter_ephemeral_files(untracked)
            migrated_files: list[Path] = []
            if untracked:
                environ_dir = cwd / "ENVIRON"
                environ_dir.mkdir(exist_ok=True)
                for file_path in untracked:
                    src = cwd / file_path
                    dest = environ_dir / file_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dest))
                    migrated_files.append(file_path)

            bare_path, default_branch = convert_to_bare(cwd)

            # Create config
            config = WorktreesConfig(
                worktrees_dir=bare_path,
                project_root=bare_path,
            )
            config.save(bare_path)

            # Create worktree for default branch
            worktree_path = bare_path / encode_branch_name(default_branch)
            add_worktree(worktree_path, default_branch, cwd=bare_path)

            err.print()
            err.print("[bold]Converted[/bold]")
            err.print(f"  repository: [cyan]{bare_path}[/cyan]")
            err.print()
            err.print("[bold]Created[/bold]")
            err.print(f"  path:   [cyan]{worktree_path}[/cyan]")
            err.print(f"  branch: [green]{default_branch}[/green]")

            if migrated_files:
                err.print()
                err.print("[bold]Migrated to ENVIRON[/bold]")
                for f in migrated_files:
                    err.print(f"  [dim]{f}[/dim]")

            err.print()
            err.print("[bold]Next[/bold]")
            err.print(f"  [dim]cd {worktree_path}[/dim]")
            err.print()

        except GitError as e:
            err.print(f"[red]error:[/red] {e}")
            raise typer.Exit(1)
    else:
        # Use external storage
        repo_name = cwd.name
        default_path = Path.home() / ".worktrees" / repo_name

        err.print()
        choice = questionary.select(
            "Where should worktrees be stored?",
            choices=[
                questionary.Choice(
                    f"~/.worktrees/{repo_name} (default)", value="default"
                ),
                questionary.Choice("Custom path...", value="custom"),
            ],
            style=STYLE,
        ).ask()

        if choice is None:
            raise typer.Exit(0)

        if choice == "custom":
            custom_path = questionary.text(
                "Enter worktrees directory:",
                style=STYLE,
            ).ask()
            if not custom_path:
                raise typer.Exit(0)
            worktrees_dir = Path(custom_path).expanduser()
        else:
            worktrees_dir = default_path

        # Create config
        config = WorktreesConfig(
            worktrees_dir=worktrees_dir,
            project_root=cwd,
        )
        config.save(cwd)

        err.print()
        err.print("[bold]Initialized[/bold]")
        err.print(f"  config:     [cyan]{WORKTREES_JSON}[/cyan]")
        err.print(f"  worktrees:  [cyan]{worktrees_dir}[/cyan]")
        err.print()


@app.command()
def clone(
    url: Annotated[str, typer.Argument(help="Repository URL to clone")],
    path: Annotated[
        Optional[str],
        typer.Argument(help="Destination directory (default: repo name)"),
    ] = None,
) -> None:
    """Clone a repository as bare with worktrees support."""
    # Determine destination path (must be absolute)
    if path:
        dest = Path(path).expanduser().resolve()
    else:
        repo_name = get_repo_name_from_url(url)
        dest = (Path.cwd() / repo_name).resolve()

    # Check if destination exists
    if dest.exists():
        err.print(f"[red]error:[/red] destination already exists: [cyan]{dest}[/cyan]")
        raise typer.Exit(1)

    try:
        # Clone as bare
        clone_bare(url, dest)

        # Create config
        config = WorktreesConfig(
            worktrees_dir=dest,
            project_root=dest,
        )
        config.save(dest)

        # Get default branch and create worktree
        default_branch = get_default_branch(dest)
        worktree_path = dest / encode_branch_name(default_branch)
        add_worktree(worktree_path, default_branch, cwd=dest)

        err.print()
        err.print("[bold]Cloned[/bold]")
        err.print(f"  repository: [cyan]{dest}[/cyan]")
        err.print()
        err.print("[bold]Created[/bold]")
        err.print(f"  path:   [cyan]{worktree_path}[/cyan]")
        err.print(f"  branch: [green]{default_branch}[/green]")
        err.print()
        err.print("[bold]Next[/bold]")
        err.print(f"  [dim]cd {worktree_path}[/dim]")
        err.print()

    except GitError as e:
        err.print(f"[red]error:[/red] {e}")
        raise typer.Exit(1)
