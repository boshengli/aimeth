from pathlib import Path
from html import escape
import re
src=Path('manuscripts/aimeth/science-review-v1.md').read_text()
blocks=[]
for block in src.split('\n\n'):
    b=block.strip()
    if not b: continue
    m=re.match(r'^(#{1,6}) (.*)$',b)
    if m:
        level=len(m.group(1)); title=m.group(2)
        ident=re.sub(r'[^a-z0-9\u4e00-\u9fff]+','-',title.lower()).strip('-')
        blocks.append(f'<h{level} id="{escape(ident)}">{escape(title)}</h{level}>')
    elif b.startswith('|'):
        rows=[[c.strip() for c in line.strip('|').split('|')] for line in b.splitlines()]
        labels=rows[0]
        blocks.append('<table><thead><tr>'+''.join('<th>'+escape(x)+'</th>' for x in labels)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td data-label="'+escape(labels[i],quote=True)+'">'+escape(x)+'</td>' for i,x in enumerate(row))+'</tr>' for row in rows[2:])+'</tbody></table>')
    elif b.startswith('- '):
        blocks.append('<ul>'+''.join('<li>'+escape(re.sub(r'^- ','',x))+'</li>' for x in b.splitlines())+'</ul>')
    else:
        b=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',lambda m:'<a href="'+escape(m.group(2),quote=True)+'">'+escape(m.group(1))+'</a>',b)
        b=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',b)
        b=re.sub(r'\*(.+?)\*',r'<em>\1</em>',b)
        blocks.append('<p>'+b.replace('\n',' ')+'</p>')
css='''
*{box-sizing:border-box}body{margin:0;background:#f4f6f4;color:#20332d;font:16px/1.72 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{background:#173f35;color:white;padding:38px max(20px,calc((100vw - 960px)/2))}header p{color:#dfeae4;margin:8px 0}h1{font-size:clamp(28px,4vw,42px);line-height:1.18;margin:18px 0}
main{max-width:1000px;margin:auto;padding:18px 20px}article{background:white;border:1px solid #dae4dd;border-radius:14px;padding:34px;box-shadow:0 3px 14px #193b2d0c}
h2{font-size:25px;line-height:1.3;margin-top:38px;color:#1b4c3c}h3{font-size:19px;margin-top:28px}p,li{overflow-wrap:anywhere}a{color:#075f47;text-underline-offset:3px}a:focus-visible{outline:3px solid #d69539}
table{width:100%;border-collapse:collapse;font-size:15px;margin:20px 0}td,th{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #d8e2dc}th{background:#edf3ef}footer{color:#64746d;padding:22px 4px;font-size:13px}
@media(max-width:600px){header{padding:25px 18px}main{padding:12px}article{padding:20px 16px}table,tbody,tr,td{display:block;width:100%}thead{display:none}tr{border-bottom:2px solid #d8e2dc;padding:8px 0}td{padding:6px 0;border:0}td:before{content:attr(data-label) " · ";font-weight:650;color:#41574e}}
@media print{body{background:white;color:#111}header{background:white;color:#111;padding:0}header p{color:#333}main{padding:0;max-width:none}article{border:0;box-shadow:none;padding:0}h2,h3{break-after:avoid}nav{display:none}a{color:#111;text-decoration:none}}
'''
header='<header><p>AIMeth · 科学进度评议 · 2026-10-04</p><h1>从细胞发育到群体功能：当前证据与判别逻辑</h1><p>一个科学目标 · 两条设计原则 · 仍待关键群体证据</p></header>'
nav='<nav aria-label="页面导览" style="max-width:1000px;margin:auto;padding:14px 20px"><a href="#唯一科学目标">科学目标</a>　<a href="#两条设计原则">设计原则</a>　<a href="#目前有依据的部分">已有依据</a>　<a href="#三-下一步科学计划-三段因果检验">科学计划</a>　<a href="#四-证据解释规则">证据规则</a></nav>'
html='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AIMeth科学进度与计划</title><style>'+css+'</style></head><body>'+header+nav+'<main><article>'+''.join(blocks)+'</article><footer>本页讨论科学假设与证据边界。提出的比较和干预仍须在确认性研究前预先规定；此报告本身不构成结果或研究预注册。</footer></main></body></html>'
Path('manuscripts/aimeth/science-review-v1.html').write_text(html)
