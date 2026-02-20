"""Worktree management commands: add, remove, list, prune."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Annotated, Optional

import questionary
import typer
from rich import print as rprint

from worktrees.cli import (
    STYLE,
    app,
    encode_branch_name,
    err,
    require_initialized,
    show_worktree_list,
)
from worktrees.cli.tmux import (
    attach_or_switch,
    create_tmux_session,
    get_tmux_sessions,
)
from worktrees.git import (
    GitError,
    add_worktree,
    branch_exists,
    create_environ_symlinks,
    get_current_branch,
    get_main_worktree,
    list_local_branches,
    list_worktrees,
    prune_worktrees,
    remove_worktree,
    run_setup_command,
)


@app.command()
def add(
    branch: Annotated[
        Optional[str],
        typer.Argument(help="Branch to checkout (interactive if omitted)"),
    ] = None,
    name: Annotated[
        Optional[str],
        typer.Option("--name", "-n", help="Custom name for the worktree directory"),
    ] = None,
    no_setup: Annotated[
        bool,
        typer.Option("--no-setup", help="Skip setup commands from .worktrees.json"),
    ] = False,
) -> None:
    """Create a new worktree for a branch.

    Creates a worktree directory, links ENVIRON files, and runs setup commands.
    If BRANCH is omitted, shows an interactive branch selector.
    """
    config = require_initialized()
    project_root = config.project_root

    # Step 1: Select branch first
    base_branch = None
    if not branch:
        try:
            branches = list_local_branches(project_root)
            try:
                current = get_current_branch(project_root)
            except GitError:
                current = None

            choices = [
                questionary.Choice(
                    f"{b} *" if b == current else b,
                    value=b,
                )
                for b in branches
            ]
            choices.insert(0, questionary.Choice("+ new branch", value="__new__"))

            selection = questionary.select(
                "Select branch:",
                choices=choices,
                style=STYLE,
            ).ask()

            if selection is None:
                raise typer.Exit(0)
            elif selection == "__new__":
                # Select base branch
                base_choices = [
                    questionary.Choice(
                        f"{b} *" if b == current else b,
                        value=b,
                    )
                    for b in branches
                ]
                base_branch = questionary.select(
                    "Base branch:",
                    choices=base_choices,
                    style=STYLE,
                ).ask()
                if base_branch is None:
                    raise typer.Exit(0)

                branch = questionary.text("New branch name:", style=STYLE).ask()
                if not branch:
                    raise typer.Exit(0)

                # Check if branch already exists
                local_exists, remote_exists = branch_exists(branch, project_root)
                if local_exists or remote_exists:
                    location = "locally" if local_exists else "on remote"
                    rprint()
                    rprint(
                        f"[yellow]warning:[/yellow] branch [green]'{branch}'[/green] already exists {location}"
                    )

                    choice = questionary.select(
                        "What would you like to do?",
                        choices=[
                            questionary.Choice(
                                f"Use existing branch '{branch}'",
                                value="use",
                            ),
                            questionary.Choice(
                                f"Create new branch based on '{branch}'",
                                value="new",
                            ),
                            questionary.Choice("Cancel", value="cancel"),
                        ],
                        style=STYLE,
                    ).ask()

                    if choice == "use":
                        # Use existing branch - don't create new branch
                        base_branch = None
                    elif choice == "new":
                        # Create a new branch based on the existing one
                        new_branch = questionary.text(
                            "New branch name:",
                            style=STYLE,
                        ).ask()
                        if not new_branch:
                            raise typer.Exit(0)
                        base_branch = branch
                        branch = new_branch
                    else:
                        raise typer.Exit(0)
            else:
                base_branch = None
                branch = selection

        except GitError as e:
            err.print(f"[red]error:[/red] {e}")
            raise typer.Exit(1)

    # At this point branch is guaranteed to be set
    assert branch is not None

    # Step 2: Derive worktree name from branch
    if not name:
        name = encode_branch_name(branch)

    # Step 3: Check if worktree already exists
    worktree_path = config.get_worktree_path(name)
    if worktree_path.exists():
        rprint()
        rprint(f"[yellow]Worktree '{name}' already exists[/yellow]")
        rprint(f"  [dim]{worktree_path}[/dim]")
        rprint()

        venv_activate = worktree_path / ".venv" / "bin" / "activate"
        if venv_activate.exists():
            cmd = f"deactivate; cd {worktree_path} && source .venv/bin/activate"
        else:
            cmd = f"cd {worktree_path}"

        choice = questionary.select(
            "What would you like to do?",
            choices=[
                questionary.Choice("Use existing worktree", value="use"),
                questionary.Choice("Create with different name", value="new"),
                questionary.Choice("Cancel", value="cancel"),
            ],
            style=STYLE,
        ).ask()

        if choice == "use":
            rprint()
            rprint("[bold]Next[/bold]")
            rprint(f"  [dim]{cmd}[/dim]")
            rprint()
            raise typer.Exit(0)
        elif choice == "new":
            name = questionary.text("Worktree name:", style=STYLE).ask()
            if not name:
                raise typer.Exit(0)
            worktree_path = config.get_worktree_path(name)
            if worktree_path.exists():
                err.print(f"[red]error:[/red] '{name}' also exists")
                raise typer.Exit(1)
        else:
            raise typer.Exit(0)

    try:
        # Create worktree
        path = add_worktree(
            worktree_path,
            branch,
            create_branch=base_branch is not None,
            base_branch=base_branch,
            cwd=project_root,
        )

        # Output: Created
        err.print()
        err.print("[bold]Created[/bold]")
        err.print(f"  path:   [cyan]{path}[/cyan]")
        err.print(f"  branch: [green]{branch}[/green]")

        # Link files from ENVIRON
        environ_dir = project_root / "ENVIRON"
        if environ_dir.is_dir() and any(environ_dir.iterdir()):
            linked = create_environ_symlinks(environ_dir, path)
            if linked:
                err.print()
                err.print("[bold]Linked[/bold]")
                for f in linked:
                    err.print(f"  [dim]{f}[/dim]")

        # Run setup
        if not no_setup:
            commands = config.get_setup_commands(path)
            if commands:
                err.print()
                err.print("[bold]Setup[/bold]")
                for cmd in commands:
                    success, output = run_setup_command(path, cmd)
                    if success:
                        err.print(f"  [green]✓[/green] {cmd}")
                    else:
                        err.print(f"  [red]✗[/red] {cmd}")
                        err.print(f"    [dim]{output[:80]}[/dim]")

        # Ask about tmux session
        has_venv = (path / ".venv" / "bin" / "activate").exists()

        rprint()
        start_tmux = questionary.confirm(
            "Start a tmux session for this worktree?",
            default=True,
            style=STYLE,
        ).ask()

        if start_tmux:
            try:
                existing = get_tmux_sessions(name)
                session_name = (
                    name if name not in existing else f"{name}-{len(existing) + 1}"
                )
                create_tmux_session(session_name, path, has_venv)
                err.print(f"[green]Created session[/green] [bold]{session_name}[/bold]")
                if has_venv:
                    err.print("  [dim](.venv activated)[/dim]")
                attach_or_switch(session_name)
            except subprocess.CalledProcessError as e:
                err.print(f"[red]error:[/red] failed to create tmux session: {e}")
                raise typer.Exit(1)
            except FileNotFoundError:
                err.print("[red]error:[/red] tmux not found")
                err.print(
                    "  install tmux: [dim]apt install tmux[/dim] or [dim]brew install tmux[/dim]"
                )
                raise typer.Exit(1)
        else:
            # Show manual instructions
            if has_venv:
                cmd = f"cd {path} && source .venv/bin/activate"
            else:
                cmd = f"cd {path}"
            rprint("[bold]Next[/bold]")
            rprint(f"  [dim]{cmd}[/dim]")
            rprint()

    except GitError as e:
        err.print(f"[red]error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def remove(
    name: Annotated[
        Optional[str],
        typer.Argument(help="Worktree to remove (interactive if omitted)"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Force removal even with uncommitted changes"
        ),
    ] = False,
) -> None:
    """Remove a worktree directory.

    If NAME is omitted, shows an interactive worktree selector.
    Cannot remove the worktree you are currently inside.
    """
    config = require_initialized()
    project_root = config.project_root
    worktrees_dir = config.worktrees_dir

    if not name:
        worktrees = list_worktrees(project_root)
        managed = [
            w
            for w in worktrees
            if str(w.path).startswith(str(worktrees_dir)) and w.branch != "(bare)"
        ]

        if not managed:
            err.print("[yellow]warning:[/yellow] no managed worktrees found")
            raise typer.Exit(0)

        choices = [
            questionary.Choice(
                f"{w.path.name} ({w.branch or 'detached'})",
                value=w.path.name,
            )
            for w in managed
        ]

        name = questionary.select(
            "Select worktree to remove:",
            choices=choices,
            style=STYLE,
        ).ask()

        if name is None:
            raise typer.Exit(0)

    # Check if current directory is inside the worktree being removed
    cwd = Path.cwd()
    worktree_path = config.get_worktree_path(name)
    try:
        if os.path.commonpath([cwd, worktree_path]) == str(worktree_path):
            rprint("[red]error:[/red] cannot remove worktree while inside it")
            rprint(f"[dim]current directory: {cwd}[/dim]")
            try:
                main_wt = get_main_worktree(project_root)
                rprint(
                    f"[dim]run: deactivate && cd {main_wt} && source .venv/bin/activate && worktrees remove {name}[/dim]"
                )
            except GitError:
                rprint(f"[dim]run: deactivate && cd ~ && worktrees remove {name}[/dim]")
            raise typer.Exit(1)
    except ValueError:
        pass  # Paths on different drives (Windows)

    def _print_removed(wt_name: str) -> None:
        rprint()
        rprint("[bold]Removed[/bold]")
        rprint(f"  [dim]{config.get_worktree_path(wt_name)}[/dim]")
        rprint()
        rprint("[bold]Remaining[/bold]")
        show_worktree_list(config)
        rprint()

    def _handle_directory_not_empty(wt_path: Path) -> None:
        """Handle removal when directory has untracked files."""
        rprint(
            "[yellow]warning:[/yellow] directory has untracked files "
            "(e.g., .venv, .pytest_cache)"
        )
        if questionary.confirm(
            "Delete remaining files?", default=False, style=STYLE
        ).ask():
            shutil.rmtree(wt_path)
            _print_removed(name)
        else:
            rprint("[dim]Directory left in place[/dim]")
            raise typer.Exit(1)

    try:
        remove_worktree(worktree_path, force=force, cwd=project_root)
        _print_removed(name)

    except GitError as e:
        error_msg = str(e).lower()
        if "uncommitted changes" in error_msg or "modified" in error_msg:
            rprint("[yellow]warning:[/yellow] worktree has uncommitted changes")
            if questionary.confirm("Force remove?", default=False, style=STYLE).ask():
                try:
                    remove_worktree(worktree_path, force=True, cwd=project_root)
                    _print_removed(name)
                except GitError as e2:
                    if "directory not empty" in str(e2).lower():
                        _handle_directory_not_empty(worktree_path)
                    else:
                        rprint(f"[red]error:[/red] {e2}")
                        raise typer.Exit(1)
        elif "directory not empty" in error_msg:
            _handle_directory_not_empty(worktree_path)
        else:
            rprint(f"[red]error:[/red] {e}")
            raise typer.Exit(1)


@app.command("list")
def list_cmd() -> None:
    """List all worktrees."""
    config = require_initialized()
    show_worktree_list(config)


@app.command()
def prune() -> None:
    """Clean up stale worktree information."""
    config = require_initialized()
    project_root = config.project_root

    try:
        output = prune_worktrees(project_root)
        rprint()
        rprint("[bold]Prune[/bold]")
        if output:
            for line in output.strip().split("\n"):
                rprint(f"  [dim]{line}[/dim]")
        else:
            rprint("  [dim]nothing to clean[/dim]")
        rprint()
    except GitError as e:
        rprint(f"[red]error:[/red] {e}")
        raise typer.Exit(1)
