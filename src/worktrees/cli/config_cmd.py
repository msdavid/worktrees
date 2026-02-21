"""Config command: interactive configuration wizard."""

from typing import Annotated, Optional

import click
import questionary
import typer

from worktrees.cli import STYLE, app, err
from worktrees.user_config import DEFAULT_PROMPT, PROVIDER_DEFAULTS, UserConfig


@app.command("config")
def config_cmd(
    provider: Annotated[
        Optional[str],
        typer.Option("--provider", help="AI provider (claude or gemini)"),
    ] = None,
    command: Annotated[
        Optional[str],
        typer.Option("--command", help="Path to AI CLI binary"),
    ] = None,
    prompt: Annotated[
        Optional[str],
        typer.Option("--prompt", help="Custom prompt text"),
    ] = None,
    default_prompt: Annotated[
        bool,
        typer.Option("--default-prompt", help="Use the default prompt"),
    ] = False,
) -> None:
    """Configure worktrees settings.

    Interactive wizard to set up AI assistant preferences for the merge command.
    Configuration is stored globally at ~/.config/worktrees/config.json.

    Pass options (--provider, --command, --prompt, --default-prompt) for
    non-interactive mode. Only the specified fields are updated.

    Examples:
        worktrees config                    # Run the configuration wizard
        worktrees config --provider claude  # Set provider non-interactively
        worktrees config --default-prompt   # Reset prompt to default
    """
    config = UserConfig.load()

    # Non-interactive mode: if any option is passed, update only those fields
    non_interactive = any(
        [provider is not None, command is not None, prompt is not None, default_prompt]
    )

    if non_interactive:
        # Validate
        if prompt is not None and default_prompt:
            err.print(
                "[red]error:[/red] --prompt and --default-prompt are mutually exclusive"
            )
            raise typer.Exit(1)

        if provider is not None:
            if provider not in ("claude", "gemini"):
                err.print(
                    f"[red]error:[/red] unknown provider '{provider}'"
                    " (use 'claude' or 'gemini')"
                )
                raise typer.Exit(1)
            config.ai.provider = provider

        if command is not None:
            config.ai.command = command.strip()

        if default_prompt:
            config.ai.prompt = DEFAULT_PROMPT
        elif prompt is not None:
            config.ai.prompt = prompt.strip() if prompt.strip() else DEFAULT_PROMPT

        config.save()

        err.print()
        err.print("[green]Configuration saved[/green]")
        err.print()
        err.print("[bold]Settings:[/bold]")
        err.print(f"  provider: [cyan]{config.ai.provider}[/cyan]")
        err.print(f"  command:  [dim]{config.ai.get_effective_command()}[/dim]")
        prompt_preview = (
            config.ai.prompt[:50] + "..."
            if len(config.ai.prompt) > 50
            else config.ai.prompt
        )
        err.print(f"  prompt:   [dim]{prompt_preview}[/dim]")
        return

    # Interactive wizard

    # Show current settings if configured
    if config.is_configured():
        err.print()
        err.print("[bold]Current configuration:[/bold]")
        err.print(f"  provider: [cyan]{config.ai.provider}[/cyan]")
        err.print(f"  command:  [dim]{config.ai.get_effective_command()}[/dim]")
        prompt_preview = (
            config.ai.prompt[:50] + "..."
            if len(config.ai.prompt) > 50
            else config.ai.prompt
        )
        err.print(f"  prompt:   [dim]{prompt_preview}[/dim]")
        err.print()

    # Provider selection
    provider_choices = [
        questionary.Choice("Claude (claude CLI)", value="claude"),
        questionary.Choice("Gemini (gemini CLI)", value="gemini"),
    ]

    # Pre-select current provider
    default_provider = config.ai.provider if config.is_configured() else "claude"

    provider = questionary.select(
        "Which AI assistant?",
        choices=provider_choices,
        default=next(
            (c for c in provider_choices if c.value == default_provider),
            provider_choices[0],
        ),
        style=STYLE,
    ).ask()

    if provider is None:
        raise typer.Exit(0)

    config.ai.provider = provider

    # Command path
    default_command = PROVIDER_DEFAULTS[provider]["command"]
    current_command = config.ai.command if config.ai.command else default_command

    err.print()
    err.print(f"[dim]Default: {default_command}[/dim]")

    command = questionary.text(
        "Binary path (leave empty for default):",
        default=current_command if current_command != default_command else "",
        style=STYLE,
    ).ask()

    if command is None:
        raise typer.Exit(0)

    config.ai.command = command.strip()

    # Prompt
    err.print()
    err.print("[dim]Default prompt:[/dim]")
    err.print(f"[dim]{DEFAULT_PROMPT}[/dim]")
    err.print()

    use_default = questionary.confirm(
        "Use default prompt?",
        default=config.ai.prompt == DEFAULT_PROMPT,
        style=STYLE,
    ).ask()

    if use_default is None:
        raise typer.Exit(0)

    if use_default:
        config.ai.prompt = DEFAULT_PROMPT
    else:
        # Open editor with current prompt (or default if not set)
        current_prompt = config.ai.prompt if config.ai.prompt else DEFAULT_PROMPT
        err.print()
        err.print(
            "[dim]Opening editor for prompt (use <target-branch> and <current-branch> placeholders)...[/dim]"
        )
        prompt = click.edit(current_prompt)

        if prompt is None:
            # User closed editor without saving - keep existing prompt
            err.print("[dim]Keeping existing prompt.[/dim]")
        else:
            config.ai.prompt = prompt.strip() if prompt.strip() else DEFAULT_PROMPT

    # Save
    config.save()

    err.print()
    err.print("[green]Configuration saved[/green]")
    err.print()
    err.print("[bold]Settings:[/bold]")
    err.print(f"  provider: [cyan]{config.ai.provider}[/cyan]")
    err.print(f"  command:  [dim]{config.ai.get_effective_command()}[/dim]")
    prompt_preview = (
        config.ai.prompt[:50] + "..."
        if len(config.ai.prompt) > 50
        else config.ai.prompt
    )
    err.print(f"  prompt:   [dim]{prompt_preview}[/dim]")
