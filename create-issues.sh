#!/bin/bash
# Run this locally where `gh auth login` has been completed.
# Usage: bash create-issues.sh

set -e

gh issue create \
  --title "Phase 1: Foundation — obsidian.py, config.py, templates.py, init, doctor" \
  --body "$(cat <<'EOF'
## Phase 1: Foundation

Everything else depends on these modules.

### Deliverables

**1a. `src/lionnotes/config.py`** — Config management
- Read/write `.lionnotes.toml` at vault root
- Fields: `vault_path`, per-subject speed counters, timezone override
- `tomllib` (stdlib 3.11+) for reading, `tomli_w` for writing
- `find_config()` walks up from cwd to find `.lionnotes.toml`

**1b. `src/lionnotes/obsidian.py`** — Obsidian CLI wrapper
- `ObsidianCLI` class wrapping subprocess calls to `obsidian` binary
- Methods: `read`, `create`, `append`, `search`, `search_context`, `property_set`, `property_get`, `tags`, `backlinks`, `daily_read`, `daily_append`, `rename`
- Structured error handling: `ObsidianCLIError`, `ObsidianNotRunningError`
- Version check method

**1c. `src/lionnotes/templates.py`** — Note template resolution
- Template strings for: speed page, POI, SMOC, GSMOC, purpose, reference, subject-bootstrap
- `render(template_name, **vars) -> str` with required variable validation

**1d. `lionnotes init` command**
- Creates vault folder structure: `_inbox/`, `_strategy/`, `_templates/`
- Creates `GSMOC.md`, `Subject Registry.md`, `Global Aliases.md`
- Writes `.lionnotes.toml`
- Idempotent — skips existing files

**1e. `lionnotes doctor` command**
- Checks: Obsidian running, CLI version >= 1.12, vault accessible, config exists
- Soft triggers: inbox count, subjects with 30+ unmapped speeds, maintenance queue

### Testing
- All tests mock `ObsidianCLI` — no real Obsidian needed
- Config round-trip, template rendering, CLI arg construction, error parsing

### References
- `docs/implementation-plan.md` — Phase 1
- `docs/corner-cases-review.md` — #1 (CLI dependency), #9 (template resolution)
- `plan.md`
EOF
)"

echo "Created Phase 1 issue"

gh issue create \
  --title "Phase 2: Core Capture Loop — capture, subjects, search" \
  --body "$(cat <<'EOF'
## Phase 2: Core Capture Loop

The most frequent operations — capturing speed thoughts and managing subjects.

### Deliverables

**2a. `src/lionnotes/capture.py`** — Speed thought capture
- `capture_speed(subject, content, hint, thought_type, obsidian, config)`
- Subject capture → append to `{subject}/speeds.md` with auto-incremented S[N]
- Pan-subject capture → append to `_inbox/unsorted.md`
- Speed counter managed in `.lionnotes.toml` per subject
- Entry format: `- S[N]: (context: hint) content #thought/type`

**2b. `src/lionnotes/subjects.py`** — Subject CRUD
- `create_subject(name, obsidian, config)` — folder + SMOC + purpose + speeds + glossary stubs
- `list_subjects(obsidian, config)` — scan vault for subject folders
- Subject name validation: no special chars, no reserved names, lowercase normalization

**2c. `src/lionnotes/vault.py`** — Vault state helpers
- `get_vault_path(config)`, `subject_exists(name, obsidian)`, `count_unmapped_speeds(subject, obsidian)`

**2d. CLI commands**
- `lionnotes capture [CONTENT]` with `--subject/-s`, `--hint/-h`, `--type/-t`, stdin fallback
- `lionnotes subjects list` / `lionnotes subjects create NAME`
- `lionnotes search QUERY` with `--subject/-s`, `--context`, `--speeds-only`

### Depends on
- Phase 1

### References
- `docs/implementation-plan.md` — Phase 2
- `docs/corner-cases-review.md` — #2 (speed numbering), #11 (subject naming)
- `plan.md`
EOF
)"

echo "Created Phase 2 issue"

gh issue create \
  --title "Phase 3: Organization & Review — maps, review, POI, refs" \
  --body "$(cat <<'EOF'
## Phase 3: Organization & Review

The synthesis pipeline — turning raw speed thoughts into structured knowledge.

### Deliverables

**3a. `src/lionnotes/maps.py`** — SMOC/GSMOC generation
- `read_smoc`, `update_smoc`, `read_gsmoc`, `update_gsmoc`
- `rebuild_smoc` — merge-based rebuild (detect new/missing, preserve existing structure)

