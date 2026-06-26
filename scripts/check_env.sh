#!/usr/bin/env bash
set -eu

missing=0

check_cmd() {
  name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    if "$name" --version >/dev/null 2>&1; then
      printf '[OK] %s: %s\n' "$name" "$(command -v "$name")"
    else
      printf '[UNUSABLE] %s: %s\n' "$name" "$(command -v "$name")"
      missing=1
    fi
  else
    printf '[MISSING] %s\n' "$name"
    missing=1
  fi
}

print_version() {
  name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    "$name" --version 2>/dev/null | head -n 1 || printf '%s: found but cannot run\n' "$name"
  fi
}

printf '== Basic tool check ==\n'
check_cmd git
check_cmd make
check_cmd gcc
check_cmd g++
check_cmd cmake
check_cmd python3
check_cmd file

printf '\n== Version info ==\n'
print_version git
print_version make
print_version gcc
print_version cmake
print_version python3

if [ "$missing" -ne 0 ]; then
  printf '\nSome basic tools are missing. Install them before building the SDK.\n'
  exit 1
fi

printf '\nEnvironment check passed for the basic tool layer.\n'
