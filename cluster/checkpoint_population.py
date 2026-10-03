#!/usr/bin/env python3
"""Create a rolling, consistent recovery copy of a node-local AIMeth run."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _backup(source, destination):
    source = Path(source)
    if not source.is_file():
        return False
    src = sqlite3.connect(f'file:{source}?mode=ro', uri=True, timeout=30)
    tmp = Path(str(destination) + '.tmp')
    dst = sqlite3.connect(tmp)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    os.replace(tmp, destination)
    return True


def capture_once(source_root, output_root):
    source_root, output_root = Path(source_root), Path(output_root)
    if not (source_root / 'journal.sqlite').is_file():
        return None
    parent = output_root / 'checkpoints'
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = f'{time.time_ns()}-{os.getpid()}'
    temporary = parent / f'.checkpoint-{stamp}.tmp'
    target = parent / f'checkpoint-{stamp}'
    temporary.mkdir(mode=0o700)
    for name in ('journal.sqlite', 'budget.sqlite'):
        _backup(source_root / name, temporary / name)
    for name in ('population.json', 'technical-stop.json'):
        source = source_root / name
        if source.is_file():
            shutil.copy2(source, temporary / name)
    receipts = source_root / 'receipts'
    dest_receipts = temporary / 'receipts'
    copied = 0
    if receipts.is_dir():
        dest_receipts.mkdir(mode=0o700)
        for source in sorted(receipts.glob('*.json')):
            shutil.copy2(source, dest_receipts / source.name)
            copied += 1
    payload_files = sorted(p for p in temporary.rglob('*') if p.is_file())
    manifest = {
        'captured_unix': time.time(),
        'source_root': str(source_root),
        'receipt_count': copied,
        'files': {str(p.relative_to(temporary)): sha256(p) for p in payload_files},
    }
    manifest_path = temporary / 'checkpoint.json'
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    os.replace(temporary, target)
    pointer_tmp = output_root / '.latest-checkpoint.json.tmp'
    pointer_tmp.write_text(json.dumps({'checkpoint': target.name,
                                      'manifest_sha256': sha256(target / 'checkpoint.json')},
                                     sort_keys=True) + '\n')
    os.replace(pointer_tmp, output_root / 'latest-checkpoint.json')
    completed = sorted(parent.glob('checkpoint-*'), key=lambda p: p.name, reverse=True)
    for old in completed[2:]:
        shutil.rmtree(old)
    return {'checkpoint': target.name, 'receipt_count': copied,
            'journal_bytes': (target / 'journal.sqlite').stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--interval-seconds', type=int, default=300)
    args = parser.parse_args()
    while True:
        try:
            result = capture_once(args.source_root, args.output_root)
            if result:
                print(json.dumps(result, sort_keys=True), flush=True)
        except Exception as exc:
            print(json.dumps({'checkpoint_error': type(exc).__name__}), flush=True)
        if not args.watch:
            return
        time.sleep(max(30, args.interval_seconds))


if __name__ == '__main__':
    main()
