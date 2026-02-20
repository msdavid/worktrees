"""Tests for configuration module."""

import json
from pathlib import Path
from unittest.mock import patch


from worktrees.config import (
    DEFAULT_SETUP_COMMANDS,
    WORKTREES_JSON,
    WorktreeConfig,
    WorktreesConfig,
    find_project_root,
)


class TestWorktreesConfig:
    """Tests for WorktreesConfig class."""

    def test_load_nonexistent_config(self, tmp_path):
        """Test loading config when file doesn't exist."""
        config = WorktreesConfig.load(tmp_path)
        assert config is None

    def test_load_and_save_roundtrip(self, tmp_path):
        """Test saving and loading config preserves data."""
        original = WorktreesConfig(
            version="1.0",
            worktrees_dir=tmp_path,
            setup_auto_detect=False,
            setup_commands=["npm install"],
            project_root=tmp_path,
        )
        original.save(tmp_path)

        loaded = WorktreesConfig.load(tmp_path)
        assert loaded is not None
        assert loaded.version == "1.0"
        assert loaded.worktrees_dir == tmp_path
        assert loaded.setup_auto_detect is False
        assert loaded.setup_commands == ["npm install"]

    def test_load_with_dot_worktrees_dir(self, tmp_path):
        """Test loading config with worktreesDir set to '.'."""
        config_file = tmp_path / WORKTREES_JSON
        config_file.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "worktreesDir": ".",
                    "setup": {"autoDetect": True, "commands": []},
                }
            )
        )

        loaded = WorktreesConfig.load(tmp_path)
        assert loaded is not None
        assert loaded.worktrees_dir == tmp_path

    def test_load_with_custom_worktrees_dir(self, tmp_path):
        """Test loading config with custom worktreesDir."""
        custom_dir = Path.home() / ".worktrees" / "test"
        config_file = tmp_path / WORKTREES_JSON
        config_file.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "worktreesDir": str(custom_dir),
                    "setup": {"autoDetect": True, "commands": []},
                }
            )
        )

        loaded = WorktreesConfig.load(tmp_path)
        assert loaded is not None
        assert loaded.worktrees_dir == custom_dir

    def test_load_with_expanduser(self, tmp_path):
        """Test loading config expands ~ in worktreesDir."""
        config_file = tmp_path / WORKTREES_JSON
        config_file.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "worktreesDir": "~/.worktrees/test",
                    "setup": {"autoDetect": True, "commands": []},
                }
            )
        )

        loaded = WorktreesConfig.load(tmp_path)
        assert loaded is not None
        assert "~" not in str(loaded.worktrees_dir)

    def test_save_with_dot_worktrees_dir(self, tmp_path):
        """Test saving config writes '.' when worktrees_dir equals project_root."""
        config = WorktreesConfig(
            worktrees_dir=tmp_path,
            project_root=tmp_path,
        )
        config.save(tmp_path)

        config_file = tmp_path / WORKTREES_JSON
        data = json.loads(config_file.read_text())
        assert data["worktreesDir"] == "."

    def test_save_with_custom_worktrees_dir(self, tmp_path):
        """Test saving config writes full path when worktrees_dir differs."""
        custom_dir = Path("/custom/worktrees")
        config = WorktreesConfig(
            worktrees_dir=custom_dir,
            project_root=tmp_path,
        )
        config.save(tmp_path)

        config_file = tmp_path / WORKTREES_JSON
        data = json.loads(config_file.read_text())
        assert data["worktreesDir"] == str(custom_dir)

    def test_get_worktree_path(self, tmp_path):
        """Test get_worktree_path returns correct path."""
        config = WorktreesConfig(
            worktrees_dir=tmp_path / "worktrees",
            project_root=tmp_path,
        )

        path = config.get_worktree_path("feature")
        assert path == tmp_path / "worktrees" / "feature"

    def test_get_setup_commands_custom(self, tmp_path):
        """Test get_setup_commands returns custom commands."""
        config = WorktreesConfig(
            worktrees_dir=tmp_path,
            setup_commands=["npm install", "npm build"],
            project_root=tmp_path,
        )

        worktree_path = tmp_path / "feature"
        worktree_path.mkdir()

        commands = config.get_setup_commands(worktree_path)
        assert commands == ["npm install", "npm build"]

    def test_get_setup_commands_auto_detect_disabled(self, tmp_path):
        """Test get_setup_commands returns empty when auto-detect disabled."""
        config = WorktreesConfig(
            worktrees_dir=tmp_path,
            setup_auto_detect=False,
            project_root=tmp_path,
        )

        worktree_path = tmp_path / "feature"
        worktree_path.mkdir()
        (worktree_path / "package.json").write_text("{}")

        commands = config.get_setup_commands(worktree_path)
        assert commands == []

    def test_get_setup_commands_auto_detect_node(self, tmp_path):
        """Test get_setup_commands auto-detects Node.js project."""
        config = WorktreesConfig(
            worktrees_dir=tmp_path,
            setup_auto_detect=True,
            project_root=tmp_path,
        )

        worktree_path = tmp_path / "feature"
        worktree_path.mkdir()
        (worktree_path / "package.json").write_text("{}")

        commands = config.get_setup_commands(worktree_path)
        assert "npm install" in commands

    def test_get_setup_commands_auto_detect_python(self, tmp_path):
        """Test get_setup_commands auto-detects Python project."""
        config = WorktreesConfig(
            worktrees_dir=tmp_path,
            setup_auto_detect=True,
            project_root=tmp_path,
        )

        worktree_path = tmp_path / "feature"
        worktree_path.mkdir()
        (worktree_path / "pyproject.toml").write_text("")

        commands = config.get_setup_commands(worktree_path)
        assert "uv sync" in commands

    def test_get_setup_commands_auto_detect_multiple(self, tmp_path):
        """Test get_setup_commands detects multiple project types."""
        config = WorktreesConfig(
            worktrees_dir=tmp_path,
            setup_auto_detect=True,
            project_root=tmp_path,
        )

        worktree_path = tmp_path / "feature"
        worktree_path.mkdir()
        (worktree_path / "Cargo.toml").write_text("")
        (worktree_path / "go.mod").write_text("")

        commands = config.get_setup_commands(worktree_path)
        assert "cargo build" in commands
        assert "go mod download" in commands


