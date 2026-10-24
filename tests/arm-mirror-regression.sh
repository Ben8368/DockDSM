#!/usr/bin/env bash
# Exercise production ARM install dispatch up to PAT acquisition, entirely offline.
# shellcheck disable=SC2329
set -Eeuo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT

run_case() (
  local scenario=$1 expected_host=global.synologydownload.com expected_rc=69 rc=0
  local expected_probes=0 cache_rc=80
  unset TZ COUNTRY URL
  DSM_PLATFORM=rtd1619b
  . "$repo/src/platform/common.sh"
  platformInit
  STORAGE="$tmp/$scenario"
  DISK_SIZE=16G
  mkdir "$STORAGE"
  printf 'existing user state' > "$STORAGE/sentinel.img"
  case "$scenario" in
    default-offline|tls-failure) expected_probes=6 ;;
    timezone-cn) TZ=Asia/Shanghai; expected_host=cndl.synology.cn ;;
    country-cn) COUNTRY=CN; expected_host=cndl.synology.cn ;;
    detected-us) expected_probes=1 ;;
    invalid-country) expected_probes=6 ;;
    explicit-url) URL=https://example.invalid/official.pat ;;
    cache-hit) cache_rc=0; expected_rc=0 ;;
    invalid-cache) cache_rc=81; expected_rc=81 ;;
    *) return 1 ;;
  esac
  local expected_url="https://$expected_host/download/DSM/release/7.2.2/72806/DSM_DS124_72806.pat"
  [[ "$scenario" != explicit-url ]] || expected_url=$URL

  info() { :; }
  html() { :; }
  error() { printf '%s\n' "$*" >&2; }
  # This test checks dispatch, not lock contention or actual disk construction.
  flock() { [[ "$1" == -x && "$2" =~ ^[0-9]+$ ]]; }
  python3() {
    [[ "$1" == "$repo/src/platform/prepare-arm-artifacts.py" && "$2" == cache ]] || {
      error 'Unexpected builder operation'; return 99;
    }
    return "$cache_rc"
  }
  platformValidateArtifacts() { printf 'validated\n' > "$STORAGE/validated"; }
  df() { printf 'Avail\n17179869184\n'; }
  curl() {
    printf 'probe\n' >> "$STORAGE/probes"
    [[ "$1" == -m && "$2" == 5 && "$3" == -H && "$4" == 'Accept: application/json' ]] || {
      error 'Country probe must retain its timeout and JSON request headers'; return 99;
    }
    [[ " $* " != *' -k '* && " $* " != *' --insecure '* ]] || {
      error 'Country probe must keep TLS certificate verification enabled'; return 99;
    }
    [[ "$scenario" != default-offline && "$scenario" != tls-failure ]] || return 60
    printf 'fixture geolocation\n'
  }
  jq() {
    local payload
    IFS= read -r payload
    [[ "$payload" == 'fixture geolocation' ]] || return 99
    if [[ "$scenario" == detected-us ]]; then printf 'us\n'; else printf 'null\n'; fi
  }
  downloadRetry() {
    [[ "$6" == "$expected_url" ]] || { error "Unexpected PAT URL: $6"; return 99; }
    printf '%s\n' "$6" > "$STORAGE/requested-url"
    return 69  # Stop at the real downloader boundary; no PAT is fetched.
  }

  platformRunStage install || rc=$?
  [[ "$rc" == "$expected_rc" ]] || { error "$scenario: expected $expected_rc, got $rc"; return 1; }
  ! declare -F installDSM >/dev/null || { error 'ARM loaded the x86 installer'; return 1; }
  if (( expected_rc == 69 )); then
    [[ "$(<"$STORAGE/requested-url")" == "$expected_url" ]]
  else
    [[ ! -e "$STORAGE/requested-url" ]]
  fi
  local probes=0
  if [[ -f "$STORAGE/probes" ]]; then probes=$(wc -l < "$STORAGE/probes"); fi
  (( probes == expected_probes )) || { error "$scenario: unexpected geolocation calls"; return 1; }
  if (( expected_rc == 0 )); then
    [[ -f "$STORAGE/validated" ]]
  else
    [[ ! -e "$STORAGE/validated" ]]
  fi
  [[ "$(<"$STORAGE/sentinel.img")" == 'existing user state' ]]
  [[ -z "$(find "$STORAGE" -maxdepth 1 -name '.rtd1619b-install-*' -print)" ]]
)

for scenario in default-offline tls-failure timezone-cn country-cn detected-us invalid-country explicit-url cache-hit invalid-cache; do
  run_case "$scenario"
done
echo 'ARM mirror regression passed: TLS failures fall back to the global mirror; timeout, dispatch, explicit URL and cache protection remain intact.'
