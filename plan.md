# Phase 4 Implementation Plan: Advanced Features

## Overview

Phase 4 adds five feature groups: **strategy**, **cache**, **index**, **alias**, and **subjects merge/split/promote**. Each follows the established pattern: core logic in a dedicated module, CLI commands in `cli.py`, unit tests for core logic, CLI integration tests in `test_cli_phase4.py`.

### Mutation strategy

The `ObsidianCLI` API has no overwrite/update primitive — only `read`, `create`, `append`, `rename`, and `delete`. Modules that need to modify note content (strategy, alias, index) use the **rename-aside-then-create** pattern already established by `maps._write_note()`:

1. Read the current note content via `obsidian.read()`
2. Modify the content in memory
3. Rename the old note aside (e.g., `note` → `note-backup-{timestamp}`)
4. Create the new note with `obsidian.create()` using the modified content
5. Delete the backup via `obsidian.delete()`

This pattern is used by strategy (`complete_priority`), alias (`set_alias`, `remove_alias`), and index (`build_index` on rebuild). The `add_priority` function uses `obsidian.append()` directly since it only adds content.

---

## Step 1: `lionnotes strategy` — Priority Management

**New file:** `src/lionnotes/strategy.py`

Parses and modifies `_strategy/active-priorities.md`. Each priority is a list entry:
```
- [SUBJECT] description #strategy
```

**Functions:**
- `list_priorities(obsidian) -> list[StrategyItem]` — parse active-priorities.md
- `add_priority(subject, description, obsidian) -> StrategyItem` — append entry
- `complete_priority(item_number, obsidian) -> None` — remove entry by number

**Dataclass:**
```python
@dataclass
class StrategyItem:
    number: int
    subject: str
    description: str
    raw_line: str
```

**CLI commands** (new `strategy_app` Typer group):
- `lionnotes strategy list` — display active priorities
- `lionnotes strategy add SUBJECT DESCRIPTION` — add a new priority
- `lionnotes strategy done ITEM` — remove a priority (by number)

**Tests:** `test_strategy.py` (unit), strategy section in `test_cli_phase4.py` (CLI integration)

---

## Step 2: `lionnotes cache` — Tier Management

**New file:** `src/lionnotes/cache.py`

Manages the carry-about / common-store / archive tiers. There are two distinct layers:

1. **Subject-level tiers** (carry-about / common-store / archive) — stored as a frontmatter property (`tier`) on the subject's SMOC note via `obsidian.property_set/property_get`. This controls how prominently the subject appears in listings and GSMOC display. All three tiers remain searchable.
2. **Note-level archival** — individual notes within a subject can be moved to `{subject}/_archive/`. This is for decluttering a subject's active workspace without losing content.

The `cache` command manages subject-level tiers. Note-level archival is a separate concern — moving individual notes into `{subject}/_archive/` via `obsidian.rename()`. A future `lionnotes archive NOTE` command could handle this; it is not in Phase 4 scope. (`subjects split` creates new subjects, which is a different operation.)

**Search behavior by tier:**
- **carry-about** (default): included in all search results, shown first in listings
- **common-store**: included in search results, shown in listings with `[common]` marker
- **archive**: excluded from search results by default; `lionnotes search --include-archived` includes them. Shown in `cache status` but omitted from `subjects list` unless `--all` is passed

**Functions:**
- `get_tier(subject, obsidian) -> str` — read tier from SMOC frontmatter (default: "carry-about")
- `set_tier(subject, tier, obsidian) -> None` — update SMOC frontmatter; validates tier is one of `carry-about`, `common-store`, `archive`
- `list_tiers(obsidian) -> dict[str, list[str]]` — all subjects grouped by tier
- `archive_subject(subject, obsidian) -> None` — set tier to "archive"
- `activate_subject(subject, obsidian) -> None` — set tier to "carry-about"

**CLI commands** (new `cache_app` Typer group):
- `lionnotes cache status` — show subjects by tier
- `lionnotes cache archive SUBJECT` — move to archive tier
- `lionnotes cache promote SUBJECT` — move to carry-about tier

**Changes to existing commands:**
- `lionnotes subjects list` — add `--all` flag; default hides archived subjects
- `lionnotes search` — add `--include-archived` flag; default excludes archived tier subjects

**Tests:** `test_cache.py` (unit), cache section in `test_cli_phase4.py`. Tests must cover search filtering by tier and `subjects list` filtering.

---

## Step 3: `lionnotes index` — Late-Bound Index Generation

**New file:** `src/lionnotes/index.py`