class TestFindProjectRoot:
    """Tests for find_project_root() function."""

    def test_find_project_root_current_dir(self, tmp_path):
        """Test finding project root in current directory."""
        config_file = tmp_path / WORKTREES_JSON
        config_file.write_text("{}")

        with patch("worktrees.config.Path.cwd", return_value=tmp_path):
            root = find_project_root()
            assert root == tmp_path

    def test_find_project_root_parent_dir(self, tmp_path):
        """Test finding project root in parent directory."""
        config_file = tmp_path / WORKTREES_JSON
        config_file.write_text("{}")

        subdir = tmp_path / "subdir" / "nested"
        subdir.mkdir(parents=True)

        with patch("worktrees.config.Path.cwd", return_value=subdir):
            root = find_project_root()
            assert root == tmp_path

    def test_find_project_root_not_found(self, tmp_path):
        """Test finding project root returns None when not found."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        with patch("worktrees.config.Path.cwd", return_value=subdir):
            root = find_project_root()
            assert root is None


class TestWorktreeConfig:
    """Tests for legacy WorktreeConfig class."""

    def test_get_setup_commands_custom(self, tmp_path):
        """Test get_setup_commands returns custom commands."""
        config = WorktreeConfig(
            setup_commands=["make install"],
            auto_detect_setup=False,
        )

        commands = config.get_setup_commands(tmp_path)
        assert commands == ["make install"]

    def test_get_setup_commands_auto_detect_disabled(self, tmp_path):
        """Test get_setup_commands with auto-detect disabled."""
        config = WorktreeConfig(
            setup_commands=[],
            auto_detect_setup=False,
        )

        (tmp_path / "package.json").write_text("{}")
        commands = config.get_setup_commands(tmp_path)
        assert commands == []

    def test_get_setup_commands_auto_detect_enabled(self, tmp_path):
        """Test get_setup_commands with auto-detect enabled."""
        config = WorktreeConfig(
            setup_commands=[],
            auto_detect_setup=True,
        )

        (tmp_path / "Cargo.toml").write_text("")
        commands = config.get_setup_commands(tmp_path)
        assert "cargo build" in commands


class TestDefaultSetupCommands:
    """Tests for DEFAULT_SETUP_COMMANDS constant."""

    def test_default_setup_commands_structure(self):
        """Test DEFAULT_SETUP_COMMANDS has expected structure."""
        assert isinstance(DEFAULT_SETUP_COMMANDS, dict)
        assert "pyproject.toml" in DEFAULT_SETUP_COMMANDS
        assert "package.json" in DEFAULT_SETUP_COMMANDS
        assert "Cargo.toml" in DEFAULT_SETUP_COMMANDS
        assert "go.mod" in DEFAULT_SETUP_COMMANDS

    def test_default_setup_commands_values(self):
        """Test DEFAULT_SETUP_COMMANDS has list values."""
        for key, value in DEFAULT_SETUP_COMMANDS.items():
            assert isinstance(value, list)
            assert len(value) > 0


class TestMarks:
    """Tests for mark functionality in WorktreesConfig."""

    def test_load_config_without_marks(self, tmp_path):
        """Test loading config that doesn't have marks field (backward compat)."""
        config_file = tmp_path / WORKTREES_JSON
        config_file.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "worktreesDir": ".",
                    "setup": {"autoDetect": True, "commands": []},
                }
            )
        )

        loaded = WorktreesConfig.load(tmp_path)
        assert loaded is not None
        assert loaded.marks == {}

    def test_load_and_save_roundtrip_with_marks(self, tmp_path):
        """Test roundtrip with marks."""
        original = WorktreesConfig(
            worktrees_dir=tmp_path,
            project_root=tmp_path,
            marks={"feature": "done"},
        )
        original.save(tmp_path)

        loaded = WorktreesConfig.load(tmp_path)
        assert loaded is not None
        assert loaded.marks == {"feature": "done"}

    def test_get_mark_none(self, tmp_path):
        """Test get_mark returns None for unmarked worktree."""
        config = WorktreesConfig(project_root=tmp_path)
        assert config.get_mark("nonexistent") is None

    def test_get_mark_existing(self, tmp_path):
        """Test get_mark returns mark text."""
        config = WorktreesConfig(
            project_root=tmp_path,
            marks={"feature": "done"},
        )
        assert config.get_mark("feature") == "done"

    def test_set_mark_new_worktree(self, tmp_path):
        """Test setting mark on worktree without existing mark."""
        config = WorktreesConfig(project_root=tmp_path)
        config.set_mark("feature", "done")
        assert config.marks == {"feature": "done"}

    def test_set_mark_replaces_existing(self, tmp_path):
        """Test setting mark replaces existing mark."""
        config = WorktreesConfig(
            project_root=tmp_path,
            marks={"feature": "done"},
        )
        config.set_mark("feature", "ready for review")
        assert config.marks == {"feature": "ready for review"}

    def test_clear_mark_existing(self, tmp_path):
        """Test clearing mark from worktree."""
        config = WorktreesConfig(
            project_root=tmp_path,
            marks={"feature": "done"},
        )
        result = config.clear_mark("feature")
        assert result is True
        assert "feature" not in config.marks

    def test_clear_mark_nonexistent(self, tmp_path):
        """Test clearing mark from worktree without mark."""
        config = WorktreesConfig(project_root=tmp_path)
        result = config.clear_mark("nonexistent")
        assert result is False

    def test_get_mark_legacy_list_format_nonempty(self, tmp_path):
        """Test get_mark handles legacy list format (non-empty)."""
        config = WorktreesConfig(
            project_root=tmp_path,
            marks={"feature": ["tag1", "tag2"]},
        )
        mark = config.get_mark("feature")
        assert mark == "tag1, tag2"

    def test_get_mark_legacy_list_format_empty(self, tmp_path):
        """Test get_mark handles legacy list format (empty)."""
        config = WorktreesConfig(
            project_root=tmp_path,
            marks={"feature": []},
        )
        mark = config.get_mark("feature")
        assert mark is None
