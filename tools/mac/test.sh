#!/usr/bin/env bash
# Run pytest headlessly (dummy SDL drivers).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tools/mac/_common.sh
. "$SCRIPT_DIR/_common.sh"

COVERAGE=0
PASSTHROUGH=()
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  write_banner "mac/test" "Run pytest headlessly"
  echo "Usage: ./tools/mac/test.sh [--coverage] [-- <pytest args>]"
  exit 0
fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    --coverage) COVERAGE=1; shift ;;
    --) shift; PASSTHROUGH+=("$@"); break ;;
    *) PASSTHROUGH+=("$1"); shift ;;
  esac
done

write_banner "mac/test" "Run pytest headlessly"
require_venv
export_repo_env
export SDL_VIDEODRIVER=dummy
export SDL_AUDIODRIVER=dummy

VENV_PY="$(venv_python)"
PYTEST_ARGS=()
if [[ "$COVERAGE" -eq 1 ]]; then
  PYTEST_ARGS+=(--cov=audio_visualizer --cov-report=term-missing)
fi
if [[ "${#PASSTHROUGH[@]}" -gt 0 ]]; then
  PYTEST_ARGS+=("${PASSTHROUGH[@]}")
fi

write_info "Running pytest ..."
set +e
if [[ "${#PYTEST_ARGS[@]}" -gt 0 ]]; then
  "$VENV_PY" -m pytest "${PYTEST_ARGS[@]}"
else
  "$VENV_PY" -m pytest
fi
code=$?
set -e

if [[ "$code" -eq 0 ]]; then
  write_ok "All tests passed."
  write_next_steps "Run app:  ./tools/mac/run.sh" "Lint:  ./tools/mac/lint.sh"
else
  write_fail "Tests failed (exit $code)."
fi
exit "$code"
