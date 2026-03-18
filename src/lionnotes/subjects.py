"""Subject CRUD operations for LionNotes."""

from __future__ import annotations

import re

from lionnotes.config import Config, save_config
from lionnotes.obsidian import ObsidianCLI, ObsidianCLIError
from lionnotes.templates import render


class SubjectError(Exception):
    """Raised for subject-related errors."""


# Reserved top-level names that cannot be used as subjects
# Stored in normalized form (lowercase, hyphens) to match after normalization
_RESERVED_NAMES = frozenset(
    {
        "_inbox",
        "_strategy",
        "_templates",
        "gsmoc",
        "subject-registry",
        "global-aliases",
    }
)

# Only allow lowercase letters, digits, and hyphens
_VALID_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


def normalize_subject_name(name: str) -> str:
    """Normalize a subject name: lowercase, spaces to hyphens, strip.

    Raises SubjectError if the result is invalid.
    """
    normalized = name.strip().lower().replace(" ", "-")

    # Remove consecutive hyphens
    while "--" in normalized:
        normalized = normalized.replace("--", "-")

    if not normalized:
        raise SubjectError("Subject name cannot be empty.")

    if normalized in _RESERVED_NAMES:
        raise SubjectError(
            f"'{normalized}' is a reserved name and cannot be used as a subject."
        )

    if not _VALID_NAME_PATTERN.match(normalized):
        raise SubjectError(
            f"Invalid subject name '{normalized}'. "
            "Use only lowercase letters, digits, and hyphens."
        )

    return normalized


def create_subject(
    name: str, obsidian: ObsidianCLI, config: Config
) -> str:
    """Create a new subject with its folder structure.

    Creates: SMOC, purpose, speeds, glossary stubs.
    Returns the normalized subject name.
    Raises SubjectError if subject already exists or name is invalid.
    """
    normalized = normalize_subject_name(name)

    # Check if subject already exists
    try:
        obsidian.read(f"{normalized}/SMOC")
        raise SubjectError(f"Subject '{normalized}' already exists.")
    except ObsidianCLIError as exc:
        if not exc.is_not_found:
            raise  # Re-raise real errors (timeouts, permissions, etc.)

    # Create the subject files
    files = [
        (f"{normalized}/SMOC", render("smoc", subject=normalized)),
        (f"{normalized}/purpose", render("purpose", subject=normalized)),
        (f"{normalized}/speeds", render("speed-page", subject=normalized)),
        (f"{normalized}/glossary", render("glossary", subject=normalized)),
    ]

    for note_name, content in files:
        obsidian.create(note_name, content=content)

    # Initialize speed counter
    config.speed_counters[normalized] = 0
    save_config(config)

    return normalized


def list_subjects(
    obsidian: ObsidianCLI, *, limit: int = 200,
) -> list[str]:
    """List all subjects in the vault by searching for SMOC notes.

    Returns a sorted list of subject names.
    *limit* controls the maximum number of search results fetched.
    """
    try:
        results = obsidian.search("type: smoc", limit=limit)
    except ObsidianCLIError:
        return []

    subjects = []
    for line in results.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Results typically contain file paths like "subject-name/SMOC.md"
        # Extract the subject name (directory part)
        if "/SMOC" in line:
            subject = line.split("/SMOC")[0]
            # Strip any leading path or formatting characters
            subject = subject.lstrip("- ").strip()
            if subject and not subject.startswith("_"):
                subjects.append(subject)

    return sorted(set(subjects))
