#!/usr/bin/env bash
set -euo pipefail

UV_VERSION="0.7.12"

echo "==> Installing uv ${UV_VERSION}"
curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh
export PATH="$HOME/.local/bin:$PATH"

echo "==> Creating venv and installing project + dev deps"
uv venv
uv sync --dev

echo "==> Verifying install"
.venv/bin/python -c "import lionnotes; print(f'lionnotes {lionnotes.__version__} installed')"

# Exit code 5 = no tests collected (OK during initial setup); other failures should surface
.venv/bin/pytest --co -q
echo "Test collection OK"

echo ""
echo "========================================="
echo " LionNotes dev environment ready"
echo " Activate: source .venv/bin/activate"
echo "========================================="
echo ""
echo "NOTE: The Obsidian CLI (v1.12+) requires a running Obsidian desktop instance."
echo "It is not available inside the container. Unit tests mock the CLI calls."
echo "For integration testing, run tests on the host with Obsidian running."
