#!/usr/bin/env python3
"""Build the offline M2.1d report from frozen evidence; never call a model."""
import argparse
from collections import Counter
import hashlib
from html import escape as esc
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NAME='m2-1-service-calibration-v1'
LABELS={'VERIFIED_WITHIN_SCOPE':'通过','INVALID_CERTIFICATE':'错误','MALFORMED':'格式不合规','TRUNCATED_GENERATION':'截断'}
SHORT={'deepseek-v4-flash-0731':'院内 DeepSeek','glm-5.3-flash':'院内 GLM'}
TASK={'integral-rational':'反导数证书','prime-counterexample':'素数反例','ns-scaling-algebra-v1':'NS 缩放代数'}

def read(p):return json.loads((ROOT/p).read_text())
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def tr(values,attributes=''):return '<tr '+attributes+'>'+''.join('<td>'+str(v)+'</td>' for v in values)+'</tr>'
def table(head,rows,ident=''):
    return '<div class="table-wrap"><table'+(' id="'+ident+'"' if ident else '')+'><thead><tr>'+''.join('<th scope="col">'+x+'</th>' for x in head)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'

def graph(arm,data):
    positions={'E0':(65,65),'E1':(295,65),'C':(180,150),'S':(180,270)}
    roles={'E0':'探索者','E1':'探索者','C':'批评者','S':'综合者'}
    edges=data['graphs'][arm];out=[f'<svg viewBox="0 0 360 335" role="img" aria-label="{arm} 信息路由图"><defs><marker id="arrow-{arm}" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0 0 L0 6 L7 3 Z" fill="#19786f"/></marker></defs>']
    for a,b in edges:
        x,y=positions[a];xx,yy=positions[b];d=math.hypot(xx-x,yy-y);ux=(xx-x)/d;uy=(yy-y)/d
        start=(x+ux*30,y+uy*30);end=(xx-ux*34,yy-uy*34)
        if [b,a] in edges:
            mid=((x+xx)/2-uy*34,(y+yy)/2+ux*34)
            path=f'M{start[0]:.2f},{start[1]:.2f} Q{mid[0]:.2f},{mid[1]:.2f} {end[0]:.2f},{end[1]:.2f}'
        else:path=f'M{start[0]:.2f},{start[1]:.2f} L{end[0]:.2f},{end[1]:.2f}'
        out.append(f'<path d="{path}" fill="none" stroke="#19786f" stroke-width="2" marker-end="url(#arrow-{arm})"/>')
    for node,(x,y) in positions.items():
        lx,ly,anchor=(x,y-36,'middle') if node=='C' else (x,y+46,'middle')
        out.append(f'<circle cx="{x}" cy="{y}" r="27" fill="#eff8f3" stroke="#19786f"/><text x="{x}" y="{y+5}" text-anchor="middle" font-size="15" fill="#12332f">{node}</text><text x="{lx}" y="{ly}" text-anchor="{anchor}" font-size="12" fill="#556761">{roles[node]}</text>')
    return ''.join(out)+'</svg>'

