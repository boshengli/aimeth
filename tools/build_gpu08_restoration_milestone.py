#!/usr/bin/env python3
"""Build a restoration assessment; do not label it a completed restoration."""
import argparse
import hashlib
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    path = ROOT / 'reports/gpu08-restoration-v1/evidence.json'
    raw = path.read_bytes()
    data = json.loads(raw)
    assert data['observations']['reservation_and_allocation_preserved']
    assert not data['readiness']['exact_preloan_state_restored']
    assert not data['readiness']['new_model_launch_ready']
    assert [j['id'] for j in data['jobs']] == [221936, 221943]
    assert all(j['state'] == 'COMPLETED' and not j['new_gpu_allocation'] for j in data['jobs'])
    assert all(value == 0 for value in data['actions'].values())
    text = (ROOT / 'templates/gpu08-restoration-v1.html').read_text()
    text = text.replace('@@EVIDENCE@@', escape(json.dumps(data, ensure_ascii=False, indent=2)))
    text = text.replace('@@HASH@@', hashlib.sha256(raw).hexdigest())
    assert '@@' not in text
    return text


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'milestones/m2-4a-gpu08-restoration-v1.html')
    args = parser.parse_args()
    args.output.write_text(build())
    print('Built M2.4a assessment; complete restoration remains unverified.')
