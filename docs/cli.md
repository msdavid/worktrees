# CLI Reference

Complete reference for all `worktrees` commands.

## Global Behavior

Running `worktrees` without any subcommand displays a list of all worktrees in the current project.

```bash
$ worktrees
path                          branch     commit
~/projects/myapp              (bare)
~/projects/myapp/main         main       a1b2c3d
~/projects/myapp/feature-x    feature-x  d4e5f6g
```

## Commands

### init

Initialize worktrees for the current repository.

```bash
worktrees init
```

**Behavior:**
1. Checks if already initialized (`.worktrees.json` exists)
2. Verifies current directory is a git repository
3. If already a bare repo, creates config and default branch worktree
4. If normal repo:
   - Checks for uncommitted changes (blocks if found)
   - Prompts to convert to bare repository (recommended)
   - If converting: migrates ENVIRON files, creates bare repo in `.git/`
   - If not converting: prompts for external worktrees storage location

**Examples:**

```bash
# Initialize in current repo
cd my-project
worktrees init

# Prompted options:
# - Convert to bare repository? (recommended)
# - Or choose external storage location
```

---

### clone

Clone a repository as bare with worktrees support.

```bash
worktrees clone <url> [path]
```

**Arguments:**
- `url` (required): Repository URL to clone
- `path` (optional): Destination directory (defaults to repo name)

**Behavior:**
1. Clones repository as bare into `.git/` subdirectory
2. Creates `.worktrees.json` configuration
3. Creates worktree for default branch (main/master)

**Examples:**

```bash
# Clone to default directory (repo name)
worktrees clone https://github.com/user/awesome-app.git

# Clone to custom directory
worktrees clone https://github.com/user/awesome-app.git ~/projects/my-awesome-app
```

---

### add

Create a new worktree for a branch.

```bash
worktrees add [branch] [--name NAME] [--no-setup]
```

**Arguments:**
- `branch` (optional): Branch to checkout. If omitted, shows interactive selector.

**Options:**
- `--name, -n NAME`: Custom name for the worktree directory
- `--no-setup`: Skip running setup commands

**Behavior:**
1. If no branch specified, shows interactive branch selector:
   - Select existing branch
   - Or create new branch (prompts for base branch and name)
2. Encodes branch name for directory use (e.g., `feat/my-feature` → `feat-slash-my-feature`)
3. Checks if worktree already exists (offers to use existing or rename)
4. Creates worktree directory
5. Symlinks files from `ENVIRON/` directory
6. Runs setup commands (unless `--no-setup`)
7. Displays next steps (cd command with venv activation if applicable)

**Examples:**

```bash
# Interactive branch selection
worktrees add

# Create worktree for existing branch
worktrees add feature/login

# Create with custom directory name
worktrees add feature/user-auth --name auth

# Skip setup commands
worktrees add bugfix/issue-123 --no-setup
```

---

### remove

Remove a worktree directory.

```bash
worktrees remove [name] [--force]
```

**Arguments:**
- `name` (optional): Worktree to remove. If omitted, shows interactive selector.

**Options:**
- `--force, -f`: Force removal even with uncommitted changes

**Behavior:**
1. Cannot remove worktree you're currently inside
2. If uncommitted changes exist, prompts for force removal
3. Removes worktree and displays remaining worktrees

**Examples:**

```bash
# Interactive selection
worktrees remove

# Remove specific worktree
worktrees remove feature-x

# Force remove (ignores uncommitted changes)
worktrees remove feature-x --force
```

---

### list

List all worktrees.

```bash
worktrees list
```

Alias: Running `worktrees` with no subcommand also lists worktrees.

**Output columns:**
- `path`: Full path to worktree
- `branch`: Current branch (or `(bare)`, `(detached)`)
- `commit`: Short commit hash

---

### status

Show current worktree status.

```bash
worktrees status
```

**Output:**
- Current worktree name and path
- Current branch
- Whether there are uncommitted changes
- Project root and total worktree count

**Example output:**

```
Status
  worktree: main
  branch:   main
  changes:  clean

Project
  root:       ~/projects/myapp
  worktrees:  3
```

