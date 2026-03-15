"""Tests for lionnotes.subjects."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lionnotes.config import Config, save_config
from lionnotes.obsidian import ObsidianCLIError
from lionnotes.subjects import (
    SubjectError,
    create_subject,
    list_subjects,
)


@pytest.fixture()
def config(tmp_path: Path) -> Config:
    vault = tmp_path / "vault"
    vault.mkdir()
    cfg = Config(vault_path=str(vault))
    save_config(cfg)
    return cfg


@pytest.fixture()
def obsidian() -> MagicMock:
    return MagicMock()


class TestCreateSubject:
    def test_creates_all_files(self, obsidian, config):
        # Subject doesn't exist yet
        obsidian.read.side_effect = ObsidianCLIError(["read"], 1, "not found")

        result = create_subject("Python", obsidian, config)
        assert result == "python"

        # Should create 5 files
        assert obsidian.create.call_count == 5
        created_names = [c.args[0] for c in obsidian.create.call_args_list]
        assert "python/SMOC" in created_names
        assert "python/purpose" in created_names
        assert "python/speeds" in created_names
        assert "python/glossary" in created_names
        assert "python/cheatsheet" in created_names

    def test_normalizes_name(self, obsidian, config):
        obsidian.read.side_effect = ObsidianCLIError(["read"], 1, "not found")
        result = create_subject("My Cool Subject", obsidian, config)
        assert result == "my-cool-subject"

    def test_preserves_display_name_in_content(self, obsidian, config):
        obsidian.read.side_effect = ObsidianCLIError(["read"], 1, "not found")
        create_subject("Personal Psychology", obsidian, config)

        # Check the SMOC content uses the display name
        smoc_call = obsidian.create.call_args_list[0]
        fallback = smoc_call.args[1] if len(smoc_call.args) > 1 else ""
        content = smoc_call.kwargs.get("content", fallback)
        assert "Personal Psychology" in content

    def test_rejects_existing_subject(self, obsidian, config):
        obsidian.read.return_value = "# SMOC content"
        with pytest.raises(SubjectError, match="already exists"):
            create_subject("python", obsidian, config)

    def test_rejects_invalid_name(self, obsidian, config):
        with pytest.raises(SubjectError, match="empty"):
            create_subject("", obsidian, config)

    def test_rejects_reserved_name(self, obsidian, config):
        with pytest.raises(SubjectError, match="reserved"):
            create_subject("_inbox", obsidian, config)

    def test_initializes_speed_counter(self, obsidian, config):
        obsidian.read.side_effect = ObsidianCLIError(["read"], 1, "not found")
        create_subject("python", obsidian, config)
        assert config.speed_counters["python"] == 0

    def test_preserves_existing_counters(self, obsidian, config):
        config.speed_counters["rust"] = 42
        save_config(config)

        obsidian.read.side_effect = ObsidianCLIError(["read"], 1, "not found")
        create_subject("python", obsidian, config)
        assert config.speed_counters["rust"] == 42
        assert config.speed_counters["python"] == 0


class TestListSubjects:
    def test_lists_subjects_from_search(self, obsidian, config):
        obsidian.search.return_value = "python/SMOC.md\nrust/SMOC.md\n"
        # has_speeds / has_purpose checks
        obsidian.read.return_value = "content"

        subjects = list_subjects(obsidian, config)
        assert len(subjects) == 2
        assert subjects[0].name == "python"
        assert subjects[1].name == "rust"

    def test_returns_empty_on_search_error(self, obsidian, config):
        obsidian.search.side_effect = ObsidianCLIError(["search"], 1, "error")
        assert list_subjects(obsidian, config) == []

    def test_sorted_by_name(self, obsidian, config):
        obsidian.search.return_value = "zebra/SMOC.md\nalpha/SMOC.md\n"
        obsidian.read.return_value = "content"

        subjects = list_subjects(obsidian, config)
        assert subjects[0].name == "alpha"
        assert subjects[1].name == "zebra"

    def test_detects_speeds_and_purpose(self, obsidian, config):
        obsidian.search.return_value = "python/SMOC.md\n"

        def read_side_effect(name):
            if name == "python/speeds":
                return "- S1: thought"
            if name == "python/purpose":
                raise ObsidianCLIError(["read"], 1, "not found")
            return "content"

        obsidian.read.side_effect = read_side_effect

        subjects = list_subjects(obsidian, config)
        assert subjects[0].has_speeds is True
        assert subjects[0].has_purpose is False
