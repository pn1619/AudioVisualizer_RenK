#!/usr/bin/env bash
# Launch the app from the macOS dev venv.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tools/mac/_common.sh
. "$SCRIPT_DIR/_common.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  write_banner "mac/run" "Launch the app from the venv"
  echo "Usage: ./tools/mac/run.sh [-- <app args>]"
  echo "  e.g. ./tools/mac/run.sh --debug --mode spectrum --selftest"
  exit 0
fi

write_banner "mac/run" "Launch the app from the venv"
require_venv
export_repo_env

VENV_PY="$(venv_python)"
write_info "Launching: python -m audio_visualizer $*"
exec "$VENV_PY" -m audio_visualizer "$@"
