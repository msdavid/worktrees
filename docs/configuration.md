# Configuration Guide

This guide covers all configuration options for `worktrees`.

## Configuration File

### .worktrees.json

The `.worktrees.json` file is created in your project root when you run `worktrees init` or `worktrees clone`. It stores project-specific settings.

**Location:** Project root (same directory as `.git/`)

**Example:**

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

### Fields

#### version

```json
"version": "1.0"
```

Configuration schema version. Currently always `"1.0"`.

#### worktreesDir

```json
"worktreesDir": "."
```

Specifies where worktree directories are created.

| Value | Meaning |
|-------|---------|
| `"."` | Worktrees created as siblings in project root (bare repo mode) |
| Absolute path | Worktrees created in specified directory |

**Bare repo mode (recommended):**
```json
"worktreesDir": "."
```

Results in:
```
my-project/
  .git/
  .worktrees.json
  main/           <- worktree
  feature-x/      <- worktree
```

**External storage mode:**
```json
"worktreesDir": "/home/user/.worktrees/my-project"
```

Results in:
```
my-project/           <- original repo
  .git/
  .worktrees.json

~/.worktrees/my-project/
  main/               <- worktree
  feature-x/          <- worktree
```

#### setup.autoDetect

```json
"setup": {
  "autoDetect": true
}
```

When `true`, `worktrees` automatically detects project type and runs appropriate setup commands after creating a worktree.

**Auto-detected setup commands:**

| Marker File | Command |
|-------------|---------|
| `pyproject.toml` | `uv sync` |
| `package.json` | `npm install` |
| `Cargo.toml` | `cargo build` |
| `go.mod` | `go mod download` |

Multiple markers can match. For example, a project with both `pyproject.toml` and `package.json` will run both `uv sync` and `npm install`.

#### setup.commands

```json
"setup": {
  "autoDetect": false,
  "commands": [
    "uv sync",
    "npm install",
    "cp .env.example .env"
  ]
}
```

Custom list of commands to run after creating a worktree. Each command is executed in sequence in the new worktree directory.

**Priority:**
- If `commands` is non-empty, it takes precedence over auto-detection
- If `commands` is empty and `autoDetect` is `true`, auto-detection is used
- If both are disabled/empty, no setup commands run

---

## ENVIRON Directory

The `ENVIRON/` directory provides a mechanism for sharing configuration files across all worktrees.

### Location

```
my-project/
  ENVIRON/          <- Shared files go here
    .env
    .env.local
    config/
      credentials.json
  main/
    .env -> ../ENVIRON/.env
```

### How It Works

1. **On worktree creation (`worktrees add`):**
   - `worktrees` scans `ENVIRON/` for files and directories
   - Creates symlinks in the new worktree pointing to `ENVIRON/`
   - Symlinks at the highest level possible (entire directories when possible)

2. **Symlink strategy:**
   - If `ENVIRON/config/` exists and worktree has no `config/` directory, symlinks the entire `config/` directory
   - If worktree already has a `config/` directory, descends into it and symlinks individual files

3. **On `worktrees init` (converting to bare):**
   - Untracked files that are in `.gitignore` are migrated to `ENVIRON/`
   - Ephemeral files (caches, build artifacts) are excluded from migration

### Manual Syncing

If you add new files to `ENVIRON/` after creating worktrees:

```bash
cd my-project/main
worktrees environ
```

This creates symlinks for any new `ENVIRON/` files.

### Stale Symlinks

If you delete files from `ENVIRON/`, worktrees may have broken symlinks:

```bash
# Check and remove stale symlinks
worktrees environ --remove-stale
```

### What Goes in ENVIRON?

**Good candidates:**
- `.env` files (environment variables)
- API credentials and secrets
- Local configuration overrides
- IDE settings you want to share

**Not recommended:**
- Large binary files (no deduplication benefit)
- Files that should differ per branch
- Temporary or generated files

### Excluded from ENVIRON Migration

When running `worktrees init` on an existing repo, these file types are NOT migrated to `ENVIRON/`:

