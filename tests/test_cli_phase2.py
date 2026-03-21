"""CLI integration tests for Phase 2 commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from lionnotes.cli import app
from lionnotes.config import Config
from lionnotes.obsidian import ObsidianCLIError

runner = CliRunner()


@pytest.fixture
def mock_env(tmp_path):
    """Set up mocked config and obsidian for CLI tests."""
    config = Config(vault_path=str(tmp_path))
    config_path = tmp_path / ".lionnotes.toml"
    config_path.write_text(f'vault_path = "{tmp_path}"\n')

    obs = MagicMock()

    with (
        patch("lionnotes.cli.find_config", return_value=config_path),
        patch("lionnotes.cli.load_config", return_value=config),
        patch("lionnotes.cli.ObsidianCLI", return_value=obs),
        patch("lionnotes.capture.save_config"),
        patch("lionnotes.subjects.save_config"),
    ):
        yield config, obs


class TestCaptureCommand:
    def test_capture_to_inbox(self, mock_env):
        config, obs = mock_env
        result = runner.invoke(app, ["capture", "A quick thought"])
        assert result.exit_code == 0
        assert "Captured to inbox" in result.output

    def test_capture_to_subject(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = "# speeds"
        result = runner.invoke(app, ["capture", "A thought", "-s", "my-topic"])
        assert result.exit_code == 0
        assert "Captured to my-topic" in result.output

    def test_capture_shows_normalized_subject(self, mock_env):
        """Output should show the normalized name, not raw input."""
        config, obs = mock_env
        obs.read.return_value = "# speeds"
        result = runner.invoke(
            app,
            ["capture", "A thought", "-s", "My Topic"],
        )
        assert result.exit_code == 0
        assert "Captured to my-topic" in result.output

    def test_capture_with_hint_and_type(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = "# speeds"
        result = runner.invoke(
            app,
            [
                "capture",
                "A thought",
                "-s",
                "my-topic",
                "-h",
                "work",
                "-t",
                "observation",
            ],
        )
        assert result.exit_code == 0
        assert "context: work" in result.output
        assert "#thought/observation" in result.output

    def test_capture_no_content_no_stdin(self, mock_env):
        result = runner.invoke(app, ["capture"])
        assert result.exit_code == 1

    def test_capture_missing_subject_error(self, mock_env):
        config, obs = mock_env
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")
        result = runner.invoke(app, ["capture", "A thought", "-s", "nonexistent"])
        assert result.exit_code == 1
        assert "does not exist" in result.output


class TestSubjectsCommands:
    def test_subjects_list_empty(self, mock_env):
        config, obs = mock_env
        obs.search.side_effect = ObsidianCLIError(["search"], 1, "no results")
        result = runner.invoke(app, ["subjects", "list"])
        assert result.exit_code == 0
        assert "No subjects found" in result.output

    def test_subjects_list_with_results(self, mock_env):
        config, obs = mock_env
        obs.search.return_value = "alpha/SMOC.md\nbeta/SMOC.md\n"
        result = runner.invoke(app, ["subjects", "list"])
        assert result.exit_code == 0
        assert "alpha" in result.output
        assert "beta" in result.output

    def test_subjects_create(self, mock_env):
        config, obs = mock_env
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")
        result = runner.invoke(app, ["subjects", "create", "My Topic"])
        assert result.exit_code == 0
        assert "Created subject: my-topic" in result.output

    def test_subjects_create_invalid_name(self, mock_env):
        config, obs = mock_env
        result = runner.invoke(app, ["subjects", "create", "_inbox"])
        assert result.exit_code == 1
        assert "reserved" in result.output

    def test_subjects_create_already_exists(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = "# Existing SMOC"
        result = runner.invoke(app, ["subjects", "create", "existing"])
        assert result.exit_code == 1
        assert "already exists" in result.output


class TestSearchCommand:
    def test_search_basic(self, mock_env):
        config, obs = mock_env
        obs.search.return_value = "my-topic/speeds.md: S1: A thought\n"
        result = runner.invoke(app, ["search", "thought"])
        assert result.exit_code == 0
        assert "thought" in result.output

    def test_search_no_results(self, mock_env):
        config, obs = mock_env
        obs.search.return_value = ""
        result = runner.invoke(app, ["search", "nonexistent"])
        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_search_with_subject_filter(self, mock_env):
        config, obs = mock_env
        obs.search.return_value = (
            "alpha/speeds.md: S1: A thought\nbeta/speeds.md: S2: Another thought\n"
        )
        result = runner.invoke(
            app,
            ["search", "thought", "-s", "alpha"],
        )
        assert result.exit_code == 0
        assert "alpha" in result.output
        assert "beta" not in result.output

    def test_search_subject_filter_uses_segments(self, mock_env):
        """Ensure filtering matches path segments, not substrings."""
        config, obs = mock_env
        obs.search.return_value = "alphabeta/speeds.md: S1: A thought\n"
        result = runner.invoke(
            app,
            ["search", "thought", "-s", "alpha"],
        )
        assert result.exit_code == 0
        assert "No results found in subject" in result.output

    def test_search_context_uses_search_context(self, mock_env):
        """--context flag should call search_context, not search."""
        config, obs = mock_env
        obs.search_context.return_value = "my-topic/speeds.md: S1: A thought\n"
        result = runner.invoke(
            app,
            ["search", "thought", "--context"],
        )
        assert result.exit_code == 0
        obs.search_context.assert_called_once()
        obs.search.assert_not_called()

    def test_search_error(self, mock_env):
        config, obs = mock_env
        obs.search.side_effect = ObsidianCLIError(["search"], 1, "error")
        result = runner.invoke(app, ["search", "query"])
        assert result.exit_code == 1
