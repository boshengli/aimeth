#!/usr/bin/env python3
"""One separately frozen, bounded operational diagnosis; never alter a service."""
import argparse
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import re
import sys
import time
from urllib import request,error
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aimeth_runtime.runner import NoRedirect
from aimeth_runtime.store import canonical


def child(endpoint,payload,pipe):
    key=os.environ['AIMETH_API_KEY']
    req=request.Request(endpoint,data=canonical(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key},method='POST')
    opener=request.build_opener(request.ProxyHandler({}),NoRedirect())
    try:
        with opener.open(req,timeout=15) as response:
            body=response.read(16385)
            if len(body)>16384:result={'error':'body_limit','http_status':response.status}
            else:result={'http_status':response.status,'response':json.loads(body)}
    except error.HTTPError as exc:
        body=exc.read(16384);status=exc.code;exc.close()
        text=body.decode('utf-8','replace').replace(key,'[CREDENTIAL_REDACTED]')
        text=re.sub(r'sk-[A-Za-z0-9_-]{8,}','[KEY_PATTERN_REDACTED]',text)
        result={'http_status':status,'error_body_restricted':text}
    except Exception as exc:result={'error':type(exc).__name__}
    pipe.send(result);pipe.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();cfg=json.loads(Path(args.config).read_text());root=Path(args.output)
    root.mkdir(parents=True,exist_ok=False)
    records=[]
    for index in range(2):
        payload={'model':'deepseek-v4-flash-0731','messages':[{'role':'user','content':'Return exactly one JSON object with status equal to ok.'}],
                 'max_tokens':32,'temperature':0}
        if index:payload.update(response_format={'type':'json_object'},chat_template_kwargs={'enable_thinking':False},top_p=1,seed=20260920)
        assert len(canonical(payload).encode())<=4096
        record={'index':index,'request':payload,'request_sha256':hashlib.sha256(canonical(payload).encode()).hexdigest(),
                'started_at':time.time(),'reserved_output_tokens':32,'source_commit':cfg['source_commit']}
        path=root/('attempt-'+str(index)+'.json');path.write_text(json.dumps(record,indent=2)+'\n')
        ctx=multiprocessing.get_context('spawn');reader,writer=ctx.Pipe(duplex=False)
        process=ctx.Process(target=child,args=(cfg['endpoint'],payload,writer));process.start();writer.close()
        try:
            result=reader.recv() if reader.poll(30) else {'error':'absolute_deadline','usage_unknown':True}
        finally:
            reader.close();process.join(timeout=.2)
            if process.is_alive():process.terminate();process.join(timeout=2)
            if process.is_alive():process.kill();process.join()
        record.update(result);record['finished_at']=time.time();path.write_text(json.dumps(record,indent=2)+'\n');records.append(record)
        if result.get('http_status')!=200:break
    public=[]
    for r in records:
        item={k:v for k,v in r.items() if k!='error_body_restricted'}
        if 'error_body_restricted' in r:
            body=r['error_body_restricted'];item['restricted_error_body_sha256']=hashlib.sha256(body.encode()).hexdigest()
            body=re.sub(r'\b(?:10\.(?:\d+\.){2}\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+)\b','[PRIVATE_ADDRESS]',body)
            item['sanitized_error_excerpt']=body[:1024]
        usage=item.get('response',{}).get('usage');item['known_total_tokens']=usage.get('total_tokens') if isinstance(usage,dict) else None
        public.append(item)
    summary={'schema_version':'1.0','scope':'operational diagnostic, not mathematical result','records':public,
             'requests':len(records),'reserved_output_tokens':32*len(records),
             'unknown_usage_attempts':sum(r['known_total_tokens'] is None for r in public)}
    (root/'public-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))

if __name__=='__main__':main()
