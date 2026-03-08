# Corner Cases Review: Memory Architecture & Implementation Plan

Reviewed: `docs/kimbro-memory-architecture.md` and `docs/implementation-plan.md`
Date: 2026-03-08
Reconciliation update: 2026-03-08

---

## 1. Obsidian CLI Dependency — Single Point of Failure

**Corner case:** The entire system assumes Obsidian CLI v1.12+ is installed, running, and that a vault is open. What happens when:

- **Obsidian is not running?** The CLI requires a running Obsidian instance. A headless server, CI environment, or SSH session won't have one. Neither document addresses this.
- **Multiple vaults are open?** The architecture doc uses `vault: None` meaning "most recently focused vault." If a user has two vaults open, the wrong one could be targeted silently.
- **CLI version mismatch?** `v1.12+` is specified but there's no version check. Older CLI versions may silently behave differently (e.g., missing `search:context`, different `move` semantics).
- **CLI command fails mid-operation?** The implementation plan's `obsidian.py` wrapper shows no retry or transactional semantics. A failed `obsidian move` could update the source but not the target, leaving broken wikilinks.

**Recommendation:** Add a `lionnotes doctor` command that validates the environment (Obsidian running, CLI version, vault accessible). The `obsidian.py` wrapper needs explicit error handling strategy — at minimum, detect and report CLI failures rather than silently swallowing them.

**Status: Partially addressed.** `lionnotes doctor` is now specified in the implementation plan (Phase 1). Error handling strategy for `obsidian.py` still needs detailed specification during implementation.

---

## 2. Speed Number Collisions and Gaps

**Corner case:** Both documents assume auto-incrementing speed numbers (`S47`, `S48`, etc.) but neither specifies the numbering authority.

- **Concurrent capture:** If both a human (via CLI) and an LLM (via MCP) capture speed thoughts simultaneously to the same subject, who allocates the number? There's no locking mechanism.
- **Number source:** Is the number derived from frontmatter `speed_number` of the last file in the folder? From a counter in the SMOC? From a config file? Each approach has different failure modes.
- **Gaps after deletion:** If speed S45 is archived/deleted, does S45 ever get reused? The architecture doc marks synthesized speeds with `[→ POI-N]` but doesn't address deletion.
- **Pan-subject to subject migration:** When a pan-subject speed is triaged to a subject, does it get renumbered in the subject's sequence, or keep its pan-subject number? The architecture doc and implementation plan differ — the architecture doc uses a single `speeds.md` file per subject (append-only), while the implementation plan uses individual speed note files in `Speeds/{subject}/`.

**Recommendation:** Define a single numbering strategy. A monotonic counter stored in `.lionnotes.toml` per subject would be simplest. Document that numbers are never reused. Resolve the structural disagreement between the two documents (single file vs. individual files for speeds).

**Status: Partially addressed.** The structural disagreement is resolved — both documents now use a single append-only `speeds.md` per subject. Per-subject speed counters in `.lionnotes.toml` are specified. Concurrent write semantics still need implementation-time design.

---

## 3. Structural Disagreement Between the Two Documents

This is the largest gap. The two documents **previously** described different vault structures (now resolved — shown here for historical context):

| Aspect | Architecture Doc (adopted) | Implementation Plan (was) |
|---|---|---|
| Speed thoughts | Single `{subject}/speeds.md` (append-only) | Individual files in `Speeds/{subject}/` |
| POIs location | `{subject}/POI-N-title.md` (inside subject folder) | `POI/{subject}/POI-{n} {title}.md` (separate top-level folder) |
| References | `{subject}/REF-N-title.md` (inside subject folder) | `References/{subject}/REF-{n} {title}.md` (separate top-level folder) |
| Subject folder | Self-contained (`{subject}/SMOC.md`, `speeds.md`, `POI-*.md`) | Split across `Subjects/`, `Speeds/`, `POI/` top-level folders |
| Inbox | `_inbox/unsorted.md` | `Speeds/_pan/` |
| Strategy | `_strategy/active-priorities.md` | `Strategy.md` (root-level file) |
| Templates | `_templates/` | `Templates/` |
| Glossary/cheatsheet | Per-subject files | Not mentioned |
| Config | Not mentioned | `.lionnotes.toml` |

