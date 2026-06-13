#!/usr/bin/env bash
set -euo pipefail

APP_NAME="BirdBros Recycle Co"
BUNDLE_ID="${BUNDLE_ID:-co.birdbros.recycleco}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

SIGN_IDENTITY="${SIGN_IDENTITY:-Developer ID Application: Kevin Green (J583YGMDCF)}"
APPLE_ID="${APPLE_ID:-}"
APPLE_TEAM_ID="${APPLE_TEAM_ID:-J583YGMDCF}"
APPLE_APP_PASSWORD="${APPLE_APP_PASSWORD:-}"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

die() {
  echo ""
  echo "❌ RELEASE BUILD FAILED:"
  echo "$1"
  echo ""
  exit 1
}

require_release_secret() {
  local name="$1"
  local value="$2"

  if [[ -z "$value" ]]; then
    die "$name is missing. This script only creates signed/notarized/stapled release builds."
  fi
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  die "This release builder must be run on macOS."
fi

require_release_secret "SIGN_IDENTITY" "$SIGN_IDENTITY"
require_release_secret "APPLE_ID" "$APPLE_ID"
require_release_secret "APPLE_TEAM_ID" "$APPLE_TEAM_ID"
require_release_secret "APPLE_APP_PASSWORD" "$APPLE_APP_PASSWORD"

if ! security find-identity -v -p codesigning | grep -F "$SIGN_IDENTITY" >/dev/null; then
  die "Signing identity not found in Keychain: $SIGN_IDENTITY"
fi

if [[ ! -f "main.py" ]]; then
  die "main.py not found. Run this from inside your BirdBros project folder."
fi

FIRST_RUN_README="packaging/FIRST_RUN_README.txt"
DMG_BACKGROUND="packaging/dmg_background.png"
ICON_PATH="assets/BirdBros.icns"

[[ -f "$FIRST_RUN_README" ]] || die "Missing $FIRST_RUN_README"
[[ -f "$DMG_BACKGROUND" ]] || die "Missing $DMG_BACKGROUND"

echo "==> Building ${APP_NAME} for macOS"

rm -rf build dist release
mkdir -p release

# Prevent dmgbuild from writing into an old mounted read-only volume.
if hdiutil info | grep -F "/Volumes/${APP_NAME}" >/dev/null; then
  echo "==> Detaching stale mounted DMG volume"
  hdiutil detach "/Volumes/${APP_NAME}" -force || true
fi

"$PYTHON_BIN" -m venv .venv_build
source .venv_build/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install \
  pyinstaller \
  dmgbuild \
  PySide6 \
  opencv-python \
  numpy \
  mss \
  python-dotenv \
  openai

PYINSTALLER_COMMON_ARGS=(
  --noconfirm
  --clean
  --windowed
  --onedir
  --name "$APP_NAME"
  --osx-bundle-identifier "$BUNDLE_ID"
  --collect-all PySide6
  --hidden-import PySide6.QtCore
  --hidden-import PySide6.QtGui
  --hidden-import PySide6.QtWidgets
  --hidden-import api_key_store
  --hidden-import first_run_setup
  --hidden-import cv2
  --hidden-import mss
)

if [[ -f "$ICON_PATH" ]]; then
  pyinstaller "${PYINSTALLER_COMMON_ARGS[@]}" --icon "$ICON_PATH" main.py
else
  pyinstaller "${PYINSTALLER_COMMON_ARGS[@]}" main.py
fi

APP_PATH="dist/${APP_NAME}.app"
[[ -d "$APP_PATH" ]] || die "Expected app bundle not found at: $APP_PATH"

find "$APP_PATH" \
  \( \
    -name "Assistant__dot__app" -o \
    -name "Assistant.app" -o \
    -name "Designer__dot__app" -o \
    -name "Designer.app" -o \
    -name "Linguist__dot__app" -o \
    -name "Linguist.app" \
  \) \
  -prune \
  -exec rm -rf {} +

mkdir -p "$HOME/Library/Application Support/${APP_NAME}"
mkdir -p "$HOME/Library/Logs/${APP_NAME}"

echo "==> Signing app with: $SIGN_IDENTITY"
codesign \
  --force \
  --deep \
  --timestamp \
  --options runtime \
  --entitlements packaging/entitlements.plist \
  --sign "$SIGN_IDENTITY" \
  "$APP_PATH"

codesign --verify --deep --strict --verbose=2 "$APP_PATH"

echo "==> Notarizing app bundle"
APP_ZIP="release/${APP_NAME// /_}_app.zip"
ditto -c -k --keepParent "$APP_PATH" "$APP_ZIP"

xcrun notarytool submit "$APP_ZIP" \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_PASSWORD" \
  --wait

echo "==> Stapling app"
xcrun stapler staple "$APP_PATH"
xcrun stapler validate "$APP_PATH"
APP_GATEKEEPER_OUTPUT="$(spctl -a -vvv -t exec "$APP_PATH" 2>&1 || true)"
echo "$APP_GATEKEEPER_OUTPUT"

echo "$APP_GATEKEEPER_OUTPUT" | grep -q "source=Notarized Developer ID" \
  || die "App failed Gatekeeper validation."

echo "==> Creating polished drag-to-Applications DMG with dmgbuild"

DMG_PATH="release/${APP_NAME// /_}_macOS.dmg"
DMG_STAGE="release/dmg_stage"
DMG_SETTINGS="release/dmgbuild_settings.py"

rm -f "$DMG_PATH"
rm -rf "$DMG_STAGE"
mkdir -p "$DMG_STAGE"

ditto "$APP_PATH" "$DMG_STAGE/${APP_NAME}.app"

mkdir -p "$DMG_STAGE/.background"
cp "$DMG_BACKGROUND" "$DMG_STAGE/.background/dmg_background.png"

APP_SIZE_MB="$(du -sm "$APP_PATH" | awk '{print $1}')"
DMG_SIZE_MB=$(( APP_SIZE_MB + 350 ))
if [[ "$DMG_SIZE_MB" -lt 700 ]]; then
  DMG_SIZE_MB=700
fi

echo "==> App size: ${APP_SIZE_MB} MB | DMG size: ${DMG_SIZE_MB} MB"

cat > "$DMG_SETTINGS" <<PYSETTINGS
format = 'UDZO'
size = '${DMG_SIZE_MB}M'
filesystem = 'HFS+'

files = [
    '${APP_NAME}.app',
]

symlinks = {
    'Applications': '/Applications',
}

badge_icon = None
background = '.background/dmg_background.png'
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False

window_rect = ((160, 110), (900, 520))
default_view = 'icon-view'
show_icon_preview = False
include_icon_view_settings = 'auto'
include_list_view_settings = False

arrange_by = None
grid_offset = (0, 0)
grid_spacing = 100
scroll_position = (0, 0)
label_pos = 'bottom'
text_size = 12
icon_size = 116

icon_locations = {
    '${APP_NAME}.app': (235, 265),
    'Applications': (665, 265),
}
PYSETTINGS

(
  cd "$DMG_STAGE"
  dmgbuild -s "../dmgbuild_settings.py" "$APP_NAME" "../${APP_NAME// /_}_macOS.dmg"
)

rm -rf "$DMG_STAGE"
rm -f "$DMG_SETTINGS"

[[ -f "$DMG_PATH" ]] || die "DMG was not created."

DMG_ACTUAL_SIZE_MB="$(du -sm "$DMG_PATH" | awk '{print $1}')"
echo "==> Final DMG actual size: ${DMG_ACTUAL_SIZE_MB} MB"

if [[ "$DMG_ACTUAL_SIZE_MB" -lt 100 ]]; then
  die "DMG is suspiciously tiny (${DMG_ACTUAL_SIZE_MB} MB). Refusing to sign/notarize broken installer."
fi

echo "==> Signing DMG"
codesign --force --timestamp --sign "$SIGN_IDENTITY" "$DMG_PATH"
codesign --verify --verbose=2 "$DMG_PATH"

echo "==> Submitting DMG for Apple notarization"
xcrun notarytool submit "$DMG_PATH" \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_PASSWORD" \
  --wait

echo "==> Stapling DMG"
xcrun stapler staple "$DMG_PATH"
xcrun stapler validate "$DMG_PATH"

DMG_GATEKEEPER_OUTPUT="$(spctl -a -vvv -t open --context context:primary-signature "$DMG_PATH" 2>&1 || true)"
echo "$DMG_GATEKEEPER_OUTPUT"

echo "$DMG_GATEKEEPER_OUTPUT" | grep -q "source=Notarized Developer ID" \
  || die "DMG failed Gatekeeper validation."

echo ""
echo "✅ DONE — signed, notarized, stapled release DMG only"
echo "DMG created at: $DMG_PATH"
