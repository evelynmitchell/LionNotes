"""Late-bound index generation for LionNotes subjects."""

from __future__ import annotations

import re
from datetime import date

from lionnotes.maps import _write_note, read_smoc
from lionnotes.obsidian import ObsidianCLI, ObsidianCLIError
from lionnotes.templates import render


class IndexBuildError(Exception):
    """Raised for index-related errors."""


# -- Keyword extraction ------------------------------------------------------

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_TAG_RE = re.compile(r"(?:^|(?<=\s))#([a-zA-Z][a-zA-Z0-9_/-]*)\b")


def _extract_keywords(content: str) -> set[str]:
    """Extract ``[[wikilinks]]`` and ``#tags`` from note content.

    Skips YAML frontmatter (between ``---`` delimiters) and HTML comments.
    Returns lowercased keyword strings.
    """
    # Strip YAML frontmatter
    stripped = _strip_frontmatter(content)
    # Strip HTML comments
    stripped = re.sub(r"<!--.*?-->", "", stripped, flags=re.DOTALL)

    keywords: set[str] = set()

    for m in _WIKILINK_RE.finditer(stripped):
        keywords.add(m.group(1).strip().lower())

    for m in _TAG_RE.finditer(stripped):
        keywords.add(f"#{m.group(1).lower()}")

    return keywords


def _strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter delimited by ``---`` on its own line."""
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\n\r") != "---":
        return content
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n\r") == "---":
            return "".join(lines[i + 1 :])
    return content


# -- Index formatting --------------------------------------------------------


def _format_index(
    keyword_map: dict[str, list[str]],
    subject: str,
) -> str:
    """Render keyword→note mappings as the index note body.

    Returns the full note content including frontmatter.
    """
    today = date.today().isoformat()
    header = render("index", subject=subject, date=today)

    lines = [header.rstrip()]

    for keyword in sorted(keyword_map):
        links = ", ".join(f"[[{n}]]" for n in sorted(keyword_map[keyword]))
        lines.append(f"- **{keyword}**: {links}")

    # Ensure trailing newline
    lines.append("")
    return "\n".join(lines)


# -- Build index -------------------------------------------------------------


def build_index(subject: str, obsidian: ObsidianCLI) -> str:
    """Scan SMOC-linked notes in a subject, extract keywords, and
    create/update the ``{subject}/Index`` note.

    Returns the generated index content.

    Raises:
        IndexBuildError: If the subject SMOC cannot be read.
    """
    try:
        smoc = read_smoc(subject, obsidian)
    except ObsidianCLIError as exc:
        raise IndexBuildError(f"Cannot read SMOC for '{subject}': {exc}") from exc

    # Gather all linked notes from the SMOC, de-duplicated
    seen: set[str] = set()
    note_names: list[str] = []
    for entry in smoc.all_entries:
        if entry.link and entry.link not in seen:
            seen.add(entry.link)
            note_names.append(entry.link)
    if "speeds" not in seen:
        note_names.append("speeds")

    # Build keyword → [note_name, ...] mapping
    keyword_map: dict[str, list[str]] = {}

    for note_name in note_names:
        full_path = f"{subject}/{note_name}"
        try:
            content = obsidian.read(full_path)
        except ObsidianCLIError as exc:
            if exc.is_not_found:
                continue  # skip missing notes
            raise

        keywords = _extract_keywords(content)
        for kw in keywords:
            keyword_map.setdefault(kw, [])
            if note_name not in keyword_map[kw]:
                keyword_map[kw].append(note_name)

    # Remove empty keyword entries (shouldn't happen, but defensive)
    keyword_map = {k: v for k, v in keyword_map.items() if v}

    index_content = _format_index(keyword_map, subject)

    # Write the index note (create or replace)
    index_path = f"{subject}/Index"
    try:
        obsidian.read(index_path)
        # Exists — use rename-aside-then-create pattern
        _write_note(index_path, index_content, obsidian)
    except ObsidianCLIError as exc:
        if exc.is_not_found:
            # Doesn't exist — create fresh
            obsidian.create(index_path, content=index_content)
        else:
            raise

    return index_content
