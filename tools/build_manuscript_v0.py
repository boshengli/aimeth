#!/usr/bin/env python3
"""Render the evidence-backed working draft and progress snapshot; no API calls."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'manuscripts/aimeth'
CSS = '''*{box-sizing:border-box}body{margin:0;background:#f3f5f4;color:#1b302a;font:16px/1.75 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{padding:42px max(22px,calc((100vw - 1080px)/2));background:#153f35;color:#fff}header p{color:#e0eee8}h1{font-size:clamp(28px,4vw,46px);line-height:1.17;letter-spacing:-.02em}h2{font-size:25px;line-height:1.3;margin-top:32px}h3{font-size:19px;line-height:1.4;margin-top:28px}main{max-width:1124px;margin:auto;padding:24px 22px}article,section{background:#fff;border:1px solid #d9e3dd;border-radius:14px;padding:28px;margin:20px 0}article{max-width:870px;margin:20px auto;font-family:Georgia,"Times New Roman",serif;font-size:18px;line-height:1.85}article h1,article h2,article h3{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}p,li,code{overflow-wrap:anywhere}a{color:#096446;text-underline-offset:3px}header a{color:#fff}nav{display:flex;flex-wrap:wrap;gap:12px;margin:18px 0}nav a,button{padding:8px 14px;background:#fff;color:#144f3c;border:1px solid #bfd2c7;border-radius:7px;font:inherit}button{cursor:pointer}a:focus-visible,button:focus-visible{outline:3px solid #eaa647;outline-offset:3px}.badge{display:inline-block;background:#e8f3dd;color:#254f2b;border-radius:20px;padding:5px 12px;font-size:14px}.warning{border-left:5px solid #d8a140;background:#fff9e8;padding:16px}.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.card{padding:20px;background:#fff;border:1px solid #d9e3dd;border-radius:12px}.card strong{display:block;font-size:28px}.card span{font-size:14px;color:#577164}table{border-collapse:collapse;width:100%;font-size:15px}th,td{padding:12px;border-bottom:1px solid #d7e2da;text-align:left;vertical-align:top}th{background:#edf4ef}td{overflow-wrap:anywhere}figure{margin:20px 0}figure svg{width:100%;height:auto}figcaption,.muted{font-size:14px;color:#596e61}code{font-size:.85em;background:#f0f3f1;padding:2px 4px}footer{padding:18px 0;font-size:14px;color:#586b5e}.status{font-weight:600;color:#926000}@media(max-width:640px){header{padding:26px 18px}main{padding:12px}section,article{padding:20px 16px}.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.card{padding:16px}.card strong{font-size:23px}article{font-size:17px}table,tbody,tr,td{display:block;width:100%}thead{display:none}tr{border-bottom:2px solid #d7e2da;padding:8px 0}td{padding:5px 0;border:0}td:before{content:attr(data-label)' · ';font-weight:bold}}@media print{body{background:white;color:#111}header{background:white;color:#111;padding:0}header p{color:#333}nav,button{display:none}main{padding:0;max-width:none}section,article{border:0;padding:0;max-width:none}h2,h3{break-after:avoid}figure,tr{break-inside:avoid}.cards{display:block}}'''


def inline(text):
    text = escape(text)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'<a href="\2">\1</a>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', text)


def markdown(text):
    blocks = []
    for block in text.split('\n\n'):
        block = block.strip()
        if not block:
            continue
        m = re.match(r'^(#{1,6}) (.*)$', block)
        if m:
            level = len(m[1]); title = m[2]
            ident = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
            blocks.append(f'<h{level} id="{ident}">{inline(title)}</h{level}>')
        elif all(re.match(r'^(?:- |\d+\. )', s) for s in block.splitlines()):
            blocks.append('<ul>'+''.join('<li>'+inline(re.sub(r'^(?:- |\d+\. )','',s))+'</li>' for s in block.splitlines())+'</ul>')
        else:
            blocks.append('<p>'+inline(block.replace('\n',' '))+'</p>')
    return '\n'.join(blocks)


def document(title, body, lang='zh-CN'):
    return '<!doctype html><html lang="'+lang+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>'+CSS+'</style></head><body>'+body+'</body></html>'


def figure(audit):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams.update({'svg.hashsalt':'aimeth-calibration-v0','font.size':10})
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), constrained_layout=True)
    colors = ['#16705b','#96583a']
    for i, channel in enumerate(['fast','deep']):
        rows = [r for r in audit['rows'] if r['channel']==channel]
        ys = [r['elapsed_s'] for r in rows]
        xs = [i + .025*(j-(len(rows)-1)/2) for j in range(len(rows))]
        axes[0].scatter(xs,ys,s=40,color=colors[i],alpha=.8)
        avg = sum(ys)/len(ys)
        axes[0].plot([i-.18,i+.18],[avg,avg],color='black',lw=2)
    axes[0].set(xticks=[0,1],xticklabels=['Fast (n=8)','Deep (n=4)'],ylabel='Completion latency (s)',title='a  Individual calibration requests',ylim=(0,13))
    prompt=[]; reasoning=[]; other=[]
    for c in ['fast','deep']:
        s=audit['channels'][c];prompt.append(s['prompt_tokens']);reasoning.append(s['reasoning_tokens']);other.append(s['completion_tokens']-s['reasoning_tokens'])
    axes[1].bar([0,1],prompt,color='#497d67',label='Prompt')
    axes[1].bar([0,1],reasoning,bottom=prompt,color='#d4a55b',label='Reasoning')
    axes[1].bar([0,1],other,bottom=[p+r for p,r in zip(prompt,reasoning)],color='#bdcfbf',label='Other completion')
    axes[1].set(xticks=[0,1],xticklabels=['Fast (8 calls)','Deep (4 calls)'],ylabel='Reported tokens, summed',title='b  Usage accounting')
    axes[1].legend(frameon=False,fontsize=8)
    for ax in axes:
        ax.spines[['top','right']].set_visible(False)
    dest=BASE/'figures';dest.mkdir(exist_ok=True)
    fig.savefig(dest/'calibration-v0.svg',metadata={'Date':None})
    fig.savefig(dest/'calibration-v0.png',dpi=160)
    plt.close(fig)
    return (dest/'calibration-v0.svg').read_text().split('<svg',1)[1].join(['<svg',''])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args()
    p=json.loads((BASE/'progress.json').read_text()); audit=json.loads((BASE/'evidence-audit-v0.json').read_text())
    text=(BASE/'manuscript.md').read_text();words=len(re.findall(r"\b[\w'-]+\b",text))
    refs=json.loads((BASE/'references-v0.json').read_text())['references']
    svg=figure(audit)
    ms=document('AIMeth manuscript '+p['version'],'<header><span class="badge">'+escape(p['version'])+' · research draft</span><h1>AIMeth working manuscript</h1><p>Full text with explicit evidence boundaries. Core population results remain pending.</p><a href="progress.html">← 进度页面</a></header><main><nav><a href="#abstract">Abstract</a><a href="#introduction">Introduction</a><a href="#results-and-current-evidence">Results</a><a href="#discussion">Discussion</a><a href="#methods-proposed-study-protocol">Methods</a><a href="#references">References</a><button onclick="window.print()">Print / PDF</button></nav><article>'+markdown(text)+'</article><section id="calibration-figure"><h2>Supplementary Figure 1</h2><figure>'+svg+'<figcaption>Existing interface calibration. Different conditions; no causal channel comparison, proof result or population effect.</figcaption></figure></section></main>','en')
    (BASE/'manuscript.html').write_text(ms)
    def progress_page(prefix):
        h='<header><span class="badge">M2.12 · 首稿与可见进度</span><h1>文章开始有正文，证据仍须补齐</h1><p>当前版本 '+escape(p['version'])+' · '+escape(p['state_label'])+'</p><p>更新：'+escape(p['updated_at'])+'　下次计划：'+escape(p['next_scheduled_at'])+'</p></header><main>'
        h+='<nav><a href="'+prefix+'manuscript.html">阅读完整英文稿</a><a href="#evidence">查看实测证据</a><a href="#gaps">查看科学缺口</a><a href="#versions">查看版本</a><button onclick="location.reload()">刷新快照</button></nav>'
        h+='<div class="cards">'+''.join('<div class="card"><strong>'+str(n)+'</strong><span>'+label+'</span></div>' for n,label in [(words,'英文单词（含方法与引用）'),(len(refs),'已核对的一手文献'),(12,'既有 API 校准请求'),(0,'本稿可用的确认性群体结果')])+'</div>'
        h+='<section id="work"><h2>本轮实际完成与进行中</h2><ul>'+''.join('<li>'+escape(x)+'</li>' for x in p['completed'])+'</ul><p class="status">当前工作：'+escape(p['current_work'])+'</p><p>触发：'+escape(p['trigger'])+'；周期起点：'+escape(p['cycle_started_at'])+'。周期与账户额度窗口分别记录。</p></section>'
        h+='<section id="evidence"><h2>现有实测证据</h2><p>重算此前 12 次 DeepSeek 回执：8 次 fast、4 次 deep，均 HTTP 200、stop、非空、JSON 可解析、必需字段存在。它们不是独立群体重复，未保存最终正文，无法复核数学正确性或完整 schema。</p><figure>'+svg+'<figcaption>每个点是一条既有请求。两个通道提示、预算和并发不同，只作描述统计。总计 8,140 tokens；图示不是新实验或 10K 吞吐结果。</figcaption></figure><a href="'+prefix+'evidence-audit-v0.json">逐请求派生数据与来源哈希</a></section>'
        h+='<section id="gaps"><h2>能写什么，尚不能声称什么</h2><table><thead><tr><th>内容</th><th>状态</th><th>科学边界</th></tr></thead><tbody>'
        for row in [('题目／摘要／引言／讨论','已有正文','完整段落不等于完整证据'),('细胞、模块、信号、谱系与对照','Methods 提案','发育规则和确认性设计尚未冻结'),('接口校准','本地重新计算','不代表任务正确率或群体优势'),('发育→组织→能力因果链','待实验','不编造效果量、P 值或证明'),('投稿状态','研究草稿','由用户选择修订；目前不具备投稿证据')]:
            h+='<tr>'+''.join('<td data-label="'+label+'">'+escape(v)+'</td>' for label,v in zip(['内容','状态','科学边界'],row))+'</tr>'
        h+='</tbody></table><p class="warning">没有展示“科研完成百分比”，因为尚无可靠的完成分母。主张、证据、实现和投稿就绪度分别记录。</p></section>'
        h+='<section id="versions"><h2>版本与证据入口</h2><ul><li><a href="'+prefix+'manuscript.md">可编辑 Markdown 主稿</a></li><li><a href="'+prefix+'claim-evidence.json">主张—证据表</a></li><li><a href="'+prefix+'literature-v0.md">文献及核验范围</a></li><li><a href="'+prefix+'independent-review-v0.md">独立方法与统计审查</a></li><li><a href="'+prefix+'next-priorities.md">断点与下一组工作</a></li></ul><p>版本历史保存在 versions/；交付哈希与验证见该里程碑的 manifest 和 validation 记录。</p></section>'
        h+='<section id="requirements"><h2>要求、交付与下一阶段</h2><p>用户要求立即执行并看见文章进度：本轮形成英文稿、已有证据复算、文献/方法审查及此页面。每 5 小时重新计时已保存；真正的定时唤醒仍需未来运行记录验证。</p><p>设计：可以继续细化；局部实现：离线契约单独验证；群体实验：仍需冻结规则、评价和预算并核清既有运行。下一阶段优先处理独立审查中的对照与资源混淆，以及运行器的持久化和真实资源账本。</p></section>'
        h+='<footer>来源基线：31740a2eeddeb81795f87b0bbd4c3c77c9e439ea。交付提交另记。此页为带时间的本地快照，不代表后台始终执行；版式核验不等于科学验证。</footer></main>'
        return document('AIMeth 文章进度 '+p['version'],h)
    (BASE/'progress.html').write_text(progress_page(''))
    (ROOT/'milestones/m2-12-manuscript-progress-v1.html').write_text(progress_page('../manuscripts/aimeth/'))
    if args.freeze:
        v=BASE/'versions'/p['version'];v.mkdir(parents=True,exist_ok=False)
        for f in ['manuscript.md','manuscript.html','claim-evidence.json','progress.json','evidence-audit-v0.json','references-v0.json']:
            (v/f).write_bytes((BASE/f).read_bytes())
        (v/'progress.html').write_text(progress_page('../../'))
        # Snapshot manuscript links refer to its matching frozen progress page.
        (v/'manifest.json').write_text(json.dumps({'version':p['version'],'created_at':p['updated_at'],'files':{x.name:sha256(x.read_bytes()).hexdigest() for x in v.iterdir() if x.is_file()}},indent=2)+'\n')
    print(json.dumps({'version':p['version'],'word_count':words,'references':len(refs),'html':'manuscripts/aimeth/progress.html'}))


if __name__=='__main__':main()
