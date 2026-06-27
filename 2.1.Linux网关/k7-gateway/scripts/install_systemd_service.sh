#!/usr/bin/env sh
set -eu

PROJECT_DIR="${PROJECT_DIR:-/root/k7-gateway}"
SERVICE_SRC="$PROJECT_DIR/systemd/k7-gateway.service"
SERVICE_DST="/etc/systemd/system/k7-gateway.service"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run as root on K7" >&2
  exit 1
fi

if [ ! -f "$SERVICE_SRC" ]; then
  echo "ERROR: missing $SERVICE_SRC" >&2
  exit 1
fi

mkdir -p /var/log/k7-gateway
cp "$SERVICE_SRC" "$SERVICE_DST"
systemctl daemon-reload
systemctl enable k7-gateway.service
systemctl restart k7-gateway.service
systemctl --no-pager --full status k7-gateway.service
