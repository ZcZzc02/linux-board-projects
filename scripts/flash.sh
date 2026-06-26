#!/usr/bin/env bash
set -eu

if [ "${FLASH_CMD:-}" = "" ]; then
  cat <<'MSG'
No flash command is configured yet.

Flashing can overwrite board storage. Confirm the exact device and image before running.
Example:
  FLASH_CMD="real flash command" I_UNDERSTAND_FLASH_RISK=1 ./scripts/flash.sh
MSG
  exit 1
fi

if [ "${I_UNDERSTAND_FLASH_RISK:-}" != "1" ]; then
  cat <<'MSG'
Refusing to flash because I_UNDERSTAND_FLASH_RISK is not set to 1.

Before flashing, confirm:
  1. Target device
  2. Image path
  3. Data that will be overwritten
  4. Recovery method if flashing fails
MSG
  exit 1
fi

printf 'Running flash command:\n%s\n' "$FLASH_CMD"
sh -c "$FLASH_CMD"
