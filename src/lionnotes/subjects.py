"""Subject CRUD operations for LionNotes."""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass, field

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


def create_subject(name: str, obsidian: ObsidianCLI, config: Config) -> str:
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
    obsidian: ObsidianCLI,
    *,
    limit: int = 200,
) -> list[str]:
    """List all subjects in the vault by searching for SMOC notes.

    Returns a sorted list of subject names.
    *limit* controls the maximum number of search results fetched.
    """
    try:
        results = obsidian.search("type: smoc", limit=limit)
    except ObsidianCLIError as exc:
        if exc.is_not_found or "no results" in exc.stderr.lower():
            return []
        raise

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


# -- Dataclasses for merge/split results ------------------------------------


@dataclass
class MoveFailure:
    """A note that failed to move during merge/split."""

    note: str
    reason: str


@dataclass
class MergeResult:
    """Result of a subject merge operation."""

    moved: list[str] = field(default_factory=list)
    failed: list[MoveFailure] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    out_card_created: bool = False


@dataclass
class SplitResult:
    """Result of a subject split operation."""

    new_subject: str = ""
    moved: list[str] = field(default_factory=list)
    failed: list[MoveFailure] = field(default_factory=list)


# -- Helpers for merge/split ------------------------------------------------

_NOTE_PREFIX_RE = re.compile(r"^(POI|REF)-(\d+)-(.+)$")
_SPEED_LINE_RE = re.compile(r"^- S(\d+):")


def _enumerate_subject_notes(subject: str, obsidian: ObsidianCLI) -> list[str]:
    """List POI/REF note names in a subject by parsing SMOC."""
    from lionnotes.maps import read_smoc

    smoc = read_smoc(subject, obsidian)
    notes = []
    for entry in smoc.all_entries:
        if entry.link and _NOTE_PREFIX_RE.match(entry.link):
            notes.append(entry.link)
    return notes


def _next_number_for_prefix(existing_notes: list[str], prefix: str) -> int:
    """Find the next available number for a prefix (POI/REF)."""
    max_num = 0
    for note in existing_notes:
        m = _NOTE_PREFIX_RE.match(note)
        if m and m.group(1) == prefix:
            max_num = max(max_num, int(m.group(2)))
    return max_num + 1


def _renumber_note(note_name: str, new_num: int) -> str:
    """Renumber a POI/REF note name."""
    m = _NOTE_PREFIX_RE.match(note_name)
    if not m:
        return note_name
    prefix = m.group(1)
    slug = m.group(3)
    return f"{prefix}-{new_num:02d}-{slug}"


# -- Merge ------------------------------------------------------------------


