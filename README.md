# worktrees

A modern CLI tool for managing git worktrees with project-local configuration.

## Why worktrees?

Git worktrees allow you to have multiple branches checked out simultaneously in separate directories. This is invaluable for:

- **Parallel development**: Work on a feature while keeping `main` checked out for reference
- **Code reviews**: Check out a PR branch without disrupting your current work
- **Hotfixes**: Quickly switch to a production branch without stashing changes
- **Testing**: Run tests on multiple branches simultaneously

`worktrees` enhances the git worktree experience with:

- **Interactive branch selection** with a polished TUI
- **Automatic setup**: Runs `uv sync`, `npm install`, etc. when creating worktrees
- **Shared environment files**: Symlinks `.env` and other config files across worktrees
- **Bare repository workflow**: Cleaner project structure with all worktrees as siblings
- **Project-local configuration**: `.worktrees.json` stores settings per-project

## Installation

```bash
# With uv (recommended)
uv tool install worktrees

# With pip
pip install worktrees

# With pipx
pipx install worktrees
```

## Quick Start

### Option 1: Clone a new repository

```bash
# Clone as a bare repository with worktrees support
worktrees clone https://github.com/user/repo.git

# This creates:
# repo/
#   .git/           # Bare repository
#   .worktrees.json # Configuration
#   main/           # Worktree for main branch
```

### Option 2: Initialize an existing repository

```bash
cd my-project
worktrees init

# Choose to convert to bare (recommended) or use external storage
```

### Create and manage worktrees

```bash
# Create a new worktree (interactive branch selection)
worktrees add

# Create a worktree for a specific branch
worktrees add feature/my-feature

# List all worktrees
worktrees list
# or just:
worktrees

# Remove a worktree
worktrees remove my-feature

# Show status of current worktree
worktrees status
```

## Commands

| Command | Description |
|---------|-------------|
| `worktrees` | List all worktrees (default action) |
| `worktrees init` | Initialize worktrees for current repository |
| `worktrees clone <url>` | Clone repository as bare with worktrees support |
| `worktrees add [branch]` | Create a new worktree |
| `worktrees remove [name]` | Remove a worktree |
| `worktrees list` | List all worktrees |
| `worktrees status` | Show current worktree status |
| `worktrees mark [text]` | Set a mark/label on a worktree |
| `worktrees unmark` | Clear mark from a worktree |
| `worktrees prune` | Clean up stale worktree references |
| `worktrees config` | Configure AI assistant settings |
| `worktrees merge [branch]` | AI-assisted merge using configured assistant |
| `worktrees tmux [name]` | Start/attach tmux session for a worktree |
| `worktrees environ` | Sync ENVIRON symlinks in current worktree |
| `worktrees convert-old` | Migrate old bare repo structure to .git/ |

## Configuration

### .worktrees.json

Created by `worktrees init` or `worktrees clone`:

```json
{
  "version": "1.0",
  "worktreesDir": ".",
  "setup": {
    "autoDetect": true,
    "commands": []
  }
}
```

| Field | Description |
|-------|-------------|
| `worktreesDir` | Where worktrees are stored (`.` = project root, or absolute path) |
| `setup.autoDetect` | Auto-detect setup commands from project files |
| `setup.commands` | Custom setup commands to run after creating worktrees |

### Auto-detected setup commands

When `autoDetect` is enabled, `worktrees` runs appropriate setup based on detected files:

| File | Command |
|------|---------|
| `pyproject.toml` | `uv sync` |
| `package.json` | `npm install` |
| `Cargo.toml` | `cargo build` |
| `go.mod` | `go mod download` |

### Custom setup commands

```json
{
  "setup": {
    "autoDetect": false,
    "commands": [
      "uv sync",
      "npm install",
      "cp .env.example .env"
    ]
  }
}
```

## ENVIRON Directory

The `ENVIRON/` directory at project root contains files that should be shared across all worktrees (symlinked, not copied):

```
project/
  .git/
  .worktrees.json
  ENVIRON/
    .env              # Shared environment variables
    .env.local        # Local overrides
    credentials.json  # API credentials
  main/               # Worktree
    .env -> ../ENVIRON/.env
  feature-x/          # Another worktree
    .env -> ../ENVIRON/.env
```

### Managing ENVIRON

```bash
# Files in ENVIRON/ are automatically symlinked when creating worktrees

# Manually sync symlinks in current worktree
worktrees environ

# Remove stale symlinks (pointing to deleted ENVIRON files)
worktrees environ --remove-stale
```

## Project Structure

After `worktrees clone` or `worktrees init` (with bare conversion):

```
my-project/
  .git/               # Bare repository (git internals)
  .worktrees.json     # worktrees configuration
  ENVIRON/            # Shared environment files (optional)
    .env
  main/               # Worktree for main branch
    .git              # File pointing to ../.git/worktrees/main
    src/
    ...
  feature-branch/     # Another worktree
    .git
    src/
    ...
```

## Workflows

### Feature branch workflow

```bash
# Start from main worktree
cd ~/projects/my-project/main

# Create worktree for new feature
worktrees add feature/awesome-thing

# After creation, you'll be prompted:
#   "Start a tmux session for this worktree?"
# If yes: creates and attaches to tmux session with venv activated
# If no: shows manual cd/source commands

# Work on feature...

# Merge back to main
cd ~/projects/my-project/main
worktrees merge feature/awesome-thing --delete-worktree
```

### Code review workflow

```bash
# Create worktree for PR review
worktrees add pr-123 --name review-123

# Review the code, run tests...

# Clean up when done
worktrees remove review-123
```

### Hotfix workflow

```bash
# From any worktree, create a hotfix branch
worktrees add hotfix/critical-bug

# Fix, test, deploy...

# Merge to main and clean up
cd ../main
worktrees merge hotfix/critical-bug --delete-worktree
```

## Advanced

### Merge with cleanup

```bash
# Merge and delete local branch
worktrees merge feature-x --delete

# Merge, delete branch AND its worktree
worktrees merge feature-x --delete-worktree

# Interactive: will prompt to delete remote branch too
```

### Migrating old projects

If you have a project with bare repo files at the root level (older worktrees setup):

```bash
worktrees convert-old
# Moves HEAD, objects/, refs/, etc. into .git/ subdirectory
```

## Requirements

- Python 3.10+
- Git 2.17+ (for worktree features)

## License

MIT

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.
