"""Tier management for LionNotes cache system.

Implements subject-level tiers (carry-about / common-store / archive)
from Lion Kimbro's "Caches/Binders" concept. Tier is stored as a
frontmatter property on the subject's SMOC note.
"""

from __future__ import annotations

from lionnotes.obsidian import ObsidianCLI, ObsidianCLIError
from lionnotes.subjects import list_subjects, normalize_subject_name

VALID_TIERS = ("carry-about", "common-store", "archive")
DEFAULT_TIER = "carry-about"
TIER_PROPERTY = "tier"


class CacheError(Exception):
    """Raised for cache/tier-related errors."""


def get_tier(subject: str, obsidian: ObsidianCLI) -> str:
    """Read the tier from a subject's SMOC frontmatter.

    Returns DEFAULT_TIER ("carry-about") if no tier property is set.
    """
    normalized = normalize_subject_name(subject)
    try:
        value = obsidian.property_get(f"{normalized}/SMOC", TIER_PROPERTY)
        value = value.strip()
        if value in VALID_TIERS:
            return value
    except ObsidianCLIError:
        pass
    return DEFAULT_TIER


def set_tier(subject: str, tier: str, obsidian: ObsidianCLI) -> None:
    """Set the tier on a subject's SMOC frontmatter.

    Raises CacheError if the tier is invalid.
    """
    if tier not in VALID_TIERS:
        raise CacheError(
            f"Invalid tier '{tier}'. Must be one of: {', '.join(VALID_TIERS)}"
        )
    normalized = normalize_subject_name(subject)
    # Verify subject exists by reading its SMOC
    try:
        obsidian.read(f"{normalized}/SMOC")
    except ObsidianCLIError as exc:
        if exc.is_not_found:
            raise CacheError(f"Subject '{normalized}' not found.") from exc
        raise
    obsidian.property_set(f"{normalized}/SMOC", TIER_PROPERTY, tier)


def list_tiers(obsidian: ObsidianCLI) -> dict[str, list[str]]:
    """Group all subjects by their tier.

    Returns a dict with tier names as keys and sorted lists of
    subject names as values.
    """
    result: dict[str, list[str]] = {t: [] for t in VALID_TIERS}
    subjects = list_subjects(obsidian)
    for subj in subjects:
        tier = get_tier(subj, obsidian)
        result[tier].append(subj)
    return result


def archive_subject(subject: str, obsidian: ObsidianCLI) -> None:
    """Move a subject to the archive tier."""
    set_tier(subject, "archive", obsidian)


def activate_subject(subject: str, obsidian: ObsidianCLI) -> None:
    """Restore a subject to the carry-about tier."""
    set_tier(subject, "carry-about", obsidian)
