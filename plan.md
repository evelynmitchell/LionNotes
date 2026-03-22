# Phase 5 Implementation Plan: MCP Server

## Overview

Phase 5 wraps the existing LionNotes core library as an **MCP (Model Context Protocol) server** so that LLM agents (Claude, etc.) can collaboratively operate the vault alongside human CLI users. The server uses the `FastMCP` class from the `mcp` Python SDK (v1.26).

All MCP tools delegate to the same core functions that the CLI uses — no business logic is duplicated. The server is a thin adapter layer.

## Architecture

```
src/lionnotes/
├── mcp_server.py          # NEW — FastMCP server: tools, resources, prompts
└── (existing modules)     # Unchanged — capture, maps, review, strategy, etc.
```

A single new file `mcp_server.py` creates a `FastMCP` instance and registers tools, resources, and prompts. The CLI entrypoint (`cli.py`) gets a new `lionnotes serve` command to launch the MCP server over stdio.

### Shared initialization

Both CLI and MCP need an `ObsidianCLI` instance and a `Config`. The MCP server constructs these at startup (vault path from env var `LIONNOTES_VAULT` or `.lionnotes.toml` discovery). A helper `_get_obsidian_and_config()` in `mcp_server.py` handles this.

## Step 1: MCP Server Skeleton + `lionnotes serve`

**File:** `src/lionnotes/mcp_server.py` (new)

Create the FastMCP app and the initialization helper:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "LionNotes",
    description="Thought mapping system for Obsidian vaults",
)
```

**File:** `src/lionnotes/cli.py` (edit)

Add a `serve` command:

```python
@app.command()
def serve():
    """Start the LionNotes MCP server (stdio transport)."""
    from lionnotes.mcp_server import mcp
    mcp.run(transport="stdio")
```

**Tests:** `tests/test_mcp_server.py` (new)

- Test that the `mcp` object is a `FastMCP` instance
- Test tool/resource/prompt registration counts match expectations

## Step 2: MCP Tools — Core Operations

Register 15 tools that map to the specification table in `implementation-plan.md`. Each tool is a thin wrapper calling the existing core function and returning a structured result.

### Tool list with signatures and error semantics

| MCP Tool | Core Function | Auto-create? | Error behavior |
|---|---|---|---|
| `capture_speed` | `capture.capture_speed()` | No — fails if subject doesn't exist | Returns error message with suggestion to create subject first |
| `list_subjects` | `subjects.list_subjects()` | N/A | Returns empty list if no subjects |
| `read_smoc` | `maps.read_smoc()` | No | Returns error if subject not found |
| `read_gsmoc` | `maps.read_gsmoc()` | No | Returns error if GSMOC not found |
| `search_vault` | `obsidian.search()` | N/A | Returns empty results on no matches |
| `read_note` | `obsidian.read()` | No | Returns error if note not found |
| `review_unmapped` | `review.get_unmapped_speeds()` | N/A | Returns empty list if none |
| `map_speed` | `review.map_speed()` | No | Returns error if speed not found or already mapped |
| `create_poi` | CLI's POI creation logic | No — subject must exist | Returns error if subject not found |
| `append_chrono` | CLI's chrono logic | N/A | Returns error on failure |
| `get_strategy` | `strategy.list_priorities()` | N/A | Returns empty list if no priorities |
| `set_strategy` | `strategy.add_priority()` | N/A | Returns error on empty input |
| `complete_strategy` | `strategy.complete_priority()` | N/A | Returns error on invalid number |
| `get_subject_pp` | `obsidian.read("{subject}/purpose")` | No | Returns error if not found |
| `add_reference` | CLI's ref creation logic | No | Returns error if subject not found |
| `build_index` | `index.build_index()` | No | Returns error if subject SMOC not found |

### Error convention

All tools return a dict with:
- Success: `{"status": "ok", ...result fields...}`
- Error: `{"status": "error", "error": "descriptive message"}`

This avoids MCP-level exceptions and gives the LLM actionable error messages.

### Pagination

`search_vault` and `review_unmapped` accept optional `limit` (default 20) and `offset` (default 0) parameters.

### Example tool implementation

```python
@mcp.tool(description="Capture a speed thought to a subject or the inbox")
def capture_speed(
    content: str,
    subject: str | None = None,
    hint: str | None = None,
    thought_type: str | None = None,
) -> dict:
    obsidian, config = _get_obsidian_and_config()
    try:
        entry = _capture_speed(content, obsidian, config, subject, hint, thought_type)
        return {"status": "ok", "entry": entry, "subject": subject or "_inbox"}
    except (SubjectError, ValueError) as e:
        return {"status": "error", "error": str(e)}
