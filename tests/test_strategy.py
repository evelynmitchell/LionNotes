"""Unit tests for lionnotes.strategy module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lionnotes.strategy import (
    StrategyError,
    _parse_priorities,
    add_priority,
    complete_priority,
    list_priorities,
)

SAMPLE_STRATEGY = """\
---
type: strategy
updated: "2026-01-01"
---
# Active Priorities

<!-- What should I be paying attention to right now? -->
<!-- This is an attention-direction mechanism, not a to-do list. -->

- [python] Deep-dive into decorators #strategy
- [rust] Start learning ownership model #strategy
- [python] Review async patterns #strategy
"""

EMPTY_STRATEGY = """\
---
type: strategy
updated: "2026-01-01"
---
# Active Priorities

<!-- What should I be paying attention to right now? -->
"""


class TestParsePriorities:
    def test_parses_entries(self):
        items = _parse_priorities(SAMPLE_STRATEGY)
        assert len(items) == 3

    def test_entry_fields(self):
        items = _parse_priorities(SAMPLE_STRATEGY)
        assert items[0].number == 1
        assert items[0].subject == "python"
        assert items[0].description == "Deep-dive into decorators"

    def test_second_entry(self):
        items = _parse_priorities(SAMPLE_STRATEGY)
        assert items[1].number == 2
        assert items[1].subject == "rust"
        assert items[1].description == "Start learning ownership model"

    def test_empty_content(self):
        items = _parse_priorities(EMPTY_STRATEGY)
        assert items == []

    def test_entries_without_strategy_tag(self):
        content = "- [python] No tag here\n"
        items = _parse_priorities(content)
        assert len(items) == 1
        assert items[0].description == "No tag here"

    def test_raw_line_preserved(self):
        items = _parse_priorities(SAMPLE_STRATEGY)
        assert items[0].raw_line == "- [python] Deep-dive into decorators #strategy"


class TestListPriorities:
    def test_returns_parsed_items(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_STRATEGY

        items = list_priorities(obs)

        assert len(items) == 3
        obs.read.assert_called_once_with("_strategy/active-priorities")

    def test_empty_list(self):
        obs = MagicMock()
        obs.read.return_value = EMPTY_STRATEGY

        items = list_priorities(obs)

        assert items == []


class TestAddPriority:
    def test_appends_entry(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_STRATEGY

        item = add_priority("python", "Learn metaclasses", obs)

        assert item.number == 4
        assert item.subject == "python"
        assert item.description == "Learn metaclasses"
        obs.append.assert_called_once()
        appended = obs.append.call_args[0][1]
        assert "[python]" in appended
        assert "Learn metaclasses" in appended
        assert "#strategy" in appended

    def test_first_entry(self):
        obs = MagicMock()
        obs.read.return_value = EMPTY_STRATEGY

        item = add_priority("rust", "Start with the book", obs)

        assert item.number == 1

    def test_empty_subject_raises(self):
        obs = MagicMock()
        with pytest.raises(StrategyError, match="Subject cannot be empty"):
            add_priority("", "desc", obs)

    def test_empty_description_raises(self):
        obs = MagicMock()
        with pytest.raises(StrategyError, match="Description cannot be empty"):
            add_priority("python", "", obs)

    def test_strips_whitespace(self):
        obs = MagicMock()
        obs.read.return_value = EMPTY_STRATEGY

        item = add_priority("  python  ", "  learn stuff  ", obs)

        assert item.subject == "python"
        assert item.description == "learn stuff"


class TestCompletePriority:
    def test_removes_entry(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_STRATEGY

        with patch("lionnotes.strategy._write_note") as mock_write:
            removed = complete_priority(2, obs)

        assert removed.number == 2
        assert removed.subject == "rust"

        # Verify the rewritten content doesn't contain the removed line
        written_content = mock_write.call_args[0][1]
        assert "rust" not in written_content
        assert "python" in written_content

    def test_removes_first_entry(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_STRATEGY

        with patch("lionnotes.strategy._write_note") as mock_write:
            removed = complete_priority(1, obs)

        assert removed.subject == "python"
        assert removed.description == "Deep-dive into decorators"

        written_content = mock_write.call_args[0][1]
        assert "Deep-dive into decorators" not in written_content
        # Other entries still present
        assert "rust" in written_content
        assert "Review async patterns" in written_content

    def test_removes_last_entry(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_STRATEGY

        with patch("lionnotes.strategy._write_note"):
            removed = complete_priority(3, obs)

        assert removed.description == "Review async patterns"

    def test_invalid_number_zero(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_STRATEGY

        with pytest.raises(StrategyError, match="Invalid item number 0"):
            complete_priority(0, obs)

    def test_invalid_number_too_high(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_STRATEGY

        with pytest.raises(StrategyError, match="Invalid item number 4"):
            complete_priority(4, obs)

    def test_invalid_number_negative(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_STRATEGY

        with pytest.raises(StrategyError, match="Invalid item number -1"):
            complete_priority(-1, obs)

    def test_empty_list_raises(self):
        obs = MagicMock()
        obs.read.return_value = EMPTY_STRATEGY

        with pytest.raises(
            StrategyError, match="No active priorities to complete"
        ):
            complete_priority(1, obs)

    def test_writes_to_correct_note(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_STRATEGY

        with patch("lionnotes.strategy._write_note") as mock_write:
            complete_priority(1, obs)

        mock_write.assert_called_once()
        assert mock_write.call_args[0][0] == "_strategy/active-priorities"
