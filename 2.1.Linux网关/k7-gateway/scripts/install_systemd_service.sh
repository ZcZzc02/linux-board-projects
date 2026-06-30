#!/usr/bin/env sh
set -eu

PROJECT_DIR="${PROJECT_DIR:-/root/k7-gateway}"
GATEWAY_SERVICE_SRC="$PROJECT_DIR/systemd/k7-gateway.service"
WATCHDOG_SERVICE_SRC="$PROJECT_DIR/systemd/k7-network-watchdog.service"
GATEWAY_SERVICE_DST="/etc/systemd/system/k7-gateway.service"
WATCHDOG_SERVICE_DST="/etc/systemd/system/k7-network-watchdog.service"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run as root on K7" >&2
  exit 1
fi

if [ ! -f "$GATEWAY_SERVICE_SRC" ]; then
  echo "ERROR: missing $GATEWAY_SERVICE_SRC" >&2
  exit 1
fi

if [ ! -f "$WATCHDOG_SERVICE_SRC" ]; then
  echo "ERROR: missing $WATCHDOG_SERVICE_SRC" >&2
  exit 1
fi

mkdir -p /var/log/k7-gateway
cp "$GATEWAY_SERVICE_SRC" "$GATEWAY_SERVICE_DST"
cp "$WATCHDOG_SERVICE_SRC" "$WATCHDOG_SERVICE_DST"
systemctl daemon-reload
systemctl enable k7-network-watchdog.service
systemctl restart k7-network-watchdog.service
systemctl enable k7-gateway.service
systemctl restart k7-gateway.service
systemctl --no-pager --full status k7-network-watchdog.service
systemctl --no-pager --full status k7-gateway.service
