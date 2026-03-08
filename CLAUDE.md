# CLAUDE.md

## Project

LionNotes is a Python CLI + MCP server that implements the thought mapping methodology from Lion Kimbro's "How to Make a Complete Map of Every Thought You Think" as collaborative tooling for a person and LLM to maintain a memory system in an Obsidian vault. All vault I/O goes through the official Obsidian CLI (v1.12+).

## Dev Environment

- **Python 3.11+**, managed with **uv**
- Open in VS Code / Codespaces via `.devcontainer/` for a batteries-included setup
- `uv venv && uv pip install -e .` for local development
- `uv pip install pytest pytest-cov ruff` for dev tools
- Run tests: `pytest`
- Lint: `ruff check src/ tests/`
- Format: `ruff format src/ tests/`
- The Obsidian CLI (v1.12+) requires a running Obsidian desktop instance on the host. Unit tests mock all CLI calls.

## Workflow Rules

- After presenting a plan, always wait for explicit user approval before starting implementation. Exiting plan mode is not approval to implement.
