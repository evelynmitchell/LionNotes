"""SMOC and GSMOC map generation and management for LionNotes."""

from __future__ import annotations

import contextlib
import re
import time
from datetime import date

from lionnotes.obsidian import ObsidianCLI, ObsidianCLIError


class MapError(Exception):
    """Raised for map-related errors."""


# -- SMOC data structures ---------------------------------------------------


class SmocEntry:
    """A single entry in a SMOC section."""

    __slots__ = ("line", "link", "missing")

    def __init__(self, line: str, link: str = "", missing: bool = False):
        self.line = line  # original line text
        self.link = link  # extracted wikilink target (e.g. "POI-01-title")
        self.missing = missing


class Smoc:
    """Parsed SMOC structure."""

    def __init__(
        self,
        raw: str,
        core: list[SmocEntry],
        peripheral: list[SmocEntry],
        references: list[SmocEntry],
    ):
        self.raw = raw
        self.core = core
        self.peripheral = peripheral
        self.references = references

    @property
    def all_entries(self) -> list[SmocEntry]:
        return self.core + self.peripheral + self.references

    @property
    def all_links(self) -> set[str]:
        return {e.link for e in self.all_entries if e.link}


# -- GSMOC data structures --------------------------------------------------


class GsmocEntry:
    """A single entry in a GSMOC section."""

    __slots__ = ("line", "link")

    def __init__(self, line: str, link: str = ""):
        self.line = line
        self.link = link


class Gsmoc:
    """Parsed GSMOC structure."""

    def __init__(
        self,
        raw: str,
        active: list[GsmocEntry],
        dormant: list[GsmocEntry],
        emerging: list[GsmocEntry],
    ):
        self.raw = raw
        self.active = active
        self.dormant = dormant
        self.emerging = emerging


# -- Parsing helpers ---------------------------------------------------------

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

# Section heading patterns for SMOC
_SMOC_SECTIONS = {
    "core": re.compile(r"^###\s+Core\b", re.IGNORECASE),
    "peripheral": re.compile(r"^###\s+Peripheral\b", re.IGNORECASE),
    "references": re.compile(r"^###\s+References\b", re.IGNORECASE),
}

# Section heading patterns for GSMOC
_GSMOC_SECTIONS = {
    "active": re.compile(r"^##\s+Active\s+Subjects\b", re.IGNORECASE),
    "dormant": re.compile(r"^##\s+Dormant\s+Subjects\b", re.IGNORECASE),
    "emerging": re.compile(r"^##\s+Emerging\b", re.IGNORECASE),
}

# Any markdown heading (to detect section boundaries)
_HEADING_RE = re.compile(r"^#{1,6}\s+")


def _extract_link(line: str) -> str:
    """Extract the first wikilink target from a line, or empty string."""
    m = _WIKILINK_RE.search(line)
    return m.group(1) if m else ""


def _has_wikilink(content: str, link: str) -> bool:
    """Check if content contains a wikilink to the given target.

    Matches both ``[[link]]`` and ``[[link|alias]]`` forms exactly,
    avoiding substring false positives.
    """
    # Escape for regex, then match [[link]] or [[link|...]]
    escaped = re.escape(link)
    return bool(re.search(rf"\[\[{escaped}(?:\|[^\]]+)?\]\]", content))


def _parse_section_entries(
    lines: list[str],
    entry_cls: type = SmocEntry,
) -> list:
    """Parse list entries from lines until next heading or end."""
    entries = []
    for line in lines:
        stripped = line.strip()
        if _HEADING_RE.match(stripped):
            break
        if stripped.startswith("- ") or stripped.startswith("* "):
            link = _extract_link(stripped)
            missing = "[missing]" in stripped
            if entry_cls is SmocEntry:
                entries.append(SmocEntry(line=stripped, link=link, missing=missing))
            else:
                entries.append(GsmocEntry(line=stripped, link=link))
        elif stripped.startswith("<!--") or not stripped:
            continue
    return entries


def _find_section_lines(lines: list[str], pattern: re.Pattern) -> list[str]:
    """Find the lines belonging to a section (after heading, before next heading)."""
    start = None
    for i, line in enumerate(lines):
        if pattern.match(line.strip()):
            start = i + 1
            break
    if start is None:
        return []
    result = []
    for line in lines[start:]:
        if _HEADING_RE.match(line.strip()):
            break
        result.append(line)
    return result


# -- SMOC operations ---------------------------------------------------------


def read_smoc(subject: str, obsidian: ObsidianCLI) -> Smoc:
    """Read and parse a subject's SMOC.

    Raises:
        ObsidianCLIError: If the SMOC cannot be read.
    """
    content = obsidian.read(f"{subject}/SMOC")
    lines = content.splitlines()

    core = _parse_section_entries(
        _find_section_lines(lines, _SMOC_SECTIONS["core"]),
    )
    peripheral = _parse_section_entries(
        _find_section_lines(lines, _SMOC_SECTIONS["peripheral"]),
    )
    references = _parse_section_entries(
        _find_section_lines(lines, _SMOC_SECTIONS["references"]),
    )

    return Smoc(raw=content, core=core, peripheral=peripheral, references=references)


