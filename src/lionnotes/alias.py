"""Abbreviation management for LionNotes alias system."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lionnotes.maps import _write_note
from lionnotes.obsidian import ObsidianCLI

GLOBAL_ALIASES_NOTE = "Global Aliases"
GLOSSARY_NOTE_SUFFIX = "glossary"

_ALIAS_RE = re.compile(
    r"^-\s+\*\*([^*]+)\*\*:\s+(.+?)\s*$",
)


class AliasError(Exception):
    """Raised for alias-related errors."""


@dataclass
class Alias:
    """A single alias entry."""

    abbreviation: str
    expansion: str
    scope: str  # "global" or subject name


def _note_path(subject: str | None) -> str:
    """Return the note path for aliases."""
    if subject is None:
        return GLOBAL_ALIASES_NOTE
    return f"{subject}/{GLOSSARY_NOTE_SUFFIX}"


def _parse_aliases(content: str, scope: str) -> list[Alias]:
    """Parse alias entries from note content."""
    aliases: list[Alias] = []
    for line in content.splitlines():
        stripped = line.strip()
        m = _ALIAS_RE.match(stripped)
        if m:
            aliases.append(
                Alias(
                    abbreviation=m.group(1).strip(),
                    expansion=m.group(2).strip(),
                    scope=scope,
                )
            )
    return aliases


def list_aliases(
    obsidian: ObsidianCLI,
    subject: str | None = None,
) -> list[Alias]:
    """Parse aliases from the global or per-subject note.

    Args:
        obsidian: ObsidianCLI instance.
        subject: Subject name for per-subject aliases, or None for global.

    Returns:
        List of Alias entries.
    """
    path = _note_path(subject)
    scope = subject if subject else "global"
    content = obsidian.read(path)
    return _parse_aliases(content, scope)


def set_alias(
    abbr: str,
    expansion: str,
    obsidian: ObsidianCLI,
    subject: str | None = None,
) -> None:
    """Add or update an alias.

    If the abbreviation already exists, rewrites the note with the
    updated expansion (rename-aside-then-create). If new, appends.

    Args:
        abbr: The abbreviation.
        expansion: The expanded form.
        obsidian: ObsidianCLI instance.
        subject: Subject name for per-subject, or None for global.
    """
    if not abbr.strip():
        raise AliasError("Abbreviation cannot be empty.")
    if not expansion.strip():
        raise AliasError("Expansion cannot be empty.")

    abbr = abbr.strip()
    expansion = expansion.strip()
    path = _note_path(subject)
    content = obsidian.read(path)
    scope = subject if subject else "global"
    existing = _parse_aliases(content, scope)

    # Check if abbreviation already exists
    match = None
    for alias in existing:
        if alias.abbreviation.lower() == abbr.lower():
            match = alias
            break

    if match is not None:
        # Update: rewrite the note with the new expansion
        lines = content.splitlines()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            m = _ALIAS_RE.match(stripped)
            if m and m.group(1).strip().lower() == abbr.lower():
                new_lines.append(f"- **{abbr}**: {expansion}")
            else:
                new_lines.append(line)
        new_content = "\n".join(new_lines)
        _write_note(path, new_content, obsidian)
    else:
        # New alias: append
        entry_line = f"\n- **{abbr}**: {expansion}"
        obsidian.append(path, entry_line)


def remove_alias(
    abbr: str,
    obsidian: ObsidianCLI,
    subject: str | None = None,
) -> None:
    """Remove an alias by abbreviation.

    Uses rename-aside-then-create to rewrite the note without the entry.

    Args:
        abbr: The abbreviation to remove.
        obsidian: ObsidianCLI instance.
        subject: Subject name for per-subject, or None for global.

    Raises:
        AliasError: If the abbreviation is not found.
    """
    if not abbr.strip():
        raise AliasError("Abbreviation cannot be empty.")

    abbr = abbr.strip()
    path = _note_path(subject)
    content = obsidian.read(path)
    scope = subject if subject else "global"
    existing = _parse_aliases(content, scope)

    found = any(a.abbreviation.lower() == abbr.lower() for a in existing)
    if not found:
        raise AliasError(f"Alias '{abbr}' not found.")

    # Rewrite without the removed entry
    lines = content.splitlines()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        m = _ALIAS_RE.match(stripped)
        if m and m.group(1).strip().lower() == abbr.lower():
            continue  # skip this line
        new_lines.append(line)

    new_content = "\n".join(new_lines)
    _write_note(path, new_content, obsidian)
