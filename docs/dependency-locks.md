# Build dependency inventory

This is the source of truth for the W01 dependency inventory and its update
procedure. Docker image and package inputs were checked on 2026-10-22. Immutable
values consumed by the build are in `Dockerfile` and `requirements.txt`.

## Locked inputs

| Input | Locked identity | Source and verification |
| --- | --- | --- |
| BuildKit Dockerfile frontend | `docker/dockerfile:1.7` index `sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e` | Docker Hub tag metadata; index includes linux/amd64 `sha256:b5f3b260a9678e1d83d2fce86eeddf79420b79147eaba2a25986f47133d73720` and linux/arm64 `sha256:c8678869a83fab70232869ba24acc1c0be661f4d65135c0eeacb6a8e78420fdd`. |
| Runtime base | `qemux/qemu:7.50` index `sha256:e7f6fda52503a546fd649670ba46e4bc23dc6dcef275bc3fac48877fbbc430df` | [Docker Hub tag metadata](https://hub.docker.com/v2/repositories/qemux/qemu/tags/7.50); linux/amd64 `sha256:1a2442ff34d4676e921597d4905c6e72924e19d90f16980725f8a344998f0358`, linux/arm64 `sha256:099637a6a59cc1fe7bb1b71780e24cf41c1f68cc484f3e6f7d8bb1e7bee6d019`. |
| QEMU host helper | `qemux/qemu-host:2.06` index `sha256:5cd89a126bd4fb59cab33de7a1636871564e5006ecf51931c211ecb9f3012b32` | [Docker Hub tag metadata](https://hub.docker.com/v2/repositories/qemux/qemu-host/tags/2.06); linux/amd64 `sha256:b98a98a6cf6db01bf805c94b5aa4dae0f4c5463ff24815c253482a2554ddfd4e`, linux/arm64 `sha256:9bb4192c156bf1c25b49fd557dd3f22381e2c6b623b2a0ec9143695c2c47ca34`. |
| QEMU build base | `debian:trixie-slim` index `sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad` | [Docker Hub tag metadata](https://hub.docker.com/v2/repositories/library/debian/tags/trixie-slim); linux/amd64 `sha256:4876fdea29cac1a33a3195f1eb1952feb1fca7dd6dd00be3e2f1879cf20d34d2`, linux/arm64 `sha256:a66b19aa552f595b4ab276c6b4f9b24fa4546632c5ecd88cccdced4a6866323a`. |
| QEMU source and Meson subprojects | QEMU `v8.2.2`, peeled commit `11aa0b1ff115b86160c4d37e7c37e6a6b13b77ea`; `dtc` `b6910bec11614980a21e46fbccc35934b671bd81`; `keycodemapdb` `f5772a62ec52591ff6870b7e8ef32482371f22c6`; `berkeley-softfloat-3` `b64af41c3276f97f0e181920400ee056b9c88037`; `berkeley-testfloat-3` `e7af9751d9f9fd3b47911f51a5cfd08af256a9ab` | QEMU tag identity verified from both [GitLab](https://gitlab.com/qemu-project/qemu/-/tree/v8.2.2) and [GitHub mirror](https://github.com/qemu/qemu/tree/v8.2.2). Its Meson wrap files select these exact Git commits; a fresh native amd64 configure fetched those four revisions. `scripts/fetch-qemu-source.sh` checks QEMU commit and `VERSION`; production patches remain exclusively in `patches/qemu/8.2.2/` and are applied by `scripts/apply-qemu-patches.sh`. |
| patology | commit `18737e0924725375a857f10a54a4b5229beec3b2`; `patology.py` SHA256 `add398aa4058dd4b6e1dbe36ed89a5b259074cb702d77b460023e98ce143a3a6` | [Pinned source file](https://github.com/sud0woodo/patology/blob/18737e0924725375a857f10a54a4b5229beec3b2/patology.py); commit resolved from `main`, bytes fetched and hashed. Docker `ADD --checksum` verifies content. |
| Python runtime and fixtures | `dissect.cstruct==4.7`, `dissect.extfs==3.15`, transitive `dissect.util==3.24` | [PyPI cstruct metadata](https://pypi.org/pypi/dissect.cstruct/4.7/json), [extfs metadata](https://pypi.org/pypi/dissect.extfs/3.15/json), [util metadata](https://pypi.org/pypi/dissect.util/3.24/json). `requirements.txt` pins selected release-file SHA256 hashes for universal wheels and the Python 3.13 linux/amd64 and linux/arm64 `dissect.util` wheels; production and CI install with `--require-hashes`. |

The Docker Hub index digests preserve native amd64 and arm64 selection. Do not
replace them with one platform's child digest. QEMU version, expected commit and
patch provenance are unchanged by this work.

The built amd64 runtime reports inherited `qemu-system-x86_64` version
`11.1.0 (Debian 1:11.1.0+ds-2)`. The extracted qemu-host helper binary SHA256 is
`bce765d32f8ebfbd85c20d5d5497d2e10a9efa88137957bd42369ad3a32496dc`; this
artifact hash has not been measured on arm64.

## Remaining mutable inputs

| Input | Current declaration | Why it remains open |
| --- | --- | --- |
| Debian package repositories | `apt-get update`; build/runtime package names and amd64 versions below | The pinned Debian image fixes the starting filesystem, but Trixie, trixie-updates and trixie-security move. Versions below are observations from this amd64 build only, not pins; full transitive closure, .deb SHA256 values and arm64 resolution are not recorded. |
| qemux image provenance | Fixed image digests above | The published bytes are immutable and architectures are present; upstream Dockerfile/source provenance and reproducible rebuild instructions were not independently verified. |

The native amd64 build resolved the direct Debian packages as follows. These
observations are not reproducible package locks; APT verifies packages against
signed repository metadata at build time, while repository state can move.

| Stage | Direct package | Resolved version (amd64, 2026-10-22) |
| --- | --- | --- |
| QEMU builder | `build-essential` | `12.12` |
| QEMU builder | `ca-certificates` | `20250419+deb13u1` |
| QEMU builder | `git` | `1:2.47.3-0+deb13u1` |
| QEMU builder | `meson` | `1.7.0-1` |
| QEMU builder | `ninja-build` | `1.12.1-1` |
| QEMU builder | `pkg-config` | `1.8.1-4` |
| QEMU builder | `python3-venv` | `3.13.5-1` |
| QEMU builder | `libglib2.0-dev` | `2.84.4-3~deb13u5` |
| QEMU builder | `libpixman-1-dev` | `0.44.0-3` |
| QEMU builder | `libslirp-dev` | `4.8.0-1+deb13u1` |
| Runtime | `fakeroot` | `1.37.1.1-1` |
| Runtime | `xz-utils` | `5.8.1-1+deb13u2` |
| Runtime | `tar` | `1.35+dfsg-3.1` |
| Runtime | `e2fsprogs` | `1.47.2-3+b12` |
| Runtime | `util-linux` | `2.41.5-0+deb13u1` |
| Runtime | `python3-msgpack` | `1.0.3-3+b4` |
| Runtime | `python3-pysodium` | `0.7.18-2` |
| Runtime | `openssh-client` | `1:10.0p1-7+deb13u4` |
| Runtime | `libslirp0` | `4.9.3-1` |
| Runtime | `libpixman-1-0` | `0.44.0-3` |

These gaps are tracked as [RISK-009](RISK_REGISTER.md#risk-009p1-apt-与镜像上游重建信息未完整锁定). Do not claim bit-for-bit image reproducibility until package repositories and base-image upstream provenance have reproducible identities.

## Update procedure

1. Resolve upstream image tags through registry metadata and record the index
   digest plus amd64/arm64 child digests. Verify both platforms remain present.
2. For source scripts, resolve a commit, fetch the exact file at that commit,
   calculate SHA256, and enforce the checksum in the Docker build.
3. For Python, update direct and transitive exact versions together; obtain
   hashes from the package index for artifacts selected on both supported
   Linux architectures. Keep `--require-hashes` enabled in image and CI installs.
4. Keep QEMU's version, source commit, patch README and patch application helper
   in sync. Changes to the production patch source require their existing QEMU
   patch regression and must not import research patches.
5. Run native amd64 and arm64 image checks before treating updated locks as
   accepted. Record unavailable builders, sources, and product-runtime evidence
   separately; a successful build alone is not DSM runtime acceptance.
