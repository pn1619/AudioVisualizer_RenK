#!/usr/bin/env bash
# Shared helpers for tools/mac/*.sh (macOS dev only — parallel to tools/*.ps1 on Windows).
#
# Source from any mac tool script:
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   # shellcheck source=tools/mac/_common.sh
#   . "$SCRIPT_DIR/_common.sh"

set -euo pipefail

_MAC_TOOLS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$_MAC_TOOLS/../.." && pwd)"
MIN_PYTHON="3.12"

write_banner() {
  local title="$1"
  local subtitle="${2:-}"
  local line
  line="$(printf '=%.0s' {1..64})"
  echo ""
  echo "$line"
  echo "  $title"
  [[ -n "$subtitle" ]] && echo "  $subtitle"
  echo "$line"
  echo ""
}

write_section() {
  echo ""
  echo "-- $1"
}

write_ok() {
  echo "  [ OK ]  $1"
}

write_info() {
  echo "  [info]  $1"
}

write_warn() {
  echo "  [warn]  $1"
}

write_fail() {
  echo "  [FAIL]  $1"
}

write_next_steps() {
  echo ""
  echo "Next steps:"
  for step in "$@"; do
    echo "  -> $step"
  done
  echo ""
}

venv_python() {
  echo "$REPO_ROOT/.venv/bin/python"
}

python_install_help() {
  cat <<'EOF'
Install Python 3.12 or newer (64-bit, Apple Silicon or Intel), then re-run:
  brew install python@3.12
  - or https://www.python.org/downloads/macos/
Verify with:  python3.12 --version
EOF
}

# Prints "command|version" on success; returns 1 when nothing qualifies.
find_python() {
  local candidates=(python3.12 python3 python)
  local cmd raw major minor micro version_text
  for cmd in "${candidates[@]}"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      continue
    fi
    raw="$("$cmd" -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)' 2>/dev/null || true)"
    [[ -z "$raw" ]] && continue
    read -r major minor micro <<<"$raw"
    version_text="${major}.${minor}.${micro}"
    if "$cmd" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" 2>/dev/null; then
      echo "${cmd}|${version_text}"
      return 0
    fi
  done
  return 1
}

require_venv() {
  local venv_py
  venv_py="$(venv_python)"
  if [[ ! -x "$venv_py" ]]; then
    write_fail ".venv not found. Run ./tools/mac/setup.sh first."
    exit 1
  fi
}

export_repo_env() {
  export PYTHONPATH="$REPO_ROOT/src"
  export PYGAME_HIDE_SUPPORT_PROMPT=1
}