Scans all notes in a subject folder, extracts keywords (wikilinks + #tags), and creates/updates an `{subject}/Index` note with keyword → note mappings.

**Functions:**
- `build_index(subject, obsidian) -> str` — scan subject notes, return index content
- `_extract_keywords(content) -> set[str]` — extract `[[wikilinks]]` and `#tags`
- `_format_index(keyword_map: dict[str, list[str]]) -> str` — render as markdown

**Index note format:**
```markdown
---
type: index
subject: "{{subject}}"
updated: "{{date}}"
---
# {{subject}} — Index

## Keywords
- **keyword-a**: [[POI-01-foo]], [[POI-03-bar]]
- **keyword-b**: [[REF-01-baz]]
```

An `index` template will be added to `templates.py` with required variable `subject`.

**Rebuild behavior:** If `{subject}/Index` already exists, uses the rename-aside-then-create pattern (see Mutation strategy above) to replace it. The index is always fully regenerated, not incrementally updated.

**CLI command:**
- `lionnotes index SUBJECT` — build/rebuild the index for a subject

**Tests:** `test_index.py` (unit), index section in `test_cli_phase4.py`

---

## Step 4: `lionnotes alias` — Abbreviation Management

**New file:** `src/lionnotes/alias.py`

Manages abbreviations in the Global Aliases note and per-subject glossary notes. Aliases are stored as list entries: `- **ABBR**: expansion`.

**Functions:**
- `list_aliases(obsidian, subject=None) -> list[Alias]` — parse global or per-subject aliases
- `set_alias(abbr, expansion, obsidian, subject=None) -> None` — add/update alias (uses rename-aside-then-create when updating an existing alias; uses `obsidian.append()` when adding a new one)
- `remove_alias(abbr, obsidian, subject=None) -> None` — remove alias (uses rename-aside-then-create to rewrite the note without the removed entry)

**Dataclass:**
```python
@dataclass
class Alias:
    abbreviation: str
    expansion: str
    scope: str  # "global" or subject name
```

**CLI commands** (new `alias_app` Typer group):
- `lionnotes alias list [--subject/-s NAME]` — list aliases (global or per-subject)
- `lionnotes alias set ABBR EXPANSION [--subject/-s NAME]` — set an alias
- `lionnotes alias remove ABBR [--subject/-s NAME]` — remove an alias

**Tests:** `test_alias.py` (unit), alias section in `test_cli_phase4.py`

---

## Step 5: `lionnotes subjects merge/split/promote`

**Extend:** `src/lionnotes/subjects.py`

### 5a: `subjects merge SOURCE TARGET`

Merge one subject into another. This is a bulk operation that moves many files — a failure mid-sequence could leave broken state. Uses a **plan-execute-report** pattern (see corner case #12):

**Execution model:**
1. **Plan phase**: read both SMOCs, enumerate all POI/REF/speed files in source, compute renumbered names in target, detect collisions. No mutations yet.
2. **Validate phase**: confirm target exists, source has content, no naming collisions after renumbering. Abort with full report if validation fails.
3. **Execute phase**: perform moves one at a time via `obsidian.rename()`. Track each success/failure in a `MergeResult`.
4. **Finalize phase**: update target SMOC (merge entries), update GSMOC (remove source, ensure target listed), create out card at `{source}/SMOC`, update config speed counters.
5. **Report phase**: return `MergeResult` listing moved/failed/skipped notes. If any moves failed, the CLI prints what succeeded and what didn't — no silent partial state.

**Steps:**
- Move all POI/REF notes from source to target (renumber to avoid collisions)
- Append source speeds to target speeds (renumber into target's sequence)
- Merge source SMOC entries into target SMOC
- Remove source from GSMOC, ensure target is listed
- Create an "out card" note at `{source}/SMOC` pointing to target
- Update config speed counters

**Function:** `merge_subjects(source, target, obsidian, config) -> MergeResult`

**Dataclass:**
```python
@dataclass
class MoveFailure:
    note: str              # note that failed to move
    reason: str            # why it failed

@dataclass
class MergeResult:
    moved: list[str]           # notes successfully moved
    failed: list[MoveFailure]  # notes that failed to move, with reasons
    skipped: list[str]         # notes skipped (e.g., already in target)
    out_card_created: bool
```

### 5b: `subjects split SOURCE --into NEW_SUBJECT --notes "..."`

Split a subject into two. Since this is inherently interactive (which notes go where), the CLI takes a new subject name and a list of note patterns to move. Uses the same **plan-execute-report** pattern as merge.

- `lionnotes subjects split SOURCE --into NEW_SUBJECT --notes "POI-01,POI-02,REF-01"`

**Execution model:**
1. **Plan phase**: resolve note patterns against source folder, compute renumbered names in new subject.
2. **Validate phase**: confirm source exists, patterns match at least one note, new subject name passes `normalize_subject_name()` validation. Abort with report if validation fails.
3. **Execute phase**: create new subject structure, move specified notes (renumber), track results.
4. **Finalize phase**: update source SMOC (remove moved entries), populate new subject's SMOC, add new subject to GSMOC.
5. **Report phase**: return `SplitResult` with moved/failed lists.

**Function:** `split_subject(source, new_name, note_patterns, obsidian, config) -> SplitResult`

**Dataclass:**
```python
@dataclass
class SplitResult:
    new_subject: str           # normalized name of the new subject
    moved: list[str]           # notes successfully moved
    failed: list[MoveFailure]  # notes that failed to move, with reasons
```

### 5c: `subjects promote`

Promote a proto-subject from `_inbox/` or unplaced notes to a full subject:
- `lionnotes subjects promote NAME` — creates full subject structure and moves any matching speeds from inbox
- Name is validated through `normalize_subject_name()` before any mutations (corner case #11)
- Matching inbox entries are identified by subject hint in their context field (e.g., `(context: python)` matches promoting to subject `python`)

**Function:** `promote_subject(name, obsidian, config) -> str`

**Tests:** `test_subjects_advanced.py` (unit), subjects section in `test_cli_phase4.py`. Tests must cover:
- Partial failure in merge (some moves succeed, some fail) — verify report is accurate
- Split with invalid new subject name — verify validation catches it before any mutations
- Promote with name that collides with reserved names — verify rejection

---

## Step 6: Tests & Validation

**New test files:**
- `tests/test_strategy.py` — unit tests for strategy.py
- `tests/test_cache.py` — unit tests for cache.py
- `tests/test_index.py` — unit tests for index.py
- `tests/test_alias.py` — unit tests for alias.py
- `tests/test_subjects_advanced.py` — unit tests for merge/split/promote
- `tests/test_cli_phase4.py` — CLI integration tests for all Phase 4 commands

All tests follow existing patterns: mock `ObsidianCLI`, use `CliRunner`, realistic sample data.

Final validation: `pytest` and `ruff check src/ tests/` pass clean.

---

## Implementation Order

1. **Strategy** (simplest — just parsing/appending a list file)
2. **Cache** (property-based tier management)
3. **Index** (scan + generate, no state mutation beyond creating a note)
4. **Alias** (similar parse/append pattern to strategy)
5. **Subjects merge/split/promote** (most complex — depends on all prior patterns)

Each step: implement core module → add CLI commands → write tests → run `pytest` + `ruff check` to verify.

---

## Corner Cases Addressed

This plan addresses the following items from `docs/corner-cases-review.md`:

| # | Corner Case | How Addressed |
|---|---|---|
| #4 | SMOC/GSMOC staleness | Merge/split finalize phase explicitly updates both SMOCs and GSMOC. Out cards prevent dangling references to merged subjects. |
| #8 | Archive semantics underspecified | Clarified two-layer model: subject-level tiers (carry/common/archive) vs. note-level `_archive/`. Defined search behavior per tier. Added `--include-archived` and `--all` flags. |
| #10 | Multi-agent concurrency | Remains deferred. Risk surface grows (strategy, alias files are shared append targets) but solving this properly requires optimistic locking in `obsidian.py`, which is out of scope. |
| #11 | Subject naming constraints | Already enforced by `normalize_subject_name()`. Promote validates name before any mutations. Split validates new subject name in plan phase. |
| #12 | Bulk move transaction safety | Merge and split use plan-execute-report pattern. All moves planned and validated before execution. Partial failures reported with full accounting of what succeeded/failed. No silent partial state. |

---

## Files Modified/Created

| File | Change |
|---|---|
| `src/lionnotes/strategy.py` | New — priority management |
| `src/lionnotes/cache.py` | New — tier management |
| `src/lionnotes/index.py` | New — index generation |
| `src/lionnotes/alias.py` | New — alias management |
| `src/lionnotes/subjects.py` | Extended — merge, split, promote |
| `src/lionnotes/cli.py` | Extended — all Phase 4 commands |
| `tests/test_strategy.py` | New |
| `tests/test_cache.py` | New |
| `tests/test_index.py` | New |
| `tests/test_alias.py` | New |
| `tests/test_subjects_advanced.py` | New |
| `tests/test_cli_phase4.py` | New |
