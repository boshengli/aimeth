#!/usr/bin/env python3
"""Rebuild the M2.3 calibration report from separately archived batches."""
import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import sys
from build_service_milestone import table,tr
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'archives/role-contract-v2'))
from aimeth_pilot.role_contract import OUTPUT_CARD

def read(p):return json.loads((ROOT/p).read_text())
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def pre(v):return '<pre>'+escape(str(v)).replace(' ','&#32;').replace('\t','&#9;')+'</pre>'
CONTRACT={'baseline':'原提示','output-card':'输出卡'}
TASK={'prime-counterexample':'素数反例','ns-scaling-algebra-v1':'NS 缩放代数'}
CONTEXT={'empty':'空上下文','recorded':'已记录上下文'}
VERDICT={'VERIFIED_WITHIN_SCOPE':'数学通过','INVALID_CERTIFICATE':'数学错误','MALFORMED':'格式失败','TECHNICAL_FAILURE':'技术未完成'}

def build():
    a=read('reports/role-contract-v1/summary.json');b=read('reports/role-contract-v2/summary.json')
    assert (len(a['results']),len(a['unstarted']),len(b['results']),len(b['unstarted']))==(2,128,64,0)
    assert (a['aggregates']['known_tokens'],b['aggregates']['known_tokens'])==(55,59122)
    assert b['aggregates']['paired_format_outcomes']=={'both_valid':11,'card_only_valid':14,'neither_valid':3,'baseline_only_valid':4}
    groups=b['aggregates']['groups']
    rows=[]
    for contract in ('baseline','output-card'):
        r=next(x for x in groups if x['dimensions']=={'model':'glm-5.3-flash','contract':contract})
        assert r['format_valid']==(15 if contract=='baseline' else 25)
        rows.append(tr([CONTRACT[contract],r['started'],r['format_valid'],r['malformed'],r['technical'],r['math_passed'],f'{r["known_tokens"]:,}']))
    summary=table(['提示','实际请求','格式合格','格式失败','技术未完成','数学通过','已报告 tokens'],rows,'comparison')
    def strata(dimensions,headers,id):
        rows=[]
        for r in groups:
            d=r['dimensions']
            if set(d)!={'model','contract',*dimensions}:continue
            labels=[TASK.get(d[k],CONTEXT.get(d[k],d[k])) for k in dimensions]
            rows.append(tr([*labels,CONTRACT[d['contract']],r['planned'],r['format_valid'],r['math_passed']]))
        return table([*headers,'提示','请求','格式合格','数学通过'],rows,id)
    rows=[]
    for r in b['results']:
        c=r['case'];candidate=r['selection']['candidate'] if r['selection'] else None
        detail='<details><summary>候选与来源</summary><code>'+c['case_id']+'</code>'+pre(candidate if candidate else '没有可提取的合规候选；原始回答保存在事件中。')+'</details>'
        rows.append(tr([CONTRACT[c['contract']],c['role'],CONTEXT[c['context']],TASK[c['task_id']],c['repetition']+1,
                        VERDICT[r['verdict']['status']],r['metrics']['usage'].get('total_tokens','未知'),detail],
                       f'data-contract="{c["contract"]}" data-role="{c["role"]}" data-context="{c["context"]}"'))
    cases=table(['提示','角色','上下文','任务','重复','结果','tokens','候选'],rows,'cases')
    probes=table(['模型','结果','已知 tokens','未知用量'],[tr([r['case']['model'],'HTTP 502' if r['errors'] else '32-token 输出截断',r['metrics']['usage'].get('total_tokens','未知'),r['metrics']['unknown_usage_attempts']]) for r in a['results']],'probes')
    rows=[]
    for u in a['unstarted']:
        c=u['case'];rows.append(tr([c['model'],c['role'],CONTEXT[c['context']],TASK[c['task_id']],CONTRACT[c['contract']],c['repetition']+1,'未启动',c['case_id']]))
    skipped=table(['模型','角色','上下文','任务','提示','重复','状态','运行 ID'],rows,'unstarted')
    inputs=['reports/role-contract-v1/summary.json','reports/role-contract-v1/events.jsonl','reports/role-contract-v2/summary.json','reports/role-contract-v2/events.jsonl','reports/role-contract-v2/validation.json','examples/role-contract-contexts-v1.json','docs/role-contract-calibration-v1.md','docs/role-contract-calibration-v2.md']
    evidence={'schema_version':'1.0','milestone':'M2.3','date':'2026-09-24','version':'1.0',
              'batches':{v:{'source':read('archives/role-contract-'+v+'/source.json')['source_commit'],
                           'started':len(s['results']),'unstarted':len(s['unstarted']),'aggregates':s['aggregates']} for v,s in [('v1',a),('v2',b)]},
              'input_hashes':{p:sha(p) for p in inputs},'validation':read('reports/role-contract-v2/validation.json'),
              'scope':'Developmental one-step frozen-context format calibration; no population or frontier proof',
              'delivery_identity':'Git commit containing this report; distinct from both execution sources'}
    values={'SUMMARY':summary,'ROLES':strata(['role'],['角色'],'roles'),'CONTEXTS':strata(['context'],['上下文'],'contexts'),
            'TASKS':strata(['task_id'],['任务'],'tasks'),'CROSS':strata(['role','context'],['角色','上下文'],'cross'),
            'CASES':cases,'PROBES':probes,'UNSTARTED':skipped,'CARD':pre(OUTPUT_CARD),'EVIDENCE':escape(json.dumps(evidence,ensure_ascii=False,indent=2))}
    html=(ROOT/'templates/contract-milestone-v1.html').read_text()
    for k,v in values.items():html=html.replace('@@'+k+'@@',v)
    assert '@@' not in html
    return html,evidence

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'milestones/m2-3-role-contract-v1.html');p.add_argument('--evidence-output',type=Path)
    args=p.parse_args();html,evidence=build();args.output.write_text(html)
    if args.evidence_output:args.evidence_output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'built','formal_cases':64,'preserved_unstarted':128}))
