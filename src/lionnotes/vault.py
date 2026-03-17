"""Vault state helpers for LionNotes."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lionnotes.obsidian import ObsidianCLI, ObsidianCLIError

# Speed entry pattern: - S[N]: ...
_SPEED_PATTERN = re.compile(r"^- S(\d+):\s")
# Mapped marker at end of line: [→ POI-N]
_MAPPED_PATTERN = re.compile(r"\[→ POI-\d+\]\s*$")

# Reserved names that cannot be used as subjects
RESERVED_NAMES: frozenset[str] = frozenset(
    {
        "gsmoc",
        "subject registry",
        "global aliases",
    }
)

# Prefixes that are reserved for internal use
RESERVED_PREFIXES: tuple[str, ...] = ("_",)


@dataclass
class SpeedEntry:
    """A parsed speed thought entry."""

    number: int
    raw_line: str
    mapped: bool


def parse_speed_entries(text: str) -> list[SpeedEntry]:
    """Parse speed entries from a speeds.md file.

    Only lines matching ``- S[N]: ...`` are recognized.
    Other bullet points or content lines are ignored.
    An entry is considered mapped if it ends with ``[→ POI-N]``.
    """
    entries = []
    for line in text.splitlines():
        match = _SPEED_PATTERN.match(line.strip())
        if match:
            number = int(match.group(1))
            mapped = bool(_MAPPED_PATTERN.search(line))
            entries.append(
                SpeedEntry(
                    number=number,
                    raw_line=line.strip(),
                    mapped=mapped,
                )
            )
    return entries


def count_unmapped_speeds(subject: str, obsidian: ObsidianCLI) -> int:
    """Count unmapped speed entries for a subject."""
    try:
        content = obsidian.read(f"{subject}/speeds")
    except ObsidianCLIError:
        return 0
    entries = parse_speed_entries(content)
    return sum(1 for e in entries if not e.mapped)


def subject_exists(name: str, obsidian: ObsidianCLI) -> bool:
    """Check if a subject exists (has a SMOC.md).

    Raises ObsidianCLIError for operational failures (permissions, etc.)
    that are not simple "not found" errors.
    """
    try:
        obsidian.read(f"{name}/SMOC")
        return True
    except ObsidianCLIError as exc:
        lower = exc.stderr.lower()
        if "not found" in lower or "does not exist" in lower or "no such" in lower:
            return False
        raise


def validate_subject_name(name: str) -> str | None:
    """Validate a subject name, return error message or None if valid."""
    stripped = name.strip()
    if not stripped:
        return "Subject name cannot be empty."

    lower = stripped.lower()

    if lower in RESERVED_NAMES:
        return f"'{stripped}' is a reserved name."

    for prefix in RESERVED_PREFIXES:
        if lower.startswith(prefix):
            return (
                f"Subject names cannot start with '{prefix}' "
                "(reserved for internal use)."
            )

    # Reject path traversal patterns
    if "/" in stripped or "\\" in stripped:
        return "Subject name cannot contain path separators."

    if stripped in (".", "..") or stripped.startswith("../") or "/.." in stripped:
        return "Subject name cannot contain path traversal sequences."

    # Check for filesystem-problematic characters
    bad_chars = set('<>:"|?*')
    found = [c for c in stripped if c in bad_chars]
    if found:
        return (
            f"Subject name contains invalid characters: "
            f"{', '.join(repr(c) for c in found)}"
        )

    if len(stripped) > 100:
        return "Subject name is too long (max 100 characters)."

    return None


def normalize_subject_name(name: str) -> str:
    """Normalize a subject name to lowercase with hyphens."""
    return name.strip().lower().replace(" ", "-")