**Impact:** These are not cosmetic differences — they affect wikilink paths, CLI command targets, and the fundamental mental model. The architecture doc's self-contained subject folders are simpler to reason about. The implementation plan's split structure makes cross-subject queries easier but complicates subject moves/merges.

**Recommendation:** Pick one. Document the rationale. The architecture doc's approach (everything in a subject folder) is more aligned with Kimbro's binder metaphor and makes `subjects merge/split` far simpler.

**Status: RESOLVED.** Both documents now use self-contained subject folders (the architecture doc's approach). Each subject is a folder containing `SMOC.md`, `purpose.md`, `glossary.md`, `speeds.md`, `cheatsheet.md`, `POI-*.md`, `REF-*.md`, and `_archive/`. Global infrastructure uses underscore-prefixed folders: `_inbox/`, `_strategy/`, `_templates/`. Rationale: closer to Kimbro's binder metaphor, simpler merge/split, easier mental model.

---

## 4. SMOC/GSMOC Staleness and Consistency

**Corner case:** The maps (SMOC, GSMOC) are separate notes that must stay in sync with the actual vault content.

- **Orphan entries:** A POI is deleted or moved but its SMOC entry isn't updated. The architecture doc's late-binding principle says "fix it when you notice," but an LLM following a broken SMOC link will waste a tool call and get an error.
- **Missing entries:** A POI is created via direct Obsidian editing (not through `lionnotes`) and never gets added to the SMOC. The map becomes incomplete.
- **GSMOC version conflicts:** The architecture doc has a `version` field on the GSMOC. When is this incremented? What does version 2 vs. version 3 mean operationally?
- **Rebuild idempotency:** `lionnotes map --rebuild` regenerates the SMOC, but what happens to manually curated ordering or annotations in the existing SMOC? A regeneration would destroy hand-crafted structure.

**Recommendation:** The `--rebuild` command should merge rather than replace — detect new/missing entries and flag them, preserving existing structure. Add a `lionnotes lint` or `lionnotes check` command that reports SMOC/GSMOC inconsistencies without modifying anything.

---

## 5. `P&P.md` Filename — Ampersand in Filenames

**Corner case:** The implementation plan uses `P&P.md` as a filename. The `&` character is problematic:

- Shell escaping: `obsidian read file="Subjects/python/P&P"` — the `&` may be interpreted by the shell as a background operator.
- URL encoding: wikilinks like `[[Subjects/python/P&P]]` may not resolve correctly in all Obsidian contexts.
- Cross-platform: Windows NTFS handles `&` in filenames but some tooling (PowerShell, batch scripts) will break.

**Recommendation:** Rename to `Purpose-and-Principles.md` or `PP.md`.

**Status: RESOLVED.** Renamed to `purpose.md` in both documents. No shell-problematic characters.

---

## 6. The "Late Binding" Escape Hatch Can Lead to Permanent Chaos

**Corner case:** Kimbro's late-binding principle ("don't organize until retrieval demands it") is a good principle, but the architecture doc provides no signal for *when* reorganization is demanded.

- **Trigger thresholds:** The architecture doc says "~30 un-synthesized entries" triggers synthesis. What triggers reorganization? There's no equivalent threshold for SMOC staleness, subject size, or link breakage.
- **Unplaced notes that stay unplaced:** The implementation plan has an `Unplaced/` folder. Without a review trigger, notes can rot there indefinitely. There's no aging mechanism or nag.
- **Inbox zero never happens:** `_inbox/unsorted.md` / `Speeds/_pan/` accumulates pan-subject speeds. The `lionnotes review --pan` command exists, but nothing prompts the user/LLM to run it.

**Recommendation:** Add soft triggers to the agent protocol: "If `Unplaced/` has more than N notes, suggest triage during session startup." "If pan-subject speeds exceed N, the session startup orientation should flag this." These aren't violations of late binding — they're demand signals.

**Status: Partially addressed.** The operator protocol (Section 3.1) now includes soft trigger checks during session startup. `lionnotes doctor` will flag inbox accumulation and subjects with 30+ un-synthesized speeds. Specific numeric thresholds still need calibration during use.

---

## 7. MCP Server — Missing Error Semantics and Pagination

**Corner case:** The MCP server table lists tools but doesn't specify:

- **Error responses:** What does `capture_speed` return when the subject doesn't exist? Does it auto-create? Fail? The MCP protocol has error conventions; none are specified.
- **Pagination for large results:** `search_vault` and `review_unmapped` could return hundreds of results. There's no `limit`/`offset` parameter on the MCP tools (the CLI `search` has `limit`, but the MCP tool table doesn't show it).
- **Idempotency:** Is `capture_speed` idempotent? If an LLM retries a failed call, will it create duplicate speed notes?
- **Authentication/authorization:** The MCP server gives full read/write access to the vault. There's no mention of scoping (e.g., read-only mode for untrusted agents).
- **Resource freshness:** MCP resources like `lionnotes://gsmoc` — are these cached? Live reads? If cached, what's the invalidation strategy?

