# Implementation Plan: LionNotes — Thought Mapping Tooling for Obsidian

## Overview

Build a **Python CLI + MCP server** that implements Lion Kimbro's thought mapping
methodology (from "How to Make a Complete Map of Every Thought You Think") as
collaborative tooling for a person and LLM to maintain a memory system in an
Obsidian vault. The tooling wraps the **official Obsidian CLI (v1.12+)** for all
vault operations.

This is not a digitization of the book — it is an implementation of the *system*
the book describes, modernized for digital use.

---

## Core Concepts → Digital Equivalents

| Kimbro Concept | Digital Implementation | CLI Command |
|---|---|---|
| **Speed Thoughts** (pan-subject & subject) | Quick-capture notes with subject/hint/content fields | `lionnotes capture` |
| **Subject Map of Contents (SMOC)** | Auto-generated MOC notes per subject with wikilinks | `lionnotes map` |
| **Grand Subject MOC (GSMOC)** | Root MOC note linking all subjects, auto-maintained | `lionnotes gsmoc` |
| **Points of Interest (POI)** | Long-form notes within a subject, numbered & titled | `lionnotes poi` |
| **Purpose & Principles (P&P)** | Frontmatter `includes`/`excludes` + boundary note per subject | `lionnotes pp` |
| **Subject Registry (GSR)** | Structured index of all subjects with metadata | `lionnotes subjects` |
| **Caches / Binders** | Vault folders: carry-about, common-store, archive | `lionnotes cache` |
| **Speed→Map→POI flow** | Review workflow: triage speeds, place on maps, expand to POIs | `lionnotes review` |
| **Chronolog** | Daily/periodic timestamped entries per subject | `lionnotes chrono` |
| **Late Binding** | Create stubs, defer structure; don't over-organize early | built into all commands |
| **4-Color System** | Obsidian callouts: `[!note]` blue, `[!tip]` green, `[!warning]` red, `[!abstract]` structural | `lionnotes color` |
| **Abbreviations/Shorthand (A/S)** | Per-subject and global alias definitions in frontmatter | `lionnotes alias` |
| **Out Cards** | Redirect notes that point to where content moved | automatic on move |
| **Transcription checkoff** | Frontmatter `mapped: true/false` on speed notes | `lionnotes review` |
| **References (REF)** | Reference notes with structured citation metadata | `lionnotes ref` |
| **Index** | Late-bound keyword→note index, built on demand | `lionnotes index` |
| **Strategy (stickies)** | Frontmatter `priority` field + `#strategy` tag on active items | `lionnotes strategy` |
| **Unplaced** | Proto-subjects folder for notes not yet assigned | `lionnotes unplaced` |

---

## Architecture

```
LionNotes/
├── original/book.txt              # Source material (existing)
├── docs/                          # Project docs (existing)
├── src/
│   └── lionnotes/
│       ├── __init__.py
│       ├── cli.py                 # Typer CLI entrypoint
│       ├── obsidian.py            # Obsidian CLI wrapper (subprocess calls)
│       ├── vault.py               # Vault state: subjects, registry, config
│       ├── capture.py             # Speed thought capture
│       ├── subjects.py            # Subject CRUD, P&P, GSMOC
│       ├── maps.py                # SMOC generation & updating
│       ├── review.py              # Speed→Map→POI triage workflow
│       ├── chrono.py              # Chronolog operations
│       ├── templates.py           # Note templates (speed, POI, P&P, etc.)
│       ├── strategy.py            # Priority/strategy management
│       ├── mcp_server.py          # MCP server exposing tools for LLMs
│       └── config.py              # LionNotes config (vault path, etc.)
├── pyproject.toml                 # Package config (Typer, MCP SDK deps)
├── tests/
│   ├── test_capture.py
│   ├── test_subjects.py
│   ├── test_maps.py
│   ├── test_review.py
│   └── ...
└── CLAUDE.md
```

---

## Obsidian CLI Integration (`obsidian.py`)

All vault I/O goes through the Obsidian CLI. This module wraps it:

