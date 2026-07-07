#!/usr/bin/env bash
# Build the macOS .app bundle with PyInstaller (parallel to tools/build-exe.ps1).
#
# Produces dist/AudioVisualizer.app, then self-tests it headlessly. See
# tools/mac/README.md and plan/macos-port.md.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tools/mac/_common.sh
. "$SCRIPT_DIR/_common.sh"

NO_SELFTEST=0
for arg in "$@"; do
  case "$arg" in
    -h | --help)
      write_banner "mac/build-app" "PyInstaller -> dist/AudioVisualizer.app"
      echo "Usage: ./tools/mac/build-app.sh [--no-selftest]"
      echo "Bundles PortAudio + pyobjc frameworks and self-tests the built app."
      exit 0
      ;;
    --no-selftest) NO_SELFTEST=1 ;;
    *)
      write_fail "Unknown argument: $arg"
      exit 1
      ;;
  esac
done

write_banner "mac/build-app" "PyInstaller -> dist/AudioVisualizer.app"
require_venv
VENV_PY="$(venv_python)"
APP="$REPO_ROOT/dist/AudioVisualizer.app"
SPEC="$REPO_ROOT/AudioVisualizer-mac.spec"

write_section "Ensure PyInstaller is installed"
if ! "$VENV_PY" -c "import PyInstaller" >/dev/null 2>&1; then
  write_info "Installing PyInstaller ..."
  "$VENV_PY" -m pip install "pyinstaller>=6.0"
fi
write_ok "PyInstaller present."

write_section "Generate app icon (.icns)"
ICON_PNG="$REPO_ROOT/src/audio_visualizer/assets/renk_icon.png"
ICON_OUT="$REPO_ROOT/build/mac/AudioVisualizer.icns"
mkdir -p "$REPO_ROOT/build/mac"
if [[ -f "$ICON_PNG" ]] && command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
  ICONSET="$REPO_ROOT/build/mac/AudioVisualizer.iconset"
  rm -rf "$ICONSET"
  mkdir -p "$ICONSET"
  for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$ICON_PNG" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null 2>&1 || true
    dbl=$((size * 2))
    sips -z "$dbl" "$dbl" "$ICON_PNG" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null 2>&1 || true
  done
  if iconutil -c icns "$ICONSET" -o "$ICON_OUT" >/dev/null 2>&1; then
    write_ok "Icon written: $ICON_OUT"
  else
    write_warn "iconutil failed; building without a custom icon."
  fi
else
  write_warn "sips/iconutil or PNG missing; building without a custom icon."
fi

write_section "Running PyInstaller"
"$VENV_PY" -m PyInstaller --noconfirm --clean "$SPEC"
if [[ ! -d "$APP" ]]; then
  write_fail "Build failed: $APP not found."
  exit 1
fi
write_ok "Built $APP"

if [[ "$NO_SELFTEST" -eq 0 ]]; then
  write_section "Self-test the built app (headless)"
  BIN="$APP/Contents/MacOS/AudioVisualizer"
  if SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy "$BIN" --selftest; then
    write_ok "Built app passed --selftest."
  else
    write_fail "Built app failed --selftest. See logs/app.log."
    exit 1
  fi
fi

write_next_steps \
  "Run it:  open dist/AudioVisualizer.app" \
  "Or from a terminal:  ./dist/AudioVisualizer.app/Contents/MacOS/AudioVisualizer" \
  "System audio: pick 'System Audio (native tap)' in Src (grant Screen Recording), or install BlackHole" \
  "Note: the app is unsigned; first launch may need right-click -> Open (Gatekeeper)."