def build():
    s=read('reports/service-calibration-v1/summary.json');p=read('reports/public-sanity-v1/summary.json')
    inv=read('reports/service-calibration-v1/inventory.json');g=read('examples/hierarchy-routing-proposal-v1.json')
    validation=read('reports/service-calibration-v1/validation.json')
    assert len(s['results'])==48 and len(p['results'])==8
    assert s['diagnostic_counts']=={'VERIFIED_WITHIN_SCOPE':18,'INVALID_CERTIFICATE':21,'MALFORMED':8,'TRUNCATED_GENERATION':1}
    assert p['verdict_counts']=={'VERIFIED_WITHIN_SCOPE':2,'INVALID_CERTIFICATE':6}
    for label in ('service-calibration-v1','public-sanity-v1'):
        archive=read('archives/'+label+'/source.json')
        for f in archive['files']:
            assert sha('archives/'+label+'/'+f['path'])==f['sha256']
    factors=[]
    for model in s['experiment']['models']:
        for contract in ('original','certificate-only'):
            for cap in (512,2048):
                subset=[r for r in s['results'] if (r['case']['model'],r['case']['contract'],r['case']['max_output_tokens'])==(model,contract,cap)]
                counts=Counter(r['diagnostic'] for r in subset)
                factors.append(tr([SHORT[model],'原提示' if contract=='original' else '格式提醒',cap,*[counts[k] for k in LABELS],len(subset)]))
    factor_table=table(['服务名称','提示','输出上限','通过','错误','格式','截断','总数'],factors,'factors')
    taskrows=[]
    for task in TASK:
        counts=Counter(r['diagnostic'] for r in s['results'] if r['case']['task_id']==task)
        taskrows.append(tr([TASK[task],*[counts[k] for k in LABELS],sum(counts.values())]))
    task_table=table(['开发题','通过','错误','格式','截断','总数'],taskrows)
    rows=[]
    for r in s['results']:
        c=r['case'];v=r['diagnostic'];candidate=r['selection']['candidate'] if r['selection'] else '无终末候选；原始截断回执见事件记录。'
        detail='<details><summary>候选与编号</summary><code>'+esc(c['case_id'])+'</code><pre>'+esc(candidate).replace(' ','&#32;').replace('\t','&#9;')+'</pre></details>'
        rows.append(tr([SHORT[c['model']],TASK[c['task_id']],'原提示' if c['contract']=='original' else '格式提醒',c['max_output_tokens'],c['repetition']+1,LABELS[v],r['usage'].get('total_tokens','未知'),detail],f'data-model="{c["model"]}" data-task="{c["task_id"]}"'))
    cases=table(['服务','任务','提示','上限','重复','结果','tokens','原始候选'],rows,'runs')
    prows=[]
    for r in p['results']:
        c=r['case'];prows.append(tr([c['provider'],esc(c['model']),'原提示' if c['contract']=='original' else '格式提醒',c['repetition']+1,LABELS[r['verdict']['status']],'<code>'+esc(r['selection']['candidate'])+'</code>']))
    public_table=table(['提供方','请求模型名','提示','重复','结果','完整候选'],prows,'public-cases')
    irows=[]
    for m in inv['models']:
        irows.append(tr([esc(m['directory_label']),esc(m['model_type']),f'{m["weight_bytes"]/1e9:.2f} GB',m['weight_shards'],'gpu08 进程引用' if m['active_process_observed'] else '仅见存储配置','<code>'+m['files']['config.json']['sha256'][:16]+'…</code>']))
    inventory_table=table(['目录标签（非权重认证）','config.model_type','权重文件总大小','分片数','本次证据','config SHA-256'],irows)
    provenance={
        'schema_version':'1.0','milestone':'M2.1d','date':'2026-09-16','version':'1.0',
        'scope':'Service metadata, 48 institutional one-step cases, 8 post-observation public sanity cases, H/F design proposal',
        'execution_sources':{label:read('archives/'+label+'/source.json')['source_commit'] for label in ('service-calibration-v1','public-sanity-v1')},
        'counts':{'institutional_cases':48,'institutional_tokens':s['usage'],'institutional_verdicts':s['diagnostic_counts'],'public_cases':8,'public_tokens':p['usage'],'public_verdicts':p['verdict_counts']},
        'validation':validation,
        'input_hashes':{path:sha(path) for path in ['reports/service-calibration-v1/summary.json','reports/service-calibration-v1/events.jsonl','reports/service-calibration-v1/inventory.json','reports/service-calibration-v1/validation.json','reports/public-sanity-v1/summary.json','reports/public-sanity-v1/events.jsonl','examples/hierarchy-routing-proposal-v1.json','docs/service-calibration-v1.md','docs/public-sanity-v1.md','docs/hierarchy-routing-proposal-v1.md']},
        'limitations':['Served names and file metadata do not attest weight bytes or gateway routes','Single-step calibration is not a population comparison','Public providers use different model identities and were tested post-observation','Scaling algebra is not a PDE theorem proof','No input-token admission, GPU-hour attribution or demonstrated multi-host failover'],
        'delivery_identity':'The Git commit containing this report is its delivery identity, separate from execution source commits. Final hosted CI is recorded in the control handoff.'}
    substitutions={'FACTOR_TABLE':factor_table,'TASK_TABLE':task_table,'CASE_TABLE':cases,'PUBLIC_TABLE':public_table,'INVENTORY_TABLE':inventory_table,'GRAPH_H':graph('H',g),'GRAPH_F':graph('F',g),'EVIDENCE':esc(json.dumps(provenance,ensure_ascii=False,indent=2))}
    html=(ROOT/'templates/service-milestone-v1.html').read_text()
    for key,value in substitutions.items():html=html.replace('@@'+key+'@@',value)
    assert '@@' not in html
    return html,provenance


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'milestones'/f'{NAME}.html')
    parser.add_argument('--evidence-output',type=Path)
    args=parser.parse_args();html,provenance=build();args.output.write_text(html)
    if args.evidence_output:args.evidence_output.write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'built','output':str(args.output),'institutional_cases':48,'public_cases':8}))

if __name__=='__main__':main()
