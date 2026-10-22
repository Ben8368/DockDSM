#!/usr/bin/env bash
# Exercise build error reporting in a disposable container without fetching sources.
set -Eeuo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
image=${1:?Production image required}
docker run --rm -i --pull=never --network none --entrypoint bash \
  --mount "type=bind,src=$repo,dst=/workspace,readonly" "$image" -s <<'CONTAINER'
set -Eeuo pipefail
mkdir /stub-bin
export PATH="/stub-bin:$PATH"
cat > /fetch-qemu-source.sh <<'FETCH'
#!/usr/bin/env bash
set -eu
mkdir /qemu
cat > /qemu/configure <<'CONFIGURE'
#!/usr/bin/env bash
case "$SCENARIO" in
  configure)
    echo 'Executing subproject libvhost-user'
    echo 'ERROR: C compiler cannot compile programs'
    exit 1 ;;
  dns)
    echo 'fatal: Could not resolve host: fixture.invalid'
    exit 1 ;;
  source)
    echo 'fatal: unable to access https://fixture.invalid: HTTP 503'
    exit 1 ;;
  compile) exit 0 ;;
esac
CONFIGURE
chmod +x /qemu/configure
FETCH
cat > /apply-qemu-patches.sh <<'PATCH'
#!/usr/bin/env bash
[[ "$SCENARIO" != patch ]]
PATCH
cat > /stub-bin/ninja <<'NINJA'
#!/usr/bin/env bash
exit 1
NINJA
chmod +x /fetch-qemu-source.sh /stub-bin/ninja
export QEMU_VERSION=8.2.2
TARGETARCH=$(dpkg --print-architecture)
export TARGETARCH SCENARIO
for SCENARIO in configure dns source patch compile; do
  # These paths belong only to this disposable container, never the host.
  rm -rf -- /qemu /out
  case "$SCENARIO" in
    configure) expected=71; marker=QEMU_CONFIGURE_FAILED ;;
    dns) expected=69; marker=QEMU_SOURCE_DNS_FAILURE ;;
    source) expected=69; marker=QEMU_SOURCE_UNAVAILABLE ;;
    patch) expected=65; marker=QEMU_PATCH_APPLY_FAILED ;;
    compile) expected=70; marker=QEMU_COMPILE_FAILED ;;
  esac
  rc=0
  bash /workspace/scripts/build-arm-qemu.sh > /tmp/build-result.log 2>&1 || rc=$?
  if [[ "$rc" != "$expected" ]] || ! grep -q "$marker:" /tmp/build-result.log; then
    cat /tmp/build-result.log >&2
    echo "Unexpected $SCENARIO result: exit=$rc, expected=$expected/$marker" >&2
    exit 1
  fi
  echo "QEMU $SCENARIO failure: $marker (exit $rc)"
done
CONTAINER
