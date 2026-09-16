#!/usr/bin/env python3
"""Export reviewed official-provider development traces, without credentials."""
import copy
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aimeth_runtime.store import Store


def main():
    source = ROOT / 'runs/public-sanity-v1'
    output = ROOT / 'reports/public-sanity-v1'
    output.mkdir(parents=True, exist_ok=True)
    data = json.loads((source / 'summary.json').read_text())
    data = copy.deepcopy(data)
    for item in data['metadata']['plan']:
        for key in ('credential_file', 'credential_variable'):
            item['provider'].pop(key)
    usage = Counter()
    with (output / 'events.jsonl').open('w') as stream:
        for result in data['results']:
            rid = result['case']['case_id']
            export = source / rid / 'export'
            with tempfile.TemporaryDirectory() as temp:
                snapshot = Path(temp) / 'snapshot.sqlite'
                shutil.copy2(export / 'snapshot.sqlite', snapshot)
                with Store(snapshot) as store:
                    assert store.verify(rid) == result['verification']
            raw = (export / 'events.jsonl').read_bytes()
            result['raw_events_sha256'] = hashlib.sha256(raw).hexdigest()
            result['raw_snapshot_sha256'] = hashlib.sha256((export / 'snapshot.sqlite').read_bytes()).hexdigest()
            per_usage = Counter()
            response_models = []
            for line in raw.decode().splitlines():
                event = json.loads(line)
                if event['kind'] == 'attempt.received':
                    response = event['payload']['receipt'].get('response', {})
                    response_models.append(response.get('model'))
                    for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                        value = (response.get('usage') or {}).get(key)
                        if type(value) is int:
                            per_usage[key] += value
                stream.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + '\n')
            result['usage'] = dict(per_usage)
            result['response_models'] = response_models
            usage.update(per_usage)
    data['usage'] = dict(usage)
    assert usage['total_tokens'] == data['quota']['known_total_tokens']
    data['verdict_counts'] = dict(Counter(r['verdict']['status'] for r in data['results']))
    data['public_trace_policy'] = 'Complete event payloads; official public endpoints; authorization headers were never journaled. Credential-variable metadata omitted from plan.'
    (output / 'summary.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'cases': len(data['results']), 'usage': data['usage'], 'verdicts': data['verdict_counts']}))


if __name__ == '__main__':
    main()
