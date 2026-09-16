#!/usr/bin/env python3
"""Render the immutable GitHub publication supplement from observed public evidence."""
import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import re


def main():
    root=Path(__file__).resolve().parents[1]
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=root/'milestones/m1-1-publication-v1.html')
    args=p.parse_args()
    source=root/'reports/github-publication-20260916-v1.json'
    template=root/'templates/milestone-publication-v1.html'
    data=json.loads(source.read_text())
    if data['repository']['private'] or not data['anonymous_access_verified'] or data['ci']['conclusion']!='success':
        raise ValueError('Publication evidence does not support a public, passing release')
    if data['ci']['headSha']!=data['published_baseline_commit'] or data['ci_tests_passed']!=32:
        raise ValueError('Unexpected tested source identity')
    commits=''.join('<li><a href="'+escape(c['url'],quote=True)+'"><code>'+c['sha'][:7]+'</code></a><div><strong>'+escape(c['title_zh'])+'</strong><small>'+escape(c['message'])+'</small></div></li>' for c in data['original_commits'])
    values={
        'DATE':data['date'],'REPOSITORY':data['repository']['html_url'],'BRANCH':data['repository']['default_branch'],
        'CI_URL':data['ci']['url'],'CI_ID':str(data['ci']['databaseId']),'PYTHON':data['ci_python_version'],
        'COMMIT':data['published_baseline_commit'],'COMMITS':commits,'TESTS':str(data['ci_tests_passed']),
        'LOG':escape((root/'reports/github-ci-35050227524.txt').read_text()),
        'METADATA':escape(json.dumps(data,ensure_ascii=False,indent=2))
    }
    html=template.read_text()
    for key,value in values.items():html=html.replace('@@'+key+'@@',value)
    if re.search(r'@@[A-Z_]+@@',html):raise ValueError('Unexpanded template field')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(html)
    inputs=[source,template,root/'tools/build_publication_milestone.py',root/'reports/github-ci-35050227524.txt',root/'reports/publication-preflight-20260916.json']
    evidence={'schema_version':'1.0','milestone':'M1.1-publication','version':'1.0','published_baseline_commit':data['published_baseline_commit'],
              'inputs':[{'path':f.relative_to(root).as_posix(),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in inputs],
              'scientific_validity_checked':False}
    args.output.with_suffix('.evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'html':str(args.output),'bytes':args.output.stat().st_size,'public_repository':data['repository']['html_url'],'observed_ci':data['ci']['url']}))


if __name__=='__main__':main()
