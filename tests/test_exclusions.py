"""Tests for exclusions module."""

from pathlib import Path

import pytest

from worktrees.exclusions import (
    ALL_EXCLUDED_DIRS,
    ALL_EXCLUDED_FILE_PATTERNS,
    EXCLUDED_DIRS,
    EXCLUDED_FILE_PATTERNS,
    filter_ephemeral_files,
    is_ephemeral_file,
)


class TestIsEphemeralFile:
    """Tests for is_ephemeral_file() function."""

    def test_is_ephemeral_file_pycache(self):
        """Test __pycache__ directory is excluded."""
        assert is_ephemeral_file(Path("__pycache__/module.pyc")) is True
        assert is_ephemeral_file(Path("src/__pycache__/module.pyc")) is True

    def test_is_ephemeral_file_node_modules(self):
        """Test node_modules directory is excluded."""
        assert is_ephemeral_file(Path("node_modules/lodash/index.js")) is True
        assert is_ephemeral_file(Path("app/node_modules/react/index.js")) is True

    def test_is_ephemeral_file_venv_dotenv_not_excluded(self):
        """Test .venv directory itself is NOT excluded (intentional)."""
        # .venv is intentionally not excluded to preserve virtual environments
        assert is_ephemeral_file(Path(".venv/lib/python3.11/site-packages/foo.py")) is False
        # However, venv/bin is excluded because "bin" is an excluded directory (.NET)
        assert is_ephemeral_file(Path("venv/bin/python")) is True

    def test_is_ephemeral_file_env_not_excluded(self):
        """Test .env files are NOT excluded."""
        assert is_ephemeral_file(Path(".env")) is False
        assert is_ephemeral_file(Path(".env.local")) is False

    def test_is_ephemeral_file_pyc_excluded(self):
        """Test .pyc files are excluded."""
        assert is_ephemeral_file(Path("module.pyc")) is True
        assert is_ephemeral_file(Path("src/module.pyc")) is True

    def test_is_ephemeral_file_log_excluded(self):
        """Test log files are excluded."""
        assert is_ephemeral_file(Path("app.log")) is True
        assert is_ephemeral_file(Path("debug.log")) is True

    def test_is_ephemeral_file_ds_store_excluded(self):
        """Test .DS_Store is excluded."""
        assert is_ephemeral_file(Path(".DS_Store")) is True
        assert is_ephemeral_file(Path("subdir/.DS_Store")) is True

    def test_is_ephemeral_file_target_dir_rust(self):
        """Test Rust target directory is excluded."""
        assert is_ephemeral_file(Path("target/debug/myapp")) is True
        assert is_ephemeral_file(Path("target/release/myapp")) is True

    def test_is_ephemeral_file_build_dir(self):
        """Test build directories are excluded."""
        assert is_ephemeral_file(Path("build/output.js")) is True
        assert is_ephemeral_file(Path("dist/bundle.js")) is True

    def test_is_ephemeral_file_coverage_excluded(self):
        """Test coverage files are excluded."""
        assert is_ephemeral_file(Path(".coverage")) is True
        assert is_ephemeral_file(Path("coverage.xml")) is True
        assert is_ephemeral_file(Path("htmlcov/index.html")) is True

    def test_is_ephemeral_file_lock_files_not_excluded(self):
        """Test lock files are NOT excluded."""
        assert is_ephemeral_file(Path("Cargo.lock")) is False
        assert is_ephemeral_file(Path("package-lock.json")) is False
        assert is_ephemeral_file(Path("poetry.lock")) is False

    def test_is_ephemeral_file_wildcard_patterns(self):
        """Test wildcard pattern matching."""
        # *.egg-info pattern
        assert is_ephemeral_file(Path("mypackage.egg-info/PKG-INFO")) is True
        # bazel-* pattern
        assert is_ephemeral_file(Path("bazel-bin/output")) is True
        assert is_ephemeral_file(Path("bazel-out/file")) is True

    def test_is_ephemeral_file_ide_caches(self):
        """Test IDE cache directories are excluded."""
        # .vscode-server is a single directory component, so it matches
        assert is_ephemeral_file(Path(".vscode-server/data.json")) is True
        # .history is also a single component
        assert is_ephemeral_file(Path(".history/file.txt")) is True

    def test_is_ephemeral_file_editor_temp_files(self):
        """Test editor temporary files are excluded."""
        assert is_ephemeral_file(Path("file.swp")) is True
        assert is_ephemeral_file(Path("file~")) is True
        assert is_ephemeral_file(Path(".#file.txt")) is True

    def test_is_ephemeral_file_config_files_not_excluded(self):
        """Test configuration files are NOT excluded."""
        assert is_ephemeral_file(Path(".eslintrc.json")) is False
        assert is_ephemeral_file(Path(".prettierrc")) is False
        assert is_ephemeral_file(Path("tsconfig.json")) is False

    def test_is_ephemeral_file_git_files_not_excluded(self):
        """Test git files are NOT excluded."""
        assert is_ephemeral_file(Path(".gitignore")) is False
        assert is_ephemeral_file(Path(".gitattributes")) is False

    def test_is_ephemeral_file_nested_paths(self):
        """Test deeply nested paths are correctly identified."""
        assert is_ephemeral_file(Path("a/b/c/__pycache__/d.pyc")) is True
        assert is_ephemeral_file(Path("src/app/node_modules/pkg/index.js")) is True


