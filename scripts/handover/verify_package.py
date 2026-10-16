"""Verify every packaged file against MANIFEST.json without touching hardware."""

import hashlib
import json
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    failures = []
    for index, item in enumerate(manifest['files'], 1):
        path = (root / item['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            failures.append(item['path'] + ': missing or invalid path')
        elif path.stat().st_size != item['bytes'] or sha256_file(path) != item['sha256']:
            failures.append(item['path'] + ': mismatch')
        if index % 250 == 0 or item['bytes'] > 100_000_000:
            print(f'Verified {index}/{len(manifest["files"])}', flush=True)
    if failures:
        raise SystemExit('\n'.join(failures))
    print(f'PASS: {len(manifest["files"])} files match the manifest.')
    print('This verifies file integrity, not hardware functionality.')


if __name__ == '__main__':
    main()
