#!/usr/bin/env python3
"""Build M2.2 from archived institutional evidence and separate scale validation."""
import argparse
from collections import Counter
import hashlib
from html import escape as esc
import json
from pathlib import Path
from build_service_milestone import graph,table,tr
ROOT=Path(__file__).resolve().parents[1]
NAME='m2-2-role-routing-v1'
LABEL={'VERIFIED_WITHIN_SCOPE':'通过','INVALID_CERTIFICATE':'错误','MALFORMED':'格式不合规','TECHNICAL_FAILURE':'未完成'}
TASK={'prime-counterexample':'素数反例','ns-scaling-algebra-v1':'NS 缩放代数','integral-rational':'反导数'}

def read(p):return json.loads((ROOT/p).read_text())
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def pre(value):return '<pre>'+esc(value).replace(' ','&#32;').replace('\t','&#9;')+'</pre>'

def build():
    s=read('reports/role-pilot-v1/summary.json');scale=read('reports/role-pilot-v1/scale-validation.json')
    validation=read('reports/role-pilot-v1/validation.json');probe=read('reports/role-pilot-v1/gateway-diagnostic.json')
    assert s['phases']['population']['verdicts']=={'MALFORMED':4,'TECHNICAL_FAILURE':2,'INVALID_CERTIFICATE':1,'VERIFIED_WITHIN_SCOPE':1}
    assert s['phases']['population']['accepted_envelope_diagnostics']=={'valid':121,'envelope_keys':80,'justification_limit':4,'invalid_dependency_reference':1}
    assert sum(x['known_total_tokens'] for x in s['budgets'].values())==195352
    assert sum(x['reserved_calls'] for x in s['budgets'].values())==224
    assert len(s['results'])==24 and len(s['unstarted'])==8
    for name in ('role-pilot-v1','role-prompt-storage-v2','gateway-diagnostic-v1'):
        archive=read('archives/'+name+'/source.json')
        for f in archive['files']:assert sha('archives/'+name+'/'+f['path'])==f['sha256']
    rows=[]
    for model in s['experiment']['models']:
        for representation in ('minimal-certificate','role-envelope'):
            subset=[r for r in s['results'] if r['case']['phase']=='representation' and r['case']['model']==model and r['case']['representation']==representation]
            count=Counter(r['verdict']['status'] for r in subset)
            rows.append(tr(['GLM' if model.startswith('glm') else 'DeepSeek','最小证书' if representation=='minimal-certificate' else '角色消息格式',*[count[k] for k in LABEL],sum(r['valid_envelopes'] for r in subset) if representation=='role-envelope' else '不适用']))
    diagnostic_table=table(['院内服务','表示方式','通过','错误','格式','未完成','消息格式合规'],rows,'diagnostic')
    rows=[]
    for arm in ('H','F'):
        subset=[r for r in s['results'] if r['case']['phase']=='population' and r['case']['arm']==arm]
        count=Counter(r['verdict']['status'] for r in subset)
        rows.append(tr([arm,*[count[k] for k in LABEL],sum(r['dispatched_requests'] for r in subset),sum(r['metrics']['usage']['total_tokens'] for r in subset)]))
    comparison=table(['GLM 组别','通过','错误','格式','未完成','实际请求','已报告 tokens'],rows,'comparison')
    rows=[]
    for result in s['results']:
        c=result['case']
        if c['phase']!='population':continue
        selection=result['selection'];candidate=selection['candidate'] if selection else None
        detail='<details><summary>候选与证据</summary><code>'+c['case_id']+'</code>'+pre(candidate if isinstance(candidate,str) else '无合规的终末候选；完整原始回答保存在事件记录中。')+'</details>'
        rows.append(tr(['GLM',c['arm'],TASK[c['task_id']],c['repetition']+1,LABEL[result['verdict']['status']],result['dispatched_requests'],str(result['valid_envelopes'])+' / '+str(result['status']['checkpoints']),detail],f'data-model="glm" data-arm="{c["arm"]}"'))
    for item in s['unstarted']:
        c=item['case'];rows.append(tr(['DeepSeek',c['arm'],TASK[c['task_id']],c['repetition']+1,'未启动',0,'不适用','校准 502 → 未通过格式门槛'],f'data-model="deepseek" data-arm="{c["arm"]}"'))
    population_table=table(['服务','组别','任务','重复','结果','请求数','合规步骤 / 已保存步骤','候选'],rows,'runs')
    rows=[]
    for r in s['results']:
        c=r['case']
        if c['phase']!='representation':continue
        candidate=r['selection']['candidate'] if r['selection'] else 'HTTP 502；没有模型候选。'
        rows.append(tr(['GLM' if c['model'].startswith('glm') else 'DeepSeek',TASK[c['task_id']],c['representation'],c['repetition']+1,LABEL[r['verdict']['status']],pre(candidate if candidate is not None else '消息格式不合规，未提取候选。')]))
    all_diagnostics=table(['服务','任务','表示','重复','结果','提取候选（无修复）'],rows)
    rows=[]
    for r in scale['measurements']:
        if r['arm']=='H':rows.append(tr([f'{r["population"]:,}',r['role_templates'],f'{r["manifest_event_bytes"]:,}',f'{r["call_slots"]:,}',f'{r["planned_messages"]:,}',0]))
    scales=table(['逻辑 Agent','角色模板','配置事件 bytes','4 轮调用槽位','计划消息','实际推理请求'],rows,'scale-table')
    files=['reports/role-pilot-v1/summary.json','reports/role-pilot-v1/events.jsonl','reports/role-pilot-v1/gateway-diagnostic.json','reports/role-pilot-v1/scale-validation.json','reports/role-pilot-v1/validation.json','docs/role-routing-pilot-v1.md','docs/gateway-diagnostic-v1.md','docs/role-prompt-storage-v2.md']
    evidence={'schema_version':'1.0','milestone':'M2.2','date':'2026-09-20','version':'1.0',
              'scope':'Executed H/F pilot with predeclared model gate; separate gateway diagnosis and post-pilot compact manifest validation',
              'validation':validation,'phases':s['phases'],'gates':s['gates'],
              'all_new_requests_including_operational_probe':225,'known_total_tokens':195352,'unknown_usage_attempts':9,
              'input_hashes':{p:sha(p) for p in files},
              'delivery_identity':'Git commit containing this report; distinct from the three recorded source commits',
              'limits':['No architecture-superiority conclusion','No frontier proof','GPU01 mapping user-reported, not independently attested','10K compilation only, no live 10K inference','Input byte admission is not a tokenizer-derived token cap']}
    values={'DIAGNOSTIC_TABLE':diagnostic_table,'COMPARISON':comparison,'POPULATIONS':population_table,
            'ALL_DIAGNOSTICS':all_diagnostics,'SCALE_TABLE':scales,
            'GRAPH_H':graph('H',read('examples/hierarchy-routing-proposal-v1.json')),
            'GRAPH_F':graph('F',read('examples/hierarchy-routing-proposal-v1.json')),
            'EVIDENCE':esc(json.dumps(evidence,ensure_ascii=False,indent=2))}
    html=(ROOT/'templates/role-milestone-v1.html').read_text()
    for key,value in values.items():html=html.replace('@@'+key+'@@',value)
    assert '@@' not in html
    return html,evidence


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'milestones'/f'{NAME}.html');p.add_argument('--evidence-output',type=Path)
    args=p.parse_args();html,evidence=build();args.output.write_text(html)
    if args.evidence_output:args.evidence_output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'built','report':str(args.output),'planned_populations':16,'started_populations':8}))

if __name__=='__main__':main()
