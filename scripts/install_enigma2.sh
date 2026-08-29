#!/bin/sh
# Install SmartTV Bridge *on* an Enigma2 receiver (OpenATV, OpenPLi,
# OpenViX, Egami ...).  Run it over SSH on the box itself:
#
#   scp -r smarttv config.example.json scripts root@RECEIVER:/tmp/bridge/
#   ssh root@RECEIVER "sh /tmp/bridge/scripts/install_enigma2.sh"
#
# The service is pure standard-library Python, which is exactly why it can
# live on a receiver: no pip, no compiler, no extra packages.
set -eu

INSTALL_DIR=/usr/local/smarttv
CONFIG=/etc/smarttv.json
PYTHON="$(command -v python3 || command -v python || true)"
SOURCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -z "$PYTHON" ]; then
  echo "no python on this image; use a receiver image with python3" >&2
  exit 1
fi
echo ">> using $PYTHON ($("$PYTHON" -V 2>&1))"

echo ">> copying to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -r "$SOURCE_DIR/smarttv" "$INSTALL_DIR/"

if [ ! -f "$CONFIG" ]; then
  echo ">> writing $CONFIG"
  cp "$SOURCE_DIR/config.example.json" "$CONFIG"
  echo "   now edit it: tv.enigma2.enabled = true, tv.enigma2.host = 127.0.0.1"
  echo "   (the service talks to OpenWebif over the loopback), and"
  echo "   player.backend = enigma2 so playback happens on this box."
else
  echo ">> keeping the existing $CONFIG"
fi

echo ">> installing the startup script"
cat > /etc/init.d/smarttv <<INNER
#!/bin/sh
### BEGIN INIT INFO
# Provides:          smarttv
# Required-Start:    \$network
# Default-Start:     3 4 5
# Default-Stop:      0 1 6
# Short-Description: SmartTV Bridge
### END INIT INFO
PIDFILE=/var/run/smarttv.pid
case "\$1" in
  start)
    echo "starting smarttv"
    cd $INSTALL_DIR
    start-stop-daemon -S -b -m -p \$PIDFILE -x $PYTHON -- -m smarttv --config $CONFIG
    ;;
  stop)
    echo "stopping smarttv"
    start-stop-daemon -K -p \$PIDFILE
    ;;
  restart)
    \$0 stop || true
    sleep 1
    \$0 start
    ;;
  *)
    echo "usage: \$0 {start|stop|restart}"
    exit 1
    ;;
esac
INNER
chmod +x /etc/init.d/smarttv
update-rc.d smarttv defaults 2>/dev/null || true
/etc/init.d/smarttv restart || /etc/init.d/smarttv start

echo
echo "done. open the remote at http://$(hostname -I 2>/dev/null | awk '{print $1}'):8099"
echo "logs: journalctl -u smarttv  (or check /var/log/messages on sysvinit images)"
