#!/usr/bin/env python3
"""Build the offline cluster report from frozen public evidence."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NAME='m2-1-cluster-pilot-v1'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'milestones'/f'{NAME}.html')
    args=parser.parse_args()
    evidence=json.loads((ROOT/'milestones'/f'{NAME}.evidence.json').read_text())
    data=json.loads((ROOT/'reports/cluster-pilot-v1/v3/summary.json').read_text())
    results=data['results'];verdicts=Counter(r['verdict']['status'] for r in results)
    labels={'VERIFIED_WITHIN_SCOPE':'证书通过','INVALID_CERTIFICATE':'证书错误','MALFORMED':'格式不合规','TECHNICAL_FAILURE':'未完成群体'}
    esc=lambda v:html.escape(str(v))
    rows=[]
    for model in data['experiment']['models']:
        for arm in 'SILX':
            records=[r for r in results if r['model']==model and r['arm']==arm]
            c=Counter(r['verdict']['status'] for r in records)
            values=[model,arm,len(records),c['VERIFIED_WITHIN_SCOPE'],c['INVALID_CERTIFICATE'],c['MALFORMED'],c['TECHNICAL_FAILURE'],sum(r['usage'].get('total_tokens',0) for r in records)]
            rows.append('<tr>'+''.join(f'<td>{esc(x)}</td>' for x in values)+'</tr>')
    runrows=[]
    for r in results:
        runrows.append(f'<tr data-model="{esc(r["model"])}" data-task="{esc(r["task_id"])}"><td><code>{esc(r["run_id"])}</code></td><td>{esc(r["model"])}</td><td>{esc(r["arm"])}</td><td>{esc(r["task_id"])}</td><td>{r["status"]["attempts"]}/16</td><td>{esc(labels[r["verdict"]["status"]])}</td><td>{r["usage"].get("total_tokens",0):,}</td></tr>')
    cases=[]
    for state in ['VERIFIED_WITHIN_SCOPE','INVALID_CERTIFICATE','MALFORMED']:
        r=next((r for r in results if r['verdict']['status']==state),None)
        if r:
            cases.append(f'<details><summary>{esc(labels[state])} · {esc(r["task_id"])} · {esc(r["arm"])}</summary><p>按执行顺序取本类别第一例，仅供解释。{esc(r["run_id"])}。</p><pre>{esc(r["selection"]["candidate"])}</pre></details>')
    values={'COUNTS':f'{verdicts["VERIFIED_WITHIN_SCOPE"]} 通过 · {verdicts["INVALID_CERTIFICATE"]} 错误 · {verdicts["MALFORMED"]} 格式不合规 · {verdicts["TECHNICAL_FAILURE"]} 未完成',
            'CALLS':str(data['quota']['reserved_calls']),'TOKENS':f'{data["usage"]["total_tokens"]:,}',
            'COMPLETED':str(sum(r['status']['complete'] for r in results)),
            'ROWS':'\n'.join(rows),'RUNROWS':'\n'.join(runrows),'CASES':'\n'.join(cases),
            'LENGTH':str(data['finish_reasons'].get('length',0)),
            'EVIDENCE':esc(json.dumps(evidence,ensure_ascii=False,indent=2)),
            'DATA':json.dumps(results,ensure_ascii=False).replace('<','\\u003c'),
            'COMMIT':esc(data['experiment']['client_code_commit']),
            'EVENTS':str(sum(r['verification']['events'] for r in results)),
            'DURATION':esc(evidence['final_job']['elapsed']),
            'MESSAGES':str(sum(r['event_kinds'].get('message.sent',0) for r in results))}
    template=(ROOT/'templates/cluster-pilot-v1.html').read_text()
    for key,value in values.items():template=template.replace('@@'+key+'@@',value)
    assert '@@' not in template
    args.output.write_text(template)
    print(args.output)


if __name__=='__main__':main()
