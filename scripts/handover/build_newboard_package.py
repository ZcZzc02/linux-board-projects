"""Build the complete K7 new-board handover ZIP. Never writes to hardware."""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from inspect_boot import inspect
from verify_package import sha256_file


ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / 'RK3576/rk3576_data'
SDK = ROOT / 'K7-SDK/Linux/sdk/20260320/rk3576-linux-20260320/rk3576-linux'
EXCLUDED_DIRS = {'.git', '.venv', 'venv', '__pycache__', '.vscode', '.idea',
                 'Objects', 'Listings', 'DebugConfig', 'Log', 'logs', 'log'}
EXCLUDED_SUFFIXES = {'.log', '.pyc', '.pyo', '.db', '.db-shm', '.db-wal', '.dmp',
                     '.uvoptx', '.axf', '.o', '.crf', '.dep', '.d', '.zip', '.rar',
                     '.pem', '.key', '.p12', '.pfx', '.hex'}


def git(*args):
    return subprocess.run(['git', '-C', str(ROOT), *args], check=True,
                          capture_output=True).stdout.decode('utf-8').strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New ZIP path; refuses overwrite')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error('Output already exists; select a new filename')
    audit = ROOT / 'handover-dist/newboard-audit'
    boot = ROOT / 'backups/k7-resource-uart3-candidate-20260627/boot-resource-uart3.img'
    resource = boot.with_name('resource-uart3.img')
    official_boot = ROOT / 'work/unpack-ubuntu-multi-20251209-firmware/Image/boot.img'
    if sha256_file(boot) != 'bd62ad91bae99d28a5a0027bc8cb3ac9dab7d5079be40f9b50e5652ddd3860f2':
        raise ValueError('Not the historical UART3 boot image')
    if sha256_file(resource) != '8cd0150fac85e6a345689bc73b27b75acc36c1dd99925a8c5fb43872f5f2f37a':
        raise ValueError('Not the matching resource image')
    report = inspect(boot, resource, official_boot, audit)
    items = {}
    transformations = []

    def add(source, destination):
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(source)
        if destination in items:
            raise ValueError('Duplicate archive path: ' + destination)
        items[destination] = source

    def tree(source, destination):
        source = Path(source)
        if not source.is_dir():
            raise FileNotFoundError(source)
        for directory, dirs, names in os.walk(source):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
            for name in sorted(names):
                file = Path(directory) / name
                if file.suffix.lower() in EXCLUDED_SUFFIXES or name.startswith('.env') or '.uvguix.' in name:
                    continue
                add(file, destination + '/' + file.relative_to(source).as_posix())

    for name in ('AGENTS.md', 'README.md', '.gitignore', '.gitattributes'):
        add(ROOT / name, name)
    tree(ROOT / 'docs', 'docs')
    tree(ROOT / 'scripts', 'scripts')
    tree(ROOT / '2.1.Linux网关', '2.1.Linux网关')
    tree(ROOT / '5.网络上位机服务', '5.网络上位机服务')
    tree(ROOT / '2.节点F767', '2.节点F767')
    tree(ROOT / '1.网关/onenet_v1', 'legacy-stm32-gateway/onenet_v1')
    add(ROOT / '2.节点F767/Onenet_BigBoard (2)_V4/Onenet_BigBoard/USER/Objects/工程文件.hex',
        'node-firmware/工程文件.hex')
    add(ROOT / 'docs/K7新板从零复现与完整交接.md', '请先阅读-新板复现.md')
    add(boot, 'firmware/uart3/boot-resource-uart3.img')
    add(resource, 'firmware/uart3/resource-uart3.img')
    add(ROOT / 'backups/k7-official-baseline-20260627-131743/boot-official-baseline.img',
        'firmware/baseline/boot-official-baseline.img')
    add(official_boot, 'firmware/baseline/boot-official-from-update.img')
    official = VENDOR / '2-Image/RK3576-K7/Ubuntu2404/update-rk3576-kickpi-k7-linux-ubuntu-multi-20251209-191847.img'
    if official.stat().st_size != 4204509827:
        raise ValueError('Official image size mismatch')
    add(official, 'firmware/official/' + official.name)
    for name in ('MiniLoaderAll.bin', 'parameter.txt', 'package-file'):
        add(ROOT / 'work/unpack-ubuntu-multi-20251209-firmware' / name, 'firmware/loader/' + name)
    tree(audit, 'firmware/inspection')
    tree(ROOT / 'kickpi-rk3576-docs', 'references/vendor-docs')
    tree(VENDOR / '4-HardwareData/K7', 'references/hardware/K7')
    tree(VENDOR / '4-HardwareData/LCD', 'references/hardware/LCD')
    tree(VENDOR / '4-HardwareData/datasheet', 'references/hardware/datasheet')
    for name in ('KICKPI-K7规格书.pdf', 'KICKPI-K7_Specification.pdf'):
        add(VENDOR / '0-Specifications/K7-RK3576' / name, 'references/hardware/' + name)
    add(ROOT / 'K7当前状态交接与续开发指南.md', 'references/历史交接说明.md')
    tree(ROOT / 'work/sdk-dts-backup-20260627', 'references/device-tree/historical-sdk-copy')
    add(ROOT / 'work/boot-uart3.its', 'references/device-tree/boot-uart3.its')
    for name in ('rk3576-kickpi-k7-linux.dts', 'rk3576-kickpi-k7.dtsi',
                 'rk3576-kickpi-k7-extend-40pin.dtsi', 'rk3576-kickpi-k7-wifi.dtsi',
                 'rk3576-pinctrl.dtsi'):
        add(SDK / 'kernel-6.1/arch/arm64/boot/dts/rockchip' / name,
            'references/device-tree/sdk-source-snapshot/' + name)
    for name in ('quectel-CM', '4G_monitor.sh'):
        add(SDK / 'debian/overlay/usr/bin' / name, 'references/cellular/' + name)

    toolroot = VENDOR / '5-DevelopmentTool'
    toolpaths = {
        'FactoryTool-v1.89': toolroot / 'win_x64_FactoryTool/FactoryTool_v1.89/FactoryTool_v1.89/FactoryTool_v1.89',
        'RKDevTool-v3.30': toolroot / 'win_x64_UsbImageBurnTool/RKDevTool_v3.30_for_window/RKDevTool_v3.30_for_window',
        'DriverAssistant-v5.13': toolroot / 'win_x64_UsbDriver/DriverAssitant_v5.13/DriverAssitant_v5.13',
    }
    for name, path in toolpaths.items():
        tree(path, 'tools/' + name)
    # Prefer locally installed current ADB without depending on its install path on the recipient PC.
    local_adb = Path(shutil.which('adb') or 'D:/tools/platform-tools/adb.exe')
    if not local_adb.is_file():
        local_adb = toolroot / 'win_x64_ADB_Tool/adb-tools/adb.exe'
    for name in ('adb.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll'):
        add(local_adb.parent / name, 'tools/platform-tools/' + name)
    for name in ('NOTICE.txt', 'source.properties'):
        if (local_adb.parent / name).is_file():
            add(local_adb.parent / name, 'tools/platform-tools/' + name)
    terminal = toolroot / 'win_x64_UartDebugTool/MobaXterm_Portable_v20.3'
    for name in ('MobaXterm_Personal_20.3.exe', 'CygUtils.plugin'):
        add(terminal / name, 'tools/serial-terminal/' + name)

    bundle = audit / 'linux-board-projects.bundle'
    # tree(audit) was already collected, so this bundle is stored only at the package root.
    items.pop('firmware/inspection/linux-board-projects.bundle', None)
    subprocess.run(['git', '-C', str(ROOT), 'bundle', 'create', str(bundle), 'HEAD',
                    git('branch', '--show-current')], check=True)
    subprocess.run(['git', '-C', str(ROOT), 'bundle', 'verify', str(bundle)], check=True)
    add(bundle, 'linux-board-projects.bundle')

    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = []
    prefix = 'K7-NewBoard-Handover/'
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as archive:
        for index, (name, source) in enumerate(sorted(items.items()), 1):
            try:
                origin = source.relative_to(ROOT).as_posix()
            except ValueError:
                origin = 'local-platform-tools/' + source.name
            raw = None
            if name == '.gitignore':
                raw = source.read_bytes() + b'\nfirmware/\ntools/\nreferences/\nnode-firmware/\n*.bundle\nMANIFEST.json\nBUILD_INFO.json\n'
                transformations.append({'path': name, 'change': 'ignore packaged binaries and generated manifests'})
            if name == 'legacy-stm32-gateway/onenet_v1/USER/main.h':
                raw = source.read_bytes()
                for macro in (b'WIFI_TEST_SSID', b'WIFI_TEST_PASSWORD', b'HIVEMQ_PASSWORD'):
                    raw, count = re.subn(rb'(?m)^(\s*#define\s+' + macro + rb'\s+)"[^"\r\n]*"',
                                         lambda match: match[1] + b'"FILL_LOCALLY"', raw)
                    if count != 1:
                        raise ValueError('Expected one legacy credential macro: ' + macro.decode())
                transformations.append({'path': name, 'change': 'three SSID/password macros redacted; original source unchanged'})
            if raw is not None:
                archive.writestr(prefix + name, raw)
                size, digest = len(raw), hashlib.sha256(raw).hexdigest()
            else:
                size = source.stat().st_size
                digest = hashlib.sha256()
                if size > 100_000_000:
                    print('Packing large file: ' + name, flush=True)
                with source.open('rb') as stream, archive.open(prefix + name, 'w', force_zip64=True) as target:
                    for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                        digest.update(chunk)
                        target.write(chunk)
                digest = digest.hexdigest()
            manifest.append({'path': name, 'bytes': size, 'sha256': digest, 'source': origin})
            if index % 250 == 0:
                print(f'Packed {index}/{len(items)} files', flush=True)
        build_info = {
            'purpose': 'Replacement K7 provisioning: official image + resource UART3 boot + app deployment',
            'documentation_date': '2026-10-16',
            'built_at_utc': datetime.now(timezone.utc).isoformat(),
            'git_commit': git('rev-parse', 'HEAD'), 'git_branch': git('branch', '--show-current'),
            'python': sys.version, 'host_os': platform.platform(),
            'hardware_tested_this_build': False, 'full_deployed_rootfs_clone_available': False,
            'complete_sdk_included': False, 'python_dependency_installation_requires_internet': True,
            'modified_boot_sha256': sha256_file(boot),
            'resource_device_tree_changes': report['device_tree_changes'],
            'transformations': transformations,
            'exclusions': sorted(EXCLUDED_DIRS | EXCLUDED_SUFFIXES),
        }
        build_bytes = json.dumps(build_info, ensure_ascii=False, indent=2).encode('utf-8')
        archive.writestr(prefix + 'BUILD_INFO.json', build_bytes)
        manifest.append({'path': 'BUILD_INFO.json', 'bytes': len(build_bytes),
                         'sha256': hashlib.sha256(build_bytes).hexdigest(), 'source': 'generated'})
        archive.writestr(prefix + 'MANIFEST.json', json.dumps({'format': 1, 'files': manifest}, ensure_ascii=False, indent=2).encode('utf-8'))

    # Read and hash EVERY compressed entry, including the >4 GB official update after decompression.
    print('Verifying all archived bytes against the manifest...', flush=True)
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) != len(manifest) + 1:
            raise ValueError('Unexpected/duplicate archive entries')
        for index, entry in enumerate(manifest, 1):
            digest = hashlib.sha256()
            count = 0
            with archive.open(prefix + entry['path']) as stream:
                for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                    digest.update(chunk)
                    count += len(chunk)
            if digest.hexdigest() != entry['sha256'] or count != entry['bytes']:
                raise ValueError('Archive verification failed: ' + entry['path'])
            if index % 250 == 0 or count > 100_000_000:
                print(f'Verified {index}/{len(manifest)}', flush=True)
    digest = sha256_file(output)
    result = {'zip_name': output.name, 'zip_bytes': output.stat().st_size,
              'sha256': digest, 'files': len(manifest) + 1,
              'uncompressed_bytes': sum(item['bytes'] for item in manifest),
              'git_commit': git('rev-parse', 'HEAD'), 'all_entry_sha256_verified': True}
    output.with_suffix('.verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    output.with_suffix('.sha256').write_text(digest + '  ' + output.name + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)


if __name__ == '__main__':
    main()