**Recommendation:** Define error behavior for each MCP tool. Add pagination parameters. Consider a `dry_run` parameter for mutating operations. Document whether resources are live or cached.

**Status: Partially addressed.** The implementation plan's Phase 5 now explicitly includes error semantics and pagination parameters as deliverables. Detailed per-tool behavior still needs specification during implementation.

---

## 8. Archive Semantics Are Underspecified

**Corner case:** Both documents mention archiving but define it differently:

- Architecture doc: `_archive/` subfolder within each subject, or `archived: true` property.
- Implementation plan: Top-level `Archive/` folder.

Additional gaps:
- **Does archived content appear in search results?** If yes, it pollutes results. If no, knowledge is lost.
- **Can archived notes be un-archived?** The `cache promote` command suggests yes, but `archive` and `cache` seem to be conflated.
- **Archive vs. cache tiers:** The implementation plan introduces carry-about/common-store/archive tiers (from Kimbro) but the architecture doc only has active/archive. These are different systems.

**Recommendation:** Clarify whether the three-tier cache system (carry/common/archive) replaces the simple active/archive distinction, or layers on top of it. Define search behavior for each tier.

**Status: Partially addressed.** Both documents now use per-subject `_archive/` subfolders (not a top-level `Archive/` folder). The `lionnotes cache` command manages carry-about/common-store/archive tiers using properties on the subject, while `_archive/` handles individual note archival within a subject. Search behavior per tier still needs specification.

---

## 9. Template Variable Resolution

**Corner case:** The architecture doc's templates use `{{subject}}`, `{{date}}`, `{{title}}`, etc. Neither document specifies:

- **Who resolves these?** The Obsidian CLI's `--template` flag? LionNotes' `templates.py`? Obsidian's Templater plugin?
- **What if a variable is missing?** Does `{{subject}}` render literally as the string `{{subject}}`? Error out? Prompt the user?
- **Template versioning:** If templates change after vault initialization, existing notes don't get updated. A v2 template with new frontmatter fields creates inconsistency with v1 notes.

**Recommendation:** LionNotes should own template resolution (in `templates.py`), not rely on Obsidian's Templater plugin. Define required vs. optional template variables. Document that template changes are forward-only.

**Status: Addressed in plan.** The implementation plan now specifies that `templates.py` owns variable resolution. Required/optional variable definitions and forward-only semantics still need specification during implementation.

---

## 10. Multi-Agent Concurrency (Phase 3 Architecture Doc)

