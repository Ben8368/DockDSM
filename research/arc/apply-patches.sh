#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARC_DIR="${1:-${ROOT}/vendor/arc}"
PATCH="${ROOT}/patches/arc/0001-show-model-architecture.patch"
EXPECTED_REV="99195dbdf4e0a21c5304ddb06e07dc57419679bc"

if [[ ! -e "${ARC_DIR}/.git" ]]; then
  printf 'ARC submodule is missing at %s\n' "${ARC_DIR}" >&2
  exit 1
fi
ARC_DIR="$(cd "${ARC_DIR}" && pwd)"

if [[ -f "${ARC_DIR}/.git" ]]; then
  read -r GIT_DIR_LINE <"${ARC_DIR}/.git"
  GIT_DIR="${GIT_DIR_LINE#gitdir: }"
  if [[ "${GIT_DIR}" =~ ^([A-Za-z]):/(.*)$ ]] && grep -qi microsoft /proc/version 2>/dev/null; then
    DRIVE="${BASH_REMATCH[1],,}"
    GIT_DIR="/mnt/${DRIVE}/${BASH_REMATCH[2]}"
  elif [[ "${GIT_DIR}" != /* && ! "${GIT_DIR}" =~ ^[A-Za-z]:/ ]]; then
    GIT_DIR="$(cd "${ARC_DIR}/${GIT_DIR}" && pwd)"
  fi
else
  GIT_DIR="${ARC_DIR}/.git"
fi

arc_git() {
  GIT_DIR="${GIT_DIR}" GIT_WORK_TREE="${ARC_DIR}" git -c core.filemode=false -C "${ARC_DIR}" "$@"
}

ACTUAL_REV="$(arc_git rev-parse HEAD)"
if [[ "${ACTUAL_REV}" != "${EXPECTED_REV}" ]]; then
  printf 'ARC revision mismatch: expected %s, got %s\n' "${EXPECTED_REV}" "${ACTUAL_REV}" >&2
  exit 1
fi

if arc_git apply --reverse --check "${PATCH}" 2>/dev/null; then
  printf 'DockDSM ARC patch is already applied in %s\n' "${ARC_DIR}"
elif arc_git apply --check "${PATCH}" 2>/dev/null; then
  arc_git apply "${PATCH}"
  printf 'Applied DockDSM ARC patch to %s\n' "${ARC_DIR}"
else
  printf 'ARC patch does not apply cleanly to %s\n' "${ACTUAL_REV}" >&2
  exit 1
fi
