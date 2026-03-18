"""Tests for lionnotes.subjects module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lionnotes.config import Config
from lionnotes.obsidian import ObsidianCLIError
from lionnotes.subjects import (
    SubjectError,
    create_subject,
    list_subjects,
    normalize_subject_name,
)


class TestNormalizeSubjectName:
    def test_lowercase(self):
        assert normalize_subject_name("Personal Psychology") == "personal-psychology"

    def test_strips_whitespace(self):
        assert normalize_subject_name("  hello  ") == "hello"

    def test_collapses_hyphens(self):
        assert normalize_subject_name("a--b") == "a-b"

    def test_single_char(self):
        assert normalize_subject_name("x") == "x"

    def test_rejects_empty(self):
        with pytest.raises(SubjectError, match="cannot be empty"):
            normalize_subject_name("")

    def test_rejects_reserved_inbox(self):
        with pytest.raises(SubjectError, match="reserved"):
            normalize_subject_name("_inbox")

    def test_rejects_reserved_strategy(self):
        with pytest.raises(SubjectError, match="reserved"):
            normalize_subject_name("_strategy")

    def test_rejects_reserved_gsmoc(self):
        with pytest.raises(SubjectError, match="reserved"):
            normalize_subject_name("GSMOC")

    def test_rejects_reserved_subject_registry(self):
        with pytest.raises(SubjectError, match="reserved"):
            normalize_subject_name("Subject Registry")

    def test_rejects_reserved_global_aliases(self):
        with pytest.raises(SubjectError, match="reserved"):
            normalize_subject_name("Global Aliases")

    def test_rejects_special_chars(self):
        with pytest.raises(SubjectError, match="Invalid"):
            normalize_subject_name("hello@world")

    def test_rejects_leading_hyphen(self):
        with pytest.raises(SubjectError, match="Invalid"):
            normalize_subject_name("-hello")

    def test_rejects_trailing_hyphen(self):
        with pytest.raises(SubjectError, match="Invalid"):
            normalize_subject_name("hello-")


class TestCreateSubject:
    def _make_config(self, tmp_path):
        config = Config(vault_path=str(tmp_path))
        # Write a config file so save_config works
        config_path = tmp_path / ".lionnotes.toml"
        config_path.write_text('vault_path = "' + str(tmp_path) + '"\n')
        return config

    def test_creates_all_files(self, tmp_path):
        obs = MagicMock()
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")
        config = self._make_config(tmp_path)

        result = create_subject("My Topic", obs, config)

        assert result == "my-topic"
        assert obs.create.call_count == 4
        call_names = [call.args[0] for call in obs.create.call_args_list]
        assert "my-topic/SMOC" in call_names
        assert "my-topic/purpose" in call_names
        assert "my-topic/speeds" in call_names
        assert "my-topic/glossary" in call_names

    def test_initializes_speed_counter(self, tmp_path):
        obs = MagicMock()
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")
        config = self._make_config(tmp_path)

        create_subject("my-topic", obs, config)

        assert config.speed_counters["my-topic"] == 0

    def test_rejects_existing_subject(self, tmp_path):
        obs = MagicMock()
        obs.read.return_value = "# Existing SMOC"
        config = self._make_config(tmp_path)

        with pytest.raises(SubjectError, match="already exists"):
            create_subject("my-topic", obs, config)

    def test_rejects_invalid_name(self, tmp_path):
        obs = MagicMock()
        config = self._make_config(tmp_path)

        with pytest.raises(SubjectError, match="reserved"):
            create_subject("_inbox", obs, config)


class TestListSubjects:
    def test_returns_subjects(self):
        obs = MagicMock()
        obs.search.return_value = (
            "alpha/SMOC.md\n"
            "beta/SMOC.md\n"
            "gamma/SMOC.md\n"
        )

        result = list_subjects(obs)
        assert result == ["alpha", "beta", "gamma"]

    def test_returns_empty_on_no_results(self):
        obs = MagicMock()
        obs.search.side_effect = ObsidianCLIError(["search"], 1, "no results")

        result = list_subjects(obs)
        assert result == []

    def test_filters_internal_folders(self):
        obs = MagicMock()
        obs.search.return_value = (
            "alpha/SMOC.md\n"
            "_inbox/SMOC.md\n"
        )

        result = list_subjects(obs)
        assert result == ["alpha"]

    def test_deduplicates(self):
        obs = MagicMock()
        obs.search.return_value = (
            "alpha/SMOC.md\n"
            "alpha/SMOC.md\n"
        )

        result = list_subjects(obs)
        assert result == ["alpha"]

    def test_passes_limit_to_search(self):
        obs = MagicMock()
        obs.search.return_value = "alpha/SMOC.md\n"

        list_subjects(obs, limit=500)
        obs.search.assert_called_once_with("type: smoc", limit=500)

    def test_default_limit_is_200(self):
        obs = MagicMock()
        obs.search.return_value = ""

        list_subjects(obs)
        obs.search.assert_called_once_with("type: smoc", limit=200)
