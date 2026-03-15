"""Smoke tests for the LionNotes CLI."""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

import lionnotes
from lionnotes.cli import app
from lionnotes.config import Config, save_config
from lionnotes.obsidian import ObsidianCLIError

runner = CliRunner()


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"lionnotes {lionnotes.__version__}" in result.output


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "Thought mapping" in result.output
    assert "Usage" in result.output


def test_help_shows_commands():
    result = runner.invoke(app, ["--help"])
    assert "capture" in result.output
    assert "subjects" in result.output
    assert "search" in result.output
    assert "init" in result.output
    assert "doctor" in result.output


class TestCaptureCLI:
    @patch("lionnotes.cli.ObsidianCLI")
    def test_capture_to_inbox(self, mock_cls, tmp_path: Path):
        vault = tmp_path / "vault"
        vault.mkdir()
        config = Config(vault_path=str(vault))
        save_config(config)

        instance = mock_cls.return_value

        result = runner.invoke(
            app,
            ["capture", "a thought", "--vault-path", str(vault)],
        )
        assert result.exit_code == 0
        assert "Captured to inbox" in result.output
        instance.append.assert_called_once()

    @patch("lionnotes.cli.ObsidianCLI")
    def test_capture_to_subject(self, mock_cls, tmp_path: Path):
        vault = tmp_path / "vault"
        vault.mkdir()
        config = Config(vault_path=str(vault), speed_counters={"python": 0})
        save_config(config)

        instance = mock_cls.return_value
        instance.read.return_value = "# SMOC"

        result = runner.invoke(
            app,
            [
                "capture",
                "generators are lazy",
                "-s",
                "python",
                "--vault-path",
                str(vault),
            ],
        )
        assert result.exit_code == 0
        assert "Captured to python" in result.output

    @patch("lionnotes.cli.ObsidianCLI")
    def test_capture_no_content_tty(self, mock_cls, tmp_path: Path):
        vault = tmp_path / "vault"
        vault.mkdir()
        save_config(Config(vault_path=str(vault)))

        result = runner.invoke(
            app,
            ["capture", "--vault-path", str(vault)],
        )
        # No content and isatty() in test runner context
        # Should either error or read empty stdin
        assert result.exit_code in (0, 1)


class TestSubjectsCLI:
    @patch("lionnotes.cli.ObsidianCLI")
    def test_subjects_create(self, mock_cls, tmp_path: Path):
        vault = tmp_path / "vault"
        vault.mkdir()
        save_config(Config(vault_path=str(vault)))

        instance = mock_cls.return_value
        instance.read.side_effect = ObsidianCLIError(["read"], 1, "not found")

        result = runner.invoke(
            app,
            [
                "subjects",
                "create",
                "Python",
                "--vault-path",
                str(vault),
            ],
        )
        assert result.exit_code == 0
        assert "Created subject 'python'" in result.output
        assert instance.create.call_count == 5

    @patch("lionnotes.cli.ObsidianCLI")
    def test_subjects_list(self, mock_cls, tmp_path: Path):
        vault = tmp_path / "vault"
        vault.mkdir()
        save_config(Config(vault_path=str(vault)))

        instance = mock_cls.return_value
        instance.search.return_value = "python/SMOC.md\n"
        instance.read.return_value = "content"

        result = runner.invoke(
            app,
            ["subjects", "list", "--vault-path", str(vault)],
        )
        assert result.exit_code == 0
        assert "python" in result.output

    @patch("lionnotes.cli.ObsidianCLI")
    def test_subjects_list_empty(self, mock_cls, tmp_path: Path):
        vault = tmp_path / "vault"
        vault.mkdir()
        save_config(Config(vault_path=str(vault)))

        instance = mock_cls.return_value
        instance.search.side_effect = ObsidianCLIError(["search"], 1, "error")

        result = runner.invoke(
            app,
            ["subjects", "list", "--vault-path", str(vault)],
        )
        assert result.exit_code == 0
        assert "No subjects found" in result.output


class TestSearchCLI:
    @patch("lionnotes.cli.ObsidianCLI")
    def test_search_basic(self, mock_cls, tmp_path: Path):
        vault = tmp_path / "vault"
        vault.mkdir()
        save_config(Config(vault_path=str(vault)))

        instance = mock_cls.return_value
        instance.search.return_value = "python/speeds.md\n"

        result = runner.invoke(
            app,
            ["search", "generators", "--vault-path", str(vault)],
        )
        assert result.exit_code == 0
        assert "python/speeds.md" in result.output

    @patch("lionnotes.cli.ObsidianCLI")
    def test_search_no_results(self, mock_cls, tmp_path: Path):
        vault = tmp_path / "vault"
        vault.mkdir()
        save_config(Config(vault_path=str(vault)))

        instance = mock_cls.return_value
        instance.search.return_value = ""

        result = runner.invoke(
            app,
            ["search", "nonexistent", "--vault-path", str(vault)],
        )
        assert result.exit_code == 0
        assert "No results found" in result.output

    @patch("lionnotes.cli.ObsidianCLI")
    def test_search_scoped_to_subject(self, mock_cls, tmp_path: Path):
        vault = tmp_path / "vault"
        vault.mkdir()
        save_config(Config(vault_path=str(vault)))

        instance = mock_cls.return_value
        instance.search.return_value = "python/speeds.md\n"

        result = runner.invoke(
            app,
            [
                "search",
                "generators",
                "-s",
                "python",
                "--vault-path",
                str(vault),
            ],
        )
        assert result.exit_code == 0
        # Verify the search query includes path scope
        search_call = instance.search.call_args
        assert "path:python" in search_call[0][0]
