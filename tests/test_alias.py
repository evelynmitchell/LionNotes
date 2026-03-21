"""Unit tests for lionnotes.alias module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lionnotes.alias import (
    AliasError,
    _parse_aliases,
    list_aliases,
    remove_alias,
    set_alias,
)

SAMPLE_GLOBAL_ALIASES = """\
---
type: aliases
updated: "2026-01-01"
---
# Global Aliases

<!-- Abbreviations used across subjects -->

- **PP**: Purpose & Principles
- **SMOC**: Subject Map of Contents
- **GSMOC**: Grand Subject Map of Contents
"""

SAMPLE_GLOSSARY = """\
---
type: glossary
subject: "python"
---
# python — Glossary

- **GIL**: Global Interpreter Lock
- **PEP**: Python Enhancement Proposal
"""

EMPTY_ALIASES = """\
---
type: aliases
updated: "2026-01-01"
---
# Global Aliases

<!-- Abbreviations used across subjects -->
"""


class TestParseAliases:
    def test_parses_entries(self):
        aliases = _parse_aliases(SAMPLE_GLOBAL_ALIASES, "global")
        assert len(aliases) == 3

    def test_entry_fields(self):
        aliases = _parse_aliases(SAMPLE_GLOBAL_ALIASES, "global")
        assert aliases[0].abbreviation == "PP"
        assert aliases[0].expansion == "Purpose & Principles"
        assert aliases[0].scope == "global"

    def test_second_entry(self):
        aliases = _parse_aliases(SAMPLE_GLOBAL_ALIASES, "global")
        assert aliases[1].abbreviation == "SMOC"
        assert aliases[1].expansion == "Subject Map of Contents"

    def test_empty_content(self):
        aliases = _parse_aliases(EMPTY_ALIASES, "global")
        assert aliases == []

    def test_subject_scope(self):
        aliases = _parse_aliases(SAMPLE_GLOSSARY, "python")
        assert len(aliases) == 2
        assert aliases[0].scope == "python"
        assert aliases[0].abbreviation == "GIL"

    def test_non_alias_lines_ignored(self):
        content = "# Heading\nSome text\n- **A**: B\n- regular list\n"
        aliases = _parse_aliases(content, "global")
        assert len(aliases) == 1
        assert aliases[0].abbreviation == "A"


class TestListAliases:
    def test_returns_global_aliases(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GLOBAL_ALIASES

        aliases = list_aliases(obs)

        assert len(aliases) == 3
        obs.read.assert_called_once_with("Global Aliases")

    def test_returns_subject_aliases(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GLOSSARY

        aliases = list_aliases(obs, subject="python")

        assert len(aliases) == 2
        obs.read.assert_called_once_with("python/glossary")

    def test_empty_list(self):
        obs = MagicMock()
        obs.read.return_value = EMPTY_ALIASES

        aliases = list_aliases(obs)

        assert aliases == []


class TestSetAlias:
    def test_appends_new_alias(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GLOBAL_ALIASES

        set_alias("POI", "Point of Interest", obs)

        obs.append.assert_called_once()
        appended = obs.append.call_args[0][1]
        assert "**POI**" in appended
        assert "Point of Interest" in appended

    def test_updates_existing_alias(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GLOBAL_ALIASES

        with patch("lionnotes.alias._write_note") as mock_write:
            set_alias("PP", "Purpose and Principles", obs)

        mock_write.assert_called_once()
        written = mock_write.call_args[0][1]
        assert "Purpose and Principles" in written
        assert "Purpose & Principles" not in written
        # Other aliases preserved
        assert "SMOC" in written
        assert "GSMOC" in written

    def test_case_insensitive_update(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GLOBAL_ALIASES

        with patch("lionnotes.alias._write_note") as mock_write:
            set_alias("pp", "Purpose and Principles", obs)

        mock_write.assert_called_once()
        written = mock_write.call_args[0][1]
        assert "**pp**" in written
        assert "Purpose and Principles" in written

    def test_subject_alias_append(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GLOSSARY

        set_alias("ABC", "Always Be Coding", obs, subject="python")

        obs.append.assert_called_once()
        assert obs.append.call_args[0][0] == "python/glossary"

    def test_empty_abbr_raises(self):
        obs = MagicMock()
        with pytest.raises(AliasError, match="Abbreviation cannot be empty"):
            set_alias("", "expansion", obs)

    def test_empty_expansion_raises(self):
        obs = MagicMock()
        with pytest.raises(AliasError, match="Expansion cannot be empty"):
            set_alias("ABC", "", obs)

    def test_strips_whitespace(self):
        obs = MagicMock()
        obs.read.return_value = EMPTY_ALIASES

        set_alias("  ABC  ", "  Always Be Coding  ", obs)

        appended = obs.append.call_args[0][1]
        assert "**ABC**" in appended
        assert "Always Be Coding" in appended


class TestRemoveAlias:
    def test_removes_alias(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GLOBAL_ALIASES

        with patch("lionnotes.alias._write_note") as mock_write:
            remove_alias("SMOC", obs)

        mock_write.assert_called_once()
        written = mock_write.call_args[0][1]
        assert "**SMOC**: Subject Map of Contents" not in written
        # Other aliases preserved
        assert "**PP**" in written
        assert "**GSMOC**" in written

    def test_removes_first_alias(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GLOBAL_ALIASES

        with patch("lionnotes.alias._write_note") as mock_write:
            remove_alias("PP", obs)

        written = mock_write.call_args[0][1]
        assert "Purpose & Principles" not in written
        assert "SMOC" in written

    def test_removes_last_alias(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GLOBAL_ALIASES

        with patch("lionnotes.alias._write_note") as mock_write:
            remove_alias("GSMOC", obs)

        written = mock_write.call_args[0][1]
        assert "Grand Subject Map" not in written
        assert "PP" in written

    def test_case_insensitive_remove(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GLOBAL_ALIASES

        with patch("lionnotes.alias._write_note") as mock_write:
            remove_alias("smoc", obs)

        written = mock_write.call_args[0][1]
        assert "**SMOC**: Subject Map of Contents" not in written

    def test_not_found_raises(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GLOBAL_ALIASES

        with pytest.raises(AliasError, match="Alias 'XYZ' not found"):
            remove_alias("XYZ", obs)

    def test_empty_abbr_raises(self):
        obs = MagicMock()
        with pytest.raises(AliasError, match="Abbreviation cannot be empty"):
            remove_alias("", obs)

    def test_subject_alias_remove(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GLOSSARY

        with patch("lionnotes.alias._write_note") as mock_write:
            remove_alias("GIL", obs, subject="python")

        mock_write.assert_called_once()
        assert mock_write.call_args[0][0] == "python/glossary"
        written = mock_write.call_args[0][1]
        assert "GIL" not in written
        assert "PEP" in written

    def test_writes_to_correct_note(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GLOBAL_ALIASES

        with patch("lionnotes.alias._write_note") as mock_write:
            remove_alias("PP", obs)

        assert mock_write.call_args[0][0] == "Global Aliases"
