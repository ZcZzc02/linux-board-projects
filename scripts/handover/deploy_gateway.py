"""Deploy the packaged gateway by ADB; inspect only unless --apply is supplied."""

import argparse
import io
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--serial', help='ADB serial, required only if multiple devices exist')
    parser.add_argument('--adb', help='Override ADB executable')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    source = root / '2.1.Linux网关/k7-gateway'
    bundled_adb = root / 'tools/platform-tools/adb.exe'
    adb = args.adb or (str(bundled_adb) if bundled_adb.is_file() else shutil.which('adb'))
    if not adb:
        parser.error('ADB not found; install Platform-Tools or supply --adb')
    command = [adb] + (['-s', args.serial] if args.serial else [])

    def run(*parts):
        return subprocess.run(command + list(parts), check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')

    print(run('get-state').stdout.strip())
    print(run('shell', 'id; uname -a; ls -l /dev/ttyS3; command -v python3; command -v nmcli').stdout)
    if not source.is_dir():
        parser.error('Gateway source is missing')
    if not args.apply:
        print('Inspection only. Use --apply after restoring UART3 and reading the guide.')
        return
    if run('shell', 'id -u').stdout.strip() != '0':
        parser.error('ADB shell must be root; use a verified root session instead')
    remote_tar = '/tmp/k7-deploy-' + uuid.uuid4().hex + '.tgz'
    with tempfile.TemporaryDirectory(prefix='k7-deploy-') as tmp:
        archive = Path(tmp) / 'gateway.tgz'
        with tarfile.open(archive, 'w:gz') as tar:
            for base in ('src', 'scripts', 'systemd'):
                for file in sorted((source / base).rglob('*')):
                    if not file.is_file() or '__pycache__' in file.parts or file.suffix == '.pyc':
                        continue
                    data = file.read_bytes().replace(b'\r\n', b'\n')
                    info = tarfile.TarInfo(file.relative_to(source).as_posix())
                    info.size = len(data)
                    info.mode = 0o755 if file.suffix == '.sh' else 0o644
                    tar.addfile(info, io.BytesIO(data))
        print(run('push', str(archive), remote_tar).stdout)
        # A single archive avoids ambiguous adb directory-copy semantics.
        shell = (
            'set -eu; mkdir -p /root/k7-gateway; '
            f'tar -xzf {remote_tar} -C /root/k7-gateway; '
            'cd /root/k7-gateway; PYTHONPATH=src python3 -m k7_gateway --help >/dev/null; '
            'sh scripts/install_systemd_service.sh'
        )
        print(run('shell', shell).stdout)
    print('Deployment finished. Check systemd logs and verify live MQTT data separately.')


if __name__ == '__main__':
    main()
