# Phase 3: Organization & Review — Detailed Implementation Plan

## Overview

Phase 3 implements the **Speed→Map→POI flow** — the heart of Kimbro's system. Raw speed thoughts are triaged, organized into Points of Interest, and indexed in Subject Maps of Contents (SMOCs) and the Grand Subject Map (GSMOC). This is what turns a pile of captures into structured, navigable knowledge.

## Dependency: Phase 2

Phase 3 depends on Phase 2 modules that don't exist yet:
- `capture.py` — speed thought capture (provides the entries we triage)
- `subjects.py` — subject CRUD (`list_subjects`, `create_subject`, name validation)
- `vault.py` — vault state helpers (`subject_exists`, `count_unmapped_speeds`)

Phase 3 modules will import from these. If Phase 2 is implemented first, Phase 3 slots in cleanly. If built concurrently, we define the Phase 2 interfaces we depend on and code against them.

---

## 3a. `src/lionnotes/maps.py` — SMOC/GSMOC Operations

This module handles reading, updating, and rebuilding the map hierarchy.

### Functions

```python
def read_smoc(subject: str, obsidian: ObsidianCLI) -> str:
    """Read and return a subject's SMOC content.

    Raises ObsidianCLIError if the subject doesn't exist or has no SMOC.
    """

def update_smoc(subject: str, poi_entry: str, section: str, obsidian: ObsidianCLI) -> None:
    """Add a POI wikilink entry to a SMOC under the specified section.

    - poi_entry: e.g. "[[POI-03-async-patterns]] — async/await patterns, from S31-S38"
    - section: one of "Core", "Peripheral", "References"
    - Appends under the correct ### heading
    - Idempotent: skips if the exact wikilink already exists in the SMOC
    - Updates the 'updated' frontmatter date
    """

def read_gsmoc(obsidian: ObsidianCLI) -> str:
    """Read and return the GSMOC content."""

def update_gsmoc(subject_entry: str, section: str, obsidian: ObsidianCLI) -> None:
    """Add a subject entry to the GSMOC under the specified section.

    - subject_entry: e.g. "[[python/SMOC|python]] — Python programming"
    - section: one of "Active Subjects", "Dormant Subjects", "Emerging"
    - Idempotent: skips if wikilink already present
    - Updates the 'updated' frontmatter date
    """

def rebuild_smoc(subject: str, obsidian: ObsidianCLI) -> RebuildResult:
    """Merge-based SMOC rebuild — detects new/missing entries, preserves existing structure.

    Process:
    1. Read current SMOC content
    2. Scan subject folder for POI-*.md and REF-*.md files via obsidian search
    3. Compare: find POIs/REFs in folder but not in SMOC (new), and in SMOC but not in folder (missing)
    4. Append new entries under appropriate sections
    5. Flag missing entries with a <!-- MISSING: ... --> comment (don't remove — may be intentional archive)
    6. Return RebuildResult with lists of added/missing/unchanged

    This is merge-based, NOT replace-based. Manually curated ordering and annotations are preserved.
    """
```

### Data types

```python
@dataclass
class RebuildResult:
    added: list[str]      # POI/REF names added to SMOC
    missing: list[str]    # POI/REF names in SMOC but not found in folder
    unchanged: list[str]  # POI/REF names already correctly listed
```

### SMOC parsing approach

The SMOC is a markdown file with `### Core`, `### Peripheral`, `### References` sections. To insert entries:
1. Read the full SMOC content
2. Find the target section heading (e.g., `### Core`)
3. Find the next `##` or `###` heading (or EOF) to determine section bounds
4. Append the new entry line before the next heading
5. Write back via `obsidian.create()` with overwrite (or read + reconstruct + write via obsidian)

**Implementation note:** Since the Obsidian CLI only supports `read`, `create`, `append`, and `rename` (no "replace" or "write"), updating mid-file content requires reading the full content, modifying it in Python, then writing back. We need to decide on the write-back strategy:
- **Option A:** Use `obsidian.create()` with the updated content (if the CLI supports overwriting existing files)
- **Option B:** Add a `write` method to `ObsidianCLI` that writes content to an existing file
- **Option C:** Fall back to direct file write for updates (breaking the "all I/O through CLI" principle)

