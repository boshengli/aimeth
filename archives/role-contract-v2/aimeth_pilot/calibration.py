"""Frozen factorial output-contract calibration using the existing journal."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import time
from urllib import request

from aimeth_runtime.store import Store,canonical,digest
from aimeth_runtime.runner import demo_manifest,NoRedirect
from aimeth_design.organizations import SYSTEM
from aimeth_design.execution import select_terminal
from aimeth_evaluation.controls import public_tasks,evaluate as evaluate_control
from aimeth_evaluation.pde_scaling import TASK,evaluate as evaluate_scaling
from .quota import Quota
from .run import STOP,bounded_response,finish,save

REMINDER=(
    'Certificate output contract: return exactly one JSON object with exactly the '
    'fields requested by the task. Do not add reasoning, commentary, Markdown, '
    'extra fields, or a JSON string containing another JSON object. Use actual '
    'derived values, never placeholder type names. When polynomial coefficients '
    'are requested in ascending powers, array element k is the coefficient of x^k; '
    'retain required zero entries. Express rational coefficients as integers or '
    'fraction strings, not floating-point approximations. This instruction gives '
    'no mathematical answer or evaluation feedback.')


def tasks():
    return {t['id']:t for t in [*public_tasks(),TASK]}


def schedule(cfg):
    cells=[]
    for model in cfg['models']:
        for task_id in cfg['tasks']:
            for repetition in range(2):
                block=[cfg['seed'],model,task_id,repetition]
                for contract in ('original','certificate-only'):
                    for cap in (512,2048):
                        cell={'model':model,'task_id':task_id,'repetition':repetition,'contract':contract,
                              'max_output_tokens':cap,'seed':int(digest(['sample',block])[:8],16)}
                        cell['case_id']='cal-'+digest(cell)[:24]
                        cell['order_key']=digest(['order',cfg['seed'],cell['case_id']])
                        cells.append(cell)
    return sorted(cells,key=lambda c:c['order_key'])


def manifest(cell,endpoint):
    task=tasks()[cell['task_id']]
    config=demo_manifest(1,1)
    config.update(model_name=cell['model'],seed=cell['seed'],selection_seed=cell['seed'],
                  max_output_tokens=cell['max_output_tokens'],max_attempts=1,max_inflight=1,
                  temperature=0.6,top_p=1,
                  transport={'kind':'openai','endpoint':endpoint,'timeout_seconds':100},
                  request_options={'chat_template_kwargs':{'enable_thinking':False},'response_format':{'type':'json_object'}},
                  calibration={k:v for k,v in cell.items() if k!='order_key'})
    config['identities']['model']='served-name:'+cell['model']
    config['identities']['task']=task['id']+':sha256:'+digest(task)
    system=SYSTEM+('\n'+REMINDER if cell['contract']=='certificate-only' else '')
    config['base_messages']=[{'role':'system','content':system},{'role':'user','content':task['statement']}]
    return config


def evaluate(task_id,candidate):
    return evaluate_scaling(candidate) if task_id==TASK['id'] else evaluate_control(task_id,candidate)


def run_case(root,cell,endpoint,quota,*,provider_options=None):
    rid=cell['case_id'];directory=root/rid;directory.mkdir(exist_ok=True)
    config=manifest(cell,endpoint);started=time.monotonic()
    if provider_options is not None:config['request_options']=provider_options
    with Store(directory/'journal.sqlite') as store:
        store.create_run(rid,config);store.enqueue_round(rid,0)
        if not STOP.is_set():
            claim=store.claim(rid,'calibration-supervisor',lease_seconds=150)
            if claim:
                if len(canonical(claim['request']).encode())>16384:
                    store.fail(claim['token'],{'category':'request_byte_budget'},retryable=False)
                else:
                    try:reserved=quota.reserve(claim['token'],rid,config['max_output_tokens'])
                    except ValueError:
                        store.fail(claim['token'],{'category':'experiment_budget'},retryable=False)
                    else:
                        if not reserved:raise ValueError('Reserved attempts cannot be dispatched twice')
                        parent=store.db.execute('SELECT started_event FROM attempts WHERE token=?',(claim['token'],)).fetchone()[0]
                        store.observe(rid,'reserved:'+claim['token'],'observation.budget_reserved',
                                      {'attempt_token':claim['token'],'output_cap':config['max_output_tokens']},parents=[parent])
                        wire=bounded_response(claim,config['transport'],quota.deadline)
                        response=wire.get('response',{})
                        if not isinstance(response,dict):wire={'error':{'category':'invalid_response_shape'}};response={}
                        quota.settle(claim['token'],{'usage':response.get('usage'),'error':wire.get('error')})
                        finish(store,claim,config,wire)
        status=store.status(rid)
        if status['complete']:
            selected=select_terminal(store,rid,config['selection_seed'])
            verdict=evaluate(cell['task_id'],selected['candidate'])
            store.observe(rid,'terminal.evaluation','observation.terminal_evaluation',verdict,parents=[selected['source_event']])
        else:selected=None;verdict={'status':'TECHNICAL_FAILURE','passed':False}
        result={'case':cell,'manifest_sha256':digest(config),'status':status,'selection':selected,
                'verdict':verdict,'verification':store.verify(rid),'elapsed_seconds':time.monotonic()-started}
        save(directory/'result.json',result)
        if not (directory/'export').exists():store.export(rid,directory/'export')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--local-root',required=True,type=Path)
    parser.add_argument('--output-root',required=True,type=Path)
    args=parser.parse_args();cfg=json.loads(args.config.read_text())
    root=args.local_root;output=args.output_root;root.mkdir(parents=True,exist_ok=True);output.mkdir(parents=True,exist_ok=True)
    lock=(root/'coordinator.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    frozen=root/'experiment.json'
    if frozen.exists() and json.loads(frozen.read_text())!=cfg:raise ValueError('Experiment changed')
    if not frozen.exists():save(frozen,cfg)
    cells=schedule(cfg)
    if len(cells)!=48 or sum(c['max_output_tokens'] for c in cells)!=61440:raise ValueError('Not the frozen 48-case design')
    save(root/'schedule.json',cells)
    runtime=root/'runtime.json'
    if not runtime.exists():save(runtime,{'deadline':time.time()+900,'started_at':time.time(),'job_id':os.environ.get('SLURM_JOB_ID')})
    meta=json.loads(runtime.read_text())
    quota=Quota(root/'quota.sqlite',calls=48,output_tokens=61440,deadline=meta['deadline'])
    signal.signal(signal.SIGTERM,lambda *_:STOP.set());signal.signal(signal.SIGINT,lambda *_:STOP.set())
    opener=request.build_opener(request.ProxyHandler({}),NoRedirect())
    headers={'Authorization':'Bearer '+os.environ['AIMETH_API_KEY']} if os.environ.get('AIMETH_API_KEY') else {}
    with opener.open(request.Request(cfg['endpoint'].removesuffix('/chat/completions')+'/models',headers=headers),timeout=10) as response:
        catalog=json.loads(response.read(262144))
    if not set(cfg['models'])<={m['id'] for m in catalog.get('data',[])}:raise ValueError('Frozen served IDs absent')
    results=[]
    for cell in cells:
        result_path=root/cell['case_id']/'result.json'
        if result_path.exists():results.append(json.loads(result_path.read_text()));continue
        if STOP.is_set() or time.time()>=quota.deadline:break
        result=run_case(root,cell,cfg['endpoint'],quota);results.append(result)
        durable=output/'records'/cell['case_id']
        if not durable.exists():shutil.copytree(result_path.parent,durable)
        save(output/'progress.json',{'completed_cases':len(results),'planned_cases':len(cells),'last':result['verdict'],'quota':quota.summary()})
        print(json.dumps({'done':len(results),'total':len(cells),'verdict':result['verdict']['status']}),flush=True)
    save(output/'summary-private.json',{'schema_version':'1.0','scope':'exploratory output-contract calibration; no population effect',
                                      'experiment':cfg,'metadata':meta,'planned_cases':len(cells),'unstarted_cases':len(cells)-len(results),
                                      'results':results,'quota':quota.summary()})
    quota.db.close()
    if not (output/'complete-record').exists():shutil.copytree(root,output/'complete-record')


if __name__=='__main__':main()
