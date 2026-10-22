#!/usr/bin/env python3
"""Run the image's real entrypoint with synthetic disks and a fake x86 QEMU."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid


def require(condition, message):
    if not condition:
        raise SystemExit('FAIL: ' + message)


require(len(sys.argv) == 2 and bool(sys.argv[1]), 'production image tag required')
with tempfile.TemporaryDirectory(prefix='virtualdsm-x86-image-') as tmp:
    directory = Path(tmp)
    storage = directory / 'storage'
    storage.mkdir(mode=0o777)
    storage.chmod(0o777)
    base = 'DSM_VirtualDSM_test'
    # Matching dsm.ver and image names take the existing-install path without a URL.
    (storage / 'dsm.ver').write_text(base + '\n')
    for suffix in ('boot.img', 'system.img'):
        with (storage / f'{base}.{suffix}').open('wb') as stream:
            stream.truncate(1024 * 1024)
    bin_dir = directory / 'bin'
    bin_dir.mkdir()
    qemu = bin_dir / 'qemu-system-x86_64'
    qemu.write_text(
        '#!/usr/bin/python3\n'
        'import json, sys\n'
        'from pathlib import Path\n'
        'if sys.argv[1:] == ["--version"]:\n'
        '    print("QEMU emulator version 11.1.0 (argument capture)")\n'
        'else:\n'
        '    Path("/storage/argv.json").write_text(json.dumps(sys.argv[1:]))\n'
        '    raise SystemExit(37)\n'
    )
    qemu.chmod(0o755)
    for name in ('curl', 'wget'):
        stub = bin_dir / name
        stub.write_text(
            '#!/bin/sh\n'
            'printf "%s\\n" "$0 $*" >> /storage/network.log\n'
            'echo UNEXPECTED_NETWORK_ACCESS >&2\n'
            'exit 86\n'
        )
        stub.chmod(0o755)

    container = 'virtual-dsm-x86-test-' + uuid.uuid4().hex[:12]
    command = [
        'docker', 'run', '--rm', '--pull=never', '--name', container,
        '--network', 'none',
        '--mount', f'type=bind,src={storage},dst=/storage',
        '--mount', f'type=bind,src={bin_dir},dst=/capture-bin,readonly',
    ]
    for value in (
        'PATH=/capture-bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
        'KVM=N', 'NETWORK=slirp', 'DEV=lo', 'IP=10.0.2.15', 'DNSMASQ_DISABLE=Y',
        'MAC=02:11:32:12:34:56', 'COUNTRY=US', 'WEB=N', 'SHUTDOWN=N',
        'DISK_SIZE=6G', 'DISK_FMT=raw', 'ALLOCATE=N', 'RAM_SIZE=2G', 'CPU_CORES=2',
    ):
        command.extend(('--env', value))
    command.append(sys.argv[1])
    try:
        try:
            process = subprocess.run(command, text=True, capture_output=True, timeout=90)
        except subprocess.TimeoutExpired as exc:
            raise SystemExit('FAIL: image entrypoint timed out after 90 seconds') from exc
    finally:
        # Killing the Docker CLI alone does not stop a timed-out container.
        subprocess.run(['docker', 'rm', '-f', container], capture_output=True, timeout=15)
    if process.returncode != 37:
        sys.stderr.write(process.stdout + process.stderr)
    require(not (storage / 'network.log').exists(), 'entrypoint attempted a download')
    require(process.returncode == 37, f'image expected fake QEMU exit 37, got {process.returncode}')
    capture = storage / 'argv.json'
    require(capture.is_file(), 'image entrypoint did not reach the fake x86 QEMU')
    args = json.loads(capture.read_text())

    def values(option):
        return [args[index + 1] for index, value in enumerate(args[:-1]) if value == option]

    require(values('-machine') == [
        'type=q35,smm=off,usb=off,vmport=off,dump-guest-core=off,hpet=off'
    ], 'image default platform must construct the accepted q35 machine')
    require(values('-boot') == ['strict=on'], 'image must preserve legacy strict boot')
    # The inherited x86 processor stage emits -accel only on amd64 hosts.
    # With the exact machine above, no -accel selects QEMU's default TCG.
    require(values('-accel') in ([], ['tcg,thread=multi']) and '-enable-kvm' not in args,
            'KVM=N must select explicit or default TCG without enabling KVM; '
            f'fake-QEMU argv: {json.dumps(args)}')
    devices = values('-device')
    for name, suffix, address, index in (
        ('synoboot', 'boot.img', '0xa', 1), ('synosys', 'system.img', '0xb', 2),
    ):
        require(any({f'file=/storage/{base}.{suffix}', f'id={name}'}.issubset(drive.split(','))
                    for drive in values('-drive')), f'missing {name} fixture drive')
        require(any(device.startswith('virtio-scsi-pci,') and
                    {f'id={name}', 'bus=pcie.0', f'addr={address}'}.issubset(device.split(','))
                    for device in devices), f'incorrect {name} PCI attachment')
        require(any(device.startswith('scsi-hd,') and
                    {f'drive={name}', f'bootindex={index}'}.issubset(device.split(','))
                    for device in devices), f'incorrect {name} boot order')
    for device in ('virtio-serial-pci', 'virtio-net-pci', 'virtio-rng-pci', 'virtio-balloon-pci'):
        require(any(value.startswith(device + ',') for value in devices), f'missing {device}')
    require(any(value.startswith('user,') for value in values('-netdev')), 'missing user network backend')
    require(not any(value in args for value in ('-kernel', '-initrd', '-dtb')),
            'x86 entrypoint must not enter the ARM direct-boot path')
    require(not any('rtd1619b' in value or 'usb-net' in value for value in args),
            'ARM device arguments leaked into the x86 entrypoint')

print('Production x86 image entrypoint passed: installed fixture, q35/PCI/VirtIO, fake QEMU exit 37, isolated network, no DSM payloads.')