def merge_subjects(
    source: str,
    target: str,
    obsidian: ObsidianCLI,
    config: Config,
) -> MergeResult:
    """Merge source subject into target subject.

    Uses plan-execute-report pattern:
    1. Plan: enumerate notes, compute renumbered names
    2. Validate: confirm both subjects exist, no collisions
    3. Execute: move notes one at a time
    4. Finalize: update SMOCs, GSMOC, create out card
    5. Report: return MergeResult
    """
    from lionnotes.maps import (
        _write_note,
        read_gsmoc,
        update_gsmoc,
    )

    source = normalize_subject_name(source)
    target = normalize_subject_name(target)

    if source == target:
        raise SubjectError("Cannot merge a subject into itself.")

    # -- Validate: both subjects exist --
    try:
        obsidian.read(f"{source}/SMOC")
    except ObsidianCLIError as exc:
        if exc.is_not_found:
            raise SubjectError(f"Source subject '{source}' does not exist.") from exc
        raise

    try:
        obsidian.read(f"{target}/SMOC")
    except ObsidianCLIError as exc:
        if exc.is_not_found:
            raise SubjectError(f"Target subject '{target}' does not exist.") from exc
        raise

    # -- Plan: enumerate source notes, compute target names --
    source_notes = _enumerate_subject_notes(source, obsidian)
    target_notes = _enumerate_subject_notes(target, obsidian)

    # Compute renumbered names for each source note in target
    move_plan: list[tuple[str, str]] = []  # (source_note, target_note)
    next_poi = _next_number_for_prefix(target_notes, "POI")
    next_ref = _next_number_for_prefix(target_notes, "REF")

    for note in source_notes:
        m = _NOTE_PREFIX_RE.match(note)
        if not m:
            continue
        prefix = m.group(1)
        if prefix == "POI":
            new_name = _renumber_note(note, next_poi)
            next_poi += 1
        else:
            new_name = _renumber_note(note, next_ref)
            next_ref += 1
        move_plan.append((note, new_name))

    result = MergeResult()

    # -- Execute: move notes one at a time --
    for src_note, tgt_note in move_plan:
        try:
            obsidian.rename(f"{source}/{src_note}", f"{target}/{tgt_note}")
            result.moved.append(tgt_note)
        except ObsidianCLIError as exc:
            result.failed.append(MoveFailure(note=src_note, reason=str(exc)))

    # -- Move speeds: append source speeds to target speeds --
    try:
        source_speeds = obsidian.read(f"{source}/speeds")
        speed_lines = []
        target_speed_num = config.speed_counters.get(target, 0)
        for line in source_speeds.splitlines():
            m = _SPEED_LINE_RE.match(line.strip())
            if m:
                target_speed_num += 1
                # Replace speed number
                new_line = re.sub(
                    r"^- S\d+:",
                    f"- S{target_speed_num}:",
                    line.strip(),
                )
                speed_lines.append(new_line)
        if speed_lines:
            obsidian.append(
                f"{target}/speeds",
                "\n" + "\n".join(speed_lines),
            )
            config.speed_counters[target] = target_speed_num
    except ObsidianCLIError:
        pass  # No speeds to move

    # -- Finalize: update target SMOC with moved entries --
    try:
        target_smoc_content = obsidian.read(f"{target}/SMOC")
        new_entries = []
        for tgt_note in result.moved:
            entry_line = f"- [[{tgt_note}]]"
            if entry_line not in target_smoc_content:
                new_entries.append(entry_line)
        if new_entries:
            obsidian.append(
                f"{target}/SMOC",
                "\n" + "\n".join(new_entries),
            )
    except ObsidianCLIError:
        pass

    # -- Create out card at source SMOC --
    try:
        out_card = (
            f"---\ntype: out-card\n---\n"
            f"# {source} — Merged\n\n"
            f"This subject has been merged into "
            f"[[{target}/SMOC|{target}]].\n"
        )
        _write_note(f"{source}/SMOC", out_card, obsidian)
        result.out_card_created = True
    except ObsidianCLIError:
        pass

    # -- Update GSMOC: remove source, ensure target --
    try:
        gsmoc = read_gsmoc(obsidian)
        gsmoc_content = gsmoc.raw
        lines = gsmoc_content.splitlines()
        # Remove lines referencing source
        filtered = [
            line
            for line in lines
            if f"[[{source}/SMOC" not in line and f"[[{source}]]" not in line
        ]
        if len(filtered) != len(lines):
            from lionnotes.maps import _update_frontmatter_date

            new_content = _update_frontmatter_date("\n".join(filtered))
            _write_note("GSMOC", new_content, obsidian)
        # Ensure target is in GSMOC
        update_gsmoc(f"- [[{target}/SMOC|{target}]]", obsidian)
    except ObsidianCLIError:
        pass

    # Update config
    save_config(config)

    return result


# -- Split ------------------------------------------------------------------


