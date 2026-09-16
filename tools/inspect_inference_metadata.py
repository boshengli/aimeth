#!/usr/bin/env python3
"""Read only model metadata and selected inference arguments, never credentials."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
from urllib import request,error


def file_identity(path,limit=32*1024*1024):
    size=path.stat().st_size
    if size>limit:return {'bytes':size,'sha256':None,'reason':'metadata_read_limit'}
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return {'bytes':size,'sha256':h.hexdigest()}


def model_metadata(root):
    result={'path':str(root),'resolved_path':None,'files':{},'weights_content_verified':False}
    try:
        result['resolved_path']=str(root.resolve(strict=True))
        config=root/'config.json'
        if config.stat().st_size>2*1024*1024:raise ValueError('config read limit')
        data=json.loads(config.read_text())
        for key in ('model_type','architectures','torch_dtype','dtype','num_hidden_layers','hidden_size','vocab_size','max_position_embeddings','transformers_version','quantization_config'):
            if key in data:result[key]=data[key]
        for name in ('config.json','generation_config.json','tokenizer_config.json','tokenizer.json','chat_template.jinja','model.safetensors.index.json'):
            p=root/name
            if p.is_file():result['files'][name]=file_identity(p)
        shards=sorted(root.glob('*.safetensors'))
        result['weight_files']=[{'name':p.name,'bytes':p.stat().st_size} for p in shards]
        result['weight_bytes']=sum(p.stat().st_size for p in shards)
    except (OSError,ValueError) as exc:result['read_error']=type(exc).__name__
    return result


def processes():
    allowed={'--model','--model-path','--served-model-name','--port','--tensor-parallel-size','--tp','--ep','--max-model-len','--context-length'}
    found=[]
    for p in Path('/proc').glob('[0-9]*/cmdline'):
        try:args=p.read_bytes().decode().split('\0')
        except (OSError,UnicodeError):continue
        if not any('vllm' in a or 'sglang' in a for a in args[:6]):continue
        fields={}
        if 'serve' in args and args.index('serve')+1<len(args):fields['model_path']=args[args.index('serve')+1]
        for i,a in enumerate(args):
            if a in allowed and i+1<len(args):fields[a]=args[i+1]
            elif '=' in a and a.split('=',1)[0] in allowed:fields[a.split('=',1)[0]]=a.split('=',1)[1]
        if fields:found.append({'pid':int(p.parent.name),'selected_arguments':fields})
    return found


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models',nargs='+',type=Path,required=True)
    args=parser.parse_args()
    local=[]
    for port in (8000,30000):
        try:
            with request.build_opener(request.ProxyHandler({})).open(f'http://127.0.0.1:{port}/v1/models',timeout=2) as response:
                obj=json.loads(response.read(262144));local.append({'port':port,'http_status':response.status,'model_ids':[m['id'] for m in obj.get('data',[])]})
        except error.HTTPError as exc:local.append({'port':port,'http_status':exc.code});exc.close()
        except (OSError,ValueError) as exc:local.append({'port':port,'error':type(exc).__name__})
    print(json.dumps({'schema_version':'1.0','observed_at':datetime.now(timezone.utc).isoformat(),'node':socket.gethostname(),
                      'scope':'read-only metadata inventory; no model load, weight-content hash or GPU probe',
                      'processes':processes(),'local_service_reads':local,'stored_models':[model_metadata(p) for p in args.models]},indent=2))


if __name__=='__main__':main()
