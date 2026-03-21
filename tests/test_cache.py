"""Unit tests for lionnotes.cache module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lionnotes.cache import (
    DEFAULT_TIER,
    VALID_TIERS,
    CacheError,
    activate_subject,
    archive_subject,
    get_tier,
    list_tiers,
    set_tier,
)
from lionnotes.obsidian import ObsidianCLIError


class TestGetTier:
    def test_returns_tier_from_property(self):
        obs = MagicMock()
        obs.property_get.return_value = "common-store\n"

        tier = get_tier("python", obs)

        assert tier == "common-store"
        obs.property_get.assert_called_once_with("python/SMOC", "tier")

    def test_returns_default_when_no_property(self):
        obs = MagicMock()
        obs.property_get.side_effect = ObsidianCLIError(
            ["property:get"], 1, "not found"
        )

        tier = get_tier("python", obs)

        assert tier == DEFAULT_TIER

    def test_returns_default_for_invalid_tier_value(self):
        obs = MagicMock()
        obs.property_get.return_value = "invalid-tier\n"

        tier = get_tier("python", obs)

        assert tier == DEFAULT_TIER

    def test_returns_carry_about(self):
        obs = MagicMock()
        obs.property_get.return_value = "carry-about"

        assert get_tier("python", obs) == "carry-about"

    def test_returns_archive(self):
        obs = MagicMock()
        obs.property_get.return_value = "archive"

        assert get_tier("python", obs) == "archive"

    def test_normalizes_subject_name(self):
        obs = MagicMock()
        obs.property_get.return_value = "carry-about"

        get_tier("My Subject", obs)

        obs.property_get.assert_called_once_with("my-subject/SMOC", "tier")


class TestSetTier:
    def test_sets_valid_tier(self):
        obs = MagicMock()
        obs.read.return_value = "smoc content"

        set_tier("python", "archive", obs)

        obs.property_set.assert_called_once_with("python/SMOC", "tier", "archive")

    def test_invalid_tier_raises(self):
        obs = MagicMock()

        with pytest.raises(CacheError, match="Invalid tier"):
            set_tier("python", "invalid", obs)

    def test_all_valid_tiers_accepted(self):
        for tier in VALID_TIERS:
            obs = MagicMock()
            obs.read.return_value = "smoc content"
            set_tier("python", tier, obs)
            obs.property_set.assert_called_once()

    def test_subject_not_found_raises(self):
        obs = MagicMock()
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")

        with pytest.raises(CacheError, match="not found"):
            set_tier("nonexistent", "archive", obs)

    def test_normalizes_subject_name(self):
        obs = MagicMock()
        obs.read.return_value = "smoc content"

        set_tier("My Subject", "archive", obs)

        obs.read.assert_called_once_with("my-subject/SMOC")
        obs.property_set.assert_called_once_with("my-subject/SMOC", "tier", "archive")

    def test_reraises_non_not_found_errors(self):
        obs = MagicMock()
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "permission denied")

        with pytest.raises(ObsidianCLIError):
            set_tier("python", "archive", obs)


class TestListTiers:
    @patch("lionnotes.cache.list_subjects")
    @patch("lionnotes.cache.get_tier")
    def test_groups_subjects_by_tier(self, mock_get_tier, mock_list):
        obs = MagicMock()
        mock_list.return_value = ["python", "rust", "old-stuff"]
        mock_get_tier.side_effect = [
            "carry-about",
            "common-store",
            "archive",
        ]

        result = list_tiers(obs)

        assert result["carry-about"] == ["python"]
        assert result["common-store"] == ["rust"]
        assert result["archive"] == ["old-stuff"]

    @patch("lionnotes.cache.list_subjects")
    def test_empty_vault(self, mock_list):
        obs = MagicMock()
        mock_list.return_value = []

        result = list_tiers(obs)

        assert result == {
            "carry-about": [],
            "common-store": [],
            "archive": [],
        }

    @patch("lionnotes.cache.list_subjects")
    @patch("lionnotes.cache.get_tier")
    def test_all_carry_about_by_default(self, mock_get_tier, mock_list):
        obs = MagicMock()
        mock_list.return_value = ["python", "rust"]
        mock_get_tier.return_value = "carry-about"

        result = list_tiers(obs)

        assert result["carry-about"] == ["python", "rust"]
        assert result["common-store"] == []
        assert result["archive"] == []


class TestArchiveSubject:
    def test_sets_archive_tier(self):
        obs = MagicMock()
        obs.read.return_value = "smoc content"

        archive_subject("python", obs)

        obs.property_set.assert_called_once_with("python/SMOC", "tier", "archive")


class TestActivateSubject:
    def test_sets_carry_about_tier(self):
        obs = MagicMock()
        obs.read.return_value = "smoc content"

        activate_subject("python", obs)

        obs.property_set.assert_called_once_with("python/SMOC", "tier", "carry-about")
