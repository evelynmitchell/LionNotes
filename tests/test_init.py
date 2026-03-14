"""Tests for the `lionnotes init` command."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from lionnotes.cli import app
from lionnotes.config import CONFIG_FILENAME
from lionnotes.obsidian import ObsidianCLIError, ObsidianNotRunningError

runner = CliRunner()


@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    d = tmp_path / "my-vault"
    d.mkdir()
    return d


class TestInitOffline:
    """Test init when Obsidian is not running (direct file writes)."""

    @patch("lionnotes.cli.ObsidianCLI")
    def test_creates_vault_structure(self, mock_cls, vault_dir: Path):
        # Make Obsidian unavailable
        instance = mock_cls.return_value
        instance.version.side_effect = ObsidianNotRunningError()

        result = runner.invoke(app, ["init", "--vault-path", str(vault_dir)])
        assert result.exit_code == 0
        assert "Initialized" in result.output or "Created" in result.output

        # Check files were created
        assert (vault_dir / "GSMOC.md").is_file()
        assert (vault_dir / "_inbox" / "unsorted.md").is_file()
        assert (vault_dir / "_strategy" / "active-priorities.md").is_file()
        assert (vault_dir / "_strategy" / "maintenance-queue.md").is_file()
        assert (vault_dir / "Subject Registry.md").is_file()
        assert (vault_dir / "Global Aliases.md").is_file()
        assert (vault_dir / CONFIG_FILENAME).is_file()

    @patch("lionnotes.cli.ObsidianCLI")
    def test_gsmoc_has_correct_content(self, mock_cls, vault_dir: Path):
        instance = mock_cls.return_value
        instance.version.side_effect = ObsidianNotRunningError()

        runner.invoke(app, ["init", "--vault-path", str(vault_dir)])

        gsmoc = (vault_dir / "GSMOC.md").read_text(encoding="utf-8")
        assert "Grand Subject Map of Contents" in gsmoc
        assert "Lion Kimbro" in gsmoc

    @patch("lionnotes.cli.ObsidianCLI")
    def test_idempotent(self, mock_cls, vault_dir: Path):
        instance = mock_cls.return_value
        instance.version.side_effect = ObsidianNotRunningError()

        # Run init twice
        runner.invoke(app, ["init", "--vault-path", str(vault_dir)])
        result = runner.invoke(app, ["init", "--vault-path", str(vault_dir)])

        assert result.exit_code == 0
        assert "skipped" in result.output.lower() or "Already exists" in result.output

    @patch("lionnotes.cli.ObsidianCLI")
    def test_config_written(self, mock_cls, vault_dir: Path):
        instance = mock_cls.return_value
        instance.version.side_effect = ObsidianNotRunningError()

        runner.invoke(app, ["init", "--vault-path", str(vault_dir)])

        config_path = vault_dir / CONFIG_FILENAME
        content = config_path.read_text(encoding="utf-8")
        assert str(vault_dir) in content

    @patch("lionnotes.cli.ObsidianCLI")
    def test_nonexistent_path_fails(self, mock_cls, tmp_path: Path):
        result = runner.invoke(
            app, ["init", "--vault-path", str(tmp_path / "nope")]
        )
        assert result.exit_code == 1
        assert "not a directory" in result.output.lower() or "Error" in result.output


class TestInitWithObsidian:
    """Test init when Obsidian is available."""

    @patch("lionnotes.cli.ObsidianCLI")
    def test_uses_obsidian_create(self, mock_cls, vault_dir: Path):
        instance = mock_cls.return_value
        instance.version.return_value = "1.12.4"
        # read raises for all files (none exist)
        instance.read.side_effect = ObsidianCLIError(["read"], 1, "not found")

        result = runner.invoke(app, ["init", "--vault-path", str(vault_dir)])
        assert result.exit_code == 0

        # Should have called create for each init file
        assert instance.create.call_count == 6

    @patch("lionnotes.cli.ObsidianCLI")
    def test_skips_existing_obsidian_files(self, mock_cls, vault_dir: Path):
        instance = mock_cls.return_value
        instance.version.return_value = "1.12.4"
        # GSMOC exists, others don't
        def read_side_effect(name):
            if name == "GSMOC":
                return "# existing"
            from lionnotes.obsidian import ObsidianCLIError
            raise ObsidianCLIError(["read"], 1, "not found")
        instance.read.side_effect = read_side_effect

        result = runner.invoke(app, ["init", "--vault-path", str(vault_dir)])
        assert result.exit_code == 0
        # Should have created 5 files (6 total - 1 existing)
        assert instance.create.call_count == 5