**Recommendation:** Option B — add an `ObsidianCLI.write()` method (or use `create` with an `overwrite` flag if the CLI supports it). This is a small Phase 1 addition needed before Phase 3 can work.

### Tests (test_maps.py)

1. `test_read_smoc` — reads SMOC via obsidian, returns content
2. `test_update_smoc_adds_entry` — adds a POI link under the correct section
3. `test_update_smoc_idempotent` — adding the same entry twice doesn't duplicate
4. `test_update_smoc_updates_date` — the 'updated' frontmatter field changes
5. `test_read_gsmoc` — reads GSMOC via obsidian
6. `test_update_gsmoc_adds_subject` — adds subject entry under correct section
7. `test_update_gsmoc_idempotent` — no duplicate entries
8. `test_rebuild_smoc_detects_new` — finds POIs in folder not in SMOC
9. `test_rebuild_smoc_detects_missing` — finds entries in SMOC not in folder
10. `test_rebuild_smoc_preserves_existing` — existing entries and structure untouched

---

## 3b. `src/lionnotes/review.py` — Triage Workflow

This module implements the Speed→Map→POI flow that is central to Kimbro's system.

### Functions

```python
def get_unmapped_speeds(subject: str, obsidian: ObsidianCLI) -> list[SpeedEntry]:
    """Parse a subject's speeds.md and return entries without a [→ POI-N] mapping.

    Parses lines matching: - S[N]: (context: ...) content #thought/type
    Returns SpeedEntry objects for entries that DON'T end with [→ POI-N].
    """

def map_speed(subject: str, speed_num: int, poi_ref: str, obsidian: ObsidianCLI) -> None:
    """Mark a speed thought as mapped by appending [→ POI-N] suffix.

    - Reads speeds.md
    - Finds the line with S[speed_num]
    - Appends ' [→ {poi_ref}]' to that line
    - Writes back the modified content
    - Raises ValueError if speed_num not found
    """

def triage_inbox(obsidian: ObsidianCLI) -> list[InboxEntry]:
    """List entries in _inbox/unsorted.md for assignment to subjects.

    Parses lines matching: - [subject?] content #thought/type
    Returns InboxEntry objects.
    """

def assign_inbox_entry(
    entry_index: int,
    target_subject: str,
    obsidian: ObsidianCLI,
    config: Config
) -> int:
    """Move an inbox entry to a subject's speeds.md.

    1. Read _inbox/unsorted.md
    2. Remove the entry at entry_index
    3. Allocate next speed number for target_subject (via config.next_speed_number)
    4. Append formatted speed entry to {subject}/speeds.md
    5. Write back modified inbox
    6. Save config (counter incremented)
    7. Return the assigned speed number
    """
```

### Data types

```python
@dataclass
class SpeedEntry:
    number: int          # e.g. 47
    content: str         # The thought content
    context: str | None  # The (context: ...) hint, if present
    thought_type: str | None  # e.g. "observation", parsed from #thought/type
    mapped_to: str | None     # e.g. "POI-12" if already mapped, None if unmapped
    raw_line: str        # The original line text

@dataclass
class InboxEntry:
    index: int           # Line position in unsorted.md
    suggested_subject: str | None  # Parsed from [subject?] prefix
    content: str
    thought_type: str | None
    raw_line: str
```

### Speed entry parsing

Speed entries follow the format: `- S[N]: (context: hint) content #thought/type [→ POI-N]`

Regex pattern:
```python
SPEED_PATTERN = re.compile(
    r"^- S\[(\d+)\]:\s*"           # - S[47]:
    r"(?:\(context:\s*([^)]*)\)\s*)?"  # optional (context: hint)
    r"(.+?)"                        # content
    r"(?:\s+#thought/(\w[\w-]*))??"  # optional #thought/type
    r"(?:\s+\[→\s*(POI-\d+)\])?"   # optional [→ POI-12]
    r"\s*$"
)
```

### Tests (test_review.py)

