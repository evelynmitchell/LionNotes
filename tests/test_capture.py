"""Tests for lionnotes.capture."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lionnotes.capture import (
    CaptureError,
    capture_speed,
    format_speed_entry,
)
from lionnotes.config import Config, save_config
from lionnotes.obsidian import ObsidianCLIError


@pytest.fixture()
def config(tmp_path: Path) -> Config:
    vault = tmp_path / "vault"
    vault.mkdir()
    cfg = Config(vault_path=str(vault), speed_counters={"python": 47})
    save_config(cfg)
    return cfg


@pytest.fixture()
def obsidian() -> MagicMock:
    mock = MagicMock()
    # Default: subject exists (SMOC readable)
    mock.read.return_value = "# SMOC"
    return mock


class TestFormatSpeedEntry:
    def test_minimal(self):
        assert format_speed_entry(1, "hello") == "- S1: hello"

    def test_with_hint(self):
        result = format_speed_entry(1, "hello", hint="debugging")
        assert result == "- S1: (context: debugging) hello"

    def test_with_type(self):
        result = format_speed_entry(1, "hello", thought_type="observation")
        assert result == "- S1: hello #thought/observation"

    def test_full(self):
        result = format_speed_entry(
            48, "generators are lazy", hint="OOM debug", thought_type="principle"
        )
        assert result == (
            "- S48: (context: OOM debug) generators are lazy #thought/principle"
        )


class TestCaptureToSubject:
    def test_appends_to_subject_speeds(self, obsidian, config):
        entry = capture_speed(
            "generators are lazy",
            obsidian,
            config,
            subject="python",
        )
        assert "S48:" in entry
        assert "generators are lazy" in entry
        obsidian.append.assert_called_once_with("python/speeds", entry)

    def test_increments_counter(self, obsidian, config):
        capture_speed("thought one", obsidian, config, subject="python")
        assert config.speed_counters["python"] == 48

        capture_speed("thought two", obsidian, config, subject="python")
        assert config.speed_counters["python"] == 49

    def test_with_hint_and_type(self, obsidian, config):
        entry = capture_speed(
            "memory issue",
            obsidian,
            config,
            subject="python",
            hint="debugging",
            thought_type="observation",
        )
        assert "(context: debugging)" in entry
        assert "#thought/observation" in entry

    def test_rejects_nonexistent_subject(self, obsidian, config):
        obsidian.read.side_effect = ObsidianCLIError(["read"], 1, "not found")
        with pytest.raises(CaptureError, match="does not exist"):
            capture_speed("thought", obsidian, config, subject="nope")

    def test_saves_config_after_capture(self, obsidian, config):
        capture_speed("thought", obsidian, config, subject="python")
        # Verify config was saved by reloading
        from lionnotes.config import load_config

        reloaded = load_config(config.config_path)
        assert reloaded.speed_counters["python"] == 48


class TestCaptureToInbox:
    def test_appends_to_inbox(self, obsidian, config):
        entry = capture_speed("random thought", obsidian, config)
        assert "random thought" in entry
        obsidian.append.assert_called_once_with("_inbox/unsorted", entry)

    def test_no_speed_number(self, obsidian, config):
        entry = capture_speed("random thought", obsidian, config)
        assert "S" not in entry or "S1" not in entry
        assert entry.startswith("- ")

    def test_with_hint_as_subject_guess(self, obsidian, config):
        entry = capture_speed("some thought", obsidian, config, hint="python")
        assert "[python?]" in entry

    def test_with_type(self, obsidian, config):
        entry = capture_speed(
            "why does X?",
            obsidian,
            config,
            thought_type="question",
        )
        assert "#thought/question" in entry

    def test_does_not_change_counter(self, obsidian, config):
        old_counters = dict(config.speed_counters)
        capture_speed("thought", obsidian, config)
        assert config.speed_counters == old_counters


class TestValidation:
    def test_empty_content_rejected(self, obsidian, config):
        with pytest.raises(CaptureError, match="empty"):
            capture_speed("", obsidian, config)

    def test_whitespace_content_rejected(self, obsidian, config):
        with pytest.raises(CaptureError, match="empty"):
            capture_speed("   ", obsidian, config)

    def test_strips_content(self, obsidian, config):
        entry = capture_speed("  hello  ", obsidian, config)
        assert "  hello  " not in entry
        assert "hello" in entry

    def test_invalid_thought_type(self, obsidian, config):
        with pytest.raises(CaptureError, match="Unknown thought type"):
            capture_speed(
                "thought",
                obsidian,
                config,
                thought_type="made_up",
            )

    def test_valid_thought_types_accepted(self, obsidian, config):
        for tt in [
            "observation",
            "question",
            "goal",
            "problem",
            "action",
            "principle",
            "warning",
            "starting-point",
            "connection",
            "idea",
        ]:
            entry = capture_speed(
                f"thought about {tt}",
                obsidian,
                config,
                thought_type=tt,
            )
            assert f"#thought/{tt}" in entry
