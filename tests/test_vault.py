"""Tests for lionnotes.vault."""

from unittest.mock import MagicMock

from lionnotes.obsidian import ObsidianCLIError
from lionnotes.vault import (
    count_unmapped_speeds,
    normalize_subject_name,
    parse_speed_entries,
    subject_exists,
    validate_subject_name,
)


class TestParseSpeedEntries:
    def test_parses_basic_entries(self):
        text = (
            "# python — Speed Thoughts\n"
            "- S1: first thought #thought/observation\n"
            "- S2: second thought #thought/question\n"
        )
        entries = parse_speed_entries(text)
        assert len(entries) == 2
        assert entries[0].number == 1
        assert entries[1].number == 2
        assert not entries[0].mapped
        assert not entries[1].mapped

    def test_detects_mapped_entries(self):
        text = (
            "- S1: thought one [→ POI-3]\n"
            "- S2: thought two\n"
            "- S3: thought three [→ POI-7]\n"
        )
        entries = parse_speed_entries(text)
        assert entries[0].mapped is True
        assert entries[1].mapped is False
        assert entries[2].mapped is True

    def test_ignores_non_speed_lines(self):
        text = (
            "# Heading\n"
            "Some paragraph text.\n"
            "- a regular bullet\n"
            "- S1: actual speed thought\n"
            "<!-- comment -->\n"
        )
        entries = parse_speed_entries(text)
        assert len(entries) == 1
        assert entries[0].number == 1

    def test_mapped_marker_must_be_at_end(self):
        text = "- S1: talking about [→ POI-3] in the middle\n"
        entries = parse_speed_entries(text)
        # Marker is not at end of line, so not mapped
        assert entries[0].mapped is False

    def test_empty_text(self):
        assert parse_speed_entries("") == []

    def test_frontmatter_only(self):
        text = "---\ntype: speeds\nsubject: python\n---\n# python — Speed Thoughts\n"
        entries = parse_speed_entries(text)
        assert entries == []

    def test_preserves_raw_line(self):
        line = "- S47: (context: debugging) memory issue #thought/observation"
        entries = parse_speed_entries(line)
        assert entries[0].raw_line == line


class TestCountUnmappedSpeeds:
    def test_counts_unmapped(self):
        obsidian = MagicMock()
        obsidian.read.return_value = "- S1: one [→ POI-1]\n- S2: two\n- S3: three\n"
        assert count_unmapped_speeds("python", obsidian) == 2
        obsidian.read.assert_called_once_with("python/speeds")

    def test_returns_zero_when_no_speeds_file(self):
        obsidian = MagicMock()
        obsidian.read.side_effect = ObsidianCLIError(["read"], 1, "not found")
        assert count_unmapped_speeds("python", obsidian) == 0

    def test_returns_zero_when_all_mapped(self):
        obsidian = MagicMock()
        obsidian.read.return_value = "- S1: one [→ POI-1]\n- S2: two [→ POI-2]\n"
        assert count_unmapped_speeds("python", obsidian) == 0


class TestSubjectExists:
    def test_exists(self):
        obsidian = MagicMock()
        obsidian.read.return_value = "# SMOC"
        assert subject_exists("python", obsidian) is True
        obsidian.read.assert_called_once_with("python/SMOC")

    def test_not_exists(self):
        obsidian = MagicMock()
        obsidian.read.side_effect = ObsidianCLIError(["read"], 1, "not found")
        assert subject_exists("python", obsidian) is False


class TestValidateSubjectName:
    def test_valid_names(self):
        assert validate_subject_name("python") is None
        assert validate_subject_name("my subject") is None
        assert validate_subject_name("rust-async") is None
        assert validate_subject_name("c++") is None

    def test_empty(self):
        assert validate_subject_name("") is not None
        assert validate_subject_name("   ") is not None

    def test_reserved_names(self):
        assert validate_subject_name("GSMOC") is not None
        assert validate_subject_name("gsmoc") is not None
        assert validate_subject_name("Subject Registry") is not None
        assert validate_subject_name("Global Aliases") is not None

    def test_reserved_prefix(self):
        assert validate_subject_name("_inbox") is not None
        assert validate_subject_name("_anything") is not None
        assert validate_subject_name("_strategy") is not None

    def test_bad_characters(self):
        assert validate_subject_name("my<subject") is not None
        assert validate_subject_name("note|pipe") is not None
        assert validate_subject_name("back\\slash") is not None

    def test_too_long(self):
        assert validate_subject_name("a" * 101) is not None
        assert validate_subject_name("a" * 100) is None


class TestNormalizeSubjectName:
    def test_lowercase(self):
        assert normalize_subject_name("Python") == "python"

    def test_spaces_to_hyphens(self):
        assert normalize_subject_name("my subject") == "my-subject"

    def test_strips_whitespace(self):
        assert normalize_subject_name("  python  ") == "python"

    def test_combined(self):
        assert normalize_subject_name("  My Cool Subject  ") == "my-cool-subject"
