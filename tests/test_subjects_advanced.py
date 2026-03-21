"""Tests for subjects merge/split/promote operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lionnotes.config import Config
from lionnotes.obsidian import ObsidianCLIError
from lionnotes.subjects import (
    MergeResult,
    MoveFailure,
    SplitResult,
    SubjectError,
    merge_subjects,
    promote_subject,
    split_subject,
)

# -- Fixtures ---------------------------------------------------------------


SAMPLE_SOURCE_SMOC = """\
---
type: smoc
subject: "source"
version: 1
created: "2026-01-01"
updated: "2026-01-01"
---
# source — Subject Map of Contents

## Purpose & Principles
- [[purpose]]

## Map

### Core
- [[POI-01-alpha]]
- [[POI-02-beta]]

### Peripheral

### References
- [[REF-01-gamma]]

## Speed Thoughts
- Current speed page: [[speeds]]

## See Also
"""

SAMPLE_TARGET_SMOC = """\
---
type: smoc
subject: "target"
version: 1
created: "2026-01-01"
updated: "2026-01-01"
---
# target — Subject Map of Contents

## Purpose & Principles
- [[purpose]]

## Map

### Core
- [[POI-01-existing]]

### Peripheral

### References

## Speed Thoughts
- Current speed page: [[speeds]]

## See Also
"""

SAMPLE_SOURCE_SPEEDS = """\
---
type: speeds
subject: "source"
---
# source — Speed Thoughts

- S1: first thought #thought/observation
- S2: second thought #thought/idea
"""

SAMPLE_INBOX = """\
---
type: inbox
created: "2026-01-01"
---
# Unsorted Speed Thoughts

- S1: (context: python) decorators are cool #thought/observation
- S2: random thought
- S3: (context: python) metaclasses too #thought/idea
"""

EMPTY_SMOC = """\
---
type: smoc
subject: "empty"
version: 1
created: "2026-01-01"
updated: "2026-01-01"
---
# empty — Subject Map of Contents

## Purpose & Principles
- [[purpose]]

## Map

### Core

### Peripheral

### References

## Speed Thoughts
- Current speed page: [[speeds]]

## See Also
"""

SAMPLE_GSMOC = """\
---
type: gsmoc
version: 1
created: "2026-01-01"
updated: "2026-01-01"
---
# Grand Subject Map of Contents

## Active Subjects
- [[source/SMOC|source]]
- [[target/SMOC|target]]

## Dormant Subjects

## Emerging

