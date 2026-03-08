#!/usr/bin/env bash
set -euo pipefail

UV_VERSION="0.7.12"
UV_CHECKSUM="4d9279ad5ca596148a0e0350a90bfe5017457e10a1823912bbe29b28e9ba4c58"

echo "==> Installing uv ${UV_VERSION}"
UV_INSTALLER="$(mktemp)"
curl -LsSf "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-installer.sh" -o "$UV_INSTALLER"
echo "${UV_CHECKSUM}  ${UV_INSTALLER}" | sha256sum -c --quiet
sh "$UV_INSTALLER"
rm -f "$UV_INSTALLER"
export PATH="$HOME/.local/bin:$PATH"

echo "==> Creating venv and installing project + dev deps"
uv venv
uv sync --dev

echo "==> Verifying install"
.venv/bin/python -c "import lionnotes; print(f'lionnotes {lionnotes.__version__} installed')"

# Exit code 0 = collected OK, exit code 5 = no tests collected (OK during initial setup)
set +e
.venv/bin/pytest --co -q
pytest_exit=$?
set -e
if [ "$pytest_exit" -eq 0 ] || [ "$pytest_exit" -eq 5 ]; then
    echo "Test collection OK (exit code ${pytest_exit})"
else
    echo "ERROR: pytest collection failed (exit code ${pytest_exit})"
    exit 1
fi

echo ""
echo "========================================="
echo " LionNotes dev environment ready"
echo " Activate: source .venv/bin/activate"
echo "========================================="
echo ""
echo "NOTE: The Obsidian CLI (v1.12+) requires a running Obsidian desktop instance."
echo "It is not available inside the container."
echo "When Obsidian CLI integration is added, unit tests will mock all CLI calls."
echo "For integration testing, run tests on the host with Obsidian running."
