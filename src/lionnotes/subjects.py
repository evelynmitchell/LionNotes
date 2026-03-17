"""Subject management for LionNotes."""

from __future__ import annotations

from dataclasses import dataclass

from lionnotes.config import Config, save_config
from lionnotes.obsidian import ObsidianCLI, ObsidianCLIError
from lionnotes.templates import render
from lionnotes.vault import (
    normalize_subject_name,
    validate_subject_name,
)


class SubjectError(Exception):
    """Error related to subject operations."""


@dataclass
class SubjectInfo:
    """Summary info for a subject."""

    name: str
    has_speeds: bool = False
    has_purpose: bool = False


def create_subject(
    name: str,
    obsidian: ObsidianCLI,
    config: Config,
) -> str:
    """Create a new subject with its folder structure.

    Returns the normalized subject name.

    Raises:
        SubjectError: If the name is invalid or subject already exists.
    """
    # Validate
    error = validate_subject_name(name)
    if error:
        raise SubjectError(error)

    normalized = normalize_subject_name(name)

    # Check for existing folder (LionNotes subject or otherwise)
    try:
        obsidian.read(f"{normalized}/SMOC")
        raise SubjectError(f"Subject '{normalized}' already exists.")
    except ObsidianCLIError:
        pass  # Good — doesn't exist yet

    # Use the display name (original casing) in templates
    display_name = name.strip()

    # Create subject files
    files = [
        (f"{normalized}/SMOC", render("smoc", subject=display_name)),
        (f"{normalized}/purpose", render("purpose", subject=display_name)),
        (
            f"{normalized}/speeds",
            render("speed-page", subject=display_name),
        ),
        (
            f"{normalized}/glossary",
            render("glossary", subject=display_name),
        ),
        (
            f"{normalized}/cheatsheet",
            render("cheatsheet", subject=display_name),
        ),
    ]

    for note_name, content in files:
        obsidian.create(note_name, content=content)

    # Initialize speed counter
    config.speed_counters.setdefault(normalized, 0)
    save_config(config)

    return normalized


def list_subjects(
    obsidian: ObsidianCLI,
    config: Config,
) -> list[SubjectInfo]:
    """List all subjects in the vault.

    Scans for folders that contain a SMOC.md file.
    """
    # Use obsidian search to find all SMOC files
    try:
        results = obsidian.search("type: smoc")
    except ObsidianCLIError:
        return []

    subjects = []
    for line in results.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Results may contain paths like "python/SMOC.md" or "python/SMOC"
        # Extract the subject name (folder part before /SMOC)
        if "/SMOC" in line:
            subject_name = line.split("/SMOC")[0]
            # Strip any leading path indicators
            subject_name = subject_name.lstrip("./")
            if subject_name:
                info = SubjectInfo(name=subject_name)
                # Check for speeds
                try:
                    obsidian.read(f"{subject_name}/speeds")
                    info.has_speeds = True
                except ObsidianCLIError:
                    pass
                # Check for purpose
                try:
                    obsidian.read(f"{subject_name}/purpose")
                    info.has_purpose = True
                except ObsidianCLIError:
                    pass
                subjects.append(info)

    return sorted(subjects, key=lambda s: s.name)
