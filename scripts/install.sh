#!/usr/bin/env sh
# Install SmartTV Bridge on a Debian/Raspberry Pi OS box.
# Usage:  sudo sh scripts/install.sh [user]
set -eu

TARGET_USER="${1:-${SUDO_USER:-$(id -un)}}"
SOURCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR=/opt/smarttv
CONFIG_DIR=/etc/smarttv

if [ "$(id -u)" -ne 0 ]; then
  echo "run me with sudo: sudo sh scripts/install.sh" >&2
  exit 1
fi

echo ">> installing packages (cec-utils, mpv, yt-dlp)"
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq
  # yt-dlp is only needed for streaming sites; keep going without it.
  apt-get install -y --no-install-recommends cec-utils mpv python3 || true
  apt-get install -y --no-install-recommends yt-dlp || \
    echo "!! yt-dlp not in apt; install it with: pip3 install --break-system-packages yt-dlp"
else
  echo "!! not a Debian system - install cec-utils and mpv yourself"
fi

echo ">> copying code to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -r "$SOURCE_DIR/smarttv" "$INSTALL_DIR/"

echo ">> writing config to $CONFIG_DIR/config.json"
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/config.json" ]; then
  cp "$SOURCE_DIR/config.example.json" "$CONFIG_DIR/config.json"
else
  echo "   (keeping the existing config)"
fi
chown -R "$TARGET_USER" "$CONFIG_DIR"

echo ">> installing the service for user $TARGET_USER"
sed "s/User=%i/User=$TARGET_USER/" "$SOURCE_DIR/scripts/smarttv.service" \
  > /etc/systemd/system/smarttv.service
systemctl daemon-reload
systemctl enable --now smarttv.service

# The CEC adapter shows up as a video device; without this group the
# service can talk to nothing.
usermod -aG video "$TARGET_USER" 2>/dev/null || true

echo
echo "done. remote:  http://$(hostname -I 2>/dev/null | awk '{print $1}'):8099"
echo "logs:          journalctl -u smarttv -f"
