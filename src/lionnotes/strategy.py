"""Priority management for LionNotes strategy system."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lionnotes.maps import _write_note
from lionnotes.obsidian import ObsidianCLI

STRATEGY_NOTE = "_strategy/active-priorities"

_ENTRY_RE = re.compile(
    r"^-\s+\[([^\]]+)\]\s+(.+?)(?:\s+#strategy)?\s*$",
)


class StrategyError(Exception):
    """Raised for strategy-related errors."""


@dataclass
class StrategyItem:
    """A single priority entry."""

    number: int
    subject: str
    description: str
    raw_line: str


def _parse_priorities(content: str) -> list[StrategyItem]:
    """Parse priority entries from the active-priorities note content."""
    items: list[StrategyItem] = []
    number = 0
    for line in content.splitlines():
        stripped = line.strip()
        m = _ENTRY_RE.match(stripped)
        if m:
            number += 1
            items.append(
                StrategyItem(
                    number=number,
                    subject=m.group(1).strip(),
                    description=m.group(2).strip(),
                    raw_line=stripped,
                )
            )
    return items


def list_priorities(obsidian: ObsidianCLI) -> list[StrategyItem]:
    """Parse active-priorities.md and return all priority items."""
    content = obsidian.read(STRATEGY_NOTE)
    return _parse_priorities(content)


def add_priority(
    subject: str,
    description: str,
    obsidian: ObsidianCLI,
) -> StrategyItem:
    """Append a new priority entry to active-priorities.md.

    Returns the created StrategyItem.
    """
    if not subject.strip():
        raise StrategyError("Subject cannot be empty.")
    if not description.strip():
        raise StrategyError("Description cannot be empty.")

    # Determine number by reading existing entries
    content = obsidian.read(STRATEGY_NOTE)
    existing = _parse_priorities(content)
    number = len(existing) + 1

    entry_line = f"- [{subject.strip()}] {description.strip()} #strategy"
    obsidian.append(STRATEGY_NOTE, f"\n{entry_line}")

    return StrategyItem(
        number=number,
        subject=subject.strip(),
        description=description.strip(),
        raw_line=entry_line,
    )


def complete_priority(
    item_number: int,
    obsidian: ObsidianCLI,
) -> StrategyItem:
    """Remove a priority by its number (1-based).

    Uses the rename-aside-then-create pattern to rewrite the note
    without the completed entry.

    Returns the removed StrategyItem.
    Raises StrategyError if the item number is invalid.
    """
    content = obsidian.read(STRATEGY_NOTE)
    items = _parse_priorities(content)

    if not items:
        raise StrategyError("No active priorities to complete.")

    if item_number < 1 or item_number > len(items):
        raise StrategyError(
            f"Invalid item number {item_number}. "
            f"Valid range: 1–{len(items)}."
        )

    removed = items[item_number - 1]

    # Rebuild content without the removed line
    lines = content.splitlines()
    new_lines = []
    removed_count = 0
    for line in lines:
        stripped = line.strip()
        if _ENTRY_RE.match(stripped):
            removed_count += 1
            if removed_count == item_number:
                continue  # skip this line
        new_lines.append(line)

    new_content = "\n".join(new_lines)
    _write_note(STRATEGY_NOTE, new_content, obsidian)

    return removed
