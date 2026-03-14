"""Tests for the `lionnotes doctor` command."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from lionnotes.cli import app
from lionnotes.config import Config, save_config

runner = CliRunner()


@pytest.fixture()
def vault_with_config(tmp_path: Path) -> Path:
    """Create a vault directory with a valid .lionnotes.toml."""
    vault = tmp_path / "vault"
    vault.mkdir()
    config = Config(vault_path=str(vault))
    save_config(config)
    return vault


class TestDoctorNoConfig:
    def test_fails_without_config(self, tmp_path: Path):
        result = runner.invoke(app, ["doctor", "--vault-path", str(tmp_path)])
        assert result.exit_code == 1
        assert "FAIL" in result.output
        assert "init" in result.output.lower()

    def test_fails_auto_detect(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1


class TestDoctorWithConfig:
    @patch("lionnotes.cli.ObsidianCLI")
    def test_obsidian_not_found(self, mock_cls, vault_with_config: Path):
        from lionnotes.obsidian import ObsidianNotFoundError

        instance = mock_cls.return_value
        instance.version.side_effect = ObsidianNotFoundError()

        result = runner.invoke(app, ["doctor", "--vault-path", str(vault_with_config)])
        assert result.exit_code == 0
        assert "PASS" in result.output  # config passed
        assert "FAIL" in result.output  # obsidian failed
        assert "Not in PATH" in result.output

    @patch("lionnotes.cli.ObsidianCLI")
    def test_obsidian_not_running(self, mock_cls, vault_with_config: Path):
        from lionnotes.obsidian import ObsidianNotRunningError

        instance = mock_cls.return_value
        instance.version.side_effect = ObsidianNotRunningError()

        result = runner.invoke(app, ["doctor", "--vault-path", str(vault_with_config)])
        assert "FAIL" in result.output
        assert "Not running" in result.output

    @patch("lionnotes.cli.ObsidianCLI")
    def test_old_version(self, mock_cls, vault_with_config: Path):
        instance = mock_cls.return_value
        instance.version.return_value = "1.11.0"
        instance.check_version.return_value = False

        result = runner.invoke(app, ["doctor", "--vault-path", str(vault_with_config)])
        assert "FAIL" in result.output

    @patch("lionnotes.cli.ObsidianCLI")
    def test_all_passing(self, mock_cls, vault_with_config: Path):
        instance = mock_cls.return_value
        instance.version.return_value = "1.12.4"
        instance.check_version.return_value = True
        instance.read.return_value = "# content"

        result = runner.invoke(app, ["doctor", "--vault-path", str(vault_with_config)])
        assert result.exit_code == 0
        assert "FAIL" not in result.output
        assert "Done" in result.output


class TestDoctorSoftTriggers:
    @patch("lionnotes.cli.ObsidianCLI")
    def test_inbox_warning(self, mock_cls, vault_with_config: Path):
        instance = mock_cls.return_value
        instance.version.return_value = "1.12.4"
        instance.check_version.return_value = True

        def read_side_effect(name):
            if name == "_inbox/unsorted":
                return "# Unsorted\n- thought one\n- thought two\n- thought three\n"
            return "# content"

        instance.read.side_effect = read_side_effect

        result = runner.invoke(app, ["doctor", "--vault-path", str(vault_with_config)])
        assert "WARN" in result.output
        assert "3 unsorted entries" in result.output

    @patch("lionnotes.cli.ObsidianCLI")
    def test_empty_inbox_no_warning(self, mock_cls, vault_with_config: Path):
        instance = mock_cls.return_value
        instance.version.return_value = "1.12.4"
        instance.check_version.return_value = True

        def read_side_effect(name):
            if name == "_inbox/unsorted":
                return "# Unsorted\n"
            return "# content"

        instance.read.side_effect = read_side_effect

        result = runner.invoke(app, ["doctor", "--vault-path", str(vault_with_config)])
        assert "WARN" not in result.output

    def test_offline_inbox_check(self, vault_with_config: Path):
        """Doctor checks inbox via direct file read when Obsidian is unavailable."""
        inbox_dir = vault_with_config / "_inbox"
        inbox_dir.mkdir()
        (inbox_dir / "unsorted.md").write_text(
            "# Unsorted\n- thought one\n- thought two\n", encoding="utf-8"
        )

        with patch("lionnotes.cli.ObsidianCLI") as mock_cls:
            from lionnotes.obsidian import ObsidianNotFoundError

            instance = mock_cls.return_value
            instance.version.side_effect = ObsidianNotFoundError()

            result = runner.invoke(
                app, ["doctor", "--vault-path", str(vault_with_config)]
            )
            assert "WARN" in result.output
            assert "2 unsorted entries" in result.output

    def test_offline_maintenance_queue_check(self, vault_with_config: Path):
        """Doctor checks maintenance queue via direct file read when offline."""
        strategy_dir = vault_with_config / "_strategy"
        strategy_dir.mkdir()
        (strategy_dir / "maintenance-queue.md").write_text(
            "# Maintenance Queue\n- reorg python subject\n",
            encoding="utf-8",
        )

        with patch("lionnotes.cli.ObsidianCLI") as mock_cls:
            from lionnotes.obsidian import ObsidianNotFoundError

            instance = mock_cls.return_value
            instance.version.side_effect = ObsidianNotFoundError()

            result = runner.invoke(
                app, ["doctor", "--vault-path", str(vault_with_config)]
            )
            assert "WARN" in result.output
            assert "1 pending items" in result.output
