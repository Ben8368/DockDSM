#!/usr/bin/env bash
# Architecture-independent PAT acquisition and extraction; original x86 behavior.
set -Eeuo pipefail

getCountry() {

  local url=$1
  local query=$2
  local json result

  { json=$(curl -m 5 -H "Accept: application/json" -sfk "$url"); local rc=$?; } || :
  (( rc != 0 )) && return 0

  { result=$(echo "$json" | jq -r "$query" 2> /dev/null); rc=$?; } || :
  (( rc != 0 )) && return 0

  [[ ${#result} -ne 2 ]] && return 0
  [[ "${result^^}" == "XX" ]] && return 0

  COUNTRY="${result^^}"

  return 0
}

# Both installers need country detection; do not depend on the x86 source chain.
setCountry() {

  local timezone="${TZ:-}"
  case "${timezone,,}" in
    asia/harbin|asia/beijing|asia/urumqi|asia/kashgar|asia/shanghai|asia/chongqing)
      COUNTRY="CN" ;;
  esac

  # Country detection is best-effort and tries independent services in order;
  # failure leaves mirror selection at its global default.
  [ -z "$COUNTRY" ] && getCountry "https://api.ipapi.is" ".location.country_code"
  [ -z "$COUNTRY" ] && getCountry "https://ifconfig.co/json" ".country_iso"
  [ -z "$COUNTRY" ] && getCountry "https://api.ip2location.io" ".country_code"
  [ -z "$COUNTRY" ] && getCountry "https://ipinfo.io/json" ".country"
  [ -z "$COUNTRY" ] && getCountry "https://api.ipquery.io/?format=json" ".location.country_code"
  [ -z "$COUNTRY" ] && getCountry "https://api.myip.com" ".cc"

  return 0
}

downloadFile() {

  local url="$1"
  local pat="$2"
  local msg="$3"
  local connections="${4:-1}"

  downloadToFile \
    "$url" \
    "$pat" \
    "$msg" \
    "0" \
    "$connections" \
    "Y"
}

downloadPat() {

  local pat="$1"
  local msg err

  if [[ "$URL" == "file://"* ]]; then
    msg="Copying DSM"
    err="Failed to copy ${URL:7}"
    info "Install: Copying installation image..."
    html "$msg..." || return $?

    rm -f "$pat" || return $?

    if [ ! -f "${URL:7}" ]; then
      error "File '${URL:7}' does not exist!"
      return 65
    fi

    cp "${URL:7}" "$pat" || return $?

  else

    msg="Downloading DSM"
    err="Failed to download $URL"
    info "Install: Downloading $BASE.pat..."

    downloadRetry \
      "$pat" \
      "$CONNECTIONS" \
      "5" \
      "$BASE.pat" \
      "0" \
      "$URL" \
      "$pat" \
      "$msg" || return 69
  fi

  if [ ! -s "$pat" ]; then
    error "$err"
    return 69
  fi

  return 0
}

extractPat() {

  local pat="$1"
  local tmp="$2"
  local size="$3"
  local msg="Extracting installation image..."
  local rc

  info "Install: $msg" && html "$msg" || return $?
  /run/progress.sh "$tmp" "$size" "$msg ([P])..." &

  # Newer PAT files are normal tar archives; older encrypted/proprietary forms
  # require the bundled extractor as a compatibility fallback.
  if { tar tf "$pat"; } >/dev/null 2>&1; then

    tar xpf "$pat" -C "$tmp/." || {
      rc=$?
      fKill "progress.sh"
      return "$rc"
    }

  else

    { (cd "$tmp" && python3 /run/extract.py -i "$pat" -d 2>/run/extract.log); rc=$?; } || :

    if (( rc != 0 )); then
      fKill "progress.sh"
      cat /run/extract.log
      error "Failed to extract PAT file, reason $rc"
      return 63
    fi

  fi

  fKill "progress.sh"
  return 0
}

# The caller declares local mirror; Bash dynamic scope keeps the original state.
selectDsmMirror() {
  local chinaMirror="https://cndl.synology.cn/download/DSM"
  local globalMirror="https://global.synologydownload.com/download/DSM"

  [[ "${URL,,}" == *"cndl.synology"* ]] && mirror="$chinaMirror"
  [[ "${URL,,}" == *"global.synology"* ]] && mirror="$globalMirror"

  # Honor an explicitly selected Synology mirror first, otherwise choose the
  # China or global endpoint from the detected country.
  if [ -z "$mirror" ]; then
    if [ -z "$COUNTRY" ]; then
      setCountry || return $?
    fi

    [ -z "$COUNTRY" ] && info "Warning: could not detect country to select mirror!"
    [[ "${COUNTRY^^}" == "CN" ]] && mirror="$chinaMirror" || mirror="$globalMirror"
  fi

  return 0
}
