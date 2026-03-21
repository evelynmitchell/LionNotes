# LionNotes Implementation Plan — CLI / MCP / Core Modules

## Current State
- Typer CLI skeleton with `--version` and placeholder `hello` command
- Package scaffolded with uv, pyproject.toml, devcontainer
- Architecture docs, implementation plan, and corner cases review all written
- No actual vault operations, capture, or MCP code yet

## Build Order

The implementation plan doc defines 6 phases. Here's the concrete coding plan for each, with files, dependencies, and test strategy.

---

### Phase 1: Foundation — `obsidian.py`, `config.py`, `templates.py`, `init`, `doctor`

**1a. `src/lionnotes/config.py`** — Config management
- Read/write `.lionnotes.toml` at vault root
- Fields: `vault_path`, per-subject speed counters, timezone override
- Use `tomllib` (stdlib 3.11+) for reading, `tomli_w` for writing
- `find_config()` walks up from cwd to find `.lionnotes.toml`
- Tests: round-trip read/write, missing config error, counter increment

**1b. `src/lionnotes/obsidian.py`** — Obsidian CLI wrapper
- `ObsidianCLI` class wrapping subprocess calls to `obsidian` binary
- Methods: `read`, `create`, `append`, `search`, `search_context`, `property_set`, `property_get`, `tags`, `backlinks`, `daily_read`, `daily_append`, `rename`
- Structured error handling: `ObsidianCLIError` for CLI failures, `ObsidianNotRunningError` for connection issues
- Version check method (`cli_version() -> tuple[int, ...]`)
- All tests mock subprocess — no real Obsidian needed
- Tests: each method builds correct CLI args, error parsing, version check

**1c. `src/lionnotes/templates.py`** — Note template resolution
- Template strings for: speed page, POI, SMOC, GSMOC, purpose, reference, subject-bootstrap
- `render(template_name, **vars) -> str` — resolves `{{subject}}`, `{{date}}`, `{{title}}`, etc.
- Raises on missing required variables
- Tests: render each template, missing var error, date formatting

**1d. `lionnotes init` command**
- Creates vault folder structure: `_inbox/unsorted.md`, `_strategy/active-priorities.md`, `_strategy/maintenance-queue.md`, `_templates/` (populated from templates.py)
- Creates `GSMOC.md`, `Subject Registry.md`, `Global Aliases.md`
- Writes `.lionnotes.toml` with vault path
- All via ObsidianCLI calls (create, append)
- Idempotent — skips existing files, warns
- Tests: mock ObsidianCLI, verify correct calls

**1e. `lionnotes doctor` command**
- Checks: Obsidian running, CLI version >= 1.12, vault accessible, `.lionnotes.toml` exists
- Soft triggers: inbox entry count, subjects with 30+ unmapped speeds, maintenance queue items
- Output: colored pass/warn/fail checklist
- Tests: mock various failure states

---

### Phase 2: Core Capture Loop — `capture.py`, `subjects.py`, `search`

**2a. `src/lionnotes/capture.py`** — Speed thought capture
- `capture_speed(subject, content, hint, thought_type, obsidian, config)` — core function
- If subject given: append to `{subject}/speeds.md` with auto-incremented S[N]
- If no subject: append to `_inbox/unsorted.md`
- Speed counter managed in `.lionnotes.toml` per subject
- Entry format: `- S[N]: (context: hint) content #thought/type`
- Tests: capture to subject, capture to inbox, counter increment, missing subject error

**2b. `src/lionnotes/subjects.py`** — Subject CRUD
- `create_subject(name, obsidian, config)` — creates folder + SMOC + purpose + speeds + glossary stubs
- `list_subjects(obsidian, config)` — scan vault for subject folders (have SMOC.md)
- Subject name validation: no special chars, no reserved names (`_inbox`, `_strategy`, etc.), lowercase normalization
- Tests: create, list, name validation rejects bad names

**2c. CLI commands**
- `lionnotes capture [CONTENT]` with `--subject/-s`, `--hint/-h`, `--type/-t`, stdin fallback
- `lionnotes subjects list`
- `lionnotes subjects create NAME`
- `lionnotes search QUERY` with `--subject/-s`, `--context`, `--speeds-only`
- Tests: CLI integration tests via CliRunner

**2d. `src/lionnotes/vault.py`** — Vault state helpers
- `get_vault_path(config)` — resolve vault path
- `subject_exists(name, obsidian)` — check if subject folder exists
- `count_unmapped_speeds(subject, obsidian)` — parse speeds.md, count entries without `[→ POI-N]`
- Tests: parsing speeds format, counting logic

---

### Phase 3: Organization & Review — `maps.py`, `review.py`, POI, refs

**Build order:** 3a (`maps.py`) must be implemented first — both `review.py` (3b) and the POI/ref commands (3c) depend on it for SMOC updates.