## Cross-Subject Connections
"""


@pytest.fixture
def mock_config(tmp_path):
    config = Config(vault_path=str(tmp_path))
    config_path = tmp_path / ".lionnotes.toml"
    config_path.write_text(f'vault_path = "{tmp_path}"\n')
    return config


# -- Merge tests ------------------------------------------------------------


class TestMergeSubjects:
    def test_merge_moves_notes(self, mock_config, tmp_path):
        obs = MagicMock()

        def read_side(path):
            if path == "source/SMOC":
                return SAMPLE_SOURCE_SMOC
            if path == "target/SMOC":
                return SAMPLE_TARGET_SMOC
            if path == "source/speeds":
                return SAMPLE_SOURCE_SPEEDS
            if path == "GSMOC":
                return SAMPLE_GSMOC
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side

        with (
            patch("lionnotes.subjects.save_config"),
            patch("lionnotes.maps._write_note"),
        ):
            result = merge_subjects("source", "target", obs, mock_config)

        assert len(result.moved) == 3
        assert result.failed == []
        assert result.out_card_created is True
        # POIs renumbered starting after target's POI-01
        assert "POI-02-alpha" in result.moved
        assert "POI-03-beta" in result.moved
        assert "REF-01-gamma" in result.moved

    def test_merge_into_self_raises(self, mock_config):
        obs = MagicMock()

        with pytest.raises(SubjectError, match="into itself"):
            merge_subjects("alpha", "alpha", obs, mock_config)

    def test_merge_source_not_found(self, mock_config):
        obs = MagicMock()
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")

        with pytest.raises(SubjectError, match="does not exist"):
            merge_subjects("missing", "target", obs, mock_config)

    def test_merge_target_not_found(self, mock_config):
        obs = MagicMock()

        def read_side(path):
            if path == "source/SMOC":
                return SAMPLE_SOURCE_SMOC
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side

        with pytest.raises(SubjectError, match="does not exist"):
            merge_subjects("source", "missing", obs, mock_config)

    def test_merge_partial_failure(self, mock_config):
        obs = MagicMock()

        def read_side(path):
            if path == "source/SMOC":
                return SAMPLE_SOURCE_SMOC
            if path == "target/SMOC":
                return SAMPLE_TARGET_SMOC
            if path == "source/speeds":
                return SAMPLE_SOURCE_SPEEDS
            if path == "GSMOC":
                return SAMPLE_GSMOC
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side

        # Make the second rename fail
        rename_count = [0]

        def rename_side(src, dst):
            rename_count[0] += 1
            if rename_count[0] == 2:
                raise ObsidianCLIError(["rename"], 1, "permission denied")

        obs.rename.side_effect = rename_side

        with (
            patch("lionnotes.subjects.save_config"),
            patch("lionnotes.maps._write_note"),
        ):
            result = merge_subjects("source", "target", obs, mock_config)

        assert len(result.moved) == 2
        assert len(result.failed) == 1
        assert result.failed[0].note == "POI-02-beta"

    def test_merge_empty_source(self, mock_config):
        obs = MagicMock()

        def read_side(path):
            if path == "empty/SMOC":
                return EMPTY_SMOC
            if path == "target/SMOC":
                return SAMPLE_TARGET_SMOC
            if path == "GSMOC":
                return SAMPLE_GSMOC
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side

        with (
            patch("lionnotes.subjects.save_config"),
            patch("lionnotes.maps._write_note"),
        ):
            result = merge_subjects("empty", "target", obs, mock_config)

        assert result.moved == []
        assert result.failed == []

    def test_merge_updates_speed_counters(self, mock_config):
        obs = MagicMock()
        mock_config.speed_counters["target"] = 5

        def read_side(path):
            if path == "source/SMOC":
                return EMPTY_SMOC.replace("empty", "source")
            if path == "target/SMOC":
                return SAMPLE_TARGET_SMOC
            if path == "source/speeds":
                return SAMPLE_SOURCE_SPEEDS
            if path == "GSMOC":
                return SAMPLE_GSMOC
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side

        with (
            patch("lionnotes.subjects.save_config"),
            patch("lionnotes.maps._write_note"),
        ):
            merge_subjects("source", "target", obs, mock_config)

        # 2 speed lines in source, starting from target's 5
        assert mock_config.speed_counters["target"] == 7


# -- Split tests ------------------------------------------------------------


class TestSplitSubject:
    def test_split_moves_matched_notes(self, mock_config):
        obs = MagicMock()

        def read_side(path):
            if path == "source/SMOC":
                return SAMPLE_SOURCE_SMOC
            if path == "new-topic/SMOC":
                raise ObsidianCLIError(["read"], 1, "not found")
            if path == "GSMOC":
                return SAMPLE_GSMOC
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side

        with (
            patch("lionnotes.subjects.save_config"),
            patch("lionnotes.maps._write_note"),
        ):
            result = split_subject(
                "source",
                "new-topic",
                ["POI-01", "REF-01"],
                obs,
                mock_config,
            )

        assert result.new_subject == "new-topic"
        assert "POI-01-alpha" in result.moved
        assert "REF-01-gamma" in result.moved
        assert len(result.moved) == 2
        assert result.failed == []

    def test_split_no_match_raises(self, mock_config):
        obs = MagicMock()

        def read_side(path):
            if path == "source/SMOC":
                return SAMPLE_SOURCE_SMOC
            if path == "new-topic/SMOC":
                raise ObsidianCLIError(["read"], 1, "not found")
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side

        with (
            patch("lionnotes.subjects.save_config"),
            pytest.raises(SubjectError, match="No notes matched"),
        ):
            split_subject(
                "source",
                "new-topic",
                ["NONEXISTENT"],
                obs,
                mock_config,
            )

    def test_split_invalid_new_name_raises(self, mock_config):
        obs = MagicMock()

        with pytest.raises(SubjectError, match="reserved"):
            split_subject(
                "source",
                "_inbox",
                ["POI-01"],
                obs,
                mock_config,
            )

    def test_split_source_not_found(self, mock_config):
        obs = MagicMock()
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")

        with pytest.raises(SubjectError, match="does not exist"):
            split_subject(
                "missing",
                "new-topic",
                ["POI-01"],
                obs,
                mock_config,
            )

    def test_split_target_already_exists(self, mock_config):
        obs = MagicMock()

        def read_side(path):
            if path == "source/SMOC":
                return SAMPLE_SOURCE_SMOC
            if path == "existing/SMOC":
                return SAMPLE_TARGET_SMOC
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side

        with pytest.raises(SubjectError, match="already exists"):
            split_subject(
                "source",
                "existing",
                ["POI-01"],
                obs,
                mock_config,
            )

    def test_split_partial_failure(self, mock_config):
        obs = MagicMock()

        def read_side(path):
            if path == "source/SMOC":
                return SAMPLE_SOURCE_SMOC
            if path == "new-topic/SMOC":
                raise ObsidianCLIError(["read"], 1, "not found")
            if path == "GSMOC":
                return SAMPLE_GSMOC
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side

        rename_count = [0]

        def rename_side(src, dst):
            rename_count[0] += 1
            if rename_count[0] == 1:
                raise ObsidianCLIError(["rename"], 1, "permission denied")

        obs.rename.side_effect = rename_side

        with (
            patch("lionnotes.subjects.save_config"),
            patch("lionnotes.maps._write_note"),
        ):
            result = split_subject(
                "source",
                "new-topic",
                ["POI-01", "POI-02"],
                obs,
                mock_config,
            )

        assert len(result.failed) == 1
        assert len(result.moved) == 1


# -- Promote tests ----------------------------------------------------------


class TestPromoteSubject:
    def test_promote_creates_subject(self, mock_config):
        obs = MagicMock()

        def read_side(path):
            if path == "python/SMOC":
                raise ObsidianCLIError(["read"], 1, "not found")
            if path == "_inbox/unsorted":
                return SAMPLE_INBOX
            if path == "GSMOC":
                return SAMPLE_GSMOC
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side

        with (
            patch("lionnotes.subjects.save_config"),
            patch("lionnotes.maps._write_note"),
        ):
            result = promote_subject("python", obs, mock_config)

        assert result == "python"
        # Subject created (4 files)
        assert obs.create.call_count == 4

    def test_promote_moves_matching_inbox_entries(self, mock_config):
        obs = MagicMock()

        def read_side(path):
            if path == "python/SMOC":
                raise ObsidianCLIError(["read"], 1, "not found")
            if path == "_inbox/unsorted":
                return SAMPLE_INBOX
            if path == "GSMOC":
                return SAMPLE_GSMOC
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side

        with (
            patch("lionnotes.subjects.save_config"),
            patch("lionnotes.maps._write_note"),
        ):
            promote_subject("python", obs, mock_config)

        # Two entries match "python" context
        # They should be appended to python/speeds
        append_calls = [
            c for c in obs.append.call_args_list if c.args[0] == "python/speeds"
        ]
        assert len(append_calls) == 1
        appended_text = append_calls[0].args[1]
        assert "decorators are cool" in appended_text
        assert "metaclasses too" in appended_text
        # Speed counter should be updated
        assert mock_config.speed_counters["python"] == 2

    def test_promote_reserved_name_raises(self, mock_config):
        obs = MagicMock()

        with pytest.raises(SubjectError, match="reserved"):
            promote_subject("_inbox", obs, mock_config)

    def test_promote_existing_subject_raises(self, mock_config):
        obs = MagicMock()
        obs.read.return_value = "# existing SMOC"

        with pytest.raises(SubjectError, match="already exists"):
            promote_subject("existing", obs, mock_config)

    def test_promote_no_inbox(self, mock_config):
        obs = MagicMock()

        call_count = [0]

        def read_side(path):
            if path.endswith("/SMOC") and "new-topic" in path:
                call_count[0] += 1
                if call_count[0] == 1:
                    raise ObsidianCLIError(["read"], 1, "not found")
                return "smoc content"
            if path == "_inbox/unsorted":
                raise ObsidianCLIError(["read"], 1, "not found")
            if path == "GSMOC":
                return SAMPLE_GSMOC
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side

        with (
            patch("lionnotes.subjects.save_config"),
            patch("lionnotes.maps._write_note"),
        ):
            result = promote_subject("new-topic", obs, mock_config)

        assert result == "new-topic"
        # Subject still created (4 files)
        assert obs.create.call_count == 4


# -- Dataclass tests --------------------------------------------------------


class TestDataclasses:
    def test_move_failure(self):
        f = MoveFailure(note="POI-01-test", reason="permission denied")
        assert f.note == "POI-01-test"
        assert f.reason == "permission denied"

    def test_merge_result_defaults(self):
        r = MergeResult()
        assert r.moved == []
        assert r.failed == []
        assert r.skipped == []
        assert r.out_card_created is False

    def test_split_result_defaults(self):
        r = SplitResult()
        assert r.new_subject == ""
        assert r.moved == []
        assert r.failed == []
