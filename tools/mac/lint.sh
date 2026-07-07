#!/usr/bin/env bash
# Lint and format-check (ruff + black --check + non-blocking mypy).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tools/mac/_common.sh
. "$SCRIPT_DIR/_common.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  write_banner "mac/lint" "ruff + black --check (+ mypy)"
  echo "Usage: ./tools/mac/lint.sh"
  exit 0
fi

write_banner "mac/lint" "ruff + black --check (+ mypy)"
require_venv
VENV_PY="$(venv_python)"
failed=0

write_section "ruff (lint)"
if ! "$VENV_PY" -m ruff check src tests; then failed=1; fi

write_section "black (format check)"
if ! "$VENV_PY" -m black --check src tests; then failed=1; fi

write_section "mypy (types, non-blocking)"
if ! "$VENV_PY" -m mypy src; then write_warn "mypy reported issues (non-blocking)."; fi

if [[ "$failed" -eq 0 ]]; then
  write_ok "Lint + format checks passed."
  exit 0
fi
write_fail "Lint/format issues found. Fix with: ./tools/mac/format.sh"
exit 1
