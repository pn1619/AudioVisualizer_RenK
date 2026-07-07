#!/usr/bin/env bash
# Verify the macOS machine is ready for AudioVisualizer porting work (read-only).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tools/mac/_common.sh
. "$SCRIPT_DIR/_common.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  write_banner "mac/check-deps" "Verify macOS dev environment (read-only)"
  echo "Usage: ./tools/mac/check-deps.sh"
  echo ""
  echo "Checks Python >= $MIN_PYTHON, .venv, macOS packages, pygame/SDL, and runs a quick test probe."
  echo "Makes no changes. Run ./tools/mac/setup.sh to fix missing pieces."
  exit 0
fi

write_banner "mac/check-deps" "Verify macOS dev environment (read-only)"

PROBLEMS=()
VENV_PY="$(venv_python)"
VENV_OK=0
[[ -x "$VENV_PY" ]] && VENV_OK=1

write_section "Python >= $MIN_PYTHON"
if PY_LINE="$(find_python)"; then
  PY_CMD="${PY_LINE%%|*}"
  PY_VERSION="${PY_LINE#*|}"
  write_ok "Python $PY_VERSION via '$PY_CMD'"
  arch="$("$PY_CMD" -c 'import platform; print(platform.machine())' 2>/dev/null || echo '?')"
  write_info "Architecture: $arch"
else
  write_fail "No Python >= $MIN_PYTHON found on PATH."
  python_install_help
  PROBLEMS+=("Install Python $MIN_PYTHON or newer.")
fi

write_section "Virtual environment (.venv)"
if [[ "$VENV_OK" -eq 1 ]]; then
  write_ok ".venv found ($VENV_PY)"
else
  write_warn ".venv not found."
  PROBLEMS+=("Run ./tools/mac/setup.sh")
fi

write_section "macOS runtime packages"
MAC_PACKAGES=(numpy pygame)
if [[ "$VENV_OK" -eq 1 ]]; then
  export PYGAME_HIDE_SUPPORT_PROMPT=1
  for pkg in "${MAC_PACKAGES[@]}"; do
    ver="$("$VENV_PY" -c "import importlib; m=importlib.import_module('$pkg'); print(getattr(m, '__version__', '?'))" 2>/dev/null || true)"
    if [[ -n "$ver" ]]; then
      write_ok "$pkg $ver"
    else
      write_fail "$pkg is not importable."
      PROBLEMS+=("Run ./tools/mac/setup.sh")
    fi
  done
else
  write_info "Skipped (no .venv)."
fi

write_section "Dev tools"
DEV_PACKAGES=(pytest ruff black mypy pre_commit)
if [[ "$VENV_OK" -eq 1 ]]; then
  for pkg in "${DEV_PACKAGES[@]}"; do
    ver="$("$VENV_PY" -c "import importlib; m=importlib.import_module('$pkg'); print(getattr(m, '__version__', '?'))" 2>/dev/null || true)"
    if [[ -n "$ver" ]]; then
      write_ok "$pkg $ver"
    else
      write_fail "$pkg is not importable."
      PROBLEMS+=("Run ./tools/mac/setup.sh")
    fi
  done
else
  write_info "Skipped (no .venv)."
fi

write_section "pygame / SDL (headless)"
if [[ "$VENV_OK" -eq 1 ]]; then
  if SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy "$VENV_PY" -c "import pygame; pygame.init(); pygame.quit()" 2>/dev/null; then
    write_ok "pygame initializes with SDL_VIDEODRIVER=dummy."
  else
    write_fail "pygame headless init failed."
    PROBLEMS+=("Reinstall deps: ./tools/mac/setup.sh --recreate")
  fi
else
  write_info "Skipped (no .venv)."
fi

write_section "Smoke probe (import app + registry)"
if [[ "$VENV_OK" -eq 1 ]]; then
  export_repo_env
  if SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy "$VENV_PY" -c "
from audio_visualizer.visuals import registry
registry.discover()
print('modes', len(registry.available()))
" 2>/dev/null; then
    write_ok "audio_visualizer imports; visual modes discovered."
  else
    write_fail "Could not import audio_visualizer or discover modes."
    PROBLEMS+=("Check PYTHONPATH=src and package install.")
  fi
else
  write_info "Skipped (no .venv)."
fi

write_section "Audio capture (porting note)"
write_info "System-audio loopback is not implemented on macOS yet (Windows uses pyaudiowpatch)."
write_info "Porting will add a Core Audio backend; dev/tests use SyntheticSource today."

write_section "Summary"
if [[ "${#PROBLEMS[@]}" -eq 0 ]]; then
  write_ok "This Mac is ready for porting development."
  write_next_steps \
    "Full test suite:  ./tools/mac/test.sh" \
    "Headless app:     ./tools/mac/run.sh --selftest" \
    "GUI (display):    ./tools/mac/run.sh --debug --mode spectrum"
  exit 0
fi

write_fail "${#PROBLEMS[@]} item(s) need attention:"
for p in "${PROBLEMS[@]}"; do
  echo "        - $p"
done
write_next_steps \
  "Fix with:  ./tools/mac/setup.sh" \
  "Re-check:  ./tools/mac/check-deps.sh"
exit 1
