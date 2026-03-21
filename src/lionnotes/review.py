"""Triage workflow for LionNotes — review and map speed thoughts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lionnotes.config import Config, next_speed_number, save_config
from lionnotes.obsidian import ObsidianCLI, ObsidianCLIError


class ReviewError(Exception):
    """Raised for review/triage errors."""


# -- Data structures ---------------------------------------------------------


@dataclass
class SpeedEntry:
    """A parsed speed thought entry."""

    number: int
    content: str
    context: str | None = None
    thought_type: str | None = None
    raw_line: str = ""
    mapped_to: str | None = None

    @property
    def is_mapped(self) -> bool:
        return self.mapped_to is not None


@dataclass
class InboxEntry:
    """A parsed inbox entry."""

    number: int
    content: str
    context: str | None = None
    thought_type: str | None = None
    raw_line: str = ""


# -- Parsing -----------------------------------------------------------------

_SPEED_RE = re.compile(
    r"^- S(\d+):\s*"
    r"(?:\(context:\s*([^)]+)\)\s*)?"
    r"(.*?)"
    r"(?:\s+(#thought/\S+))?"
    r"(?:\s+\[→\s*(POI-\d+)\])?"
    r"\s*$",
)


def _parse_speed_line(line: str) -> SpeedEntry | None:
    """Parse a single speed entry line, or None if not a speed line."""
    m = _SPEED_RE.match(line.strip())
    if not m:
        return None
    number = int(m.group(1))
    context = m.group(2)
    content = m.group(3).strip()
    thought_type = m.group(4)
    mapped_to = m.group(5)
    return SpeedEntry(
        number=number,
        content=content,
        context=context,
        thought_type=thought_type,
        raw_line=line.strip(),
        mapped_to=mapped_to,
    )


def _parse_inbox_line(line: str) -> InboxEntry | None:
    """Parse an inbox entry line."""
    # Inbox uses the same format as speeds
    entry = _parse_speed_line(line)
    if entry is None:
        return None
    return InboxEntry(
        number=entry.number,
        content=entry.content,
        context=entry.context,
        thought_type=entry.thought_type,
        raw_line=entry.raw_line,
    )


# -- Core functions ----------------------------------------------------------


def get_unmapped_speeds(
    subject: str,
    obsidian: ObsidianCLI,
) -> list[SpeedEntry]:
    """Parse a subject's speeds and return unmapped entries.

    Returns an empty list if the speeds file doesn't exist.
    """
    try:
        content = obsidian.read(f"{subject}/speeds")
    except ObsidianCLIError as exc:
        if exc.is_not_found:
            return []
        raise

    entries = []
    for line in content.splitlines():
        entry = _parse_speed_line(line)
        if entry is not None and not entry.is_mapped:
            entries.append(entry)
    return entries


_MAPPED_SUFFIX_RE = re.compile(r"\[→\s*POI-\d+\]")


def map_speed(
    subject: str,
    speed_num: int,
    poi_ref: str,
    obsidian: ObsidianCLI,
) -> None:
    """Mark a speed as mapped by appending ``[→ POI-N]`` suffix.

    Args:
        subject: Subject name.
        speed_num: Speed entry number to mark.
        poi_ref: POI reference, e.g. ``POI-3`` or just ``3``.
        obsidian: ObsidianCLI instance.

    Raises:
        ReviewError: If speed entry not found or already mapped.
    """
    # Normalize poi_ref
    if poi_ref.isdigit() or not poi_ref.startswith("POI-"):
        poi_ref = f"POI-{poi_ref}"

    content = obsidian.read(f"{subject}/speeds")
    lines = content.splitlines()
    found = False

    for i, line in enumerate(lines):
        entry = _parse_speed_line(line)
        if entry is not None and entry.number == speed_num:
            if entry.is_mapped:
                raise ReviewError(
                    f"Speed S{speed_num} is already mapped to {entry.mapped_to}.",
                )
            lines[i] = line.rstrip() + f" [→ {poi_ref}]"
            found = True
            break

    if not found:
        raise ReviewError(f"Speed entry S{speed_num} not found in {subject}/speeds.")

    new_content = "\n".join(lines)
    # Use the same write pattern as maps.py
    from lionnotes.maps import _write_note

    _write_note(f"{subject}/speeds", new_content, obsidian)


def triage_inbox(obsidian: ObsidianCLI) -> list[InboxEntry]:
    """List inbox entries for assignment.

    Returns an empty list if the inbox file doesn't exist.
    """
    try:
        content = obsidian.read("_inbox/unsorted")
    except ObsidianCLIError as exc:
        if exc.is_not_found:
            return []
        raise

    entries = []
    for line in content.splitlines():
        entry = _parse_inbox_line(line)
        if entry is not None:
            entries.append(entry)
    return entries


def assign_inbox_entry(
    entry: InboxEntry,
    target_subject: str,
    obsidian: ObsidianCLI,
    config: Config,
) -> SpeedEntry:
    """Move an inbox entry to a target subject's speeds.

    Removes the entry from ``_inbox/unsorted`` and appends it to the
    target subject's speeds with a renumbered sequence number.

    Returns the new SpeedEntry with the target subject's numbering.
    """
    from lionnotes.capture import _format_speed_entry
    from lionnotes.maps import _write_note

    # Read and remove from inbox
    inbox_content = obsidian.read("_inbox/unsorted")
    inbox_lines = inbox_content.splitlines()
    new_inbox_lines = []
    removed = False
    for line in inbox_lines:
        parsed = _parse_inbox_line(line)
        if parsed is not None and parsed.number == entry.number and not removed:
            removed = True
            continue
        new_inbox_lines.append(line)

    if not removed:
        raise ReviewError(
            f"Inbox entry S{entry.number} not found in _inbox/unsorted.",
        )

    # Write updated inbox
    _write_note("_inbox/unsorted", "\n".join(new_inbox_lines), obsidian)

    # Append to target subject's speeds with new number
    new_number = next_speed_number(config, target_subject)
    new_entry_line = _format_speed_entry(
        new_number,
        entry.content,
        entry.context,
        entry.thought_type,
    )
    obsidian.append(f"{target_subject}/speeds", f"\n{new_entry_line}")
    save_config(config)

    return SpeedEntry(
        number=new_number,
        content=entry.content,
        context=entry.context,
        thought_type=entry.thought_type,
        raw_line=new_entry_line,
    )
