# CLAUDE.md

## Project

LionNotes is a Python CLI + MCP server that implements the thought mapping methodology from Lion Kimbro's "How to Make a Complete Map of Every Thought You Think" as collaborative tooling for a person and LLM to maintain a memory system in an Obsidian vault. All vault I/O goes through the official Obsidian CLI (v1.12+).

## Dev Environment

- **Python 3.11+**, managed with **uv**
- Open in VS Code / Codespaces via `.devcontainer/` for a batteries-included setup
- `uv venv && uv sync --dev` for local development (installs project + dev tools)
- Run tests: `pytest`
- Lint: `ruff check src/ tests/`
- Format: `ruff format src/ tests/`
- The Obsidian CLI (v1.12+) requires a running Obsidian desktop instance on the host. When Obsidian CLI integration is added, unit tests will mock all CLI calls.

## Dev Patterns

- **Mocking `_write_note`**: Modules that import `from lionnotes.maps import _write_note` at module level must be mocked at the *usage site* (e.g. `patch("lionnotes.strategy._write_note")`), not the definition site. The `mock_env` fixture in CLI integration tests patches both `lionnotes.maps._write_note` and any consuming module's copy.
- **Ruff line limit**: 88 characters. Watch f-strings with multiple interpolations.
- **Typer `no_args_is_help`**: Returns exit code 2 (not 0) when invoked with no args.

## Workflow Rules

- After presenting a plan, always wait for explicit user approval before starting implementation. Exiting plan mode is not approval to implement.
