"""Tests for lionnotes.review module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lionnotes.config import Config
from lionnotes.obsidian import ObsidianCLIError
from lionnotes.review import (
    InboxEntry,
    ReviewError,
    assign_inbox_entry,
    get_unmapped_speeds,
    map_speed,
    triage_inbox,
)

# -- Sample content ----------------------------------------------------------

SAMPLE_SPEEDS = """\
---
type: speeds
subject: "python"
created: "2026-01-01"
last_entry: null
entry_count: 0
---
# python — Speed Thoughts

<!-- Append new speeds below. Format: - S[N]: (context: ...) content #thought/type -->
- S1: (context: reading) Decorators are just closures #thought/observation
- S2: Generators can be used for lazy evaluation #thought/observation
- S3: (context: work) Need to explore asyncio more #thought/question [→ POI-1]
- S4: Type hints improve readability #thought/principle
"""

SAMPLE_INBOX = """\
---
type: inbox
created: "2026-01-01"
---
# Unsorted Speed Thoughts

<!-- Pan-subject speed thoughts awaiting triage. -->
- S1: (context: morning) Random idea about project structure #thought/observation
- S2: Should learn more about Rust #thought/goal
- S3: (context: reading) Interesting FP pattern #thought/connection
"""


# -- get_unmapped_speeds tests -----------------------------------------------


class TestGetUnmappedSpeeds:
    def test_returns_unmapped_entries(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_SPEEDS

        result = get_unmapped_speeds("python", obs)

        assert len(result) == 3  # S1, S2, S4 are unmapped; S3 is mapped
        assert result[0].number == 1
        assert result[1].number == 2
        assert result[2].number == 4

    def test_parses_content(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_SPEEDS

        result = get_unmapped_speeds("python", obs)

        assert result[0].content == "Decorators are just closures"
        assert result[0].context == "reading"
        assert result[0].thought_type == "#thought/observation"

    def test_excludes_mapped(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_SPEEDS

        result = get_unmapped_speeds("python", obs)

        numbers = [e.number for e in result]
        assert 3 not in numbers  # S3 is mapped

    def test_empty_speeds_file(self):
        obs = MagicMock()
        obs.read.return_value = "---\ntype: speeds\n---\n# Speeds\n"

        result = get_unmapped_speeds("python", obs)

        assert result == []

    def test_missing_speeds_file(self):
        obs = MagicMock()
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")

        result = get_unmapped_speeds("python", obs)

        assert result == []

    def test_reraises_non_not_found_errors(self):
        obs = MagicMock()
        obs.read.side_effect = ObsidianCLIError(["read"], -1, "timed out")

        with pytest.raises(ObsidianCLIError, match="timed out"):
            get_unmapped_speeds("python", obs)

    def test_reads_correct_file(self):
        obs = MagicMock()
        obs.read.return_value = "# speeds\n"

        get_unmapped_speeds("my-subject", obs)

        obs.read.assert_called_once_with("my-subject/speeds")


# -- map_speed tests ---------------------------------------------------------


class TestMapSpeed:
    def test_marks_speed_as_mapped(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_SPEEDS

        map_speed("python", 1, "POI-5", obs)

        obs.create.assert_called()
        created_content = obs.create.call_args.kwargs.get(
            "content",
            obs.create.call_args.args[1] if len(obs.create.call_args.args) > 1 else "",
        )
        assert "[→ POI-5]" in created_content

    def test_normalizes_numeric_poi_ref(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_SPEEDS

        map_speed("python", 2, "5", obs)

        created_content = obs.create.call_args.kwargs.get(
            "content",
            obs.create.call_args.args[1] if len(obs.create.call_args.args) > 1 else "",
        )
        assert "[→ POI-5]" in created_content

    def test_already_mapped_raises(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_SPEEDS

        with pytest.raises(ReviewError, match="already mapped"):
            map_speed("python", 3, "POI-2", obs)

    def test_not_found_raises(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_SPEEDS

        with pytest.raises(ReviewError, match="not found"):
            map_speed("python", 99, "POI-1", obs)


# -- triage_inbox tests ------------------------------------------------------


class TestTriageInbox:
    def test_lists_entries(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_INBOX

        result = triage_inbox(obs)

        assert len(result) == 3
        assert result[0].number == 1
        assert result[1].number == 2
        assert result[2].number == 3

    def test_parses_content(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_INBOX

        result = triage_inbox(obs)

        assert result[0].content == "Random idea about project structure"
        assert result[0].context == "morning"
        assert result[0].thought_type == "#thought/observation"

    def test_missing_inbox(self):
        obs = MagicMock()
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")

        result = triage_inbox(obs)

        assert result == []

    def test_reads_correct_file(self):
        obs = MagicMock()
        obs.read.return_value = "# inbox\n"

        triage_inbox(obs)

        obs.read.assert_called_once_with("_inbox/unsorted")


# -- assign_inbox_entry tests ------------------------------------------------


class TestAssignInboxEntry:
    def _make_config(self, tmp_path):
        config = Config(vault_path=str(tmp_path))
        config_path = tmp_path / ".lionnotes.toml"
        config_path.write_text('vault_path = "' + str(tmp_path) + '"\n')
        return config

    def test_moves_entry_to_subject(self, tmp_path):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_INBOX
        config = self._make_config(tmp_path)

        entry = InboxEntry(
            number=2,
            content="Should learn more about Rust",
            thought_type="#thought/goal",
            raw_line="- S2: Should learn more about Rust #thought/goal",
        )

        result = assign_inbox_entry(entry, "rust", obs, config)

        assert result.number == 1  # first speed in target subject
        assert result.content == "Should learn more about Rust"
        # Should append to target subject's speeds
        obs.append.assert_called_once()
        assert "rust/speeds" in obs.append.call_args.args[0]

    def test_removes_from_inbox(self, tmp_path):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_INBOX
        config = self._make_config(tmp_path)

        entry = InboxEntry(
            number=2,
            content="Should learn more about Rust",
            raw_line="- S2: Should learn more about Rust #thought/goal",
        )

        assign_inbox_entry(entry, "rust", obs, config)

        # The inbox rewrite should not contain S2
        obs.create.assert_called()  # _write_note creates
        created_content = obs.create.call_args.kwargs.get(
            "content",
            obs.create.call_args.args[1] if len(obs.create.call_args.args) > 1 else "",
        )
        assert "S2:" not in created_content
        assert "S1:" in created_content
        assert "S3:" in created_content

    def test_entry_not_found_raises(self, tmp_path):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_INBOX
        config = self._make_config(tmp_path)

        entry = InboxEntry(number=99, content="nonexistent", raw_line="")

        with pytest.raises(ReviewError, match="not found"):
            assign_inbox_entry(entry, "rust", obs, config)
