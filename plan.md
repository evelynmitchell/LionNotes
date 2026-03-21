# Phase 4 Implementation Plan: Advanced Features

## Overview

Phase 4 adds five feature groups: **strategy**, **cache**, **index**, **alias**, and **subjects merge/split/promote**. Each follows the established pattern: core logic in a dedicated module, CLI commands in `cli.py`, unit tests for core logic, CLI integration tests in `test_cli_phase4.py`.

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

Manages the carry-about / common-store / archive tiers. The tier is stored as a frontmatter property (`tier`) on the subject's SMOC note, using `obsidian.property_set/property_get`. Archive moves notes into `{subject}/_archive/` subfolder.

**Functions:**
- `get_tier(subject, obsidian) -> str` — read tier from SMOC frontmatter (default: "active")
- `set_tier(subject, tier, obsidian) -> None` — update SMOC frontmatter
- `list_tiers(obsidian) -> dict[str, list[str]]` — all subjects grouped by tier
- `archive_subject(subject, obsidian) -> None` — set tier to "archive"
- `promote_subject(subject, obsidian) -> None` — set tier to "active"

**CLI commands** (new `cache_app` Typer group):
- `lionnotes cache status` — show subjects by tier
- `lionnotes cache archive SUBJECT` — move to archive tier
- `lionnotes cache promote SUBJECT` — move to active tier

**Tests:** `test_cache.py` (unit), cache section in `test_cli_phase4.py`

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
subject: "subject-name"
updated: "2026-03-21"
---
# subject-name — Index

## Keywords
- **keyword-a**: [[POI-01-foo]], [[POI-03-bar]]
- **keyword-b**: [[REF-01-baz]]
```

**CLI command:**
- `lionnotes index SUBJECT` — build/rebuild the index for a subject

**Tests:** `test_index.py` (unit), index section in `test_cli_phase4.py`

---

## Step 4: `lionnotes alias` — Abbreviation Management

**New file:** `src/lionnotes/alias.py`

Manages abbreviations in the Global Aliases note and per-subject glossary notes. Aliases are stored as list entries: `- **ABBR**: expansion`.

**Functions:**
- `list_aliases(obsidian, subject=None) -> list[Alias]` — parse global or per-subject aliases
- `set_alias(abbr, expansion, obsidian, subject=None) -> None` — add/update alias
- `remove_alias(abbr, obsidian, subject=None) -> None` — remove alias

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

Merge one subject into another:
- Move all POI/REF notes from source to target (renumber to avoid collisions)
- Append source speeds to target speeds (renumber)
- Merge source SMOC entries into target SMOC
- Remove source from GSMOC, ensure target is listed
- Create an "out card" note at `{source}/SMOC` pointing to target
- Update config speed counters

**Function:** `merge_subjects(source, target, obsidian, config) -> MergeResult`

### 5b: `subjects split NAME`

Split a subject into two. Since this is inherently interactive (which notes go where), the CLI takes a new subject name and a list of note patterns to move.

- `lionnotes subjects split SOURCE --into NEW_SUBJECT --notes "POI-01,POI-02,REF-01"`
- Creates new subject structure
- Moves specified notes to new subject (renumber)
- Updates both SMOCs
- Adds new subject to GSMOC

**Function:** `split_subject(source, new_name, note_patterns, obsidian, config) -> SplitResult`

### 5c: `subjects promote`

Promote a proto-subject from `_inbox/` or unplaced notes to a full subject:
- `lionnotes subjects promote NAME` — creates full subject structure and moves any matching speeds from inbox

**Function:** `promote_subject(name, obsidian, config) -> str`

**Tests:** `test_subjects_advanced.py` (unit), subjects section in `test_cli_phase4.py`

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
