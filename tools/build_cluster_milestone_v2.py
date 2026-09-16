#!/usr/bin/env python3
"""Reproducible correction of failure attribution; preserve published v1."""
import argparse
import html
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.verify_artifacts import verify


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'milestones/m2-1-cluster-pilot-v2.html')
    args=parser.parse_args()
    verify(ROOT/'cluster-report-manifest.json')
    trial=json.loads((ROOT/'reports/cluster-pilot-v1/v2/summary.json').read_text())
    failed=[r for r in trial['results'] if r['verdict']['status']=='TECHNICAL_FAILURE']
    premature=sum(r['status']['steps']['pending']>0 and r['status']['steps']['failed']==0 for r in failed)
    truncated=sum(r['status']['steps']['pending']==0 and r['status']['steps']['failed']>0 for r in failed)
    assert (len(failed),premature,truncated,trial['finish_reasons']['length'])==(21,14,7,8)
    rejected=[json.loads(line)['event']['payload'] for line in
              (ROOT/'reports/cluster-pilot-v1/v2/events.jsonl').read_text().splitlines()
              if json.loads(line)['event']['kind']=='attempt.received'
              and not json.loads(line)['event']['payload']['accepted']]
    assert len(rejected)==8 and all(p['generation_status']=='length' and p['transport_status']=='ok' for p in rejected)
    old=json.loads((ROOT/'milestones/m2-1-cluster-pilot-v1.evidence.json').read_text())
    evidence=json.loads((ROOT/'milestones/m2-1-cluster-pilot-v2.evidence.json').read_text())
    assert evidence['correction']['v2_failure_causes']=={'premature_coordinator_exit':14,'generation_length':7}
    text=(ROOT/'milestones/m2-1-cluster-pilot-v1.html').read_text()
    replacements={
        '报告 v1.0':'报告 v2.0',
        '32 群体中 21 个因调度器提前结束未完成。':'32 群体中 21 个未完成：14 个因调度器提前退出，7 个因 8 次输出截断停止。',
        '../cluster-report-manifest.json':'../cluster-report-v2-manifest.json',
        'python3 tools/build_cluster_milestone.py':'python3 tools/build_cluster_milestone_v2.py',
        'python3 tools/verify_artifacts.py cluster-report-manifest.json':'python3 tools/verify_artifacts.py cluster-report-v2-manifest.json',
        'cmp milestones/m2-1-cluster-pilot-v1.html':'cmp milestones/m2-1-cluster-pilot-v2.html',
        html.escape(json.dumps(old,ensure_ascii=False,indent=2)):html.escape(json.dumps(evidence,ensure_ascii=False,indent=2)),
        '<h2>四个作业的完整账本</h2>':'<h2>四个作业的完整账本</h2><div class="note"><strong>v2 更正：</strong>首版将第二轮的 21 个未完成群体全部归因于调度器。逐群体复核后更正为 14 个调度器提前退出、7 个输出截断；第三轮结果和全部原始数据不变。<a href="m2-1-cluster-pilot-v1.html">已提交的首版保留供追溯</a>。</div>'}
    for before,after in replacements.items():
        assert text.count(before)==1,before[:80]
        text=text.replace(before,after)
    args.output.write_text(text)
    print(args.output)


if __name__=='__main__':main()
