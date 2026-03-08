#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing uv"
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo "==> Creating venv and installing project"
uv venv
uv pip install -e ".[dev]" 2>/dev/null || uv pip install -e .
uv pip install pytest pytest-cov ruff

echo "==> Verifying install"
.venv/bin/python -c "import lionnotes; print(f'lionnotes {lionnotes.__version__} installed')"
.venv/bin/pytest --co -q 2>/dev/null && echo "Test collection OK" || echo "No tests collected yet"

echo ""
echo "========================================="
echo " LionNotes dev environment ready"
echo " Activate: source .venv/bin/activate"
echo "========================================="
echo ""
echo "NOTE: The Obsidian CLI (v1.12+) requires a running Obsidian desktop instance."
echo "It is not available inside the container. Unit tests mock the CLI calls."
echo "For integration testing, run tests on the host with Obsidian running."
