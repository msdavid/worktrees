"""Ephemeral file exclusion patterns for ENVIRON migration.

These patterns identify build artifacts, caches, and runtime files that should
NOT be migrated to ENVIRON during `worktrees init`. These files are regenerable
and would waste space in the shared environment directory.

Virtual environments (.venv, venv) are intentionally NOT excluded as they
represent intentional user setup and may contain locally-compiled packages.

Lock files (Cargo.lock, package-lock.json, etc.) are also NOT excluded as
they ensure reproducibility of dependencies.
"""

from fnmatch import fnmatch
from pathlib import Path

# =============================================================================
# EXCLUDED DIRECTORIES
# =============================================================================
# If ANY component of a path matches these, exclude the entire path.
# These are cache/build directories that should never be migrated.

EXCLUDED_DIRS: dict[str, set[str]] = {
    # -------------------------------------------------------------------------
    # Python
    # -------------------------------------------------------------------------
    "python": {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".pytype",
        ".pyre",
        ".hypothesis",
        ".tox",
        ".nox",
        ".coverage_cache",
        ".eggs",
        "*.egg-info",
        "build",
        "dist",
        "htmlcov",
        ".pdm-build",
        ".hatch",
        ".uv",
    },
    # -------------------------------------------------------------------------
    # JavaScript / Node.js
    # -------------------------------------------------------------------------
    "javascript": {
        "node_modules",
        ".npm",
        ".yarn",
        ".pnpm-store",
        ".parcel-cache",
        ".cache",
        ".next",
        ".nuxt",
        ".output",
        ".svelte-kit",
        ".turbo",
        "coverage",
        ".nyc_output",
        ".angular",
        ".vite",
        ".astro",
    },
    # -------------------------------------------------------------------------
    # TypeScript
    # -------------------------------------------------------------------------
    "typescript": {
        ".tsbuildinfo_cache",
    },
    # -------------------------------------------------------------------------
    # Rust
    # -------------------------------------------------------------------------
    "rust": {
        "target",
    },
    # -------------------------------------------------------------------------
    # Go
    # -------------------------------------------------------------------------
    "go": {
        # Go module cache is typically in ~/go/pkg/mod, not in project
    },
    # -------------------------------------------------------------------------
    # Java / Kotlin / Scala / JVM
    # -------------------------------------------------------------------------
    "jvm": {
        "target",
        "build",
        ".gradle",
        "out",
        ".kotlin",
        ".scala_dependencies",
        ".bsp",
        ".metals",
        ".bloop",
    },
    # -------------------------------------------------------------------------
    # C / C++
    # -------------------------------------------------------------------------
    "c_cpp": {
        "CMakeFiles",
        "_deps",
        ".cmake",
        "cmake-build-*",
        ".ccache",
        ".ccls-cache",
        ".clangd",
    },
    # -------------------------------------------------------------------------
    # .NET / C#
    # -------------------------------------------------------------------------
    "dotnet": {
        "bin",
        "obj",
        ".vs",
        "packages",
        ".nuget",
    },
    # -------------------------------------------------------------------------
    # Ruby
    # -------------------------------------------------------------------------
    "ruby": {
        ".bundle",
        "vendor/bundle",
        ".ruby-lsp",
    },
    # -------------------------------------------------------------------------
    # PHP
    # -------------------------------------------------------------------------
    "php": {
        "vendor",
        ".phpunit.cache",
        ".php-cs-fixer.cache",
        ".phpstan",
    },
    # -------------------------------------------------------------------------
    # Swift / Objective-C / Xcode
    # -------------------------------------------------------------------------
    "apple": {
        ".build",
        "DerivedData",
        "Build",
        "xcuserdata",
        ".swiftpm",
    },
    # -------------------------------------------------------------------------
    # General Build Tools
    # -------------------------------------------------------------------------
    "build_tools": {
        "bazel-*",
        ".bazel",
        "_build",
        ".makefiles",
        ".zig-cache",
        "zig-out",
    },
    # -------------------------------------------------------------------------
    # IDE Caches (NOT configs - configs are kept)
    # -------------------------------------------------------------------------
    "ide_caches": {
        # VS Code caches
        ".vscode-server",
        ".vscode-test",
        ".history",
        # JetBrains caches and runtime state
        ".idea/caches",
        ".idea/artifacts",
        ".idea/libraries",
        ".idea/shelf",
        ".idea/httpRequests",
        ".idea/dataSources",
        # Vim / Neovim caches
        ".vim/swap",
        ".vim/undo",
        ".vim/backup",
        ".nvim",
        ".neovim",
        # Emacs caches
        ".emacs.d/auto-save-list",
        ".emacs.d/eln-cache",
        ".emacs.d/elpa",
        ".emacs.d/transient",
        ".emacs.d/.cache",
    },
    # -------------------------------------------------------------------------
    # OS Generated
    # -------------------------------------------------------------------------
    "os": {
        ".Trash",
        ".Spotlight-V100",
        ".fseventsd",
        "$RECYCLE.BIN",
        "System Volume Information",
    },
    # -------------------------------------------------------------------------
    # Miscellaneous
    # -------------------------------------------------------------------------
    "misc": {
        ".terraform",
        ".vagrant",
        ".docker",
        "__snapshots__",
        ".serverless",
        ".aws-sam",
        ".amplify",
        ".vercel",
        ".netlify",
        ".deno",
    },
}

# =============================================================================
# EXCLUDED FILE PATTERNS
# =============================================================================
# Matched against filename only (not full path)

