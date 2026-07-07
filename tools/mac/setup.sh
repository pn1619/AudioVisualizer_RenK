#!/usr/bin/env bash
# Create the macOS dev virtual environment and install dependencies.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tools/mac/_common.sh
. "$SCRIPT_DIR/_common.sh"

RECREATE=0
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  write_banner "mac/setup" "Create .venv and install macOS dev dependencies"
  echo "Usage: ./tools/mac/setup.sh [--recreate]"
  echo ""
  echo "  --recreate   Delete and rebuild .venv from scratch."
  echo ""
  echo "Uses requirements-mac-dev.txt (not the Windows requirements files)."
  echo "Run ./tools/mac/check-deps.sh to inspect the environment."
  exit 0
fi
if [[ "${1:-}" == "--recreate" ]]; then
  RECREATE=1
fi

write_banner "mac/setup" "Create .venv and install macOS dev dependencies"

write_section "Locate Python >= $MIN_PYTHON"
PY_LINE=""
if ! PY_LINE="$(find_python)"; then
  write_fail "No Python interpreter found."
  python_install_help
  write_next_steps "Install Python $MIN_PYTHON+, then re-run:  ./tools/mac/setup.sh"
  exit 1
fi
PY_CMD="${PY_LINE%%|*}"
PY_VERSION="${PY_LINE#*|}"
write_ok "Using Python $PY_VERSION via '$PY_CMD'"

write_section "Virtual environment"
VENV_DIR="$REPO_ROOT/.venv"
VENV_PY="$(venv_python)"
if [[ "$RECREATE" -eq 1 && -d "$VENV_DIR" ]]; then
  write_info "Removing existing .venv (--recreate)..."
  rm -rf "$VENV_DIR"
fi
if [[ -x "$VENV_PY" ]]; then
  write_ok ".venv already exists (use --recreate to rebuild)."
else
  write_info "Creating .venv ..."
  "$PY_CMD" -m venv "$VENV_DIR"
  write_ok ".venv created."
fi

write_section "Install macOS dev dependencies"
write_info "Upgrading pip ..."
"$VENV_PY" -m pip install --upgrade pip

REQ_DEV="$REPO_ROOT/requirements-mac-dev.txt"
if [[ ! -f "$REQ_DEV" ]]; then
  write_fail "Missing $REQ_DEV"
  exit 1
fi
write_info "Installing from requirements-mac-dev.txt ..."
"$VENV_PY" -m pip install -r "$REQ_DEV"
write_ok "Dependencies installed."

write_section "pre-commit hook"
if [[ -f "$REPO_ROOT/.pre-commit-config.yaml" && -d "$REPO_ROOT/.git" ]]; then
  if "$VENV_PY" -m pre_commit install 2>/dev/null; then
    write_ok "pre-commit hook installed."
  else
    write_warn "Could not install pre-commit."
  fi
else
  write_info "Skipped pre-commit (no config or not a git repo)."
fi

write_section "Done"
write_ok "macOS dev environment is set up."
write_next_steps \
  "Verify:     ./tools/mac/check-deps.sh" \
  "Activate:   source .venv/bin/activate" \
  "Tests:      ./tools/mac/test.sh" \
  "Self-test:  ./tools/mac/run.sh --selftest"
