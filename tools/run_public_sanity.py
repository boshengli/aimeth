#!/usr/bin/env python3
"""Eight bounded, separate official-provider diagnostic requests; no retries."""
import argparse
import json
import os
from pathlib import Path
import shlex
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from aimeth_pilot.calibration import run_case
from aimeth_pilot.quota import Quota
from aimeth_pilot.run import STOP,save
from aimeth_runtime.store import digest


def credential(path,key):
    for line in path.read_text().splitlines():
        if '=' not in line or line.lstrip().startswith('#'):continue
        k,v=line.removeprefix('export ').split('=',1)
        if k.strip()==key:return shlex.split(v)[0]
    raise ValueError('Credential variable absent')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--source-commit',required=True);args=parser.parse_args()
    root=args.root;root.mkdir(parents=True,exist_ok=False)
    local=json.loads((ROOT/'reports/service-calibration-v1/summary.json').read_text())
    providers=[{'name':'DeepSeek','model':'deepseek-flash','source_model':'deepseek-v4-flash-0731',
                'endpoint':'https://api.deepseek.com/v1/chat/completions','credential_file':'deepseek.env','credential_variable':'DEEPSEEK_API_KEY'},
               {'name':'GLM','model':'glm-5.2','source_model':'glm-5.3-flash',
                'endpoint':'https://open.bigmodel.cn/api/paas/v4/chat/completions','credential_file':'zhipu-payg.env','credential_variable':'ZHIPU_PAYG_API_KEY'}]
    plan=[]
    for provider in providers:
        for result in local['results']:
            cell=result['case']
            if cell['model']==provider['source_model'] and cell['task_id']=='integral-rational' and cell['max_output_tokens']==2048:
                case=dict(cell);case.update(model=provider['model'],source_case_id=cell['case_id'],provider=provider['name'])
                case['case_id']='public-'+digest(case)[:24];plan.append({'provider':provider,'case':case})
    assert len(plan)==8
    meta={'schema_version':'1.0','source_commit':args.source_commit,'planned_cases':8,'calls_cap':8,
          'reserved_output_cap':16384,'started_at':time.time(),'deadline':time.time()+600,'plan':plan,
          'scope':'post-observation antiderivative diagnostic; distinct model versions; not a causal deployment comparison'}
    save(root/'experiment.json',meta)
    quota=Quota(root/'quota.sqlite',calls=8,output_tokens=16384,deadline=meta['deadline'])
    signal.signal(signal.SIGTERM,lambda *_:STOP.set());signal.signal(signal.SIGINT,lambda *_:STOP.set())
    results=[];disabled=set()
    try:
        for item in plan:
            provider=item['provider'];case=item['case']
            if provider['name'] in disabled:continue
            if STOP.is_set() or time.time()>=quota.deadline:break
            os.environ['AIMETH_API_KEY']=credential(Path.home()/'.config/llm-providers'/provider['credential_file'],provider['credential_variable'])
            result=run_case(root,case,provider['endpoint'],quota,provider_options={'thinking':{'type':'disabled'},'response_format':{'type':'json_object'}})
            results.append(result)
            events=[json.loads(l) for l in (root/case['case_id']/'export/events.jsonl').read_text().splitlines()]
            codes=[e['payload']['receipt'].get('error',{}).get('http_status') for e in events if e['kind']=='attempt.received']
            if any(c in (401,403,404) for c in codes):disabled.add(provider['name'])
            save(root/'progress.json',{'completed':len(results),'planned':8,'quota':quota.summary(),'last_verdict':result['verdict']})
            print(json.dumps({'done':len(results),'provider':provider['name'],'verdict':result['verdict']['status']}),flush=True)
    finally:
        os.environ.pop('AIMETH_API_KEY',None)
        save(root/'summary.json',{'schema_version':'1.0','metadata':meta,'results':results,'unstarted_cases':8-len(results),'quota':quota.summary()})
        quota.db.close()


if __name__=='__main__':main()