def update_smoc(
    subject: str,
    poi_entry: str,
    obsidian: ObsidianCLI,
    *,
    section: str = "core",
) -> None:
    """Add a POI/REF link to a SMOC section. Idempotent.

    Args:
        subject: Subject name.
        poi_entry: Wikilink entry line, e.g. ``- [[POI-01-my-title]]``.
        obsidian: ObsidianCLI instance.
        section: Which section to add to ("core", "peripheral", "references").
    """
    content = obsidian.read(f"{subject}/SMOC")

    # Extract the link from the entry to check idempotency
    link = _extract_link(poi_entry)
    if link and _has_wikilink(content, link):
        return  # already present

    lines = content.splitlines()
    section_pattern = _SMOC_SECTIONS.get(section)
    if section_pattern is None:
        raise MapError(f"Unknown SMOC section: {section!r}")

    # Find the section and insert after comments/existing entries
    insert_idx = None
    in_section = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if section_pattern.match(stripped):
            in_section = True
            insert_idx = i + 1  # default: right after heading
            continue
        if in_section:
            if _HEADING_RE.match(stripped):
                break  # hit next section
            if stripped.startswith("- ") or stripped.startswith("* "):
                insert_idx = i + 1  # after last existing entry
            elif stripped.startswith("<!--"):
                insert_idx = i + 1  # after comment

    if insert_idx is None:
        # Section not found — append to end of file
        lines.append("")
        lines.append(f"### {section.title()}")
        lines.append(poi_entry)
    else:
        lines.insert(insert_idx, poi_entry)

    # Update the 'updated' date in frontmatter
    new_content = "\n".join(lines)
    new_content = _update_frontmatter_date(new_content)

    # Write back by creating with overwrite semantics
    # Since obsidian CLI doesn't have a "write" command, we read+create
    # Actually, we need to use a different approach — let's use the full
    # content replacement pattern
    _write_note(f"{subject}/SMOC", new_content, obsidian)


