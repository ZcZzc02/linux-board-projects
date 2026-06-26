#!/usr/bin/env bash
set -eu

if [ "${TEST_CMD:-}" = "" ]; then
  printf 'No TEST_CMD configured. Running basic environment check instead.\n\n'
  "$(dirname "$0")/check_env.sh"
  exit 0
fi

printf 'Running test command:\n%s\n' "$TEST_CMD"
sh -c "$TEST_CMD"