---

### prune

Clean up stale worktree information.

```bash
worktrees prune
```

Runs `git worktree prune -v` to remove references to worktrees that no longer exist on disk.

---

### merge

Merge a branch into the current branch.

```bash
worktrees merge [branch] [--delete] [--delete-worktree]
```

**Arguments:**
- `branch` (optional): Branch to merge. If omitted, shows interactive selector.

**Options:**
- `--delete, -d`: Delete the merged branch after successful merge
- `--delete-worktree, -w`: Delete branch AND its worktree (implies `--delete`)

**Requirements:**
- Must be run from inside a worktree
- AI assistant must be configured (run `worktrees config` first)
- Source branch worktree must have all changes committed (if a worktree exists for the source branch)

**Behavior:**
1. Performs git merge
2. If conflicts occur, displays conflicting files and abort instructions
3. If `--delete` or `--delete-worktree`:
   - Deletes local branch
   - If worktree exists for branch and `--delete-worktree`, removes it
   - Prompts to delete remote branch if it exists

**Examples:**

```bash
# Interactive merge
worktrees merge

# Merge specific branch
worktrees merge feature/login

# Merge and delete branch
worktrees merge feature/login --delete

# Merge, delete branch, and remove worktree
worktrees merge feature/login --delete-worktree
```

---

### environ

Sync ENVIRON symlinks in the current worktree.

```bash
worktrees environ [--remove-stale]
```

**Options:**
- `--remove-stale, -s`: Remove symlinks pointing to deleted ENVIRON files

**Requirements:**
- Must be run from inside a worktree

**Behavior:**
1. Finds stale symlinks (pointing to non-existent ENVIRON files)
2. If stale found and `--remove-stale` not set, prompts for removal
3. Creates symlinks for any new ENVIRON files
4. Symlinks at highest possible level (directories before individual files)

**Examples:**

```bash
# Sync symlinks (prompts for stale removal)
worktrees environ

# Automatically remove stale symlinks
worktrees environ --remove-stale
```

---

### config

Configure AI assistant settings for the merge command.

```bash
worktrees config
```

**Behavior:**
Interactive wizard that prompts for:
1. **AI Provider**: Choose between Claude or Gemini CLI
2. **Binary path**: Custom path to the AI CLI executable (or use default)
3. **Prompt**: Use the default merge prompt or customize via your `$EDITOR`

Configuration is stored globally at `~/.config/worktrees/config.json`.

**Default prompt:**
```
merge <target-branch> into <current-branch>. If there are conflicts work
interactively with me to resolve by presenting the conflicts, the options
and your suggestion. if merge is successful run `worktrees mark merged into <current-branch>`
```

**Custom prompt placeholders:**
- `<target-branch>`: Replaced with the branch being merged
- `<current-branch>`: Replaced with your current branch

**Example config file:**
```json
{
  "ai": {
    "provider": "claude",
    "command": "",
    "prompt": "merge <target-branch> into <current-branch>..."
  }
}
```

---

### convert-old

Migrate existing bare repository to `.git/` structure.

```bash
worktrees convert-old
```

**Use case:**
For projects created with older versions of worktrees that have bare repo files (HEAD, objects/, refs/, etc.) at the project root.

**Behavior:**
1. Validates `.worktrees.json` exists
2. Checks if `.git/` directory already exists (skips if migrated)
3. Creates `.git/` directory
4. Moves all git internals into `.git/`
5. Updates worktree `.git` file references
6. Verifies worktrees still function

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (invalid arguments, git errors, etc.) |

## Environment

`worktrees` respects standard git environment variables like `GIT_DIR` and `GIT_WORK_TREE`.

## Tips

### Shell Integration

Add to your shell config for quick navigation:

```bash
# Bash/Zsh function to cd into a worktree
wt() {
  local dir
  dir=$(worktrees list 2>/dev/null | fzf | awk '{print $1}')
  [[ -n "$dir" ]] && cd "$dir"
}
```

### Aliases

```bash
alias wta='worktrees add'
alias wtr='worktrees remove'
alias wtl='worktrees list'
alias wts='worktrees status'
```