**Corner case:** The architecture doc mentions "multiple agents sharing one vault" as a Phase 3 feature, but the implementation plan doesn't address it at all.

- **Write conflicts:** Two agents appending to the same `speeds.md` simultaneously. Obsidian CLI likely doesn't handle concurrent writes.
- **Strategy conflicts:** Two agents updating `active-priorities.md` with different priorities.
- **SMOC update races:** Agent A creates POI-13 and updates the SMOC. Agent B creates POI-14 and overwrites A's SMOC update.
- **Identity:** How does a speed thought's provenance get tracked? Which agent (or human) captured it?

**Recommendation:** If multi-agent is a goal, the `obsidian.py` wrapper needs at minimum optimistic locking (read-modify-write with conflict detection). Add an `author` field to speed thought frontmatter. Consider whether this is realistic given Obsidian CLI's design.

---

## 11. Subject Naming Constraints

**Corner case:** Neither document specifies valid subject names.

- **Spaces and special characters:** `"Personal Psychology"` is used as an example subject. This becomes a folder name. Spaces in folder paths require careful quoting in every CLI command.
- **Case sensitivity:** Is `Python` the same subject as `python`? On macOS (case-insensitive FS) yes, on Linux no.
- **Nested subjects:** Can subjects be hierarchical (`programming/python`)? The architecture doc's `async-python` split example suggests flat naming, but nothing prevents nesting.
- **Reserved names:** `_inbox`, `_strategy`, `_templates`, `_archive` use underscore prefixes. What if a user creates a subject called `_archive`?
- **Name collisions with vault structure:** A subject named `GSMOC`, `Templates`, or `Archive` would collide with the top-level vault structure.

**Recommendation:** Define a subject name validation function: allowed characters, case normalization, reserved name list. Enforce it in `subjects create`.

---

## 12. Obsidian CLI `move` and Wikilink Integrity

**Corner case:** Both documents rely on `obsidian move` / `obsidian rename` to keep wikilinks intact. But:

- **Cross-vault moves:** Not supported by the CLI. Migrating content between vaults is unaddressed.
- **Bulk operations:** `subjects merge` and `subjects split` involve moving many files. If the CLI is called per-file, a failure mid-sequence leaves the merge half-done with broken links.
- **Wikilink formats:** Obsidian supports `[[note]]`, `[[note|alias]]`, `[[folder/note]]`, and `[[note#heading]]`. Does `obsidian move` update all variants? The architecture doc's "Out Card" concept (redirect notes) suggests it might not.

**Recommendation:** Wrap `subjects merge` and `subjects split` in a transaction-like pattern: plan all moves, validate, execute, verify. If any step fails, report what succeeded and what didn't rather than silently leaving a broken state.

---

## 13. Daily Notes Ambiguity

**Corner case:** The architecture doc uses `obsidian daily:read` and `obsidian daily:append`. The implementation plan has `Chrono/{YYYY-MM-DD}.md`.

- **Are these the same thing?** Obsidian's daily notes feature creates notes in a configured folder with a configured date format. The implementation plan's `Chrono/` folder may or may not match.
- **Timezone:** `YYYY-MM-DD` — whose timezone? The server's? The user's configured timezone? An LLM agent doesn't have an inherent timezone.
- **Daily note template:** Obsidian has its own daily note template. LionNotes has a `Chronolog.md` template. Conflict?

