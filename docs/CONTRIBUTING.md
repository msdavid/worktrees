# Contributing to worktrees

Thank you for your interest in contributing to worktrees! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful and constructive in all interactions. We welcome contributors of all backgrounds and experience levels.

## Ways to Contribute

- **Bug Reports**: Found a bug? Open an issue with steps to reproduce.
- **Feature Requests**: Have an idea? Open an issue to discuss it.
- **Documentation**: Improvements to docs are always welcome.
- **Code**: Fix bugs, add features, improve tests.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git 2.17 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Getting Started

1. **Fork the repository** on GitHub

2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/worktrees.git
   cd worktrees
   ```

3. **Set up development environment**:
   ```bash
   # With uv (recommended)
   uv sync

   # Or with pip
   python -m venv .venv
   source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
   pip install -e ".[dev]"
   ```

4. **Verify setup**:
   ```bash
   pytest
   worktrees --help
   ```

## Making Changes

### Branch Naming

Use descriptive branch names:
- `feature/add-foo-command`
- `fix/worktree-path-issue`
- `docs/update-readme`

### Commit Messages

Write clear, concise commit messages:

```
feat: add status command

Shows current worktree, branch, and uncommitted changes status.
Also displays project root and total worktree count.
```

Prefixes:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation only
- `test:` Adding or updating tests
- `refactor:` Code changes that don't add features or fix bugs
- `chore:` Maintenance tasks

### Code Style

- Use type hints for all function parameters and return values
- Include docstrings for public functions
- Follow existing code patterns
- Keep functions focused and reasonably sized

Example:

```python
def my_function(path: Path, verbose: bool = False) -> list[str]:
    """Brief description of what this does.

    Args:
        path: Path to the directory
        verbose: Whether to include extra information

    Returns:
        List of results

    Raises:
        GitError: If git operation fails
    """
    # Implementation
```

### Testing

- Write tests for new functionality
- Update tests when changing existing behavior
- Ensure all tests pass before submitting:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=worktrees --cov-report=html

# Run specific test file
pytest tests/test_git.py
```

## Pull Request Process

### Before Submitting

1. **Run tests**: Ensure all tests pass
2. **Update documentation**: If you changed behavior, update relevant docs
3. **Review your changes**: Check for debug code, unnecessary changes

### Submitting

1. **Push your branch** to your fork
2. **Open a Pull Request** against `main`
3. **Fill out the PR template** with:
   - What the PR does
   - Why it's needed
   - How to test it

### After Submitting

- Respond to review feedback
- Make requested changes in new commits (we'll squash on merge)
- Keep the PR focused on one thing

## Project Structure

```
worktrees/
  src/worktrees/
    cli/              # CLI commands
      __init__.py     # Main app, shared utilities
      worktree.py     # add, remove, list, prune
      init_clone.py   # init, clone
      advanced.py     # convert-old, environ, merge
      status.py       # status
    config.py         # Configuration handling
    git.py            # Git operations
    exclusions.py     # ENVIRON file filtering
  tests/              # Test files
  docs/               # Documentation
  pyproject.toml      # Project configuration
  README.md           # Main readme
```

## Adding New Commands

1. **Choose the right module**:
   - `worktree.py`: Core worktree operations
   - `init_clone.py`: Repository setup
   - `advanced.py`: Power user features
   - `status.py`: Status/info commands
   - Or create a new module if it doesn't fit

2. **Implement the command**:
   ```python
   @app.command()
   def my_command(
       arg: Annotated[str, typer.Argument(help="Argument description")],
       flag: Annotated[bool, typer.Option("--flag", "-f", help="Flag description")] = False,
   ) -> None:
       """Brief command description.

       Detailed description of what the command does and when to use it.
       """
       config = require_initialized()
       # Implementation
   ```

3. **Add tests** in `tests/test_*.py`

4. **Update documentation**:
   - Add to `docs/cli.md`
   - Update `README.md` if user-facing

5. **Submit PR**

## Reporting Issues

### Bug Reports

Include:
- worktrees version (`worktrees --version` or check pyproject.toml)
- Python version (`python --version`)
- Git version (`git --version`)
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages (full traceback if available)

### Feature Requests

Include:
- Use case: What problem are you trying to solve?
- Proposed solution: How do you envision it working?
- Alternatives considered: Other ways to solve the problem?

## Questions?

- Open an issue for questions
- Check existing issues first

## License

By contributing, you agree that your contributions will be licensed under the project's MIT License.
