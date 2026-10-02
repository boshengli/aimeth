#!/usr/bin/env python3
"""Render the proposed M2.11 submission protocol; performs no network calls."""
from html import escape as e
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STEM='m2-11-public-api-submission-plan-v1'

def main():
    d=json.loads((ROOT/'milestones'/f'{STEM}.json').read_text())
    blocks=[]
    md=[f"# {d['title']} · {d['version']}",f"日期：{d['date']}；状态：提案，未冻结、未提交。基线：{d['baseline_commit']}。"]
    for s in d['sections']:
        text=''.join(f'<p>{e(p)}</p>' for p in s['paragraphs'])
        md.extend(['',f"## {s['title']}",'','\n\n'.join(s['paragraphs'])])
        if 'headers' in s:
            text+='<table><thead><tr>'+''.join(f'<th scope="col">{e(h)}</th>' for h in s['headers'])+'</tr></thead><tbody>'
            for row in s['rows']:
                text+='<tr>'+''.join(f'<td data-label="{e(h)}">{e(v)}</td>' for h,v in zip(s['headers'],row))+'</tr>'
            text+='</tbody></table>'
            md+=['',' | '.join(s['headers']),' | '.join('---' for _ in s['headers'])]+[' | '.join(row) for row in s['rows']]
        blocks.append(f'<section id="{s["id"]}"><h2>{e(s["title"])}</h2>{text}</section>')
    nav=''.join(f'<a href="#{s["id"]}">{e(s["title"])}</a>' for s in d['sections'])
    links=''.join(f'<li><a href="{e(l["href"])}">{e(l["label"])}</a></li>' for l in d['links'])
    css='''*{box-sizing:border-box}body{margin:0;background:#f1f5f4;color:#18382f;font:16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{background:#163d35;color:white;padding:38px max(20px,calc((100vw - 1100px)/2))}h1{font-size:clamp(25px,3vw,39px);line-height:1.3}header p{color:#daeee7}.badge{display:inline-block;background:#d7eddf;color:#174c38;padding:4px 12px;border-radius:20px}main{max-width:1140px;margin:auto;padding:22px 20px}nav{display:flex;flex-wrap:wrap;gap:10px;padding:12px 0}a{color:#116451;overflow-wrap:anywhere}nav a{background:white;padding:6px 12px;border-radius:6px}section{background:white;border:1px solid #dae6df;padding:24px;border-radius:12px;margin:20px 0}h2{font-size:23px;margin:0 0 14px}p{overflow-wrap:anywhere}table{width:100%;border-collapse:collapse;font-size:15px}td,th{vertical-align:top;text-align:left;border-bottom:1px solid #dbe7e1;padding:12px;overflow-wrap:anywhere}th{background:#eaf3ee}footer{padding:20px;color:#526c60;font-size:14px}code{overflow-wrap:anywhere}a:focus-visible{outline:3px solid #d89823}section:target{border:2px solid #39775d}@media(max-width:640px){header{padding:24px 18px}main{padding:12px}section{padding:17px}h2{font-size:21px}table,tbody,tr,td{display:block;width:100%}thead{display:none}tr{border-bottom:2px solid #cadfd2;padding:8px 0}td{border:0;padding:5px 0}td:before{content:attr(data-label)'：';font-weight:600}nav{font-size:14px}body{font-size:15px}}@media print{body{background:white}header{background:white;color:#173b31;padding:0}header p{color:#173b31}nav{display:none}main{padding:0;max-width:none}section{border:0;padding:10px 0}h2{break-after:avoid}tr{break-inside:avoid}}'''
    html=f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(d["title"])}</title><style>{css}</style></head><body><header><span class="badge">M2.11 · 规划交付 / 尚未执行</span><h1>{e(d["title"])}</h1><p>复用已有测试 → 76 次有界工程测试 → 10K 发育实验候选</p><p>{d["date"]} · {d["version"]} · 一个科学目标，两条原则</p></header><main><nav aria-label="章节导航">{nav}</nav>{"".join(blocks)}<section id="sources"><h2>来源与版本</h2><ul>{links}</ul><p>DeepSeek 回执 SHA-256：<code>{d["evidence"]["deepseek_receipts_sha256"]}</code></p><p>基线提交：<code>{d["baseline_commit"]}</code>。交付提交由同版 manifest 的 Git 记录标识；布局核验见 <a href="{STEM}.validation.json">validation</a>，内容哈希见 <a href="{STEM}.manifest.json">manifest</a>。</p></section><footer>自包含离线报告；无凭据、私有响应正文或参考答案。布局检查不等于科学验证。当前仅设计就绪。</footer></main></body></html>'
    (ROOT/'milestones'/f'{STEM}.html').write_text(html)
    md+=['','## 来源与版本','']+[f'- [{x["label"]}]({x["href"]})' for x in d['links'] if x['href'].startswith('https:')]
    md+=['',f"私有校准回执 SHA-256：{d['evidence']['deepseek_receipts_sha256']}。",'交付提交见同版本 milestone manifest 的 Git 记录。']
    (ROOT/'docs/public-api-submission-test-plan-v1.md').write_text('\n\n'.join(md)+'\n')
    print('Rendered M2.11 HTML and Markdown from versioned JSON.')

if __name__=='__main__':main()
