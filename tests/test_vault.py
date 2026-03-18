"""Tests for lionnotes.vault module."""

from __future__ import annotations

from unittest.mock import MagicMock

from lionnotes.config import Config
from lionnotes.obsidian import ObsidianCLIError
from lionnotes.vault import count_unmapped_speeds, get_vault_path, subject_exists


def _make_config(vault_path: str = "/tmp/test-vault") -> Config:
    return Config(vault_path=vault_path)


def _make_obsidian() -> MagicMock:
    return MagicMock()


class TestGetVaultPath:
    def test_resolves_path(self):
        config = _make_config("/tmp/test-vault")
        result = get_vault_path(config)
        assert result.is_absolute()
        assert str(result).endswith("test-vault")


class TestSubjectExists:
    def test_exists(self):
        obs = _make_obsidian()
        obs.read.return_value = "# SMOC content"
        assert subject_exists("my-subject", obs) is True
        obs.read.assert_called_once_with("my-subject/SMOC")

    def test_not_exists(self):
        obs = _make_obsidian()
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")
        assert subject_exists("nonexistent", obs) is False


class TestCountUnmappedSpeeds:
    def test_no_speeds_file(self):
        obs = _make_obsidian()
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")
        assert count_unmapped_speeds("my-subject", obs) == 0

    def test_all_unmapped(self):
        obs = _make_obsidian()
        obs.read.return_value = (
            "---\ntype: speeds\n---\n"
            "# Subject — Speed Thoughts\n\n"
            "- S1: (context: test) First thought #thought/observation\n"
            "- S2: (context: test) Second thought #thought/question\n"
            "- S3: Third thought\n"
        )
        assert count_unmapped_speeds("my-subject", obs) == 3

    def test_some_mapped(self):
        obs = _make_obsidian()
        obs.read.return_value = (
            "---\ntype: speeds\n---\n"
            "# Subject — Speed Thoughts\n\n"
            "- S1: First thought #thought/observation [→ POI-01]\n"
            "- S2: Second thought #thought/question\n"
            "- S3: Third thought [→ POI-03]\n"
        )
        assert count_unmapped_speeds("my-subject", obs) == 1

    def test_all_mapped(self):
        obs = _make_obsidian()
        obs.read.return_value = (
            "- S1: thought one [→ POI-01]\n"
            "- S2: thought two [→ POI-02]\n"
        )
        assert count_unmapped_speeds("my-subject", obs) == 0

    def test_ignores_non_speed_lines(self):
        obs = _make_obsidian()
        obs.read.return_value = (
            "# Title\n"
            "Some text\n"
            "- Not a speed entry\n"
            "- S1: Actual speed\n"
        )
        assert count_unmapped_speeds("my-subject", obs) == 1