```

## Step 3: MCP Resources — Vault State

Register 4 resources for read-only vault state access. Resources are live reads (no caching) — the vault is the source of truth.

| Resource URI | Description | Implementation |
|---|---|---|
| `lionnotes://gsmoc` | Current GSMOC content (raw markdown) | `maps.read_gsmoc()` → `.raw` |
| `lionnotes://subjects` | Subject registry (list with metadata) | `subjects.list_subjects()` → formatted |
| `lionnotes://strategy` | Active strategy items | `strategy.list_priorities()` → formatted |
| `lionnotes://speeds/{subject}` | Unmapped speeds for a subject | `review.get_unmapped_speeds()` → formatted |

The `speeds/{subject}` resource uses a URI template for parameterized access.

### Example resource implementation

```python
@mcp.resource("lionnotes://gsmoc", description="Grand Subject Map of Contents")
def gsmoc_resource() -> str:
    obsidian, _ = _get_obsidian_and_config()
    gsmoc = read_gsmoc(obsidian)
    return gsmoc.raw
```

## Step 4: MCP Prompts — Guided LLM Workflows

Register 4 prompts that embed the operator protocol from `kimbro-memory-architecture.md`. These guide an LLM through structured workflows.

| Prompt Name | Description | Arguments | Returns |
|---|---|---|---|
| `review_speeds` | Guide through reviewing unmapped speed thoughts for a subject | `subject: str` | System message with protocol + current unmapped speeds |
| `suggest_subjects` | Analyze inbox entries and suggest subject categorizations | (none) | System message with inbox contents + existing subjects |
| `expand_to_poi` | Help expand a speed thought into a structured POI | `subject: str, speed_number: int` | System message with speed content + POI template + SMOC context |
| `update_smoc` | Suggest SMOC reorganization based on current content | `subject: str` | System message with current SMOC + all linked notes' titles |

### Example prompt implementation

```python
from mcp.server.fastmcp.prompts import base

@mcp.prompt(description="Guide through reviewing unmapped speed thoughts")
def review_speeds(subject: str) -> list[base.Message]:
    obsidian, _ = _get_obsidian_and_config()
    unmapped = get_unmapped_speeds(subject, obsidian)
    speeds_text = "\n".join(e.raw_line for e in unmapped)
    return [base.UserMessage(
        content=f"Review these unmapped speed thoughts for '{subject}' "
        f"and suggest which should be mapped to existing POIs, "
        f"which should become new POIs, and which can be skipped:\n\n"
        f"{speeds_text}"
    )]
```

## Step 5: `lionnotes serve` CLI Integration + MCP Config

### CLI command

The `serve` command runs the MCP server over stdio (the standard transport for local MCP servers):

```python
@app.command()
def serve():
    """Start the LionNotes MCP server (stdio transport)."""
    from lionnotes.mcp_server import mcp
    mcp.run(transport="stdio")
```

### Claude Code integration

Document in README (Phase 6) how to configure Claude Code to use the server:

```json
{
  "mcpServers": {
    "lionnotes": {
      "command": "lionnotes",
      "args": ["serve"],
      "env": {
        "LIONNOTES_VAULT": "/path/to/vault"
      }
    }
  }
}
```

