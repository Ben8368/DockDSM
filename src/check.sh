#!/usr/bin/env bash
set -Eeuo pipefail

cd /run
. utils.sh      # Load functions

: "${DHCP:="N"}"
: "${NETWORK:="Y"}"

[ -f "/run/shm/qemu.end" ] && echo "QEMU is shutting down..." && exit 1

if [ ! -s "/run/shm/qemu.pid" ]; then
  echo "QEMU is not running yet..."
  exit 1
fi

pid=$(<"/run/shm/qemu.pid")
pid=$(echo "$pid" | tr -d '[:space:]')

if [[ ! "$pid" =~ ^[1-9][0-9]*$ ]] || ! kill -0 "$pid" 2>/dev/null; then
  echo "QEMU process is not running..."
  exit 1
fi

disabled "$NETWORK" && echo "Networking is disabled." && exit 0

file="/run/shm/dsm.url"
address="/run/shm/qemu.host"
gateway="/run/shm/qemu.gw"

# dsm.url is written only after the guest agent reports both the DSM
# address and its configured HTTP port.
if [ ! -s "$file" ]; then
  echo "DSM has not enabled networking yet..."
  exit 1
fi

location=$(<"$file")

if ! curl -m 20 -LfSs -o /dev/null "http://$location/"; then

  # In DHCP mode the firewall must allow the container address; with port
  # forwarding it must allow the internal gateway used to reach the guest.
  if enabled "$DHCP"; then
    ip=$(<"$address")
    echo "Failed to reach DSM at http://$location"
  else
    ip=$(<"$gateway")
    port="${location##*:}"
    echo "Failed to reach DSM at port $port"
  fi

  echo "You might need to whitelist IP $ip in the DSM firewall." && exit 1

fi

echo "Healthcheck OK"
exit 0
