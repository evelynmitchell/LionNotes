"""CLI integration tests for Phase 3 commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from lionnotes.cli import app
from lionnotes.config import Config
from lionnotes.obsidian import ObsidianCLIError

runner = CliRunner()


SAMPLE_SMOC = """\
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
<!-- The most important POIs -->

### Peripheral
<!-- Related but less central -->

### References
<!-- External sources annotated -->

## Speed Thoughts
- Current speed page: [[speeds]]

## See Also
<!-- Cross-subject links -->
"""

SAMPLE_GSMOC = """\
---
type: gsmoc
version: 1
created: "2026-01-01"
updated: "2026-01-01"
---
# Grand Subject Map of Contents

> "The GSMOC is a mirror of the mind." — Lion Kimbro

## Active Subjects
<!-- Subjects currently being developed. -->
- [[python/SMOC|python]]

## Dormant Subjects
<!-- Subjects with content but not currently active. -->

## Emerging
<!-- Speed thoughts accumulating that may become subjects. -->

## Cross-Subject Connections
<!-- Links between subjects that don't belong to either. -->
"""

SAMPLE_SPEEDS = """\
---
type: speeds
subject: "python"
---
# python — Speed Thoughts

- S1: (context: reading) Decorators are closures #thought/observation
- S2: Generators for lazy eval #thought/observation
- S3: Asyncio patterns #thought/question [→ POI-1]
- S4: Type hints improve code #thought/principle
"""

SAMPLE_PP = """\
---
type: pp
subject: "python"
version: 1
---
# python — Purpose & Principles

## Purpose
Learn and document Python patterns.
"""

SAMPLE_INBOX = """\
---
type: inbox
created: "2026-01-01"
---
# Unsorted Speed Thoughts

- S1: Random idea about structure #thought/observation
- S2: Should learn Rust #thought/goal
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
    ):
        yield config, obs


# -- poi command tests -------------------------------------------------------


class TestPoiCommand:
    def test_creates_poi(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = SAMPLE_SMOC

        result = runner.invoke(app, ["poi", "python", "Decorator Patterns"])

        assert result.exit_code == 0
        assert "Created python/POI-01-decorator-patterns" in result.output
        obs.create.assert_called_once()

    def test_poi_auto_numbers(self, mock_env):
        config, obs = mock_env
        # SMOC already has POI-01
        smoc_with_poi = SAMPLE_SMOC.replace(
            "### Core\n<!-- The most important POIs -->",
            "### Core\n<!-- The most important POIs -->\n- [[POI-01-existing]]",
        )
        obs.read.return_value = smoc_with_poi

        result = runner.invoke(app, ["poi", "python", "New Idea"])

        assert result.exit_code == 0
        assert "POI-02" in result.output

    def test_poi_invalid_subject(self, mock_env):
        config, obs = mock_env
        result = runner.invoke(app, ["poi", "_inbox", "Bad"])
        assert result.exit_code == 1
        assert "reserved" in result.output


# -- ref command tests -------------------------------------------------------


class TestRefCommand:
    def test_creates_ref(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = SAMPLE_SMOC

        result = runner.invoke(
            app,
            ["ref", "python", "PEP 484", "--author", "Guido", "--year", "2014"],
        )

        assert result.exit_code == 0
        assert "Created python/REF-01-pep-484" in result.output
        obs.create.assert_called_once()

    def test_ref_with_url(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = SAMPLE_SMOC

        result = runner.invoke(
            app,
            ["ref", "python", "Docs", "--url", "https://docs.python.org"],
        )

        assert result.exit_code == 0
        assert "REF-01" in result.output


# -- map command tests -------------------------------------------------------


class TestMapCommand:
    def test_shows_smoc(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = SAMPLE_SMOC

        result = runner.invoke(app, ["map", "python"])

        assert result.exit_code == 0
        assert "Subject Map of Contents" in result.output

    def test_shows_gsmoc(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = SAMPLE_GSMOC

        result = runner.invoke(app, ["map"])

        assert result.exit_code == 0
        assert "Grand Subject Map" in result.output

    def test_map_not_found(self, mock_env):
        config, obs = mock_env
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")

        result = runner.invoke(app, ["map", "nonexistent"])

        assert result.exit_code == 1


# -- review command tests ----------------------------------------------------


class TestReviewCommand:
    def test_review_subject(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = SAMPLE_SPEEDS

        result = runner.invoke(app, ["review", "-s", "python"])

        assert result.exit_code == 0
        assert "Unmapped speeds" in result.output
        assert "S1:" in result.output
        assert "S2:" in result.output
        assert "S4:" in result.output
        # S3 is mapped, should not appear
        assert "Asyncio" not in result.output

    def test_review_pan(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = SAMPLE_INBOX

        result = runner.invoke(app, ["review", "--pan"])

        assert result.exit_code == 0
        assert "Inbox entries" in result.output
        assert "S1:" in result.output
        assert "S2:" in result.output

    def test_review_empty_inbox(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = "---\ntype: inbox\n---\n# Inbox\n"

        result = runner.invoke(app, ["review", "--pan"])

        assert result.exit_code == 0
        assert "Inbox is empty" in result.output

    def test_review_no_unmapped(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = (
            "---\ntype: speeds\n---\n# speeds\n- S1: thought [→ POI-1]\n"
        )

        result = runner.invoke(app, ["review", "-s", "python"])

        assert result.exit_code == 0
        assert "No unmapped speeds" in result.output

    def test_review_no_flags(self, mock_env):
        result = runner.invoke(app, ["review"])
        assert result.exit_code == 1


# -- subjects pp command tests -----------------------------------------------


class TestSubjectsPpCommand:
    def test_shows_pp(self, mock_env):
        config, obs = mock_env
        obs.read.return_value = SAMPLE_PP

        result = runner.invoke(app, ["subjects", "pp", "python"])

        assert result.exit_code == 0
        assert "Purpose & Principles" in result.output

    def test_pp_not_found(self, mock_env):
        config, obs = mock_env
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")

        result = runner.invoke(app, ["subjects", "pp", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_pp_invalid_name(self, mock_env):
        config, obs = mock_env
        result = runner.invoke(app, ["subjects", "pp", "_inbox"])
        assert result.exit_code == 1
        assert "reserved" in result.output