## Step 6: Tests

**File:** `tests/test_mcp_server.py` (new)

### Unit tests (mocked Obsidian CLI)

All tests mock `ObsidianCLI` the same way existing tests do — no real vault needed.

1. **Registration tests**: Verify tool/resource/prompt counts and names
2. **Tool tests** (one per tool):
   - `test_capture_speed_to_subject` — happy path, verifies entry returned
   - `test_capture_speed_to_inbox` — no subject, goes to inbox
   - `test_capture_speed_missing_subject` — returns error dict
   - `test_list_subjects` — returns subject list
   - `test_read_smoc` / `test_read_gsmoc` — returns raw content
   - `test_search_vault` — with limit/offset
   - `test_read_note` — reads arbitrary note
   - `test_review_unmapped` — returns unmapped speeds with pagination
   - `test_map_speed` — marks speed as mapped
   - `test_create_poi` — creates POI, links from SMOC
   - `test_get_strategy` / `test_set_strategy` / `test_complete_strategy`
   - `test_get_subject_pp` — reads purpose.md
   - `test_add_reference` — creates REF note
   - `test_build_index` — builds keyword index
3. **Resource tests**: Verify each resource returns expected content
4. **Prompt tests**: Verify each prompt returns well-formed messages
5. **Error tests**: Each tool returns `{"status": "error", ...}` on failure (not exceptions)

### CLI integration test

**File:** `tests/test_cli_phase5.py` (new)

- `test_serve_command_exists` — verify `lionnotes serve --help` works

## Implementation Order

1. **Step 1**: Server skeleton + `serve` command (can test immediately)
2. **Step 2**: Tools (largest step — 16 tools, but each is ~10-15 lines)
3. **Step 3**: Resources (4 resources, straightforward)
4. **Step 4**: Prompts (4 prompts, mostly template text)
5. **Step 5**: CLI integration polish
6. **Step 6**: Full test suite

## Key Design Decisions

1. **No business logic in mcp_server.py** — every tool delegates to existing core functions. This ensures CLI and MCP behavior are identical.

2. **Error dicts, not exceptions** — MCP tools return `{"status": "error", "error": "..."}` so the LLM gets actionable feedback rather than opaque protocol errors.

3. **Live resource reads** — no caching. The vault is the single source of truth. Resources always reflect current state.

4. **Vault discovery** — `LIONNOTES_VAULT` env var takes precedence, then `.lionnotes.toml` discovery (same as CLI). This allows flexible configuration in the MCP server config.

5. **stdio transport only** — consistent with MCP convention for local tools. SSE/HTTP can be added later if needed.

6. **POI creation and reference creation** — these require logic currently embedded in `cli.py` (numbering, template rendering, SMOC linking). This logic will be extracted into helper functions in the respective modules (`maps.py` or a new thin helper) so both CLI and MCP can share it. This is the only refactoring needed.

## Corner Cases Addressed

- **Corner case #7** (MCP error semantics): Every tool has defined error behavior. Pagination on search/review.
- **Corner case #1** (Obsidian not running): Tools catch `ObsidianNotRunningError` and return clear error messages.
- **Corner case #2** (speed numbering): Uses same `Config` counter as CLI — no divergence.

## Files Changed

| File | Action | Description |
|---|---|---|
| `src/lionnotes/mcp_server.py` | **New** | FastMCP server: 16 tools, 4 resources, 4 prompts |
| `src/lionnotes/cli.py` | **Edit** | Add `serve` command (~5 lines) |
| `tests/test_mcp_server.py` | **New** | Unit tests for all MCP tools, resources, prompts |
| `tests/test_cli_phase5.py` | **New** | CLI integration test for `serve` command |

Existing core modules are **not modified** (zero regression risk) except for one small refactor: extracting POI-creation and REF-creation helpers from `cli.py` into `maps.py`/`subjects.py` so both CLI and MCP can call them.
