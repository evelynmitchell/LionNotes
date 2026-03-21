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
        patch("lionnotes.index._write_note"),
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


# -- cache command tests ----------------------------------------------------

SEARCH_RESULTS_WITH_SUBJECTS = """\
python/SMOC.md
python/speeds.md
rust/SMOC.md
old-stuff/SMOC.md
old-stuff/speeds.md
"""


class TestCacheStatus:
    def test_shows_tiers(self, mock_env):
        config, obs = mock_env
        # list_subjects uses search
        obs.search.return_value = "python/SMOC.md\nrust/SMOC.md\nold-stuff/SMOC.md\n"

        def prop_get(file, name):
            if file == "python/SMOC" and name == "tier":
                return "carry-about"
            if file == "rust/SMOC" and name == "tier":
                return "common-store"
            if file == "old-stuff/SMOC" and name == "tier":
                return "archive"
            raise ObsidianCLIError(["property:get"], 1, "not found")

        obs.property_get.side_effect = prop_get

        result = runner.invoke(app, ["cache", "status"])

        assert result.exit_code == 0
        assert "carry-about (1)" in result.output
        assert "common-store (1)" in result.output
        assert "archive (1)" in result.output
        assert "python" in result.output
        assert "rust" in result.output
        assert "old-stuff" in result.output

    def test_empty_vault(self, mock_env):
        config, obs = mock_env
        obs.search.side_effect = ObsidianCLIError(["search"], 1, "no results")

        result = runner.invoke(app, ["cache", "status"])

        assert result.exit_code == 0
        assert "(none)" in result.output


