"""Vault state helpers for LionNotes."""

from __future__ import annotations

import re
from pathlib import Path

from lionnotes.config import Config
from lionnotes.obsidian import ObsidianCLI, ObsidianCLIError


def get_vault_path(config: Config) -> Path:
    """Resolve and return the vault path from config."""
    return Path(config.vault_path).resolve()


def subject_exists(name: str, obsidian: ObsidianCLI) -> bool:
    """Check if a subject folder exists by trying to read its SMOC.

    Raises ObsidianCLIError for non-"not found" failures (e.g. timeouts).
    """
    try:
        obsidian.read(f"{name}/SMOC")
        return True
    except ObsidianCLIError as exc:
        if exc.is_not_found:
            return False
        raise


_MAPPED_PATTERN = re.compile(r"\[→\s*POI-\d+\]")


def count_unmapped_speeds(subject: str, obsidian: ObsidianCLI) -> int:
    """Parse a subject's speeds.md and count entries without a POI mapping.

    Returns 0 if the speeds file doesn't exist.
    """
    try:
        content = obsidian.read(f"{subject}/speeds")
    except ObsidianCLIError:
        return 0

    count = 0
    for line in content.splitlines():
        stripped = line.strip()
        if (
            stripped.startswith("- S")
            and ":" in stripped
            and not _MAPPED_PATTERN.search(stripped)
        ):
            count += 1
    return count