**Recommendation:** Decide whether to use Obsidian's built-in daily notes or LionNotes' own chronolog system. If both, document how they relate. Specify timezone handling (use vault's configured timezone or UTC).

---

## 14. Search Limitations

**Corner case:** The architecture doc's retrieval strategy starts with navigational retrieval (GSMOC → SMOC → POI) and falls back to `obsidian search`. But:

- **New subjects have no map structure.** Until speeds are synthesized into POIs and indexed in a SMOC, navigational retrieval finds nothing. The system bootstraps poorly.
- **Search query syntax:** `obsidian search query="type:reference"` — is this Obsidian's search syntax? Dataview query? Frontmatter property filter? The exact query capabilities are unspecified.
- **Speed thought content format:** Speed thoughts contain inline metadata like `(context: ...)` and `#thought/type`. Search results will include this markup. Is there a parser that strips it for clean display?

**Recommendation:** Document the expected search syntax. For the bootstrap problem, the session startup protocol should fall back to folder listing when a subject has no SMOC yet. Speed thought content should have a structured format (frontmatter fields, not inline markup) so it's queryable.

---

## 15. The Architecture Doc and Implementation Plan Target Different Users

**Meta-observation:** The architecture doc (`kimbro-memory-architecture.md`) describes a protocol for an **autonomous LLM agent** operating a vault directly via raw Obsidian CLI commands. The implementation plan describes a **CLI tool for humans** (with MCP as a secondary interface for LLMs).

This creates tension:
- The architecture doc says the agent calls `obsidian append` directly. The implementation plan says everything goes through `lionnotes capture`.
- The architecture doc's agent protocol (Section 3) isn't referenced in the implementation plan at all.
- The implementation plan's `review` command is interactive (human-in-the-loop). The architecture doc's synthesis is agent-autonomous.

**Recommendation:** Clarify the intended usage model. If LionNotes is the abstraction layer, then the architecture doc's raw CLI examples should be updated to use `lionnotes` commands (or MCP tools). The agent protocol from the architecture doc should be referenced in the implementation plan, perhaps as a "session startup" MCP prompt or as instructions embedded in the CLAUDE.md for vault-operating agents.

**Status: RESOLVED.** The usage model is now "true peers" — human (CLI) and LLM (MCP) are co-equal operators of the vault. The architecture doc now shows both raw Obsidian CLI commands and their LionNotes/MCP equivalents. The implementation plan references the architecture doc's operator protocol and includes it in the MCP prompts deliverable (Phase 5). The architecture doc's title changed from "Agent Protocol" to "Operator Protocol" to reflect this.

---

## Summary

| # | Corner Case | Severity | Effort to Fix | Status |
|---|---|---|---|---|
| 1 | Obsidian CLI not running / wrong vault | High | Medium | Partially addressed (`doctor` command) |
| 2 | Speed number collisions | Medium | Low | Partially addressed (counters in `.lionnotes.toml`) |
| 3 | ~~Structural disagreement between docs~~ | ~~High~~ | ~~Medium~~ | **RESOLVED** — self-contained subject folders |
| 4 | SMOC/GSMOC staleness | Medium | Medium | Open |
| 5 | ~~`P&P.md` ampersand in filename~~ | ~~Low~~ | ~~Trivial~~ | **RESOLVED** — renamed to `purpose.md` |
| 6 | Late binding without triggers | Medium | Low | Partially addressed (soft triggers in protocol) |
| 7 | MCP error semantics / pagination | Medium | Medium | Partially addressed (in Phase 5 scope) |
| 8 | Archive semantics underspecified | Medium | Low | Partially addressed (per-subject `_archive/`) |
| 9 | Template variable resolution | Low | Low | Addressed in plan (`templates.py` owns resolution) |
| 10 | Multi-agent concurrency | High | High | Open (deferred, out of initial scope) |
| 11 | Subject naming constraints | Medium | Low | Open |
| 12 | Bulk move transaction safety | Medium | Medium | Open |
| 13 | Daily notes / chronolog ambiguity | Low | Low | Open |
| 14 | Search bootstrap problem | Medium | Low | Open |
| 15 | ~~Docs target different users~~ | ~~High~~ | ~~Medium~~ | **RESOLVED** — co-equal peers model |

The two previously highest-priority items (**#3** and **#15**) are now resolved. Remaining high-severity items are **#10** (multi-agent concurrency, deferred) and **#1** (partially addressed). The remaining open items (#4, #11, #12, #13, #14) should be resolved during implementation.