class TestCacheArchive:
    def test_archives_subject(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = "smoc content"

        result = runner.invoke(app, ["cache", "archive", "python"])

        assert result.exit_code == 0
        assert "Archived: python" in result.output
        obs.property_set.assert_called_once_with("python/SMOC", "tier", "archive")

    def test_subject_not_found(self, mock_env):
        config, obs = mock_env
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")

        result = runner.invoke(app, ["cache", "archive", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestCachePromote:
    def test_promotes_subject(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = "smoc content"

        result = runner.invoke(app, ["cache", "promote", "python"])

        assert result.exit_code == 0
        assert "Promoted: python" in result.output
        obs.property_set.assert_called_once_with("python/SMOC", "tier", "carry-about")


class TestCacheSet:
    def test_sets_tier(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = "smoc content"

        result = runner.invoke(app, ["cache", "set", "python", "common-store"])

        assert result.exit_code == 0
        assert "Set python to common-store" in result.output

    def test_invalid_tier(self, mock_env):
        config, obs = mock_env

        result = runner.invoke(app, ["cache", "set", "python", "invalid"])

        assert result.exit_code == 1
        assert "Invalid tier" in result.output


class TestCacheNoArgs:
    def test_no_args_shows_help(self):
        result = runner.invoke(app, ["cache"])
        assert result.exit_code == 2
        assert "Usage" in result.output


# -- subjects list with tier filtering --------------------------------------


class TestSubjectsListTierFiltering:
    def test_hides_archived_by_default(self, mock_env):
        config, obs = mock_env
        obs.search.return_value = "python/SMOC.md\nold-stuff/SMOC.md\n"

        def prop_get(file, name):
            if file == "python/SMOC" and name == "tier":
                return "carry-about"
            if file == "old-stuff/SMOC" and name == "tier":
                return "archive"
            raise ObsidianCLIError(["property:get"], 1, "not found")

        obs.property_get.side_effect = prop_get

        result = runner.invoke(app, ["subjects", "list"])

        assert result.exit_code == 0
        assert "python" in result.output
        assert "old-stuff" not in result.output

    def test_shows_all_with_flag(self, mock_env):
        config, obs = mock_env
        obs.search.return_value = "python/SMOC.md\nold-stuff/SMOC.md\n"

        def prop_get(file, name):
            if file == "python/SMOC" and name == "tier":
                return "carry-about"
            if file == "old-stuff/SMOC" and name == "tier":
                return "archive"
            raise ObsidianCLIError(["property:get"], 1, "not found")

        obs.property_get.side_effect = prop_get

        result = runner.invoke(app, ["subjects", "list", "--all"])

        assert result.exit_code == 0
        assert "python" in result.output
        assert "old-stuff" in result.output
        assert "[archived]" in result.output

    def test_common_store_marker(self, mock_env):
        config, obs = mock_env
        obs.search.return_value = "rust/SMOC.md\n"

        obs.property_get.return_value = "common-store"

        result = runner.invoke(app, ["subjects", "list"])

        assert result.exit_code == 0
        assert "rust" in result.output
        assert "[common]" in result.output


# -- search with tier filtering --------------------------------------------


class TestSearchTierFiltering:
    def test_excludes_archived_by_default(self, mock_env):
        config, obs = mock_env
        obs.search.return_value = "python/speeds.md\nold-stuff/speeds.md\n"

        # list_tiers calls list_subjects then get_tier for each
        # We need search called twice: once for the search query,
        # once for list_subjects inside list_tiers.
        # The mock returns the same for all search calls.
        # We need to distinguish search calls.
        search_calls = [0]

        def search_side_effect(query, limit=20):
            search_calls[0] += 1
            if "type: smoc" in query:
                return "python/SMOC.md\nold-stuff/SMOC.md\n"
            return "python/speeds.md\nold-stuff/speeds.md\n"

        obs.search.side_effect = search_side_effect

        def prop_get(file, name):
            if file == "old-stuff/SMOC" and name == "tier":
                return "archive"
            raise ObsidianCLIError(["property:get"], 1, "not found")

        obs.property_get.side_effect = prop_get

        result = runner.invoke(app, ["search", "speeds"])

        assert result.exit_code == 0
        assert "python" in result.output
        assert "old-stuff" not in result.output

    def test_includes_archived_with_flag(self, mock_env):
        config, obs = mock_env

        def search_side_effect(query, limit=20):
            if "type: smoc" in query:
                return "python/SMOC.md\nold-stuff/SMOC.md\n"
            return "python/speeds.md\nold-stuff/speeds.md\n"

        obs.search.side_effect = search_side_effect

        def prop_get(file, name):
            if file == "old-stuff/SMOC" and name == "tier":
                return "archive"
            raise ObsidianCLIError(["property:get"], 1, "not found")

        obs.property_get.side_effect = prop_get

        result = runner.invoke(app, ["search", "--include-archived", "speeds"])

        assert result.exit_code == 0
        assert "python" in result.output
        assert "old-stuff" in result.output


# -- index command tests ----------------------------------------------------

SAMPLE_SMOC_FOR_INDEX = """\
---
type: smoc
subject: "python"
version: 1
created: "2026-01-01"
updated: "2026-01-01"
---
# python — Subject Map of Contents

## Purpose & Principles
- [[purpose]]

## Map

### Core
- [[POI-01-decorators]]

### Peripheral

### References

## Speed Thoughts
- Current speed page: [[speeds]]

## See Also
"""

SAMPLE_POI_FOR_INDEX = """\
---
type: poi
subject: "python"
---
# POI 1: Decorators

## Content
Decorators use #metaprogramming. See [[REF-01-pep-318]].
"""

SAMPLE_SPEEDS_FOR_INDEX = """\
---
type: speeds
subject: "python"
---
# python — Speed Thoughts

- S1: decorators are cool #thought/observation
"""


class TestIndexCommand:
    def test_builds_index(self, mock_env):
        config, obs = mock_env

        def read_side_effect(path):
            if path == "python/SMOC":
                return SAMPLE_SMOC_FOR_INDEX
            if path == "python/POI-01-decorators":
                return SAMPLE_POI_FOR_INDEX
            if path == "python/speeds":
                return SAMPLE_SPEEDS_FOR_INDEX
            if path == "python/Index":
                raise ObsidianCLIError(["read"], 1, "not found")
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side_effect

        result = runner.invoke(app, ["index", "python"])

        assert result.exit_code == 0
        assert "Built index for python" in result.output
        assert "python/Index" in result.output

    def test_smoc_not_found(self, mock_env):
        config, obs = mock_env
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")

        result = runner.invoke(app, ["index", "nonexistent"])

        assert result.exit_code == 1
        assert "Cannot read SMOC" in result.output

    def test_invalid_subject_name(self, mock_env):
        config, obs = mock_env

        result = runner.invoke(app, ["index", "!!!"])

        assert result.exit_code == 1