1. `test_parse_speed_entry` — parses a well-formed speed line
2. `test_parse_speed_entry_no_context` — parses entry without (context: ...)
3. `test_parse_speed_entry_mapped` — recognizes [→ POI-N] suffix
4. `test_get_unmapped_speeds` — filters to only unmapped entries
5. `test_get_unmapped_speeds_all_mapped` — returns empty list when all mapped
6. `test_map_speed_marks_entry` — appends [→ POI-N] to the correct line
7. `test_map_speed_nonexistent` — raises ValueError for missing speed number
8. `test_triage_inbox` — parses inbox entries
9. `test_assign_inbox_entry` — moves entry from inbox to subject speeds
10. `test_assign_inbox_entry_increments_counter` — config counter advances

---

## 3c. POI and Reference Commands + CLI

### New core functions (in maps.py or a new poi.py — recommend keeping in maps.py for cohesion)

```python
def create_poi(
    subject: str,
    title: str,
    obsidian: ObsidianCLI,
    config: Config,
    synthesized_from: list[int] | None = None,
) -> str:
    """Create a numbered POI note and auto-link it in the SMOC.

    1. Determine next POI number by scanning subject folder for POI-*.md files
    2. Render the 'poi' template with subject, title, poi_number, date
    3. If synthesized_from provided, populate the synthesized_from frontmatter field
    4. Create the note: {subject}/POI-{NN}-{slug}.md  (NN zero-padded to 2 digits)
    5. Auto-add entry to SMOC under ### Core section
    6. Return the created note name (e.g. "POI-03-async-patterns")
    """

def create_reference(
    subject: str,
    title: str,
    author: str,
    year: int,
    url: str,
    obsidian: ObsidianCLI,
    notes: str = "",
) -> str:
    """Create a numbered reference note and auto-link it in the SMOC.

    1. Determine next REF number by scanning subject folder for REF-*.md files
    2. Render the 'reference' template
    3. Create the note: {subject}/REF-{NN}-{slug}.md
    4. Auto-add entry to SMOC under ### References section
    5. Return the created note name
    """

def next_poi_number(subject: str, obsidian: ObsidianCLI) -> int:
    """Scan subject folder for existing POI-NN-*.md files and return next number."""

def next_ref_number(subject: str, obsidian: ObsidianCLI) -> int:
    """Scan subject folder for existing REF-NN-*.md files and return next number."""

def slugify(title: str) -> str:
    """Convert a title to a filename-safe slug: lowercase, hyphens for spaces, strip special chars."""
```

### CLI commands (additions to cli.py)

```python
# --- review command ---
@app.command()
def review(
    subject: str | None = typer.Option(None, "--subject", "-s"),
    pan: bool = typer.Option(False, "--pan", help="Triage inbox entries"),
):
    """Review unmapped speed thoughts for a subject (or triage inbox with --pan)."""
    # --pan mode: list inbox entries, show suggested subjects
    # subject mode: list unmapped speeds, show count and content

# --- map command ---
@app.command()
def map(
    subject: str | None = typer.Argument(None),
    rebuild: bool = typer.Option(False, "--rebuild", help="Merge-rebuild the SMOC"),
):
    """View a subject's SMOC, or the GSMOC if no subject given."""
    # No subject: read and display GSMOC
    # With subject: read and display that subject's SMOC
    # --rebuild: run rebuild_smoc and report results

# --- poi command ---
@app.command()
def poi(
    subject: str = typer.Argument(...),
    title: str = typer.Argument(...),
    synthesized_from: str | None = typer.Option(
        None, "--from", "-f", help="Comma-separated speed numbers (e.g. '31,32,35')"
    ),
):
    """Create a new Point of Interest in a subject."""
    # Parse --from into list[int]
    # Call create_poi()
    # If --from provided, also call map_speed() for each speed number

# --- ref command ---
@app.command()
def ref(
    subject: str = typer.Argument(...),
    title: str = typer.Argument(...),
    url: str = typer.Option("", "--url"),
    author: str = typer.Option("", "--author"),
    year: int = typer.Option(0, "--year"),
    notes: str = typer.Option("", "--notes"),
):
    """Add a reference annotation to a subject."""

# --- subjects pp command ---
# Add to existing subjects subcommand group (from Phase 2)
@subjects_app.command("pp")
def subjects_pp(
    name: str = typer.Argument(...),
):
    """View a subject's Purpose & Principles."""
    # Read and display {subject}/purpose.md
```

### Tests (test_cli_phase3.py or extend existing test files)

