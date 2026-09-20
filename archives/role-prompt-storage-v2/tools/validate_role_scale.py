#!/usr/bin/env python3
"""Measure compiler payloads and compare old/new request bytes, with no inference."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aimeth_runtime.store import Store,canonical,digest
from aimeth_design.role_routing import compile_roles
from aimeth_pilot.calibration import tasks


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    script='''import sys,json,tempfile
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from aimeth_design.role_routing import compile_roles
from aimeth_pilot.calibration import tasks
from aimeth_runtime.store import Store,canonical,digest
config=compile_roles('H',tasks()['prime-counterexample'])
with tempfile.TemporaryDirectory() as temp,Store(Path(temp)/'x.sqlite') as store:
 store.create_run('fixture',config);store.enqueue_round('fixture',0)
 requests=[json.loads(r[0]) for r in store.db.execute('SELECT request FROM steps ORDER BY step_id')]
try:
 compile_roles('H',tasks()['prime-counterexample'],population=10000)
 large='unexpectedly accepted'
except ValueError as exc:large=str(exc)
print(json.dumps({'requests':requests,'n8_manifest_event_bytes':len(canonical({'manifest':config,'fingerprint':digest(config)}).encode()),'n10000_outcome':large}))
'''
    old=json.loads(subprocess.check_output([sys.executable,'-c',script,str(ROOT/'archives/role-pilot-v1')],text=True))
    config=compile_roles('H',tasks()['prime-counterexample'])
    with tempfile.TemporaryDirectory() as temp,Store(Path(temp)/'x.sqlite') as store:
        store.create_run('fixture',config);store.enqueue_round('fixture',0)
        requests=[json.loads(r[0]) for r in store.db.execute('SELECT request FROM steps ORDER BY step_id')]
    assert old['requests']==requests
    assert old['n10000_outcome']=='Manifest exceeds 2 MiB journal event limit'
    rows=[]
    for n in (8,32,128,512,10000):
        for arm in ('H','F'):
            start=time.monotonic();config=compile_roles(arm,tasks()['prime-counterexample'],population=n)
            size=len(canonical({'manifest':config,'fingerprint':digest(config)}).encode())
            rows.append({'population':n,'arm':arm,'rounds':4,'call_slots':n*4,
                         'planned_messages':sum(map(len,config['round_edges'].values())),
                         'manifest_event_bytes':size,'elapsed_seconds':time.monotonic()-start,
                         'role_templates':len(config['message_templates']),'inference_requests':0})
    result={'schema_version':'1.0','scope':'local compiler and first-round request equivalence; no 10K inference',
            'old_execution_source':'8712fd9d62eb6fe0025b05a86b603b33f464005c',
            'first_round_requests_byte_identical':True,'compared_requests':len(requests),'request_set_sha256':digest(requests),
            'old_n8_manifest_event_bytes':old['n8_manifest_event_bytes'],'old_n10000_outcome':old['n10000_outcome'],
            'measurements':rows,'live_10k_launch_ready':False,
            'source_files':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['aimeth_runtime/store.py','aimeth_design/role_routing.py','tools/validate_role_scale.py']}}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'equivalent_requests':len(requests),'n10000':[r for r in rows if r['population']==10000]},indent=2))

if __name__=='__main__':main()
