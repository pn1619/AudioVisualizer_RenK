#!/usr/bin/env bash
# Auto-format: black + ruff --fix.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tools/mac/_common.sh
. "$SCRIPT_DIR/_common.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  write_banner "mac/format" "black + ruff --fix"
  echo "Usage: ./tools/mac/format.sh"
  exit 0
fi

write_banner "mac/format" "black + ruff --fix"
require_venv
VENV_PY="$(venv_python)"

write_section "ruff --fix"
"$VENV_PY" -m ruff check --fix src tests

write_section "black"
"$VENV_PY" -m black src tests

write_ok "Formatting applied."
write_next_steps "Re-check:  ./tools/mac/lint.sh" "Tests:  ./tools/mac/test.sh"
