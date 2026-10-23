# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

FROM qemux/qemu:7.50@sha256:e7f6fda52503a546fd649670ba46e4bc23dc6dcef275bc3fac48877fbbc430df AS base

# BuildKit uses TARGETPLATFORM for every stage, independently of guest CPU.
FROM debian:trixie-slim@sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad AS arm-qemu-build
ARG TARGETARCH
ARG QEMU_VERSION="8.2.2"
RUN apt-get update && apt-get --no-install-recommends -y install \
    build-essential ca-certificates git meson ninja-build pkg-config \
    python3-venv libglib2.0-dev libpixman-1-dev libslirp-dev \
    && rm -rf /var/lib/apt/lists/*
COPY patches/qemu/8.2.2/ /patches/
COPY --chmod=755 scripts/build-arm-qemu.sh /build-arm-qemu.sh
COPY --chmod=755 scripts/apply-qemu-patches.sh /apply-qemu-patches.sh
COPY --chmod=755 scripts/fetch-qemu-source.sh /fetch-qemu-source.sh
RUN /build-arm-qemu.sh

FROM base AS runtime
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY --from=arm-qemu-build /out/qemu-system-aarch64 /usr/local/bin/qemu-system-aarch64

ARG VERSION_ARG="0.0"

ARG DEBCONF_NOWARNINGS="yes"
ARG DEBIAN_FRONTEND="noninteractive"
ARG DEBCONF_NONINTERACTIVE_SEEN="true"

COPY requirements.txt /tmp/requirements.txt
RUN <<EOF
  set -eu

  apt-get update
  apt-get --no-install-recommends -y install \
    fakeroot \
    xz-utils \
    tar \
    e2fsprogs \
    util-linux \
    python3-msgpack \
    python3-pysodium \
    openssh-client \
    libslirp0 \
    libpixman-1-0

  apt-get clean

  # Install Python dependencies
  pip3 install --no-cache-dir --break-system-packages --root-user-action=ignore --require-hashes -r /tmp/requirements.txt

  qemu-system-aarch64 --version
  qemu-system-x86_64 --version
  if ldd /usr/local/bin/qemu-system-aarch64 | grep -q "not found"; then exit 1; fi

  # Set version file
  echo "$VERSION_ARG" > /etc/version

  rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
EOF

COPY --chmod=755 ./src /run/
COPY --chmod=755 ./scripts/package-readiness.py /run/package-readiness.py
COPY --chmod=755 ./web /var/www/
COPY --chmod=744 ./web/conf/nginx.conf /etc/nginx/default.conf
COPY --chmod=755 --from=qemux/qemu-host:2.06@sha256:5cd89a126bd4fb59cab33de7a1636871564e5006ecf51931c211ecb9f3012b32 /qemu-host.bin /run/host.bin
ADD --chmod=775 --checksum=sha256:add398aa4058dd4b6e1dbe36ed89a5b259074cb702d77b460023e98ce143a3a6 https://raw.githubusercontent.com/sud0woodo/patology/18737e0924725375a857f10a54a4b5229beec3b2/patology.py /run/extract.py

VOLUME /storage
EXPOSE 445 5000

ENV RAM_SIZE="2G"
ENV CPU_CORES="2"
ENV DISK_SIZE="256G"

# ARM TCG multi cold boots commonly need ~8–15 minutes before management HTTP
# answers; keep failures from counting until that window elapses. x86 still
# becomes healthy as soon as check.sh succeeds inside the period.
HEALTHCHECK --interval=60s --start-period=900s --retries=2 CMD ["/run/check.sh"]

ENTRYPOINT ["/usr/bin/tini", "-s", "/run/entry.sh"]
