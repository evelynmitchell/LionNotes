"""Tests for lionnotes.capture module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lionnotes.capture import _format_speed_entry, capture_speed
from lionnotes.config import Config
from lionnotes.obsidian import ObsidianCLIError
from lionnotes.subjects import SubjectError


class TestFormatSpeedEntry:
    def test_basic(self):
        result = _format_speed_entry(1, "A thought")
        assert result == "- S1: A thought"

    def test_with_hint(self):
        result = _format_speed_entry(5, "A thought", hint="motivation")
        assert result == "- S5: (context: motivation) A thought"

    def test_with_type(self):
        result = _format_speed_entry(3, "A thought", thought_type="observation")
        assert result == "- S3: A thought #thought/observation"

    def test_with_hint_and_type(self):
        result = _format_speed_entry(
            10,
            "A thought",
            hint="work",
            thought_type="question",
        )
        assert result == "- S10: (context: work) A thought #thought/question"

    def test_normalizes_type_with_hash(self):
        result = _format_speed_entry(1, "A thought", thought_type="#observation")
        assert result == "- S1: A thought #thought/observation"

    def test_normalizes_type_with_prefix(self):
        result = _format_speed_entry(1, "A thought", thought_type="thought/observation")
        assert result == "- S1: A thought #thought/observation"

    def test_empty_type_after_normalization_skipped(self):
        """'#' or 'thought/' normalizes to empty — no tag appended."""
        expected = "- S1: A thought"
        assert _format_speed_entry(1, "A thought", thought_type="#") == expected
        assert (
            _format_speed_entry(
                1,
                "A thought",
                thought_type="thought/",
            )
            == expected
        )
        assert (
            _format_speed_entry(
                1,
                "A thought",
                thought_type="# ",
            )
            == expected
        )


class TestCaptureSpeed:
    def _make_config(self, tmp_path):
        config = Config(vault_path=str(tmp_path))
        config_path = tmp_path / ".lionnotes.toml"
        config_path.write_text('vault_path = "' + str(tmp_path) + '"\n')
        return config

    def test_capture_to_subject(self, tmp_path):
        obs = MagicMock()
        obs.read.return_value = "# speeds"
        config = self._make_config(tmp_path)

        entry = capture_speed("My thought", obs, config, subject="my-topic")

        assert entry == "- S1: My thought"
        obs.append.assert_called_once()
        assert "my-topic/speeds" in obs.append.call_args.args[0]
        assert config.speed_counters["my-topic"] == 1

    def test_capture_to_inbox(self, tmp_path):
        obs = MagicMock()
        config = self._make_config(tmp_path)

        entry = capture_speed("Pan-subject thought", obs, config)

        assert entry == "- S1: Pan-subject thought"
        obs.append.assert_called_once()
        assert "_inbox/unsorted" in obs.append.call_args.args[0]

    def test_counter_increments(self, tmp_path):
        obs = MagicMock()
        obs.read.return_value = "# speeds"
        config = self._make_config(tmp_path)

        capture_speed("First", obs, config, subject="my-topic")
        capture_speed("Second", obs, config, subject="my-topic")
        capture_speed("Third", obs, config, subject="my-topic")

        assert config.speed_counters["my-topic"] == 3
        # Verify the entries have correct numbers
        calls = obs.append.call_args_list
        assert "S1:" in calls[0].args[1]
        assert "S2:" in calls[1].args[1]
        assert "S3:" in calls[2].args[1]

    def test_capture_with_hint_and_type(self, tmp_path):
        obs = MagicMock()
        obs.read.return_value = "# speeds"
        config = self._make_config(tmp_path)

        entry = capture_speed(
            "My thought",
            obs,
            config,
            subject="my-topic",
            hint="work",
            thought_type="observation",
        )

        assert "(context: work)" in entry
        assert "#thought/observation" in entry

    def test_missing_subject_raises(self, tmp_path):
        """No SMOC means the subject doesn't exist at all."""
        obs = MagicMock()
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")
        config = self._make_config(tmp_path)

        with pytest.raises(SubjectError, match="does not exist"):
            capture_speed("A thought", obs, config, subject="nonexistent")

    def test_missing_speeds_file_raises(self, tmp_path):
        """SMOC exists but speeds file is missing."""
        obs = MagicMock()

        def read_side_effect(path):
            if "SMOC" in path:
                return "# SMOC content"
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side_effect
        config = self._make_config(tmp_path)

        with pytest.raises(SubjectError, match="missing its speeds"):
            capture_speed(
                "A thought",
                obs,
                config,
                subject="my-topic",
            )

    def test_empty_content_raises(self, tmp_path):
        obs = MagicMock()
        config = self._make_config(tmp_path)

        with pytest.raises(ValueError, match="cannot be empty"):
            capture_speed("", obs, config)

    def test_whitespace_only_content_raises(self, tmp_path):
        obs = MagicMock()
        config = self._make_config(tmp_path)

        with pytest.raises(ValueError, match="cannot be empty"):
            capture_speed("   ", obs, config)

    def test_normalizes_subject_name(self, tmp_path):
        obs = MagicMock()
        obs.read.return_value = "# speeds"
        config = self._make_config(tmp_path)

        entry = capture_speed(
            "A thought",
            obs,
            config,
            subject="My Topic",
        )

        assert entry == "- S1: A thought"
        obs.append.assert_called_once()
        assert "my-topic/speeds" in obs.append.call_args.args[0]
        assert config.speed_counters["my-topic"] == 1

    def test_reraises_non_not_found_errors(self, tmp_path):
        obs = MagicMock()
        obs.read.side_effect = ObsidianCLIError(
            ["read"],
            -1,
            "Command timed out",
        )
        config = self._make_config(tmp_path)

        with pytest.raises(ObsidianCLIError, match="timed out"):
            capture_speed("A thought", obs, config, subject="my-topic")

    def test_empty_string_subject_raises(self, tmp_path):
        """Empty string subject should error, not silently go to inbox."""
        obs = MagicMock()
        config = self._make_config(tmp_path)

        with pytest.raises(SubjectError, match="cannot be empty"):
            capture_speed("A thought", obs, config, subject="")
