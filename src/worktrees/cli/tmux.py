"""Tmux session management for worktrees."""

import os
import re
import subprocess
from pathlib import Path
from typing import Annotated, Optional

import questionary
import typer

from worktrees.cli import STYLE, app, err, require_initialized
from worktrees.config import WorktreesConfig
from worktrees.git import GitError, list_worktrees


def get_current_worktree_name(config: WorktreesConfig) -> str | None:
    """Get the name of the current worktree if inside one."""
    cwd = Path.cwd()
    try:
        worktrees = list_worktrees(config.project_root)
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


def get_tmux_sessions(prefix: str) -> list[str]:
    """Get tmux sessions matching the worktree name pattern.

    Matches exact name or name with suffix (e.g., 'main', 'main-2', 'main-3').
    """
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return []

        sessions = result.stdout.strip().split("\n")
        sessions = [s for s in sessions if s]  # Filter empty strings

        # Match exact name or name-N pattern
        pattern = re.compile(rf"^{re.escape(prefix)}(-\d+)?$")
        return sorted([s for s in sessions if pattern.match(s)])
    except FileNotFoundError:
        return []


def get_next_session_name(worktree_name: str, existing: list[str]) -> str:
    """Get the next available session name.

    If no sessions exist, returns worktree_name.
    Otherwise returns worktree_name-N where N is the next available suffix.
    """
    if not existing:
        return worktree_name

    if worktree_name not in existing:
        return worktree_name

    # Find the highest suffix
    max_suffix = 1
    for session in existing:
        if session == worktree_name:
            continue
        match = re.match(rf"^{re.escape(worktree_name)}-(\d+)$", session)
        if match:
            max_suffix = max(max_suffix, int(match.group(1)))

    return f"{worktree_name}-{max_suffix + 1}"


def is_inside_tmux() -> bool:
    """Check if currently running inside a tmux session."""
    return bool(os.environ.get("TMUX"))


def create_tmux_session(name: str, path: Path, activate_venv: bool) -> None:
    """Create a new detached tmux session.

    Args:
        name: Session name
        path: Working directory for the session
        activate_venv: Whether to send venv activation command
    """
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", name, "-c", str(path)],
        check=True,
    )

    if activate_venv:
        subprocess.run(
            ["tmux", "send-keys", "-t", name, "source .venv/bin/activate", "Enter"],
            check=True,
        )


def attach_or_switch(session_name: str) -> None:
    """Attach to or switch to a tmux session.

    Uses switch-client if inside tmux, attach otherwise.
    """
    if is_inside_tmux():
        subprocess.run(["tmux", "switch-client", "-t", session_name], check=True)
    else:
        subprocess.run(["tmux", "attach", "-t", session_name], check=True)


@app.command()
def tmux(
    worktree_name: Annotated[
        Optional[str],
        typer.Argument(help="Worktree name (defaults to current)"),
    ] = None,
    new: Annotated[
        bool,
        typer.Option("--new", help="Create a new session (skip prompt)"),
    ] = False,
    attach: Annotated[
        Optional[str],
        typer.Option("--attach", help="Attach to a specific session (skip prompt)"),
    ] = None,
) -> None:
    """Start or attach to a tmux session for a worktree.

    Creates a new tmux session in the worktree directory with automatic
    virtual environment activation if .venv exists.

    If sessions already exist for the worktree, prompts to attach to
    an existing session or create a new one.

    Examples:
        worktrees tmux main     # Start/attach session for 'main' worktree
        worktrees tmux          # Start/attach session for current worktree
        worktrees tmux main --new       # Create new session without prompting
        worktrees tmux main --attach main-2  # Attach to specific session
    """
    config = require_initialized()

    # Validate options
    if new and attach is not None:
        err.print("[red]error:[/red] --new and --attach are mutually exclusive")
        raise typer.Exit(1)

    # Resolve worktree name
    if worktree_name is None:
        worktree_name = get_current_worktree_name(config)
        if worktree_name is None:
            err.print("[red]error:[/red] not inside a worktree")
            err.print("  specify a worktree name: [dim]worktrees tmux <name>[/dim]")
            raise typer.Exit(1)

    # Validate worktree exists
    worktree_names = get_worktree_names(config)
    if worktree_name not in worktree_names:
        err.print(f"[red]error:[/red] worktree '{worktree_name}' not found")
        if worktree_names:
            err.print(f"  available: {', '.join(sorted(worktree_names))}")
        raise typer.Exit(1)

    # Get worktree path
    worktree_path = config.get_worktree_path(worktree_name)

    # Check for existing sessions
    existing_sessions = get_tmux_sessions(worktree_name)

    if attach is not None:
        # --attach: directly attach to specified session
        if attach not in existing_sessions:
            err.print(f"[red]error:[/red] session '{attach}' not found")
            if existing_sessions:
                err.print(f"  available: {', '.join(existing_sessions)}")
            raise typer.Exit(1)
        try:
            attach_or_switch(attach)
        except subprocess.CalledProcessError as e:
            err.print(f"[red]error:[/red] tmux operation failed: {e}")
            raise typer.Exit(1)
        except FileNotFoundError:
            err.print("[red]error:[/red] tmux not found")
            raise typer.Exit(1)

    elif new or not existing_sessions:
        # --new or no sessions: create new session
        session_name = get_next_session_name(worktree_name, existing_sessions)
        has_venv = (worktree_path / ".venv" / "bin" / "activate").exists()

        try:
            create_tmux_session(session_name, worktree_path, has_venv)
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
        # Sessions exist - prompt user
        choices = []
        for session in existing_sessions:
            choices.append(
                questionary.Choice(f"Attach to '{session}'", value=("attach", session))
            )

        next_name = get_next_session_name(worktree_name, existing_sessions)
        choices.append(
            questionary.Choice(
                f"Create new session '{next_name}'", value=("create", next_name)
            )
        )

        err.print(f"[bold]Existing sessions for {worktree_name}:[/bold]")
        for session in existing_sessions:
            err.print(f"  - {session}")
        err.print()

        selection = questionary.select(
            "What would you like to do?",
            choices=choices,
            style=STYLE,
        ).ask()

        if selection is None:
            # User cancelled
            raise typer.Exit(0)

        action, session_name = selection

        try:
            if action == "create":
                has_venv = (worktree_path / ".venv" / "bin" / "activate").exists()
                create_tmux_session(session_name, worktree_path, has_venv)
                err.print(f"[green]Created session[/green] [bold]{session_name}[/bold]")
                if has_venv:
                    err.print("  [dim](.venv activated)[/dim]")

            attach_or_switch(session_name)
        except subprocess.CalledProcessError as e:
            err.print(f"[red]error:[/red] tmux operation failed: {e}")
            raise typer.Exit(1)
        except FileNotFoundError:
            err.print("[red]error:[/red] tmux not found")
            raise typer.Exit(1)