class TestFilterEphemeralFiles:
    """Tests for filter_ephemeral_files() function."""

    def test_filter_ephemeral_files_empty_list(self):
        """Test filtering empty list returns empty list."""
        result = filter_ephemeral_files([])
        assert result == []

    def test_filter_ephemeral_files_all_ephemeral(self):
        """Test filtering removes all ephemeral files."""
        paths = [
            Path("__pycache__/module.pyc"),
            Path("node_modules/pkg/index.js"),
            Path("build/output.js"),
        ]
        result = filter_ephemeral_files(paths)
        assert result == []

    def test_filter_ephemeral_files_all_persistent(self):
        """Test filtering keeps all persistent files."""
        paths = [
            Path(".env"),
            Path(".env.local"),
            Path("credentials.json"),
        ]
        result = filter_ephemeral_files(paths)
        assert result == paths

    def test_filter_ephemeral_files_mixed(self):
        """Test filtering correctly separates ephemeral and persistent."""
        paths = [
            Path(".env"),
            Path("__pycache__/module.pyc"),
            Path(".env.local"),
            Path("node_modules/pkg/index.js"),
            Path("secrets.txt"),
            Path("app.log"),
        ]
        result = filter_ephemeral_files(paths)
        assert result == [
            Path(".env"),
            Path(".env.local"),
            Path("secrets.txt"),
        ]

    def test_filter_ephemeral_files_preserves_order(self):
        """Test filtering preserves original order."""
        paths = [
            Path("z.txt"),
            Path("a.log"),
            Path("m.env"),
            Path("b.pyc"),
        ]
        result = filter_ephemeral_files(paths)
        assert result == [Path("z.txt"), Path("m.env")]


class TestExclusionConstants:
    """Tests for exclusion pattern constants."""

    def test_excluded_dirs_structure(self):
        """Test EXCLUDED_DIRS has expected structure."""
        assert isinstance(EXCLUDED_DIRS, dict)
        assert "python" in EXCLUDED_DIRS
        assert "javascript" in EXCLUDED_DIRS
        assert "rust" in EXCLUDED_DIRS

    def test_excluded_file_patterns_structure(self):
        """Test EXCLUDED_FILE_PATTERNS has expected structure."""
        assert isinstance(EXCLUDED_FILE_PATTERNS, dict)
        assert "python" in EXCLUDED_FILE_PATTERNS
        assert "javascript" in EXCLUDED_FILE_PATTERNS
        assert "os" in EXCLUDED_FILE_PATTERNS

    def test_all_excluded_dirs_is_set(self):
        """Test ALL_EXCLUDED_DIRS is a set."""
        assert isinstance(ALL_EXCLUDED_DIRS, set)
        assert len(ALL_EXCLUDED_DIRS) > 0

    def test_all_excluded_file_patterns_is_set(self):
        """Test ALL_EXCLUDED_FILE_PATTERNS is a set."""
        assert isinstance(ALL_EXCLUDED_FILE_PATTERNS, set)
        assert len(ALL_EXCLUDED_FILE_PATTERNS) > 0

    def test_all_excluded_dirs_contains_common_patterns(self):
        """Test ALL_EXCLUDED_DIRS contains common patterns."""
        assert "__pycache__" in ALL_EXCLUDED_DIRS
        assert "node_modules" in ALL_EXCLUDED_DIRS
        assert "target" in ALL_EXCLUDED_DIRS

    def test_all_excluded_file_patterns_contains_common_patterns(self):
        """Test ALL_EXCLUDED_FILE_PATTERNS contains common patterns."""
        assert "*.pyc" in ALL_EXCLUDED_FILE_PATTERNS
        assert "*.log" in ALL_EXCLUDED_FILE_PATTERNS
        assert ".DS_Store" in ALL_EXCLUDED_FILE_PATTERNS


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_is_ephemeral_file_with_single_component(self):
        """Test files at root level."""
        assert is_ephemeral_file(Path("test.pyc")) is True
        assert is_ephemeral_file(Path("test.env")) is False

    def test_is_ephemeral_file_case_sensitivity(self):
        """Test pattern matching is case-sensitive."""
        # Python extension patterns are lowercase
        assert is_ephemeral_file(Path("module.pyc")) is True
        # Directory names are case-sensitive
        assert is_ephemeral_file(Path("__pycache__/file")) is True
        assert is_ephemeral_file(Path("__PYCACHE__/file")) is False

    def test_is_ephemeral_file_partial_match(self):
        """Test patterns don't match partial names."""
        # Should match __pycache__ exactly, not anything containing it
        assert is_ephemeral_file(Path("my__pycache__/file")) is False
        assert is_ephemeral_file(Path("__pycache__test/file")) is False