**Directories:**
- Python: `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.venv/`, etc.
- JavaScript: `node_modules/`, `.next/`, `.cache/`, `coverage/`, etc.
- Rust: `target/`
- Build tools: `build/`, `dist/`, `out/`
- IDE caches: `.vscode-server/`, `.idea/caches/`

**Files:**
- Compiled: `*.pyc`, `*.o`, `*.class`, `*.dll`
- Logs: `*.log`
- OS: `.DS_Store`, `Thumbs.db`
- Editor: `*~`, `*.swp`

See `src/worktrees/exclusions.py` for the complete list.

---

## Project Structures

### Recommended: Bare Repository Mode

```
my-project/
  .git/               # Bare repository internals
  .worktrees.json     # worktrees configuration
  ENVIRON/            # Shared config files
    .env
  main/               # Default branch worktree
    .git              # File (not directory) pointing to ../.git/worktrees/main
    src/
    pyproject.toml
  feature-x/          # Feature branch worktree
    .git
    src/
    pyproject.toml
```

**Advantages:**
- All worktrees are siblings, easy to navigate
- Clean separation of git internals and working directories
- ENVIRON symlinks work naturally with relative paths

### Alternative: External Storage Mode

```
my-project/           # Original repository
  .git/               # Normal git directory
  .worktrees.json
  src/
  pyproject.toml

~/.worktrees/my-project/
  feature-x/          # Worktrees stored externally
    .git
    src/
```

**Advantages:**
- Doesn't modify original repository structure
- Works with repos you don't want to convert to bare

**Disadvantages:**
- ENVIRON symlinks use absolute paths
- Worktrees are in a separate location from main repo

---

## Customization Examples

### Python Project

```json
{
  "version": "1.0",
  "worktreesDir": ".",
  "setup": {
    "autoDetect": false,
    "commands": [
      "uv sync",
      "pre-commit install"
    ]
  }
}
```

### Node.js Project with Multiple Package Managers

```json
{
  "version": "1.0",
  "worktreesDir": ".",
  "setup": {
    "autoDetect": false,
    "commands": [
      "pnpm install",
      "pnpm build"
    ]
  }
}
```

### Monorepo

```json
{
  "version": "1.0",
  "worktreesDir": ".",
  "setup": {
    "autoDetect": false,
    "commands": [
      "pnpm install",
      "pnpm -r build"
    ]
  }
}
```

### Skip All Setup

```json
{
  "version": "1.0",
  "worktreesDir": ".",
  "setup": {
    "autoDetect": false,
    "commands": []
  }
}
```

Or use `--no-setup` flag when creating worktrees:

```bash
worktrees add feature-x --no-setup
```

---

## Global User Configuration

### ~/.config/worktrees/config.json

Global settings stored per-user, separate from project configuration. Created when you run `worktrees config`.

**Location:** `~/.config/worktrees/config.json`

**Example:**

```json
{
  "ai": {
    "provider": "claude",
    "command": "",
    "prompt": "merge <target-branch> into <current-branch>..."
  }
}
```

### AI Configuration

Controls the AI assistant used by `worktrees merge`:

| Field | Description | Default |
|-------|-------------|---------|
| `provider` | AI provider (`claude` or `gemini`) | `claude` |
| `command` | Custom path to AI CLI (uses provider default if empty) | `""` |
| `prompt` | Prompt template with `<target-branch>` and `<current-branch>` placeholders | See below |

**Default prompt:**
```
merge <target-branch> into <current-branch>. If there are conflicts work
interactively with me to resolve by presenting the conflicts, the options
and your suggestion. if merge is successful run `worktrees mark merged into <current-branch>`
```

**Provider defaults:**

| Provider | Default Command | Invocation Pattern |
|----------|-----------------|-------------------|
| `claude` | `~/.claude/local/claude` | `{command} "{prompt}"` |
| `gemini` | `/home/user/.npm-global/bin/gemini` | `{command} -i "{prompt}"` |

### Configuring AI Settings

```bash
# Interactive configuration
worktrees config

# View current settings
cat ~/.config/worktrees/config.json
```