```python
class ObsidianCLI:
    """Wrapper around `obsidian` CLI (v1.12+)."""

    def __init__(self, vault: str | None = None):
        self.vault = vault  # None = most recently focused vault

    def read(self, file: str) -> str: ...
    def create(self, name: str, content: str, template: str = None, silent: bool = True) -> None: ...
    def append(self, file: str, content: str) -> None: ...
    def search(self, query: str, path: str = None, limit: int = 20) -> list[str]: ...
    def search_context(self, query: str, limit: int = 10) -> list[dict]: ...
    def property_set(self, file: str, name: str, value: str) -> None: ...
    def property_get(self, file: str, name: str) -> str: ...
    def tags(self, sort: str = "count") -> list[str]: ...
    def backlinks(self, file: str) -> list[str]: ...
    def daily_read(self) -> str: ...
    def daily_append(self, content: str) -> None: ...
    def rename(self, file: str, new_name: str) -> None: ...  # auto-updates wikilinks
```

Key design decision: **All file operations go through the Obsidian CLI** so that
wikilinks are automatically updated on renames/moves, the search index stays
current, and the vault state is always consistent. No direct file manipulation.

---

## CLI Commands (`cli.py`)

Built with [Typer](https://typer.tiangolo.com/). Installed as `lionnotes`.

### `lionnotes init`
Initialize a new LionNotes vault (or adopt an existing Obsidian vault):
- Create folder structure: `_inbox/`, `_strategy/`, `_templates/`
- Create GSMOC note
- Create Global A/S note
- Create Subject Registry note
- Store config in `.lionnotes.toml` at vault root

### `lionnotes doctor`
Validate the LionNotes environment and flag maintenance needs:
- Check Obsidian is running and CLI version is v1.12+
- Verify vault is accessible and `.lionnotes.toml` exists
- Report SMOC/GSMOC inconsistencies (orphan links, missing entries)
- Check for unresolved template variables in notes
- **Soft triggers** (non-blocking warnings):
  - `_inbox/unsorted.md` has accumulated entries → suggest triage
  - Any subject has 30+ unmapped speed entries → suggest synthesis
  - Subjects on `_strategy/maintenance-queue.md` → remind about pending reorg

### `lionnotes capture [CONTENT]`
Capture a speed thought (the core daily operation):
- `--subject` / `-s`: Target subject (if known; omit for pan-subject)
- `--hint` / `-h`: Context hint (1-3 words)
- `--type` / `-t`: Thought type (observation, question, goal, problem, action, idea...)
- If no `CONTENT` arg, opens `$EDITOR` or reads from stdin
- If subject is specified, appends to `{subject}/speeds.md`
- If pan-subject (no `-s`), appends to `_inbox/unsorted.md` for later triage
- Each speed page (`speeds.md`) has frontmatter: `type: speeds`, `subject`, `entry_count`, `last_entry`
- Each entry within the page follows the format: `- S[N]: (context: hint) content #thought/type`
- Mapped entries are suffixed with `[→ POI-N]` (e.g., `[→ POI-07]`); unmapped entries have no suffix

### `lionnotes review`
Interactive triage of unmapped speed thoughts:
- `--subject` / `-s`: Review speeds for one subject (default: all)
- `--pan`: Review `_inbox/unsorted.md` speeds and assign them to subjects
- For each unmapped speed:
  - Show content, hint, context
  - Options: **map** (place on SMOC), **expand** (start a POI), **skip**, **archive**
  - On map: add wikilink to subject's SMOC, mark `mapped: true`
  - On expand: create new POI note, link from SMOC

### `lionnotes subjects`
Manage the subject taxonomy:
- `lionnotes subjects list` — show all subjects with speed counts, last activity
- `lionnotes subjects create NAME` — create a new subject (tab + SMOC + P&P stub)
- `lionnotes subjects pp NAME` — view/edit Purpose & Principles (`purpose.md`) for a subject
- `lionnotes subjects merge SOURCE TARGET` — merge one subject into another
- `lionnotes subjects split NAME` — interactive split of a subject into two
- `lionnotes subjects promote` — promote an unplaced proto-subject to full subject

### `lionnotes map [SUBJECT]`
View or regenerate a Subject Map of Contents:
- Without args: show the GSMOC
- With subject: show/regenerate that subject's SMOC
- `--rebuild`: Regenerate from all linked notes (useful after reorganization)
- `--format json|text|graph`: Output format

### `lionnotes poi SUBJECT TITLE`
Create or manage Points of Interest:
- Creates a numbered POI note in `{subject}/POI-{n}-{title}.md`
- Auto-links from the subject's SMOC
- `--continue POI_NUM`: Append to an existing POI (sequence continuation)
- POI frontmatter: `poi_number`, `subject`, `title`, `date`, `sequence_page`

### `lionnotes chrono [CONTENT]`
Add a chronolog entry:
- Appends timestamped entry to today's daily note or a subject's speed page
- `--subject` / `-s`: Subject-specific entry (default: global daily note via `obsidian daily:append`)
- Timestamps use the host machine's local timezone (Obsidian CLI runs locally). Override via `timezone` in `.lionnotes.toml` if needed

### `lionnotes ref SUBJECT TITLE`
Add a reference:
- `--url`, `--author`, `--year`, `--notes`
- Creates a reference note in `{subject}/REF-{n}-{title}.md`
- Auto-numbered, linked from subject's reference TOC

### `lionnotes strategy`
Manage active priorities in `_strategy/active-priorities.md` (the digital equivalent of stickies on the GSMOC):
- `lionnotes strategy list` — show active strategy items
- `lionnotes strategy add SUBJECT DESCRIPTION` — flag something as strategically active
- `lionnotes strategy done ITEM` — remove a strategy flag
- Renders as a special section at the top of the GSMOC

### `lionnotes search QUERY`
Search the vault using Obsidian's index:
- `--subject` / `-s`: Scope to a subject folder
- `--context`: Show surrounding content (uses `search:context`)
- `--speeds-only`: Only search speed notes

### `lionnotes cache`
Manage the carry-about / common-store / archive tiers:
- `lionnotes cache status` — show which subjects are in which tier
- `lionnotes cache promote SUBJECT` — move notes from `{subject}/_archive/` back to active
- `lionnotes cache archive SUBJECT` — move notes into `{subject}/_archive/`
- Archive tier uses per-subject `_archive/` subfolders, not a top-level `Archive/` folder

### `lionnotes index SUBJECT`
Build or update a late-bound index for a subject:
- Scans all notes in the subject for keywords
- Creates/updates an `Index` note with keyword → note mappings
- Only built when requested (late binding principle)

### `lionnotes alias`
Manage abbreviations/shorthands:
- `lionnotes alias set ABBR EXPANSION` — global or per-subject
- `lionnotes alias list` — show all active aliases
- Used by other commands to expand shorthands in display

---

## MCP Server (`mcp_server.py`)

Exposes the same operations as [MCP tools](https://modelcontextprotocol.io/) so
an LLM (Claude, etc.) can collaboratively operate the vault.

Built with the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).

### Tools exposed:

| MCP Tool | Maps to CLI | Description |
|---|---|---|
| `capture_speed` | `lionnotes capture` | Capture a speed thought |
| `list_subjects` | `lionnotes subjects list` | List all subjects |
| `read_smoc` | `lionnotes map SUBJECT` | Read a subject's map of contents |
| `read_gsmoc` | `lionnotes map` | Read the grand subject map |
| `search_vault` | `lionnotes search` | Search the vault |
| `read_note` | (obsidian read) | Read any note's content |
| `review_unmapped` | `lionnotes review` | Get unmapped speeds for review |
| `map_speed` | (part of review) | Place a speed thought on a SMOC |
| `create_poi` | `lionnotes poi` | Create a point of interest |
| `append_chrono` | `lionnotes chrono` | Add a chronolog entry |
| `get_strategy` | `lionnotes strategy list` | Get active strategy items |
| `set_strategy` | `lionnotes strategy add` | Flag something as strategically active |
| `get_subject_pp` | `lionnotes subjects pp` | Read purpose & principles |
| `add_reference` | `lionnotes ref` | Add a reference to a subject |
| `build_index` | `lionnotes index` | Build a late-bound index |

### Resources exposed:

| MCP Resource | Description |
|---|---|
| `lionnotes://gsmoc` | Current GSMOC content |
| `lionnotes://subjects` | Subject registry |
| `lionnotes://strategy` | Active strategy items |
| `lionnotes://speeds/{subject}` | Unmapped speeds for a subject (from `{subject}/speeds.md`) |

### Prompts exposed:

| MCP Prompt | Description |
|---|---|
| `review_speeds` | Guide the LLM through reviewing unmapped speed thoughts |
| `suggest_subjects` | Analyze captured thoughts and suggest subject categorizations |
| `expand_to_poi` | Help expand a speed thought into a full POI |
| `update_smoc` | Suggest SMOC reorganization based on new content |

---

## Vault Structure (generated by `lionnotes init`)

Each subject is a self-contained folder — its speeds, POIs, references, and maps
all live together, like Kimbro's binder metaphor. This makes subject merge/split
operations straightforward and keeps the mental model simple.

```
vault/
├── GSMOC.md                    # Grand Subject Map of Contents (root note)
├── Subject Registry.md         # Hash/index of all subjects
├── Global Aliases.md           # Global abbreviations/shorthands
├── _inbox/
│   └── unsorted.md             # Pan-subject speed thoughts (temporary capture)
├── _strategy/
│   ├── active-priorities.md    # Kimbro's "stickies" — what's hot right now
│   └── maintenance-queue.md    # Subjects needing reorganization
├── _templates/
│   ├── speed-page.md
│   ├── poi.md
│   ├── smoc.md
│   ├── purpose.md
│   ├── reference.md
│   └── subject-bootstrap.md    # Template for initializing a new subject
├── {subject-name}/             # Self-contained subject folder
│   ├── SMOC.md                 # Subject Map of Contents
│   ├── purpose.md              # Purpose & Principles
│   ├── glossary.md             # Abbreviations & Shorthand
│   ├── speeds.md               # Speed thoughts (append-only log)
│   ├── cheatsheet.md           # Quick-reference summary
│   ├── POI-01-topic-name.md    # Point of Interest #1
│   ├── POI-02-topic-name.md    # Point of Interest #2
│   ├── REF-01-source-name.md   # Reference annotation #1
│   └── _archive/               # Archived pages within this subject
├── another-subject/
│   └── ...
└── .lionnotes.toml             # LionNotes config
```
These checks are performed by `lionnotes doctor`:

1. **Link validation**: Check all `[[wikilinks]]` resolve to actual files
2. **Tag consistency**: Verify tag taxonomy is consistently applied
3. **Graph connectivity**: Ensure no orphan notes exist
4. **SMOC/GSMOC consistency**: Detect orphan entries and missing POIs in maps

---

## Frontmatter Schemas

### Speed Page (`speeds.md`)
```yaml
---
type: speeds
subject: "Personal Psychology"
entry_count: 47
last_entry: 2026-03-07T14:23:00
---
# Personal Psychology — Speed Thoughts

- S46: (context: procrastination) Motivation decays exponentially after initial enthusiasm #thought/observation
- S47: (context: motivation decay) The "kitty model" — interest must be rekindled, not sustained #thought/principle [→ POI-07]
```
Each entry is a line in the append-only log. Metadata (context, type, mapped status) is inline, not YAML frontmatter.

### POI
```yaml
---
type: poi
poi_number: 7
subject: "Personal Psychology"
title: "The Kitty Model"
sequence_page: 1
date_created: 2026-03-07
date_modified: 2026-03-07
---
```

### Subject SMOC
```yaml
---
type: smoc
subject: "Personal Psychology"
version: 2
speed_count: 140
poi_count: 26
last_activity: 2026-03-07
---
```

### Purpose & Principles (`purpose.md`)
```yaml
---
type: pp
subject: "Personal Psychology"
version: 1
includes:
  - "Psychological forces"
  - "Self-image"
  - "Motivation"
excludes:
  - target: "Metaphysics"
    items: ["Non-mechanical forces", "National forces"]
  - target: "Values"
    items: ["Values", "Goals"]
---
```

### Reference
```yaml
---
type: reference
ref_number: 3
subject: "Global Knowledge Infrastructure"
title: "Towards High-Performance Organizations"
author: "Douglas C Engelbart"
year: 1992
url: ""
expanded: false
---
```

---

## Implementation Phases

### Phase 1: Foundation
- `pyproject.toml` with Typer + MCP SDK dependencies
- `obsidian.py` — Obsidian CLI wrapper with error handling
- `config.py` — `.lionnotes.toml` reader/writer (including per-subject speed counters)
- `templates.py` — note template resolution (LionNotes owns variable resolution, not Obsidian Templater)
- `lionnotes init` command (creates `_inbox/`, `_strategy/`, `_templates/`)
- `lionnotes doctor` command (validates Obsidian CLI version, vault access, environment)
- Basic tests for Obsidian CLI wrapper (mocked)

### Phase 2: Core Capture Loop
- `lionnotes capture` — speed thought capture (the most frequent operation)
- `lionnotes chrono` — daily chronolog
- `lionnotes subjects create` / `list`
- `lionnotes search` — vault search
- Integration tests with a test vault

### Phase 3: Organization & Review
- `lionnotes review` — triage unmapped speeds
- `lionnotes map` — SMOC generation & viewing
- `lionnotes poi` — POI creation
- `lionnotes subjects pp` — Purpose & Principles
- `lionnotes gsmoc` — GSMOC auto-generation
- `lionnotes ref` — reference management

### Phase 4: Advanced Features
- `lionnotes strategy` — priority management
- `lionnotes cache` — tier management (carry/common/archive)
- `lionnotes index` — late-bound index generation
- `lionnotes alias` — abbreviation management
- `lionnotes subjects merge/split/promote`

### Phase 5: MCP Server
- MCP server with all tools from the table above
- MCP resources for vault state
- MCP prompts for guided LLM workflows (including the agent protocol from `kimbro-memory-architecture.md`)
- Integration with Claude Code via MCP config
- Error semantics for each MCP tool (auto-create vs. fail on missing subject, etc.)
- Pagination parameters for `search_vault` and `review_unmapped`

### Phase 6: Polish
- Error handling and edge cases
- `--help` documentation for all commands
- Config validation
- README with setup instructions

---

## Technology Choices

| Concern | Choice | Rationale |
|---|---|---|
| CLI framework | Typer | Pythonic, auto-help, type hints |
| Vault I/O | Obsidian CLI (v1.12+) | Consistent index, auto-link updates, no corruption risk |
| MCP server | `mcp` Python SDK | Official protocol, works with Claude Code |
| Config format | TOML (`.lionnotes.toml`) | Standard, readable, Python stdlib in 3.11+ |
| Package management | `pyproject.toml` + pip | Standard Python packaging |
| Testing | pytest | Standard, good Typer/CLI testing support |

---

## Key Design Principles

1. **Obsidian CLI as the only I/O layer** — never read/write vault files directly.
   This ensures search indexes, backlinks, and wikilink resolution stay consistent.

2. **Late binding everywhere** — don't force structure prematurely. Subjects start
   as unplaced notes and graduate. SMOCs are generated on demand. Indexes are built
   only when requested.

3. **Human and LLM are co-equal operators** — the CLI and MCP server operate on
   the same vault. Neither is primary; both are first-class. The MCP server
   exposes the core capture, retrieval, and organization operations; some
   administrative operations (merge, split, doctor, cache) are CLI-only.
   A human can capture, review, and organize via the CLI; an LLM can do the same
   via MCP tools. The vault is the shared state and single source of truth. The
   agent protocol defined in `kimbro-memory-architecture.md` applies to both
   operators — the behavioral rules (session orientation, capture-to-subject,
   synthesis triggers, late-binding reorganization) are the same whether a human
   or LLM is following them.

4. **Speed of capture is paramount** — `lionnotes capture "thought"` must be
   fast and frictionless. All categorization can happen later during review.

5. **Vault is portable** — the vault is standard Obsidian markdown. LionNotes
   tooling enhances it but doesn't lock it in. You can always use the vault
   without LionNotes.

6. **Self-contained subject folders** — each subject is a binder. Its speeds,
   POIs, references, maps, and archive all live in one folder. This makes merge
   and split operations simple and keeps the mental model aligned with Kimbro's
   original binder metaphor.

---

## Related Documents

- **`kimbro-memory-architecture.md`** — the agent protocol (session startup,
  capture rules, synthesis triggers, late-binding reorganization). This protocol
  defines behavioral rules that apply to both human and LLM operators.
- **`corner-cases-review.md`** — edge cases and gaps identified during review.

## What This Plan Does NOT Include

- **Digitizing the book itself** — the original plan for converting book.txt into
  vault content is a separate effort (see `LionVault.md`)
- **Obsidian plugin development** — we use the CLI, not the plugin API
- **Graph database export** — possible future feature, not in scope
- **Mobile support** — Obsidian CLI is desktop-only; mobile use would need a
  different approach
- **Multi-agent concurrency** — multiple agents sharing one vault is a future
  concern requiring optimistic locking (see corner case #10)