**3b. `src/lionnotes/review.py`** — Triage workflow
- `get_unmapped_speeds` — parse speeds.md, return unmapped entries
- `map_speed` — mark a speed as mapped (`[→ POI-N]`)
- `triage_inbox` / `assign_inbox_entry` — inbox to subject assignment

**3c. POI and reference management**
- `lionnotes poi SUBJECT TITLE` — create numbered POI, auto-link from SMOC
- `lionnotes ref SUBJECT TITLE` with `--url`, `--author`, `--year`, `--notes`
- `lionnotes map [SUBJECT]` — view SMOC or GSMOC
- `lionnotes subjects pp NAME` — view/edit purpose & principles

### Depends on
- Phase 2

### References
- `docs/implementation-plan.md` — Phase 3
- `docs/corner-cases-review.md` — #4 (SMOC staleness), #14 (search bootstrap)
- `plan.md`
EOF
)"

echo "Created Phase 3 issue"

gh issue create \
  --title "Phase 4: Advanced Features — strategy, cache, index, alias, merge/split" \
  --body "$(cat <<'EOF'
## Phase 4: Advanced Features

### Deliverables

**4a. `src/lionnotes/strategy.py`** — Priority management
- `list_strategy`, `add_strategy`, `remove_strategy`
- CLI: `lionnotes strategy list/add/done`

**4b. Remaining CLI commands**
- `lionnotes cache status/promote/archive` — carry-about/common-store/archive tiers
- `lionnotes index SUBJECT` — late-bound keyword index
- `lionnotes alias set/list` — abbreviation/shorthand management
- `lionnotes subjects merge SOURCE TARGET`
- `lionnotes subjects split NAME`
- `lionnotes subjects promote` — promote unplaced to full subject
- `lionnotes chrono [CONTENT]` with `--subject/-s`

### Depends on
- Phase 3

### References
- `docs/implementation-plan.md` — Phase 4
- `docs/corner-cases-review.md` — #8 (archive semantics), #12 (bulk move safety)
- `plan.md`
EOF
)"

echo "Created Phase 4 issue"

gh issue create \
  --title "Phase 5: MCP Server — tools, resources, prompts" \
  --body "$(cat <<'EOF'
## Phase 5: MCP Server

Expose LionNotes operations as MCP tools so LLMs can collaboratively operate the vault.

### Deliverables

**`src/lionnotes/mcp_server.py`**

**Tools (15):**
| MCP Tool | Maps to |
|---|---|
| `capture_speed` | `capture.py` |
| `list_subjects` | `subjects.py` |
| `read_smoc` | `maps.py` |
| `read_gsmoc` | `maps.py` |
| `search_vault` | search command |
| `read_note` | `obsidian.read()` |
| `review_unmapped` | `review.py` |
| `map_speed` | `review.py` |
| `create_poi` | POI creation |
| `append_chrono` | chrono command |
| `get_strategy` | `strategy.py` |
| `set_strategy` | `strategy.py` |
| `get_subject_pp` | subjects pp |
| `add_reference` | ref command |
| `build_index` | index command |

**Resources (4):** `lionnotes://gsmoc`, `lionnotes://subjects`, `lionnotes://strategy`, `lionnotes://speeds/{subject}`

**Prompts (4):** `review_speeds`, `suggest_subjects`, `expand_to_poi`, `update_smoc`

### Key requirements
- Each tool delegates to the same core functions the CLI uses
- Error semantics per tool (auto-create subject on capture vs. fail on read of nonexistent)
- Pagination: `limit`/`offset` on `search_vault` and `review_unmapped`
- Register MCP server entrypoint in pyproject.toml

### Depends on
- Phase 4

### References
- `docs/implementation-plan.md` — Phase 5
- `docs/kimbro-memory-architecture.md` — operator protocol (embed in MCP prompts)
- `docs/corner-cases-review.md` — #7 (MCP error semantics)
- `plan.md`
EOF
)"

echo "Created Phase 5 issue"

gh issue create \
  --title "Phase 6: Polish — error handling, help text, edge cases" \
  --body "$(cat <<'EOF'
## Phase 6: Polish

### Deliverables

- Error messages and `--help` text for all commands
- Config validation in `lionnotes doctor`
- Edge case handling from `docs/corner-cases-review.md`:
  - #4: SMOC/GSMOC staleness detection
  - #8: Archive search behavior (include/exclude archived notes)
  - #11: Subject naming constraints enforcement
  - #12: Bulk move transaction safety for merge/split
  - #13: Daily notes timezone handling
  - #14: Search bootstrap for new subjects without SMOC
- README with setup instructions (if requested)

### Depends on
- Phase 5

### References
- `docs/corner-cases-review.md` — all remaining open items
- `plan.md`
EOF
)"

echo "Created Phase 6 issue"
echo "All 6 phase issues created."
