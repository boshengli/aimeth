#!/usr/bin/env python3
"""Check exported synthetic event chains and frozen configuration linkage."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.verify_artifacts import verify


def digest(value):
    encoded=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def main():
    evidence=json.loads((ROOT/'reports/m2-1-validation.json').read_text())
    counts={}
    for result in evidence['trace_runs']:
        arm=result['arm']; base=ROOT/'examples/organizations/traces'/arm
        verify(base/'manifest.json')
        events=[json.loads(line) for line in (base/'events.jsonl').read_text().splitlines()]
        previous='0'*64; seen=set()
        for event in events:
            assert event['prev_hash']==previous
            assert set(event['parents']) <= seen
            assert digest({k:v for k,v in event.items() if k not in ('seq','event_hash')})==event['event_hash']
            previous=event['event_hash'];seen.add(event['event_id'])
        assert previous==result['verification']['tail_hash']
        assert len(events)==result['verification']['events']
        config=json.loads((ROOT/f'examples/organizations/{arm}.manifest.json').read_text())
        assert digest(config)==result['manifest_sha256']
        assert events[0]['payload']['manifest']==config
        selected=[e for e in events if e['kind']=='observation.terminal_selection']
        assert len(selected)==1 and selected[0]['payload']==result['selection']
        assert selected[0]['parents']==[result['selection']['source_event']]
        counts[arm]=len(events)
    print(json.dumps({'status':'passed','synthetic_event_chains':counts,'mathematical_effect_checked':False},indent=2))


if __name__=='__main__':
    main()
