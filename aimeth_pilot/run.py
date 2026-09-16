"""One supervised, bounded cluster client job; inference uses existing services."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import signal
import shutil
import socket
import sqlite3
import time
import threading
from urllib import request

from aimeth_runtime.store import Store, canonical, digest
from aimeth_runtime.runner import http_response, TransportFailure, NoRedirect
from aimeth_design.organizations import compile_arm, pilot_schedule
from aimeth_design.execution import select_terminal
from aimeth_evaluation.controls import public_tasks, evaluate
from .quota import Quota

STOP=threading.Event()


def save(path, value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    temporary.replace(path)


def call_child(claim, transport, pipe):
    try:
        response=http_response(claim,transport)
        pipe.send({'response':response})
    except TransportFailure as exc:
        pipe.send({'error':exc.details})
    except Exception as exc:
        pipe.send({'error':{'category':type(exc).__name__}})
    finally:pipe.close()


def bounded_response(claim,transport,deadline):
    if STOP.is_set():return {'error':{'category':'coordinator_stop'}}
    context=multiprocessing.get_context('spawn')
    reader,writer=context.Pipe(duplex=False)
    process=context.Process(target=call_child,args=(claim,transport,writer))
    process.start();writer.close()
    try:
        limit=min(time.time()+120,deadline)
        while time.time()<limit and not STOP.is_set():
            if reader.poll(min(0.2,max(0,limit-time.time()))):
                try:return reader.recv()
                except EOFError:return {'error':{'category':'child_exit_without_receipt'}}
        return {'error':{'category':'coordinator_stop' if STOP.is_set() else 'absolute_request_deadline'}}
    finally:
        reader.close()
        process.join(timeout=0.2)
        if process.is_alive():process.terminate();process.join(timeout=2)
        if process.is_alive():process.kill();process.join()


def finish(store,claim,config,wire):
    if 'error' in wire:
        store.fail(claim['token'],wire['error'],retryable=False);return
    response=wire['response']
    try:content=response['choices'][0]['message']['content']
    except (KeyError,IndexError,TypeError):content=None
    peer={'candidate_excerpt':content[:config['max_message_chars']-128] if isinstance(content,str) else None,
          'proof_verification_status':'unverified'}
    while len(canonical(peer))>config['max_message_chars'] and peer['candidate_excerpt']:
        peer['candidate_excerpt']=peer['candidate_excerpt'][:len(peer['candidate_excerpt'])//2]
    outgoing=[{'recipient':b,'target_round':claim['round_index']+1,'content':peer}
              for a,b in config['round_edges'][str(claim['round_index'])] if a==claim['agent_id']]
    store.complete(claim['token'],response,{'candidate':content,'proof_verification_status':'unverified'},outgoing)


def run_population(root,run_id,config,quota,task_id):
    task=next((t for t in public_tasks() if t['id']==task_id),None)
    if task is None or config['identities']['task'] != task_id+':sha256:'+digest(task):
        raise ValueError('Evaluator task does not match the frozen generator task')
    directory=root/run_id;directory.mkdir(exist_ok=True)
    started=time.monotonic()
    with Store(directory/'journal.sqlite') as store:
        store.create_run(run_id,config)
        with ThreadPoolExecutor(max_workers=config['max_inflight']) as pool:
            for r in range(config['rounds']):
                if time.time()>=quota.deadline:break
                if r and store.db.execute('SELECT COUNT(*) FROM steps WHERE round_index=? AND status!=?',(r-1,'succeeded')).fetchone()[0]:break
                store.enqueue_round(run_id,r)
                active={}; halted=False
                while True:
                    if STOP.is_set():halted=True
                    while not halted and len(active)<config['max_inflight']:
                        claim=store.claim(run_id,'supervised-pilot',lease_seconds=150)
                        if claim is None:break
                        if len(canonical(claim['request']).encode())>16384:
                            store.fail(claim['token'],{'category':'request_byte_budget'},retryable=False);halted=True;break
                        try:reserved=quota.reserve(claim['token'],run_id,config['max_output_tokens'])
                        except ValueError:
                            store.fail(claim['token'],{'category':'experiment_budget'},retryable=False);halted=True;break
                        if not reserved:
                            raise ValueError('Cannot re-dispatch an already reserved attempt')
                        store.observe(run_id,'reserved:'+claim['token'],'observation.budget_reserved',
                                      {'attempt_token':claim['token'],'output_cap':config['max_output_tokens'],
                                       'request_bytes':len(canonical(claim['request']).encode())},parents=[store.db.execute('SELECT started_event FROM attempts WHERE token=?',(claim['token'],)).fetchone()[0]])
                        active[pool.submit(bounded_response,claim,config['transport'],quota.deadline)]=claim
                    done=[future for future in active if future.done()]
                    for future in done:
                        claim=active.pop(future)
                        try:wire=future.result()
                        except Exception as exc:wire={'error':{'category':type(exc).__name__}}
                        response=wire.get('response',{})
                        quota.settle(claim['token'],{'usage':response.get('usage'), 'error':wire.get('error')})
                        finish(store,claim,config,wire)
                    if not active:
                        # A completed batch may still leave unclaimed work. Refill
                        # once more; exit only after admission itself found none.
                        if halted or not done:break
                        continue
                    time.sleep(0.02)
                if halted:break
        status=store.status(run_id)
        if status['complete']:
            selected=select_terminal(store,run_id,config['selection_seed'])
            verdict=evaluate(task_id,selected['candidate'])
            parent=selected['source_event']
            store.observe(run_id,'terminal.evaluation','observation.terminal_evaluation',verdict,parents=[parent])
        else:selected=None;verdict={'status':'TECHNICAL_FAILURE','passed':False}
        result={'run_id':run_id,'arm':config['organization']['arm'],'model':config['model_name'],
                'task_id':task_id,'manifest_sha256':digest(config),'status':status,
                'selection':selected,'verdict':verdict,'verification':store.verify(run_id),
                'elapsed_seconds':time.monotonic()-started}
        save(directory/'result.json',result)
        if not (directory/'export').exists():store.export(run_id,directory/'export')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--local-root',required=True)
    parser.add_argument('--output-root',required=True)
    args=parser.parse_args()
    cfg=json.loads(Path(args.config).read_text())
    root=Path(args.local_root);root.mkdir(parents=True,exist_ok=True)
    output=Path(args.output_root);output.mkdir(parents=True,exist_ok=True)
    lock=(root/'coordinator.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    frozen=root/'experiment.json'
    if frozen.exists() and json.loads(frozen.read_text())!=cfg:raise ValueError('Experiment changed')
    if not frozen.exists():save(frozen,cfg)
    runtime=root/'runtime.json'
    if runtime.exists():metadata=json.loads(runtime.read_text())
    else:
        metadata={'deadline':time.time()+cfg['wall_seconds'],'started_at':time.time(),
                  'hostname':socket.gethostname(),'job_id':os.environ.get('SLURM_JOB_ID')}
        save(runtime,metadata)
    quota=Quota(root/'quota.sqlite',calls=cfg['calls_cap'],output_tokens=cfg['output_cap'],deadline=metadata['deadline'])
    stop=False
    def stop_handler(signum,frame):
        nonlocal stop
        stop=True
        STOP.set()
    signal.signal(signal.SIGTERM,stop_handler);signal.signal(signal.SIGINT,stop_handler)
    catalog_url=cfg['endpoint'].removesuffix('/chat/completions')+'/models'
    headers={}
    if os.environ.get('AIMETH_API_KEY'):headers['Authorization']='Bearer '+os.environ['AIMETH_API_KEY']
    opener=request.build_opener(request.ProxyHandler({}),NoRedirect())
    with opener.open(request.Request(catalog_url,headers=headers),timeout=10) as response:
        catalog=json.loads(response.read(262144))
    served={item['id'] for item in catalog.get('data',[])}
    if not set(cfg['models'])<=served:raise ValueError('Frozen model IDs are absent from cluster catalog')
    save(output/'model-catalog.json',{'served_ids':sorted(served),'observed_at':time.time()})
    tasks={task['id']:task for task in public_tasks()}
    results=[]
    # Freeze task/repetition blocks, then randomize model order within each block.
    schedule=pilot_schedule(cfg['tasks'],cfg['repeats'],cfg['seed'])
    planned=[]
    for block in schedule['blocks']:
        for model in sorted(cfg['models'],key=lambda m:digest([block['block_id'],m])):
            for arm in block['arm_order']:
                planned.append((block,model,arm))
    save(root/'schedule.json',{'planned_population_runs':len(planned),'blocks':schedule})
    for block,model,arm in planned:
        run_id=block['block_id']+'-'+hashlib.sha256(model.encode()).hexdigest()[:8]+'-'+arm
        result_path=root/run_id/'result.json'
        if result_path.exists():results.append(json.loads(result_path.read_text()));continue
        if stop or time.time()>=quota.deadline:break
        config=compile_arm(arm,population=cfg['population'],rounds=cfg['rounds'],group_size=4,
                           seed=block['seed'],output_tokens=cfg['max_output_tokens'],concurrency=cfg['concurrency'],task=tasks[block['task_id']])
        config['transport']={'kind':'openai','endpoint':cfg['endpoint'],'timeout_seconds':100}
        config['organization']['evidence_scope']='public-development live calibration; no confirmatory effect estimate'
        config['model_name']=model;config['identities']['model']='served-name:'+model
        config['max_attempts']=1;config['temperature']=0.6
        config['selection_seed']=block['selection_seed'];config['request_options']=cfg['request_options']
        result=run_population(root,run_id,config,quota,block['task_id']);results.append(result)
        durable=output/'records'/run_id
        if not durable.exists():shutil.copytree(root/run_id,durable)
        save(output/'progress.json',{'completed_populations':len(results),'planned_populations':len(planned),
                                    'last':{k:result[k] for k in ('model','arm','task_id','verdict')},'quota':quota.summary()})
        print(json.dumps({'done':len(results),'total':len(planned),'model':model,'arm':arm,'verdict':result['verdict']['status']}),flush=True)
    summary={'schema_version':'1.0','scope':'public-development live calibration; no frontier/confirmatory claim',
             'metadata':metadata,'experiment':cfg,'results':results,'planned_populations':len(planned),
             'unstarted_populations':len(planned)-len(results),'quota':quota.summary(),
             'frontier_proof_verified':False,'weights_independently_attested':False}
    save(output/'summary-private.json',summary)
    quota.db.close()
    # The journal lives on node-local storage while open; export only after writers stop.
    if not (output/'complete-record').exists():shutil.copytree(root,output/'complete-record')
    print(json.dumps({'finished':True,'completed':len(results),'unstarted':summary['unstarted_populations']}),flush=True)

if __name__=='__main__':main()
