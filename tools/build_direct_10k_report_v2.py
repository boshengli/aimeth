#!/usr/bin/env python3
"""Reproduce and validate the offline direct-10K v2 status report."""
from html.parser import HTMLParser
from pathlib import Path
import argparse, json
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'milestones/m2-7-direct-10k-v2.html'
TEMPLATE=ROOT/'milestones/m2-7-direct-10k-v2.template.html'
EVIDENCE=ROOT/'milestones/m2-7-direct-10k-v2.json'
class Audit(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=set(); self.links=[]; self.scripts=0; self.external_assets=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.add(attrs['id'])
        if 'href' in attrs:self.links.append(attrs['href'])
        if tag=='script':self.scripts+=1
        for key in ('src','poster'):
            if attrs.get(key):self.external_assets.append(attrs[key])
def validate(text,e):
    a=Audit(); a.feed(text)
    assert a.scripts==0 and not a.external_assets, 'Report must be offline with no active script or external media.'
    for href in a.links:
        if href.startswith('#'):
            assert href[1:] in a.ids, f'Missing in-page target: {href}'
        elif not href.startswith(('https://','http://')):
            assert (REPORT.parent/href).exists(), f'Missing local link target: {href}'
    for value in (e['gpu08_attempt']['job_id'],e['gateway_v1']['job_id'],e['gateway_v1']['source_commit'],'4fa42e960fd9dd068fe974ab793c6358717d2f9b9fae416d86cb0de4d5bf10d5',e['gateway_v1']['provider_usage']['total_tokens']):
        display=str(value) if not isinstance(value,int) else format(value,',')
        assert display in text, f'Evidence value absent from report: {display}'
    assert '@media(max-width:650px)' in text and '@media print' in text
    assert '受控停止' in text and 'NODE_FAIL' in text and 'missing_final_content' not in text
    return {'html_parser':'PASS','local_and_anchor_links':'PASS','offline_no_script_or_remote_assets':'PASS','narrow_and_print_css':'PASS','evidence_crosschecks':'PASS','browser_visual_qa':'NOT_PERFORMED; prior project record documents browser policy block'}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
    text=TEMPLATE.read_text();e=json.loads(EVIDENCE.read_text()); result=validate(text,e)
    if args.check: assert REPORT.read_text()==text, 'Generated report differs from committed report.'
    else: REPORT.write_text(text)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