EXCLUDED_FILE_PATTERNS: dict[str, set[str]] = {
    # -------------------------------------------------------------------------
    # Python
    # -------------------------------------------------------------------------
    "python": {
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".coverage",
        ".coverage.*",
        "coverage.xml",
        "*.egg",
        "*.whl",
        ".python-version",
    },
    # -------------------------------------------------------------------------
    # JavaScript / TypeScript
    # -------------------------------------------------------------------------
    "javascript": {
        "*.tsbuildinfo",
        ".eslintcache",
        ".stylelintcache",
        ".prettiercache",
        "npm-debug.log*",
        "yarn-debug.log*",
        "yarn-error.log*",
        "pnpm-debug.log*",
        ".pnpm-debug.log",
    },
    # -------------------------------------------------------------------------
    # Rust
    # -------------------------------------------------------------------------
    "rust": {
        "*.rlib",
        "*.rmeta",
    },
    # -------------------------------------------------------------------------
    # C / C++
    # -------------------------------------------------------------------------
    "c_cpp": {
        "*.o",
        "*.obj",
        "*.a",
        "*.lib",
        "*.so",
        "*.so.*",
        "*.dylib",
        "*.dll",
        "*.exe",
        "*.out",
        "*.dSYM",
        "*.gcno",
        "*.gcda",
        "*.gcov",
        "*.pch",
        "*.gch",
    },
    # -------------------------------------------------------------------------
    # Java / JVM
    # -------------------------------------------------------------------------
    "jvm": {
        "*.class",
        "*.jar",
        "*.war",
        "*.ear",
        "*.nar",
        "hs_err_pid*",
        "replay_pid*",
    },
    # -------------------------------------------------------------------------
    # .NET
    # -------------------------------------------------------------------------
    "dotnet": {
        "*.pdb",
        "*.user",
        "*.nupkg",
        "*.snupkg",
    },
    # -------------------------------------------------------------------------
    # Ruby
    # -------------------------------------------------------------------------
    "ruby": {
        "*.gem",
    },
    # -------------------------------------------------------------------------
    # OS Files
    # -------------------------------------------------------------------------
    "os": {
        ".DS_Store",
        ".DS_Store?",
        "._*",
        "Thumbs.db",
        "Thumbs.db:encryptable",
        "ehthumbs.db",
        "ehthumbs_vista.db",
        "Desktop.ini",
        "*.lnk",
    },
    # -------------------------------------------------------------------------
    # Editor Backup/Temp/Swap Files
    # -------------------------------------------------------------------------
    "editor": {
        "*~",
        "*.swp",
        "*.swo",
        "*.swn",
        "#*#",
        ".#*",
        "*.bak",
        "*.tmp",
        "*.temp",
        "*.orig",
    },
    # -------------------------------------------------------------------------
    # Logs
    # -------------------------------------------------------------------------
    "logs": {
        "*.log",
        "*.log.*",
    },
    # -------------------------------------------------------------------------
    # IDE runtime state files
    # -------------------------------------------------------------------------
    "ide_state": {
        "workspace.xml",
        "tasks.xml",
        "usage.statistics.xml",
        "*.iws",
    },
}


# =============================================================================
# COMBINED SETS (for efficient lookups)
# =============================================================================


def _flatten_patterns(grouped: dict[str, set[str]]) -> set[str]:
    """Flatten grouped patterns into a single set."""
    result: set[str] = set()
    for patterns in grouped.values():
        result.update(patterns)
    return result


# Pre-computed combined sets for runtime efficiency
ALL_EXCLUDED_DIRS: set[str] = _flatten_patterns(EXCLUDED_DIRS)
ALL_EXCLUDED_FILE_PATTERNS: set[str] = _flatten_patterns(EXCLUDED_FILE_PATTERNS)


# =============================================================================
# FILTERING FUNCTIONS
# =============================================================================


def is_ephemeral_file(path: Path) -> bool:
    """Check if a file path should be excluded from ENVIRON migration.

    Args:
        path: Relative path from repository root (as returned by
              get_untracked_gitignored_files)

    Returns:
        True if the file is ephemeral (cache/build artifact) and should
        be excluded from migration, False if it should be migrated.

    Examples:
        >>> is_ephemeral_file(Path("__pycache__/module.pyc"))
        True
        >>> is_ephemeral_file(Path(".env"))
        False
        >>> is_ephemeral_file(Path("node_modules/lodash/index.js"))
        True
        >>> is_ephemeral_file(Path(".venv/lib/python3.11/site-packages/foo.py"))
        False
    """
    # Check each component of the path against directory patterns
    for part in path.parts[:-1]:  # All directories (not the filename)
        # Direct match
        if part in ALL_EXCLUDED_DIRS:
            return True
        # Pattern match for wildcards (e.g., "*.egg-info", "bazel-*")
        for pattern in ALL_EXCLUDED_DIRS:
            if "*" in pattern and fnmatch(part, pattern):
                return True

    # Check filename against file patterns
    filename = path.name

    # Direct match
    if filename in ALL_EXCLUDED_FILE_PATTERNS:
        return True

    # Pattern match
    for pattern in ALL_EXCLUDED_FILE_PATTERNS:
        if fnmatch(filename, pattern):
            return True

    return False


def filter_ephemeral_files(paths: list[Path]) -> list[Path]:
    """Filter out ephemeral files from a list of paths.

    Args:
        paths: List of relative paths (from get_untracked_gitignored_files)

    Returns:
        Filtered list with ephemeral files removed (only files to migrate)
    """
    return [p for p in paths if not is_ephemeral_file(p)]
