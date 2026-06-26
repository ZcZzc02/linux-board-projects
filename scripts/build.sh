#!/usr/bin/env bash
set -eu

if [ "${BUILD_CMD:-}" = "" ]; then
  cat <<'MSG'
No build command is configured yet.

Set BUILD_CMD to the real SDK build command after the build flow is confirmed.
Example:
  BUILD_CMD="make" ./scripts/build.sh
MSG
  exit 1
fi

printf 'Running build command:\n%s\n' "$BUILD_CMD"
sh -c "$BUILD_CMD"