**3a. `src/lionnotes/maps.py`** — SMOC/GSMOC generation
- `read_smoc(subject, obsidian)` — read and parse a subject's SMOC
- `update_smoc(subject, poi_entry, obsidian)` — add a POI link to a SMOC
- `read_gsmoc(obsidian)` — read the grand map
- `update_gsmoc(subject_entry, obsidian)` — add a subject to GSMOC
- `rebuild_smoc(subject, obsidian)` — merge-based rebuild: scans the subject folder for POI/REF files, compares against existing SMOC entries, adds new entries, flags missing files (but preserves their SMOC entries with a `[missing]` marker rather than deleting them), and preserves any manual ordering/annotations. See corner case #4 in `docs/corner-cases-review.md`
- Tests: SMOC parsing, update idempotency, rebuild merge logic, rebuild preserves manual annotations, rebuild flags missing files

**3b. `src/lionnotes/review.py`** — Triage workflow
- `get_unmapped_speeds(subject, obsidian)` — delegates to `vault.py` speed-parsing helpers, returns full entry objects (not just count)
- `map_speed(subject, speed_num, poi_ref, obsidian)` — mark a speed as mapped by appending inline `[→ POI-N]` suffix (consistent with Phase 2 convention; no separate `mapped` frontmatter field)
- `triage_inbox(obsidian)` — list inbox entries for assignment
- `assign_inbox_entry(entry, target_subject, obsidian, config)` — move from inbox to subject speeds (renumbers into target subject's sequence)
- CLI: `lionnotes review` with `--subject/-s` and `--pan` flags
- Tests: unmapped parsing, mapping marks correctly, inbox assignment
- **Depends on:** `maps.py` (3a) — the "map" and "expand" actions both update the SMOC

**3c. POI and reference commands**
- `lionnotes poi SUBJECT TITLE` — create numbered POI, auto-link from SMOC
- `lionnotes ref SUBJECT TITLE` with `--url`, `--author`, `--year`, `--notes`
- `lionnotes map [SUBJECT]` — view SMOC (with subject) or GSMOC (no args). There is no separate `gsmoc` command
- `lionnotes subjects pp NAME` — view/edit purpose & principles
- Tests: POI numbering, ref numbering, SMOC auto-linking
- **Depends on:** `maps.py` (3a) — POI creation and ref linking both update the SMOC

---

### Phase 4: Advanced Features — `strategy.py`, cache, index, alias, merge/split

**4a. `src/lionnotes/strategy.py`** — Priority management
- `list_strategy(obsidian)` — parse `_strategy/active-priorities.md`
- `add_strategy(subject, description, obsidian)` — append priority item
- `remove_strategy(item, obsidian)` — remove a priority
- CLI: `lionnotes strategy list/add/done`

**4b. Remaining CLI commands**
- `lionnotes cache status/promote/archive`
- `lionnotes index SUBJECT` — late-bound keyword index
- `lionnotes alias set/list`
- `lionnotes subjects merge SOURCE TARGET`
- `lionnotes subjects split NAME`
- `lionnotes subjects promote` — promote unplaced to full subject
- `lionnotes chrono [CONTENT]` with `--subject/-s`

---

### Phase 5: MCP Server — `mcp_server.py`

**5a. `src/lionnotes/mcp_server.py`**
- Built with `mcp` Python SDK
- **Tools** (15 total): `capture_speed`, `list_subjects`, `read_smoc`, `read_gsmoc`, `search_vault`, `read_note`, `review_unmapped`, `map_speed`, `create_poi`, `append_chrono`, `get_strategy`, `set_strategy`, `get_subject_pp`, `add_reference`, `build_index`
- **Resources** (4): `lionnotes://gsmoc`, `lionnotes://subjects`, `lionnotes://strategy`, `lionnotes://speeds/{subject}`
- **Prompts** (4): `review_speeds`, `suggest_subjects`, `expand_to_poi`, `update_smoc`
- Each tool delegates to the same core functions the CLI uses (capture.py, subjects.py, etc.)
- Error semantics per tool: auto-create subject on capture vs. fail on read of nonexistent
- Pagination: `limit`/`offset` on `search_vault` and `review_unmapped`
- Register MCP server entrypoint in pyproject.toml
- Tests: mock core functions, verify tool schemas, test error responses

---

### Phase 6: Polish

- Error messages and `--help` text for all commands
- Config validation in `lionnotes doctor`
- Edge case handling from corner-cases-review.md (subject naming, archive search, SMOC staleness)
- README with setup instructions (if requested)

---

## Key Architectural Decisions

1. **Core functions are CLI-independent** — `capture.py`, `subjects.py`, `maps.py`, etc. are plain Python functions that take an `ObsidianCLI` instance. CLI and MCP both call into them. No business logic in `cli.py` or `mcp_server.py`.

2. **Vault I/O through ObsidianCLI when available** — runtime commands use `ObsidianCLI` for all vault I/O so that the search index and wikilinks stay consistent. `init` and `doctor` fall back to direct file reads/writes when Obsidian is not running (setup may happen before Obsidian is available). Tests mock the `ObsidianCLI` class.

3. **Subject name normalization** — lowercase, hyphens for spaces, reject reserved names and special chars. Applied at creation time.

4. **Speed counter in config** — `.lionnotes.toml` holds per-subject monotonic counters. Never reused. Concurrent writes are a known limitation (corner case #10, deferred).

5. **Templates owned by LionNotes** — `templates.py` does `{{var}}` resolution. Obsidian Templater is not involved.

## Suggested Starting Point

Phase 1 (foundation) first — `config.py`, `obsidian.py`, `templates.py`, then `init` and `doctor`. Everything else depends on these.
