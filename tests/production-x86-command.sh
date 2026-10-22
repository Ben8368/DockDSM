#!/usr/bin/env bash
# Host command regression; an optional image also exercises its real entrypoint.
set -Eeuo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if (( $# > 1 )); then
  echo 'Usage: production-x86-command.sh [production-image]' >&2
  exit 64
fi
python3 "$repo/tests/production-x86-command.py"
if [[ $# == 1 ]]; then
  exec python3 "$repo/tests/production-x86-image.py" "$1"
fi
