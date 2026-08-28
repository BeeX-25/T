#!/data/data/com.termux/files/usr/bin/sh
# Install SmartTV Bridge on an Android phone, inside Termux.
# Usage:  sh scripts/install_termux.sh
#
# Get Termux (and Termux:API, Termux:Boot) from F-Droid - the Play Store
# builds are abandoned and their add-ons do not talk to each other.
set -eu

SOURCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PREFIX_BIN="${PREFIX:-/data/data/com.termux/files/usr}/bin"
CONFIG_DIR="$HOME/.smarttv"

if [ ! -d "${PREFIX:-/nowhere}" ]; then
  echo "this script is for Termux; on a PC or a Pi use scripts/install.sh" >&2
  exit 1
fi

echo ">> installing packages"
pkg update -y >/dev/null 2>&1 || true
# termux-api gives the IR blaster and the volume control; python runs the service.
pkg install -y python termux-api

echo ">> writing config to $CONFIG_DIR/config.json"
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/config.json" ]; then
  cp "$SOURCE_DIR/config.example.json" "$CONFIG_DIR/config.json"
  echo "   edit it to set tv.ir.brand (or enable samsung/webos) and your playlists"
else
  echo "   (keeping the existing config)"
fi

echo ">> checking the hardware this phone offers"
if command -v termux-infrared-transmit >/dev/null 2>&1; then
  echo "   IR blaster command found - set tv.ir.enabled to true"
else
  echo "   no termux-infrared-transmit; install the Termux:API app from F-Droid"
fi
if command -v termux-am >/dev/null 2>&1 || command -v am >/dev/null 2>&1; then
  echo "   am found - the phone can hand streams to VLC/YouTube"
fi

echo ">> setting up autostart (needs the Termux:Boot app)"
mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/smarttv" <<INNER
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
cd "$SOURCE_DIR"
exec python3 -m smarttv --config "$CONFIG_DIR/config.json" >> "$CONFIG_DIR/smarttv.log" 2>&1
INNER
chmod +x "$HOME/.termux/boot/smarttv"

ADDRESS="$(ip route get 1 2>/dev/null | awk '{print $NF; exit}')"
echo
echo "done. start it now with:"
echo "  termux-wake-lock && python3 -m smarttv --config $CONFIG_DIR/config.json"
echo "then open the remote from any phone on the same Wi-Fi:"
echo "  http://${ADDRESS:-<phone-ip>}:8099"