def _update_frontmatter_date(content: str) -> str:
    """Update the 'updated' field in YAML frontmatter to today."""
    today = date.today().isoformat()
    return re.sub(
        r'^(updated:\s*)"[^"]*"',
        rf'\1"{today}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )


def _write_note(path: str, content: str, obsidian: ObsidianCLI) -> None:
    """Write full content to a note by deleting and re-creating it.

    The Obsidian CLI doesn't have a direct 'write' or 'update' command,
    so we rename the old note aside, create the new one, then clean up.
    Uses a two-step approach: rename old → create new.
    """
    # Strategy: use property_set for simple changes, but for full rewrites
    # we need to use append on an empty note. Since the CLI doesn't support
    # full overwrite, we'll use rename + create.
    ts = int(time.time() * 1000)
    backup_name = f"{path}__lionnotes_bak_{ts}"
    with contextlib.suppress(ObsidianCLIError):
        obsidian.rename(path, backup_name)

    try:
        obsidian.create(path, content=content)
    except ObsidianCLIError:
        with contextlib.suppress(ObsidianCLIError):
            obsidian.rename(backup_name, path)
        raise

    # Archive backup alongside the note: per-subject for subject notes,
    # root _archive/ for top-level notes.
    parts = path.split("/")
    if len(parts) >= 2:
        # e.g. "subject/SMOC" -> "subject/_archive/SMOC__lionnotes_bak_..."
        archive_dest = f"{parts[0]}/_archive/{'/'.join(parts[1:])}__lionnotes_bak_{ts}"
    else:
        archive_dest = f"_archive/{backup_name}"
    with contextlib.suppress(ObsidianCLIError):
        obsidian.rename(backup_name, archive_dest)


# -- GSMOC operations -------------------------------------------------------


def read_gsmoc(obsidian: ObsidianCLI) -> Gsmoc:
    """Read and parse the Grand Subject Map of Contents.

    Raises:
        ObsidianCLIError: If the GSMOC cannot be read.
    """
    content = obsidian.read("GSMOC")
    lines = content.splitlines()

    active = _parse_section_entries(
        _find_section_lines(lines, _GSMOC_SECTIONS["active"]),
        entry_cls=GsmocEntry,
    )
    dormant = _parse_section_entries(
        _find_section_lines(lines, _GSMOC_SECTIONS["dormant"]),
        entry_cls=GsmocEntry,
    )
    emerging = _parse_section_entries(
        _find_section_lines(lines, _GSMOC_SECTIONS["emerging"]),
        entry_cls=GsmocEntry,
    )

    return Gsmoc(raw=content, active=active, dormant=dormant, emerging=emerging)


def update_gsmoc(subject_entry: str, obsidian: ObsidianCLI) -> None:
    """Add a subject entry to the GSMOC Active Subjects section. Idempotent.

    Args:
        subject_entry: Entry line, e.g. ``- [[my-subject/SMOC|my-subject]]``.
        obsidian: ObsidianCLI instance.
    """
    content = obsidian.read("GSMOC")

    link = _extract_link(subject_entry)
    if link and _has_wikilink(content, link):
        return  # already present

    lines = content.splitlines()
    pattern = _GSMOC_SECTIONS["active"]

    insert_idx = None
    in_section = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if pattern.match(stripped):
            in_section = True
            insert_idx = i + 1
            continue
        if in_section:
            if _HEADING_RE.match(stripped):
                break
            if (
                stripped.startswith("- ")
                or stripped.startswith("* ")
                or stripped.startswith("<!--")
            ):
                insert_idx = i + 1

    if insert_idx is None:
        lines.append(subject_entry)
    else:
        lines.insert(insert_idx, subject_entry)

    new_content = "\n".join(lines)
    new_content = _update_frontmatter_date(new_content)
    _write_note("GSMOC", new_content, obsidian)


# -- Rebuild -----------------------------------------------------------------


def rebuild_smoc(subject: str, obsidian: ObsidianCLI) -> Smoc:
    """Merge-based SMOC rebuild.

    Scans the subject folder for POI and REF files, compares against the
    existing SMOC entries, adds new entries, and flags missing files with
    ``[missing]`` markers. Preserves manual ordering and annotations.

    Returns the updated Smoc.
    """
    # Read existing SMOC
    smoc = read_smoc(subject, obsidian)

    # Scan for POI/REF files in the subject folder
    try:
        search_results = obsidian.search(f"type: poi subject: {subject}", limit=1000)
    except ObsidianCLIError:
        search_results = ""

    try:
        ref_results = obsidian.search(f"type: reference subject: {subject}", limit=1000)
    except ObsidianCLIError:
        ref_results = ""

    # Parse found files
    found_pois: set[str] = set()
    found_refs: set[str] = set()

    for line in search_results.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Search results return file paths; extract the note name
        # Format is typically: "subject/POI-01-title"
        parts = line.split("/")
        if len(parts) >= 2:
            note = parts[-1].replace(".md", "")
            if note.startswith("POI-"):
                found_pois.add(note)
        elif line.startswith("POI-"):
            found_pois.add(line.replace(".md", ""))

    for line in ref_results.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("/")
        if len(parts) >= 2:
            note = parts[-1].replace(".md", "")
            if note.startswith("REF-"):
                found_refs.add(note)
        elif line.startswith("REF-"):
            found_refs.add(line.replace(".md", ""))

    # Determine what's in the SMOC already
    existing_links = smoc.all_links

    # Collect existing POI/REF links by note name
    existing_pois = {
        link for link in existing_links if "/" not in link and link.startswith("POI-")
    }
    existing_refs = {
        link for link in existing_links if "/" not in link and link.startswith("REF-")
    }

    # Find new entries not yet in SMOC
    new_pois = found_pois - existing_pois
    new_refs = found_refs - existing_refs

    # Find entries in SMOC that are no longer on disk
    missing_pois = existing_pois - found_pois
    missing_refs = existing_refs - found_refs

    # Build updated content
    content = smoc.raw
    lines = content.splitlines()

    # Flag missing entries with [missing] marker
    for i, line in enumerate(lines):
        link = _extract_link(line)
        if (link in missing_pois or link in missing_refs) and "[missing]" not in line:
            lines[i] = line.rstrip() + " [missing]"

    # Add new POIs to Core section
    if new_pois:
        core_insert = _find_section_insert_point(lines, _SMOC_SECTIONS["core"])
        for poi_name in sorted(new_pois):
            entry = f"- [[{poi_name}]]"
            if core_insert is not None:
                lines.insert(core_insert, entry)
                core_insert += 1
            else:
                lines.append(entry)

    # Add new REFs to References section
    if new_refs:
        ref_insert = _find_section_insert_point(
            lines,
            _SMOC_SECTIONS["references"],
        )
        for ref_name in sorted(new_refs):
            entry = f"- [[{ref_name}]]"
            if ref_insert is not None:
                lines.insert(ref_insert, entry)
                ref_insert += 1
            else:
                lines.append(entry)

    new_content = "\n".join(lines)
    new_content = _update_frontmatter_date(new_content)
    _write_note(f"{subject}/SMOC", new_content, obsidian)

    return read_smoc(subject, obsidian)


def _find_section_insert_point(
    lines: list[str],
    pattern: re.Pattern,
) -> int | None:
    """Find the insertion point at the end of a section's entries."""
    insert_idx = None
    in_section = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if pattern.match(stripped):
            in_section = True
            insert_idx = i + 1
            continue
        if in_section:
            if _HEADING_RE.match(stripped):
                break
            if (
                stripped.startswith("- ")
                or stripped.startswith("* ")
                or stripped.startswith("<!--")
            ):
                insert_idx = i + 1
    return insert_idx
