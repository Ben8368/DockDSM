#!/bin/sh
# Read-only Surveillance Station collector. Never emits logs, camera credentials,
# serials, license keys, request bodies, or camera addresses.
set -eu

network=N
camera_ip=
rtsp_port=554
while [ "$#" -gt 0 ]; do
  case "$1" in
    --network) network=Y ;;
    --camera-ip)
      [ "$#" -ge 2 ] || { echo 'Missing --camera-ip value' >&2; exit 64; }
      camera_ip=$2
      shift
      ;;
    --rtsp-port)
      [ "$#" -ge 2 ] || { echo 'Missing --rtsp-port value' >&2; exit 64; }
      rtsp_port=$2
      shift
      ;;
    *) echo 'Usage: surveillance-diagnostics.sh [--network] [--camera-ip ADDRESS] [--rtsp-port PORT]' >&2; exit 64 ;;
  esac
  shift
done

emit() { printf '%s\t%s\n' "$1" "$2"; }
key() {
  [ -r "$1" ] || return 0
  awk -F= -v wanted="$2" '
    $1 == wanted {
      value = substr($0, index($0, "=") + 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      gsub(/"/, "", value)
      print value
      exit
    }
  ' "$1"
}
valid_ip() {
  case "$1" in
    ''|*[!0-9A-Fa-f:.]*) return 1 ;;
  esac
  case "$1" in
    *:*) return 0 ;;
  esac
  printf '%s\n' "$1" | awk -F. '
    NF != 4 { exit 1 }
    {
      for (i = 1; i <= NF; i++) {
        if ($i !~ /^[0-9]+$/ || ($i + 0) > 255) exit 1
      }
    }
  '
}
if [ -n "$camera_ip" ]; then
  valid_ip "$camera_ip" || { echo 'Camera target must be a numeric IPv4 or IPv6 address' >&2; exit 64; }
fi
case "$rtsp_port" in ''|*[!0-9]*) echo 'RTSP port must be decimal' >&2; exit 64 ;; esac
if [ "$rtsp_port" -lt 1 ] 2>/dev/null || [ "$rtsp_port" -gt 65535 ] 2>/dev/null; then
  echo 'RTSP port must be 1-65535' >&2
  exit 64
fi

emit format 1
emit epoch "$(date -u +%s)"
emit guest_arch "$(uname -m)"
emit unique "$(key /etc.defaults/synoinfo.conf unique)"
emit dsm_version "$(key /etc.defaults/VERSION productversion)"
emit dsm_build "$(key /etc.defaults/VERSION buildnumber)"

volume=$(awk '$2 == "/volume1" { print $3 ":" $4; found = 1 } END { if (!found) exit 0 }' /proc/mounts)
emit volume1 "$volume"
if [ -n "$volume" ]; then
  if [ -w /volume1 ]; then volume1_access=yes; else volume1_access=no; fi
  free_bytes=$(df -Pk /volume1 2>/dev/null | awk 'NR == 2 && $4 ~ /^[0-9]+$/ { printf "%.0f\n", $4 * 1024 }')
else
  volume1_access=no
  free_bytes=
fi
emit volume1.collector_write_access "$volume1_access"
emit volume1.free_bytes "$free_bytes"
if [ -d /volume1/surveillance ]; then
  emit recording_share.present yes
  if [ -w /volume1/surveillance ]; then
    emit recording_share.collector_write_access yes
  else
    emit recording_share.collector_write_access no
  fi
else
  emit recording_share.present no
  emit recording_share.collector_write_access no
fi

service_state() {
  systemctl is-active "$1" 2>/dev/null || :
}
emit service.postgresql "$(service_state pgsql-adapter.service)"
for package in StorageManager SurveillanceVideoExtension SurveillanceStation; do
  info="/var/packages/$package/INFO"
  if [ -r "$info" ]; then
    emit "package.$package.info_present" yes
    emit "package.$package.version" "$(key "$info" version)"
    emit "package.$package.arch" "$(key "$info" arch)"
    emit "package.$package.os_min_ver" "$(key "$info" os_min_ver)"
    emit "package.$package.os_max_ver" "$(key "$info" os_max_ver)"
  else
    emit "package.$package.info_present" no
    emit "package.$package.version" ''
    emit "package.$package.arch" ''
    emit "package.$package.os_min_ver" ''
    emit "package.$package.os_max_ver" ''
  fi
  rc=127
  status=unavailable
  if command -v synopkg >/dev/null 2>&1; then
    response=$(synopkg status "$package" 2>/dev/null) && rc=0 || rc=$?
    parsed=$(printf '%s\n' "$response" |
      sed -n 's/.*"status"[[:space:]]*:[[:space:]]*"\([A-Za-z0-9_.-]*\)".*/\1/p' |
      tail -n 1)
    if [ -n "$parsed" ]; then status=$(printf '%s' "$parsed" | tr '[:upper:]' '[:lower:]'); else status=unknown; fi
  fi
  emit "package.$package.synopkg_rc" "$rc"
  emit "package.$package.synopkg_status" "$status"
  emit "package.$package.service" "$(service_state "pkgctl-$package.service")"
