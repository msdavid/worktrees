"""Entry point for running worktrees as a module: python -m worktrees"""

from worktrees.cli import app  # Now imports from cli/__init__.py

if __name__ == "__main__":
    app()
