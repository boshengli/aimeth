#!/usr/bin/env python3
"""Build the M2.10 report from its versioned JSON evidence."""
import argparse
from html import escape
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=root/'milestones/m2-10-scientific-main-plan-v1.html')
    args = parser.parse_args()
    data = json.loads((root/'milestones/m2-10-scientific-main-plan-v1.json').read_text())
    principles = ''.join('<li>'+escape(x)+'</li>' for x in data['principles'])
    rows = ''.join('<tr><th>'+escape(w['id']+' · '+w['title'])+'</th><td><b>依赖：</b>'+escape(w['dependency'])+'<br><b>交付：</b>'+escape(w['deliverable'])+'</td></tr>' for w in data['work_packages'])
    readiness = ''.join('<div class="card"><h3>'+escape(x['stage'])+'</h3><p>'+escape(x['state'])+'</p></div>' for x in data['readiness'])
    limits = ''.join('<li>'+escape(x)+'</li>' for x in data['limits'])
    html='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'''+escape(data['title'])+''' · '''+escape(data['version'])+'''</title><style>
:root{color-scheme:light;--ink:#18332d;--muted:#60726d;--line:#dae4df;--paper:#fff;--bg:#f1f5f2;--accent:#126b56}*{box-sizing:border-box}html,body{width:100%;max-width:100%;margin:0;overflow-x:hidden}body{background:var(--bg);color:var(--ink);font:16px/1.58 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{background:#173e37;color:#fff;padding:34px max(18px,calc((100vw - 1000px)/2))}header p{color:#d1e2da;margin:0}h1{font-size:clamp(1.8rem,4vw,2.6rem);line-height:1.2;margin:.35em 0}main{width:100%;min-width:0;max-width:1000px;margin:24px auto;padding:0 18px 40px}section{min-width:0;max-width:100%;background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:22px;margin:15px 0;box-shadow:0 2px 12px #19372e0d}h2{font-size:1.3rem;margin:0 0 10px}.goal{min-width:0;max-width:100%;font-size:1.12rem;border-left:5px solid var(--accent);padding:14px 16px;background:#e9f3ee;border-radius:4px;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;padding:11px;border-bottom:1px solid var(--line)}th{width:30%;background:#f5f8f6}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.card{background:#f4f7f5;padding:14px;border-radius:8px}a{color:var(--accent)}code{overflow-wrap:anywhere}footer{color:var(--muted);font-size:.9rem;padding:6px 3px}@media(max-width:680px){header{padding:24px 16px}header h1{max-width:100%;white-space:normal;word-break:break-all;font-size:1.25rem;line-height:1.35}main{margin:12px auto;padding:0 11px 28px}section{padding:16px}.cards{grid-template-columns:1fr}body{font-size:15px}table,tbody,tr,th,td{display:block;width:100%;min-width:0}tr{padding:9px 0;border-bottom:1px solid var(--line)}th{padding:4px 9px;border:0}td{padding:4px 9px;border:0}}@media print{body{background:#fff}header{background:#fff;color:var(--ink);padding:8px 0}header p{color:var(--muted)}main{max-width:none;margin:0;padding:0}section{box-shadow:none;break-inside:avoid}}
</style></head><body><header><p>AIMeth · '''+escape(data['id']+' · '+data['date']+' · '+data['version'])+'''</p><h1>任务驱动的细胞自组织与组织形成</h1><p>主计划更新与工作包加载 · 规划交付，未实现或运行</p></header><main>
<section><h2>唯一科学目标</h2><p class="goal">'''+escape(data['goal'])+'''</p><p>形态形成与功能提升分别测量；本研究检验二者是否存在可重复联系。数学是可独立核验的评估领域之一，不是智能的唯一界定。</p></section>
<section><h2>两条设计原则</h2><ol>'''+principles+'''</ol><p>数千至数万细胞构建介观结构、十几万至百万细胞形成组织，是用户提出的项目工作尺度，待模型成本校准后再用于实验设计。</p></section>
<section><h2>按主计划加载的工作包</h2><table><tbody>'''+rows+'''</tbody></table><p>WP1先行；WP2、WP3依赖其定义。WP4可并行列候选，但正式指标在机制与细胞定义明确后冻结。工作包属于设计任务，不代表代码已实现。</p></section>
<section><h2>就绪度</h2><div class="cards">'''+readiness+'''</div><p>当前执行v8仍为单独冻结的探索性运行，没有实施这里的细胞发育假设。无需为本计划重解释或修改其结果。</p></section>
<section><h2>限制与下一步</h2><ul>'''+limits+'''</ul><p>先完成 WP1 的细胞、人工基因、表达、信号和状态定义，再细化发育规则及尺度模型。</p><p>主计划：<a href="../docs/organization-development-plan-v1.md">organization-development-plan-v1.md</a> · 任务：<a href="../tasks/T-20261002-002.md">T-20261002-002.md</a> · <a href="m2-10-scientific-main-plan-v1.json">结构化证据</a> · 基线提交 <code>'''+escape(data['baseline_commit'])+'''</code></p></section><footer>离线核心内容；无外部运行依赖。来源哈希和HTML布局核验记于同版本的清单及验证记录。报告不包含私有回执、参考答案或凭据。</footer></main></body></html>'''
    args.output.write_text(html,encoding='utf-8')
    print(json.dumps({'html':str(args.output),'bytes':args.output.stat().st_size}))


if __name__ == '__main__': main()