done

for file in synopkg.log synopkgmgr.log SurveillanceStation.log; do
  case "$file" in
    SurveillanceStation.log) path="/var/log/packages/$file" ;;
    *) path="/var/log/$file" ;;
  esac
  if [ ! -r "$path" ]; then
    emit "logs.$file" unavailable
    continue
  fi
  emit "logs.$file" readable
  recent=$(tail -n 200 "$path")
  for rule in authorization dependency architecture network tls filesystem service_start install_failure; do
    case "$rule" in
      authorization) pattern='[Aa]uthoriz.*([Ff]ail|[Ee]rror)|([Ff]ail|[Ee]rror).*([Aa]uthoriz|[Ll]icense)|[Ll]icense.*([Ee]rror|[Ff]ail)' ;;
      dependency) pattern='[Dd]ependen.*([Ff]ail|[Mm]iss)|([Ff]ail|[Mm]iss).*[Dd]ependen|SurveillanceVideoExtension.*(ret=\[[1-9]|[Ff]ail)' ;;
      architecture) pattern='[Aa]rchitecture.*([Ii]ncompat|[Uu]nsupported|[Ff]ail)|[Uu]nsupported.*[Aa]rchitecture|[Pp]latform.*[Ii]ncompat' ;;
      network) pattern='curl (ret|returned|code)[=: ]+(6|7|28)([ ,]|$)|[Tt]imed out|[Nn]etwork.*(unreachable|fail)' ;;
      tls) pattern='(SSL|TLS|[Cc]ertificate).*([Ee]rror|[Ff]ail|[Ii]nvalid|[Ee]xpired)|curl (ret|returned|code)[=: ]+(35|60|77)([ ,]|$)' ;;
      filesystem) pattern='[Ff]ilesystem.*([Rr]ead.only|[Ff]ull|[Ff]ail)|[Nn]o space left|[Pp]ermission denied.*(record|volume|surveillance)' ;;
      service_start) pattern='(start|starting).*(SurveillanceStation|sscored|sscamerad).*(fail|error)|([Ff]ail|[Ee]rror).*(SurveillanceStation|sscored|sscamerad)' ;;
      install_failure) pattern='install.*([Ff]ail|ret=\[[1-9])|[Ff]ail.*install' ;;
    esac
    if printf '%s\n' "$recent" | grep -Eq "$pattern"; then found=yes; else found=no; fi
    emit "history.$file.$rule" "$found"
  done
done

if [ "$network" = Y ]; then
  if ! command -v curl >/dev/null 2>&1; then
    emit network.curl unavailable
  else
    emit network.curl available
    for endpoint in pkgupdate download; do
      case "$endpoint" in
        pkgupdate) url=https://pkgupdate7.synology.com/ ;;
        download) url=https://global.synologydownload.com/ ;;
      esac
      rc=0
      status=$(curl --connect-timeout 8 --max-time 15 --silent --output /dev/null \
        --write-out '%{http_code}' "$url" 2>/dev/null) || rc=$?
      emit "network.$endpoint.curl" "$rc"
      emit "network.$endpoint.http" "$status"
    done
  fi
else
  emit network.not_checked yes
fi

if [ -n "$camera_ip" ]; then
  if ! command -v curl >/dev/null 2>&1; then
    emit camera_rtsp.curl unavailable
    emit camera_rtsp.response ''
  else
    case "$camera_ip" in *:*) target="[$camera_ip]" ;; *) target=$camera_ip ;; esac
    rc=0
    response=$(curl --connect-timeout 4 --max-time 8 --silent --output /dev/null \
      --write-out '%{http_code}' --request OPTIONS "rtsp://$target:$rtsp_port/" 2>/dev/null) || rc=$?
    emit camera_rtsp.curl "$rc"
    emit camera_rtsp.response "$response"
  fi
else
  emit camera_rtsp.not_checked yes
fi
