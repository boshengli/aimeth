#!/usr/bin/env python3
"""Build the self-contained M2.14 handoff from its structured evidence record."""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path


def render(data: dict) -> str:
    run = data["run"]
    snapshot = run["snapshot"]
    pairing = run["amendment3_pairing_audit"]
    arms = "\n".join(
        "<tr><th scope=\"row\">{}</th><td>{}</td><td>{}</td></tr>".format(
            escape(row["name"]), escape(row["mechanism"]), escape(row["control_for"]))
        for row in data["arms"])
    tests = "\n".join(f"<li>{escape(item)}</li>" for item in data["validation"]["other_checks"])
    limitations = "\n".join(f"<li>{escape(item)}</li>" for item in data["limitations"])
    commits = " · ".join(
        f"<a href=\"https://github.com/boshengli/aimeth/commit/{escape(commit)}\"><code>{escape(commit[:8])}</code></a>"
        for commit in data["implementation_commits"])
    sources = []
    for source in data["sources"]:
        href = source.get("url") or ("../" + source["path"] if source.get("path") else None)
        label = escape(source["label"])
        sources.append(f"<li><a href=\"{escape(href, quote=True)}\">{label}</a></li>" if href else f"<li>{label}</li>")
    source_list = "\n".join(sources)
    budget = run["budget"]
    requirement_rows = """<tr><th scope="row">等调用与 token 预算</th><td>七个非发育对照共用同一模型、任务、8 次逻辑调用和 262,144 completion/reasoning token 上限；多调用臂单次上限 32,768。</td><td>冻结协议、预算审计测试；运行尚未结束。</td></tr>
<tr><th scope="row">独立基线与组织机制对照</th><td>保留 independent、self_repair、single_long、vote、orchestrator_worker、debate、evolution 七臂，分别隔离采样、修订、长推理、聚合、编排、互评和非空间搜索。</td><td>七臂 runtime、fake-LLM/可见评分测试；没有臂间测量结果。</td></tr>
<tr><th scope="row">答案隔离与失败分母</th><td>生成端只见公开任务和可见反馈；隐藏答案留在隔离评分端；未知启动结果保留在分母且不得重发。</td><td>隔离评估路径和审计器已实现；尚无隐藏评分。</td></tr>
<tr><th scope="row">与发育臂按题配对</th><td>Amendment 3 指定发育臂已冻结的 ARC-40 清单。</td><td>当前控制臂在 Amendment 3 到达前已启动；两套 40 题仅重合 9 题。当前控制结果不可作为与发育臂逐题配对的比较。</td></tr>
<tr><th scope="row">独立群体重复</th><td>正式解释组织效应需要每题多个独立初始化群体。</td><td>当前每任务臂 1 次，仅探索性 pilot；不能推断稳定架构效应或发育机制。</td></tr>"""
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{escape(data["milestone"])} · {escape(data["title"])}</title>
<style>
:root {{ color-scheme: light; --ink:#16232e; --muted:#51616e; --line:#d5dee5; --paper:#fff; --wash:#f3f7fa; --blue:#174f76; --amber:#80520b; --amber-bg:#fff5dd; --green:#176044; }}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; }}
body {{ margin:0; color:var(--ink); background:#eaf0f4; font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
main {{ max-width:1040px; margin:24px auto; padding:clamp(18px,4vw,48px); background:var(--paper); box-shadow:0 8px 30px #17324a18; }}
header {{ border-bottom:1px solid var(--line); padding-bottom:24px; }}
h1 {{ max-width:850px; margin:10px 0 12px; font-size:clamp(2rem,5vw,3.15rem); line-height:1.13; letter-spacing:-.025em; }}
h2 {{ margin:36px 0 12px; font-size:1.45rem; line-height:1.25; }}
h3 {{ margin:22px 0 6px; font-size:1.05rem; }}
p {{ margin:10px 0; }}
a {{ color:var(--blue); text-underline-offset:3px; overflow-wrap:anywhere; }}
code {{ overflow-wrap:anywhere; }}
.eyebrow {{ color:var(--blue); font-weight:700; letter-spacing:.06em; text-transform:uppercase; }}
.status {{ display:inline-block; border-radius:99px; padding:4px 12px; color:var(--amber); background:var(--amber-bg); font-size:.9rem; font-weight:700; }}
.lede {{ max-width:840px; color:var(--muted); font-size:1.12rem; }}
.callout {{ border-left:5px solid var(--amber); padding:13px 16px; background:var(--amber-bg); }}
.grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin:18px 0; }}
.card {{ padding:14px; border:1px solid var(--line); border-radius:8px; background:var(--wash); min-width:0; }}
.card b {{ display:block; color:var(--blue); font-size:.88rem; margin-bottom:4px; }}
nav {{ margin:18px 0 4px; padding:12px 14px; background:var(--wash); border-radius:8px; }}
nav ul {{ display:flex; flex-wrap:wrap; gap:8px 18px; margin:0; padding:0; list-style:none; }}
table {{ width:100%; border-collapse:collapse; margin:14px 0 22px; }}
th,td {{ border:1px solid var(--line); padding:10px 12px; text-align:left; vertical-align:top; }}
thead th {{ background:var(--wash); }}
tbody th {{ white-space:nowrap; color:var(--blue); }}
.small {{ color:var(--muted); font-size:.92rem; }}
.mono {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.9rem; }}
.steps {{ padding-left:1.3rem; }}
.steps li {{ margin:7px 0; }}
.decision {{ padding:15px 18px; border:1px solid var(--line); border-radius:8px; }}
footer {{ margin-top:34px; padding-top:14px; border-top:1px solid var(--line); color:var(--muted); font-size:.9rem; }}
@media (max-width:700px) {{
  body {{ background:var(--paper); font-size:15px; }}
  main {{ margin:0; padding:18px 16px 30px; box-shadow:none; }}
  .grid {{ grid-template-columns:1fr; }}
  table {{ display:block; overflow-x:auto; white-space:normal; }}
  tbody th {{ white-space:normal; }}
  nav ul {{ display:grid; grid-template-columns:1fr 1fr; gap:8px 12px; }}
}}
@media print {{
  body {{ background:#fff; font-size:11pt; }} main {{ max-width:none; margin:0; padding:0; box-shadow:none; }}
  nav {{ display:none; }} a {{ color:inherit; }} h2 {{ break-after:avoid; }} tr {{ break-inside:avoid; }}
}}
</style>
</head>
<body>
<main>
<header id="top">
  <div class="eyebrow">AIMeth · {escape(data['milestone'])} · Version {escape(data['version'])}</div>
  <h1>{escape(data['title'])}</h1>
  <span class="status">{escape(data['status'])}</span>
  <p class="lede">本阶段落实七种同模型、同预算的非发育型对照。截至 {escape(snapshot['captured_at'])}，运行仍在进行：532 条任务—对照臂记录中，{snapshot['settled']} 条已结算（{snapshot['settled_stop_reasons']['arc_train_perfect']} 条可见训练完美停止，{snapshot['settled_stop_reasons']['planned_calls_or_tokens_exhausted']} 条预算耗尽），{snapshot['unknown_started']} 条启动结果未知，{snapshot['started_unsettled']} 条已启动但未结算，{snapshot['not_started_or_pending']} 条尚未启动。尚未进行隐藏评分，也没有科学效应结论。</p>
  <div class="grid" aria-label="当前研究状态">
    <div class="card"><b>科学问题</b>相同预算下，发育型组织是否超过非发育型策略？机制需要后续消融来区分。</div>
    <div class="card"><b>已完成</b>7 个对照臂、泄漏隔离评估路径、冻结任务与预算、自动审计和成对分析程序。</div>
    <div class="card"><b>正在进行</b>DeepSeek Flash 的 ARC-AGI-2 与番茄愈伤插补试验；当前仅有 ARC independent 臂的少量可见检查记录，其他条件仍待运行和盲化评分。</div>
  </div>
</header>

<nav aria-label="报告目录"><ul>
  <li><a href="#requirements">要求与证据</a></li><li><a href="#question">科学逻辑</a></li><li><a href="#design">对照设计</a></li>
  <li><a href="#evidence">证据与验证</a></li><li><a href="#run">运行状态</a></li>
  <li><a href="#limits">边界与后续</a></li><li><a href="#sources">来源</a></li>
</ul></nav>

<section id="requirements">
<h2>用户要求、实现与证据</h2>
<table><thead><tr><th scope="col">要求</th><th scope="col">设计/实现</th><th scope="col">证据与缺口</th></tr></thead><tbody>{requirement_rows}</tbody></table>
<p class="small">Amendment 3 的开发臂 ARC-40 参考清单已通过只读集群访问保存为 <a href="../plans/arc2-pilot40-developmental-pairing-reference-v1.json">配对核查清单</a>。当前控制样本清单也原样保留。运行未更改，不重新发送任何已启动请求。</p>
</section>

<section id="question">
<h2>科学逻辑</h2>
<p>发育型计算组织包含局部调控、分化、增殖和交流。要检验其是否带来任务能力提升，先需要能解释“非发育策略本身已经做到什么”的基线。本阶段的对照臂不包含细胞分化或空间组织，因而能分辨通常的采样、互评和搜索机制。</p>
<p>相同模型、任务、调用上限和输出 token 上限，减少资源差异对组织比较的混淆。独立评分只使用可见训练/伪任务检查来选择最终答案；隐藏测试答案只进入隔离评分路径。</p>
<div class="callout"><strong>当前解释边界：</strong>工程通过和提示格式有效，不等于数学正确、插补准确或群体涌现。Phase B 仍在运行，不能据此宣称任何架构更强。</div>
</section>

<section id="design">
<h2>七个匹配对照臂</h2>
<table><thead><tr><th scope="col">对照臂</th><th scope="col">操作机制</th><th scope="col">主要隔离的因素</th></tr></thead><tbody>{arms}</tbody></table>
<h3>冻结预算与抽样</h3>
<ul class="steps">
  <li><strong>ARC-AGI-2：</strong>官方评估集 120 题中，按预先写定的 SHA-256 规则盲选 40 题；不按模型难度或结果分层。</li>
  <li><strong>愈伤插补：</strong>使用既有基准中的 36 道冻结任务；输入模型的提示以公开字段构造，答案键留在私有评分端。</li>
  <li><strong>匹配上限：</strong>每个任务—对照臂最多 8 次逻辑调用、总计 262,144 个生成/推理 token；多调用臂单次最多 32,768。单次长思考臂只发 1 次，单次有效上限为 262,144。</li>
  <li><strong>模型与重复：</strong>统一使用 <code>deepseek-flash</code>，种子 1000，每任务每臂一个运行实例；ARC-AGI-2 推理 effort 为 low，愈伤插补为 medium。早停后的未用预算不补造。</li>
</ul>
<p class="small">官方 DeepSeek 文档当前列出 <code>deepseek-flash</code> 最大输出 384K；本研究 262,144 单次请求上限由任务总预算约束，低于服务上限。HTTP 429 作为速率限制响应处理；金额估计仅记录，不作停止门槛。模型服务规格可能更新，应以运行日期对应的官方文档为准。</p>
</section>

<section id="evidence">
<h2>已经取得的工程证据</h2>
<ul class="steps">{tests}</ul>
<p><strong>端到端预检：</strong>{escape(data['validation']['preflight_transport_issue'])}</p>
<p><strong>测试：</strong><span class="mono">{escape(data['validation']['test_command'])}</span></p>
<p><strong>源码提交：</strong>{commits}</p>
<p class="small">主分支基点：<code>{escape(data['base_commit'])}</code>。记录与参考答案相互隔离；运行时 API key 仅来自本地进程环境，不进入 Git、任务参数或报告。</p>
</section>

<section id="run">
<h2>本轮运行记录</h2>
<table><tbody>
<tr><th scope="row">运行编号</th><td><code>{escape(run['run_id'])}</code></td></tr>
<tr><th scope="row">启动时间</th><td>{escape(run['started_at'])}</td></tr>
<tr><th scope="row">提交后状态</th><td>{escape(run['results_at_report_snapshot'])}</td></tr>
<tr><th scope="row">任务臂规模</th><td>{run['task_arm_records']} 条任务—对照臂记录：40 × 7 个 ARC 条件与 36 × 7 个愈伤条件。</td></tr>
<tr><th scope="row">状态拆分</th><td>{snapshot['settled']} 条已结算（{snapshot['settled_stop_reasons']['arc_train_perfect']} 条 visible train-perfect，{snapshot['settled_stop_reasons']['planned_calls_or_tokens_exhausted']} 条 calls/tokens 上限）；{snapshot['unknown_started']} 条 dispatch 结果未知；{snapshot['started_unsettled']} 条已启动但未结算；{snapshot['not_started_or_pending']} 条尚未启动/pending。未知与未启动项保留在分母；未知请求不会重发。</td></tr>
<tr><th scope="row">ARC 样本配对核查</th><td>Phase B 控制清单与 Amendment 3 指定的发育臂清单都是 40 题，但只重合 {pairing['overlap_count']} 题，完整清单不同。因此这次 Phase B 可在自身七臂间比较，不能与发育臂结果作逐题配对比较。清单哈希：控制 <code>{escape(pairing['control_manifest_sha256'])}</code>；发育参考 <code>{escape(pairing['developmental_id_list_sha256'])}</code>。</td></tr>
<tr><th scope="row">隔离评分作业</th><td>Slurm <code>{escape(run['evaluator_job_id'])}</code>，运行于 {escape(run['evaluator_node'])}；8 CPU、32 GB 内存、0 GPU。</td></tr>
<tr><th scope="row">受保护状态</th><td>既有作业 {', '.join(escape(str(j)) for j in run['existing_jobs_left_untouched'])} 未更改。预检阶段付费模型调用为 {run['preflight_model_calls']}。</td></tr>
<tr><th scope="row">冻结清单</th><td>ARC-40 manifest SHA-256 <code>{escape(run['arc_manifest_sha256'])}</code><br>Callus public prompt manifest SHA-256 <code>{escape(run['callus_prompt_manifest_sha256'])}</code></td></tr>
</tbody></table>
<h3>独立评分和统计计划</h3>
<p>生成停止后，先运行已有隐藏答案隔离路径进行评分，再计算每臂平均表现及相对 independent 的任务配对差；按任务实例 bootstrap 10,000 次并报告区间。失败或未评分实例留在分母，得分记零并另行报告未评分数。由于每臂仅一个初始化，区间只作探索性描述，不能替代同一任务上的独立群体重复。</p>
</section>

<section id="limits">
<h2>结论边界与下一步</h2>
<ul class="steps">{limitations}</ul>
<div class="decision"><strong>下一步条件：</strong>本运行自然结束后只评分、审计和汇总，不重新派发模型请求。因 Amendment 3 的 ARC 样本不一致，不能把当前控制臂和发育臂合并成逐题配对效应；若需要该结论，须另立冻结且任务清单一致的运行。解释稳定组织效应还需要多个独立初始化群体和与发育机制相配套的消融证据。</div>
<h3>完成状态</h3>
<p><strong>可设计：</strong>已具备。<strong>可实现：</strong>已实现并通过本地测试。<strong>当前已运行：</strong>Phase B detached 试验仍在进行。<strong>可解释科学效果：</strong>当前不可；需全量结算、隐藏评分，且与发育臂的 task pairing 缺口须先解决或明确保留为限制。</p>
</section>

<section id="sources"><h2>来源与可追溯材料</h2><ul>{source_list}</ul>
<p>核心文件：<a href="../docs/p2-control-arms-v1.md">冻结对照协议及 Amendment 3 配对审计</a>；<a href="../plans/arc2-pilot40-v1.json">当前控制臂 ARC-40 manifest</a>；<a href="../plans/arc2-pilot40-developmental-pairing-reference-v1.json">发育臂 ARC-40 配对参考清单</a>；<a href="../plans/callus-public-prompt-hashes-v1.json">Callus 提示哈希清单</a>；<a href="../tools/analyze_p2_controls.py">配对分析程序</a>。</p>
</section>

<footer>由仓库中的 <code>tools/build_m2_14_p2_report.py</code> 从此 HTML 同目录的结构化 JSON 生成。报告冻结了本次提交时的状态快照；运行中的结果不在本页面被动态轮询或推断。</footer>
</main></body></html>
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("milestones/m2-14-p2-control-arms-v1.json"))
    parser.add_argument("--output", type=Path, default=Path("milestones/m2-14-p2-control-arms-v1.html"))
    args = parser.parse_args()
    args.output.write_text(render(json.loads(args.source.read_text())), encoding="utf-8")


if __name__ == "__main__":
    main()
