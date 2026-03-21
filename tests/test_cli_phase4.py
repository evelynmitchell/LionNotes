"""CLI integration tests for Phase 4 commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from lionnotes.cli import app
from lionnotes.config import Config
from lionnotes.obsidian import ObsidianCLIError

runner = CliRunner()


SAMPLE_STRATEGY = """\
---
type: strategy
updated: "2026-01-01"
---
# Active Priorities

<!-- What should I be paying attention to right now? -->

- [python] Deep-dive into decorators #strategy
- [rust] Start learning ownership model #strategy
"""

EMPTY_STRATEGY = """\
---
type: strategy
updated: "2026-01-01"
---
# Active Priorities

<!-- What should I be paying attention to right now? -->
"""


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
        patch("lionnotes.maps._write_note"),
        patch("lionnotes.strategy._write_note"),
    ):
        yield config, obs


# -- strategy command tests --------------------------------------------------


class TestStrategyList:
    def test_shows_priorities(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = SAMPLE_STRATEGY

        result = runner.invoke(app, ["strategy", "list"])

        assert result.exit_code == 0
        assert "Active priorities (2)" in result.output
        assert "[python]" in result.output
        assert "[rust]" in result.output

    def test_empty_priorities(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = EMPTY_STRATEGY

        result = runner.invoke(app, ["strategy", "list"])

        assert result.exit_code == 0
        assert "No active priorities" in result.output

    def test_obsidian_error(self, mock_env):
        config, obs = mock_env
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")

        result = runner.invoke(app, ["strategy", "list"])

        assert result.exit_code == 1


class TestStrategyAdd:
    def test_adds_priority(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = SAMPLE_STRATEGY

        result = runner.invoke(app, ["strategy", "add", "python", "Learn metaclasses"])

        assert result.exit_code == 0
        assert "Added priority #3" in result.output
        assert "[python]" in result.output
        assert "Learn metaclasses" in result.output
        obs.append.assert_called_once()

    def test_adds_first_priority(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = EMPTY_STRATEGY

        result = runner.invoke(app, ["strategy", "add", "rust", "Read the Rust book"])

        assert result.exit_code == 0
        assert "Added priority #1" in result.output


class TestStrategyDone:
    def test_completes_priority(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = SAMPLE_STRATEGY

        result = runner.invoke(app, ["strategy", "done", "1"])

        assert result.exit_code == 0
        assert "Completed priority #1" in result.output
        assert "[python]" in result.output

    def test_invalid_number(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = SAMPLE_STRATEGY

        result = runner.invoke(app, ["strategy", "done", "5"])

        assert result.exit_code == 1
        assert "Invalid item number" in result.output

    def test_done_empty_list(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = EMPTY_STRATEGY

        result = runner.invoke(app, ["strategy", "done", "1"])

        assert result.exit_code == 1
        assert "No active priorities" in result.output

    def test_no_args_shows_help(self):
        result = runner.invoke(app, ["strategy"])
        assert result.exit_code == 2
        assert "Usage" in result.output
