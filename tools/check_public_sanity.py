#!/usr/bin/env python3
"""Offline replay of public API plan, full event hashes and exact verdicts."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'archives/public-sanity-v1'))
from aimeth_runtime.store import digest
from aimeth_pilot.calibration import evaluate, manifest, schedule


def main():
    root = ROOT / 'reports/public-sanity-v1'
    data = json.loads((root / 'summary.json').read_text())
    plan = data['metadata']['plan']
    assert len(plan) == 8 and len(data['results']) + data['unstarted_cases'] == 8
    local = json.loads((ROOT / 'reports/service-calibration-v1/summary.json').read_text())
    cells = {c['case_id']: c for c in schedule(local['experiment'])}
    for item in plan:
        case = item['case']; source = cells[case['source_case_id']]
        for key in ('task_id', 'repetition', 'contract', 'max_output_tokens', 'seed', 'order_key'):
            assert case[key] == source[key]
        assert case['model'] == item['provider']['model']
        assert source['model'] == item['provider']['source_model']
        assert case['task_id'] == 'integral-rational' and case['max_output_tokens'] == 2048
    runs = defaultdict(list)
    for line in (root / 'events.jsonl').read_text().splitlines():
        event = json.loads(line); runs[event['run_id']].append(event)
    assert set(runs) == {r['case']['case_id'] for r in data['results']}
    usage = Counter(); counts = Counter(); attempts = 0
    for result in data['results']:
        case = result['case']; rid = case['case_id']
        planned = next(p for p in plan if p['case']['case_id'] == rid)
        assert case == planned['case']
        expected = manifest(case, planned['provider']['endpoint'])
        expected['request_options'] = {'thinking': {'type': 'disabled'}, 'response_format': {'type': 'json_object'}}
        assert runs[rid][0]['payload']['manifest'] == expected
        assert digest(expected) == result['manifest_sha256']
        seen = {}; previous = '0' * 64; per_usage = Counter(); models = []
        for index, event in enumerate(runs[rid]):
            assert event['seq'] == index + 1 and event['prev_hash'] == previous
            assert set(event['parents']) <= set(seen)
            assert digest({k: v for k, v in event.items() if k not in ('seq', 'event_hash')}) == event['event_hash']
            payload = event['payload']
            if event['kind'] == 'step.enqueued':
                assert digest(payload['request']) == payload['request_hash']
            if event['kind'] == 'attempt.received':
                assert digest(payload['receipt']) == payload['receipt_hash']
                response = payload['receipt'].get('response', {})
                models.append(response.get('model'))
                for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                    value = (response.get('usage') or {}).get(key)
                    if type(value) is int: per_usage[key] += value
            seen[event['event_id']] = event; previous = event['event_hash']
        assert previous == result['verification']['tail_hash']
        assert len(seen) == result['verification']['events']
        assert models == result['response_models'] and dict(per_usage) == result['usage']
        selected = result['selection']; parent = seen[selected['source_event']]
        assert parent['kind'] == 'checkpoint.saved' and parent['agent_id'] == 'a00000'
        assert parent['payload']['state']['candidate'] == selected['candidate']
        assert selected['selection_seed'] == expected['selection_seed']
        assert evaluate(case['task_id'], selected['candidate']) == result['verdict']
        assert [e['payload'] for e in seen.values() if e['kind'] == 'observation.terminal_evaluation'] == [result['verdict']]
        assert sum(e['kind'] == 'observation.budget_reserved' for e in seen.values()) == result['status']['attempts']
        attempts += result['status']['attempts']; usage.update(per_usage); counts[result['verdict']['status']] += 1
    assert dict(usage) == data['usage'] and dict(counts) == data['verdict_counts']
    assert attempts == data['quota']['reserved_calls'] == 8
    assert usage['total_tokens'] == data['quota']['known_total_tokens']
    print(json.dumps({'status': 'passed', 'cases': len(runs), 'events': sum(map(len, runs.values())),
                      'usage': dict(usage), 'verdicts': dict(counts)}, indent=2))


if __name__ == '__main__':
    main()