def split_subject(
    source: str,
    new_name: str,
    note_patterns: list[str],
    obsidian: ObsidianCLI,
    config: Config,
) -> SplitResult:
    """Split notes from source into a new subject.

    Uses plan-execute-report pattern.
    """
    from lionnotes.maps import read_smoc, update_gsmoc

    source = normalize_subject_name(source)
    new_name = normalize_subject_name(new_name)

    # -- Validate source exists --
    try:
        obsidian.read(f"{source}/SMOC")
    except ObsidianCLIError as exc:
        if exc.is_not_found:
            raise SubjectError(f"Source subject '{source}' does not exist.") from exc
        raise

    # -- Validate new subject doesn't exist --
    try:
        obsidian.read(f"{new_name}/SMOC")
        raise SubjectError(f"Subject '{new_name}' already exists.")
    except ObsidianCLIError as exc:
        if not exc.is_not_found:
            raise

    # -- Plan: resolve note patterns against source --
    source_notes = _enumerate_subject_notes(source, obsidian)
    matched_notes: list[str] = []
    for pattern in note_patterns:
        pattern = pattern.strip()
        for note in source_notes:
            if (
                note == pattern or note.startswith(f"{pattern}-")
            ) and note not in matched_notes:
                matched_notes.append(note)

    if not matched_notes:
        raise SubjectError(
            f"No notes matched the given patterns in subject '{source}'."
        )

    # -- Create new subject --
    create_subject(new_name, obsidian, config)

    result = SplitResult(new_subject=new_name)

    # -- Execute: move matched notes --
    next_poi = 1
    next_ref = 1
    for note in matched_notes:
        m = _NOTE_PREFIX_RE.match(note)
        if not m:
            continue
        prefix = m.group(1)
        if prefix == "POI":
            new_note = _renumber_note(note, next_poi)
            next_poi += 1
        else:
            new_note = _renumber_note(note, next_ref)
            next_ref += 1
        try:
            obsidian.rename(f"{source}/{note}", f"{new_name}/{new_note}")
            result.moved.append(new_note)
        except ObsidianCLIError as exc:
            result.failed.append(MoveFailure(note=note, reason=str(exc)))

    # -- Finalize: update new subject SMOC --
    if result.moved:
        try:
            smoc = read_smoc(new_name, obsidian)
            new_entries = []
            for note in result.moved:
                entry = f"- [[{note}]]"
                if entry not in smoc.raw:
                    new_entries.append(entry)
            if new_entries:
                obsidian.append(
                    f"{new_name}/SMOC",
                    "\n" + "\n".join(new_entries),
                )
        except ObsidianCLIError:
            pass

    # -- Update GSMOC --
    with contextlib.suppress(ObsidianCLIError):
        update_gsmoc(f"- [[{new_name}/SMOC|{new_name}]]", obsidian)

    save_config(config)
    return result


# -- Promote ----------------------------------------------------------------


def promote_subject(
    name: str,
    obsidian: ObsidianCLI,
    config: Config,
) -> str:
    """Promote a proto-subject from inbox to a full subject.

    Creates the full subject structure and moves any matching
    inbox entries (by context hint) into the new subject's speeds.

    Returns the normalized subject name.
    """
    from lionnotes.maps import _write_note, update_gsmoc
    from lionnotes.review import _parse_inbox_line

    normalized = normalize_subject_name(name)

    # Create the subject (validates name, checks not exists)
    create_subject(normalized, obsidian, config)

    # Move matching inbox entries
    try:
        inbox_content = obsidian.read("_inbox/unsorted")
    except ObsidianCLIError:
        # No inbox — just create the subject
        with contextlib.suppress(ObsidianCLIError):
            update_gsmoc(
                f"- [[{normalized}/SMOC|{normalized}]]",
                obsidian,
            )
        return normalized

    inbox_lines = inbox_content.splitlines()
    kept_lines: list[str] = []
    moved_entries: list[str] = []
    speed_num = config.speed_counters.get(normalized, 0)

    for line in inbox_lines:
        entry = _parse_inbox_line(line)
        if (
            entry is not None
            and entry.context
            and entry.context.strip().lower() == normalized
        ):
            # Move to new subject's speeds
            speed_num += 1
            new_line = re.sub(r"^- S\d+:", f"- S{speed_num}:", line.strip())
            moved_entries.append(new_line)
        else:
            kept_lines.append(line)

    if moved_entries:
        config.speed_counters[normalized] = speed_num
        obsidian.append(
            f"{normalized}/speeds",
            "\n" + "\n".join(moved_entries),
        )
        _write_note(
            "_inbox/unsorted",
            "\n".join(kept_lines),
            obsidian,
        )
        save_config(config)

    # Add to GSMOC
    with contextlib.suppress(ObsidianCLIError):
        update_gsmoc(f"- [[{normalized}/SMOC|{normalized}]]", obsidian)

    return normalized