1. `test_poi_creates_note` — creates POI-NN-slug.md with correct template
2. `test_poi_auto_links_smoc` — SMOC updated with new POI entry
3. `test_poi_numbering_sequential` — POI numbers increment correctly
4. `test_poi_with_synthesized_from` — --from flag marks speeds as mapped
5. `test_ref_creates_note` — creates REF-NN-slug.md with correct template
6. `test_ref_auto_links_smoc` — SMOC updated under References section
7. `test_review_subject` — lists unmapped speeds for a subject
8. `test_review_pan` — lists inbox entries
9. `test_map_no_subject` — displays GSMOC
10. `test_map_with_subject` — displays subject SMOC
11. `test_map_rebuild` — runs merge-rebuild and reports results
12. `test_subjects_pp` — displays purpose.md content

---

## Implementation Order

Within Phase 3, the recommended build order is:

1. **ObsidianCLI.write() addition** — needed for mid-file content updates (SMOC/speeds editing). Small change to obsidian.py.
2. **maps.py — read functions** (`read_smoc`, `read_gsmoc`) — simplest, just wrap obsidian.read()
3. **review.py — parsing functions** (`SpeedEntry`, `InboxEntry` dataclasses, `get_unmapped_speeds`, `triage_inbox`) — pure parsing, no writes
4. **review.py — mutation functions** (`map_speed`, `assign_inbox_entry`) — depend on parsing + ObsidianCLI.write()
5. **maps.py — update functions** (`update_smoc`, `update_gsmoc`) — SMOC section parsing + insertion
6. **maps.py — POI/ref creation** (`create_poi`, `create_reference`, numbering helpers) — depend on update functions
7. **maps.py — rebuild** (`rebuild_smoc`) — most complex, depends on everything above
8. **CLI commands** — wire up review, map, poi, ref, subjects pp
9. **Tests** — written alongside each step (TDD preferred)

## Open Design Questions

1. **File content replacement strategy**: The Obsidian CLI has `read`, `create`, `append` but no `update`/`write` for existing files. How do we modify mid-file content (e.g., inserting a mapping marker into speeds.md)? Options:
   - Add `ObsidianCLI.write()` that does direct file write (breaking pure CLI principle for updates)
   - Check if `obsidian create` supports overwriting existing notes
   - Use a combination of read + delete + create

2. **POI numbering persistence**: POI numbers are determined by scanning the folder, not stored in config (unlike speed counters). This means deleted POIs leave gaps, and the next number is max(existing) + 1. Is this acceptable, or should POI counters go in `.lionnotes.toml` too?

3. **Review command interactivity**: The plan.md says `lionnotes review` is interactive (triage workflow). For Phase 3, should it be:
   - **Read-only listing** (just show unmapped speeds / inbox entries) — simpler, sufficient for MCP
   - **Interactive prompts** (step through each entry, ask where to assign) — better human UX but more complex
   - Recommendation: read-only listing for Phase 3, interactive mode deferred to Phase 6 polish

4. **SMOC section detection**: SMOCs have `### Core`, `### Peripheral`, `### References` headings. What if a user renames or removes these? Should we:
   - Fail with a clear error
   - Fall back to appending at end of `## Map` section
   - Recommendation: fall back to end of `## Map`, warn if expected section not found

---

## Files Modified/Created

| File | Action | Description |
|---|---|---|
| `src/lionnotes/maps.py` | **Create** | SMOC/GSMOC read, update, rebuild; POI/ref creation |
| `src/lionnotes/review.py` | **Create** | Speed parsing, mapping, inbox triage |
| `src/lionnotes/obsidian.py` | **Modify** | Add `write()` method for content replacement |
| `src/lionnotes/cli.py` | **Modify** | Add review, map, poi, ref, subjects pp commands |
| `tests/test_maps.py` | **Create** | Tests for maps module |
| `tests/test_review.py` | **Create** | Tests for review module |
| `tests/test_cli_phase3.py` | **Create** | CLI integration tests for Phase 3 commands |

## Estimated Scope

- ~250-300 LOC for maps.py
- ~150-200 LOC for review.py
- ~100-150 LOC for CLI additions
- ~300-400 LOC for tests
- Total: ~800-1050 LOC
