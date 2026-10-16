"""Read Rockchip FIT/resource images and report their embedded device trees."""

import argparse
import hashlib
import json
import struct
from pathlib import Path


def fdt_nodes(blob):
    header = struct.unpack_from('>10I', blob)
    magic, total, off_struct, off_strings = header[:4]
    if magic != 0xD00DFEED or total > len(blob):
        raise ValueError('Invalid FDT header')
    strings = blob[off_strings:off_strings + header[8]]
    pos = off_struct
    stack = []
    nodes = {}
    while pos < off_struct + header[9]:
        token, = struct.unpack_from('>I', blob, pos)
        pos += 4
        if token == 1:
            end = blob.index(b'\0', pos)
            stack.append(blob[pos:end].decode('ascii'))
            pos = (end + 4) & ~3
            nodes['/' + '/'.join(stack[1:])] = {}
        elif token == 2:
            stack.pop()
        elif token == 3:
            size, nameoff = struct.unpack_from('>II', blob, pos)
            pos += 8
            name = strings[nameoff:strings.index(b'\0', nameoff)].decode('ascii')
            nodes['/' + '/'.join(stack[1:])][name] = blob[pos:pos + size]
            pos = (pos + size + 3) & ~3
        elif token == 4:
            continue
        elif token == 9:
            break
        else:
            raise ValueError('Invalid FDT token')
    return nodes


def fit_images(blob):
    nodes = fdt_nodes(blob)
    total, = struct.unpack_from('>I', blob, 4)
    images = {}
    hashes = {}
    for path, props in nodes.items():
        if not path.startswith('/images/') or path.count('/') != 2:
            continue
        name = path.rsplit('/', 1)[1]
        if 'data' in props:
            data = props['data']
        else:
            size = int.from_bytes(props['data-size'], 'big')
            if 'data-position' in props:
                offset = int.from_bytes(props['data-position'], 'big')
            else:
                offset = ((total + 3) & ~3) + int.from_bytes(props['data-offset'], 'big')
            data = blob[offset:offset + size]
            if len(data) != size:
                raise ValueError('Truncated FIT image')
        images[name] = data
        digest = hashlib.sha256(data).hexdigest()
        for child, childprops in nodes.items():
            if child.startswith(path + '/') and childprops.get('algo') == b'sha256\0':
                if childprops.get('value') != bytes.fromhex(digest):
                    raise ValueError('FIT hash mismatch: ' + name)
        hashes[name] = {'bytes': len(data), 'sha256': digest}
    return images, hashes


def resource_files(blob):
    if blob[:4] != b'RSCE':
        raise ValueError('Not a Rockchip resource image')
    header_blocks, table_blocks, entry_blocks = blob[8:11]
    count, = struct.unpack_from('<I', blob, 12)
    files = {}
    for index in range(count):
        offset = (header_blocks + table_blocks - 1 + index * entry_blocks) * 512
        if blob[offset:offset + 4] != b'ENTR':
            raise ValueError('Invalid resource entry')
        name = blob[offset + 4:offset + 224].split(b'\0')[0].decode('utf-8')
        # ENTR: tag(4), path(220), hash(32), hash_size(4), block(4), size(4).
        block, size = struct.unpack_from('<II', blob, offset + 260)
        data = blob[block * 512:block * 512 + size]
        if len(data) != size:
            raise ValueError('Truncated resource entry')
        files[name] = data
    return files


def describe_tree(blob):
    nodes = fdt_nodes(blob)
    result = {}
    for path, props in nodes.items():
        if path == '/':
            result['model'] = props.get('model', b'').rstrip(b'\0').decode('utf-8')
        if path.endswith(('serial@2ad60000', 'i2c@2aca0000')):
            result[path] = {
                'status': props.get('status', b'okay\0').rstrip(b'\0').decode('ascii'),
                'pinctrl-0': props.get('pinctrl-0', b'').hex(),
            }
    return result


def inspect(boot, resource, official, output):
    output.mkdir(parents=True, exist_ok=True)
    images, report = fit_images(boot.read_bytes())
    originals, original_report = fit_images(official.read_bytes())
    embedded_resource = images['resource']
    resource_equal = embedded_resource == resource.read_bytes()
    files = resource_files(embedded_resource)
    original_files = resource_files(originals['resource'])
    if files.keys() != original_files.keys():
        raise ValueError('Resource file list changed')
    dtb = files['rk-kernel.dtb']
    (output / 'rk-kernel-uart3.dtb').write_bytes(dtb)
    (output / 'kernel-official-preserved.bin').write_bytes(images['kernel'])
    report = {
        'fit_images': report,
        'official_fit_images': original_report,
        'kernel_unchanged': images['kernel'] == originals['kernel'],
        'fit_fdt_unchanged': images['fdt'] == originals['fdt'],
        'embedded_resource_matches_file': resource_equal,
        'fit_device_tree': describe_tree(images['fdt']),
        'resource_device_tree': describe_tree(dtb),
        'resource_files': {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                           for name, data in files.items()},
        'device_tree_changes': {},
    }
    for name, data in files.items():
        if not name.endswith('.dtb'):
            if data != original_files[name]:
                raise ValueError('Non-DTB resource changed: ' + name)
            continue
        new_nodes, old_nodes = fdt_nodes(data), fdt_nodes(original_files[name])
        changes = []
        for node in sorted(new_nodes.keys() | old_nodes.keys()):
            old, new = old_nodes.get(node, {}), new_nodes.get(node, {})
            for prop in sorted(old.keys() | new.keys()):
                if old.get(prop) != new.get(prop):
                    changes.append({'node': node, 'property': prop,
                                    'before_hex': old.get(prop, b'').hex(),
                                    'after_hex': new.get(prop, b'').hex()})
        report['device_tree_changes'][name] = changes
        expected_changes = {('/serial@2ad60000', 'status'), ('/i2c@2aca0000', 'status')}
        if {(item['node'], item['property']) for item in changes} != expected_changes:
            raise ValueError('Unexpected device-tree modifications: ' + name)
        (output / name).write_bytes(data)
        tree = describe_tree(data)
        statuses = {p.rsplit('/', 1)[-1]: props['status'] for p, props in tree.items() if isinstance(props, dict)}
        if statuses.get('serial@2ad60000') != 'okay' or statuses.get('i2c@2aca0000') != 'disabled':
            raise ValueError('Resource UART3/I2C7 validation failed: ' + name)
    (output / 'boot-inspection.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if not report['kernel_unchanged'] or not resource_equal:
        raise ValueError('Boot provenance validation failed')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot', type=Path, required=True)
    parser.add_argument('--resource', type=Path, required=True)
    parser.add_argument('--official-boot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.boot, args.resource, args.official_boot, args.output), ensure_ascii=False, indent=2))
