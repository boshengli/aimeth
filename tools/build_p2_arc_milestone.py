"""Build a standalone, source-backed P2 ARC milestone HTML report."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path


def tag(value):
    return escape(str(value))


def provider_row(name, record):
    return ("<tr><th scope='row'>" + tag(name) + "</th>"
            + "<td>" + tag(record["settled"]) + "/" + tag(record["planned_v2"]) + "</td>"
            + "<td>" + tag(record["http_statuses"].get("200", 0)) + "</td>"
            + "<td>" + tag(record["programs_extracted"]) + "</td>"
            + "<td>" + tag(record["execution_ok"]) + "</td>"
            + "<td>" + tag(record["sample_successes"]) + "</td>"
            + "<td>" + tag(record["task_pass_at_4_count"]) + "</td>"
            + "<td>" + tag(record["conservative_estimated_cny"]) + "</td></tr>")


def build(summary_path: Path, output: Path, baseline_commit: str, implementation_commit: str):
    data = json.loads(summary_path.read_text())
    ready = bool(data["complete"] and data.get("pilot"))
    status = "校准完成；40 题 pilot 清单已冻结" if ready else "校准仍在进行或选题条件未满足"
    rows = "".join(provider_row(k, v) for k, v in data["providers"].items())
    pilot = data.get("pilot")
    pilot_text = (f"{pilot['count']} 题；合格候选 {pilot['eligible_count']} 题；清单哈希 <code>{tag(pilot['manifest_sha256'])}</code>"
                  if pilot else "尚未形成符合事先条件的 40 题冻结清单。")
    negatives = []
    for name, record in data["providers"].items():
        length = record["finish_reasons"].get("length", 0)
        if length:
            negatives.append(f"{name} 有 {length} 次以长度上限结束；不能把 HTTP 200 当作有效程序。")
        if record["transport_unknown"]:
            negatives.append(f"{name} 有 {record['transport_unknown']} 次发送后状态不明；未自动重发。")
    negative_html = "".join("<li>" + tag(x) + "</li>" for x in negatives) or "<li>未见传输未知或长度截断。</li>"
    created = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIMeth M2.12 · ARC P2 校准 v1</title>
<style>
:root{{--ink:#17233d;--muted:#53627a;--line:#dce4ee;--blue:#1c5c9d;--pale:#f2f7fc}}
*{{box-sizing:border-box}}body{{margin:0;font:16px/1.68 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:var(--ink);background:#fff}}
header{{background:#12223e;color:#fff;padding:2.8rem max(1.25rem,calc((100vw - 1060px)/2)) 2.3rem}}header p{{max-width:840px;color:#dce9f7}}h1{{font-size:clamp(1.85rem,4vw,2.75rem);line-height:1.2;margin:.4rem 0}}
nav{{border-bottom:1px solid var(--line);padding:.7rem max(1.25rem,calc((100vw - 1060px)/2));display:flex;gap:1rem;flex-wrap:wrap}}a{{color:var(--blue)}}nav a{{font-weight:600}}
main{{max-width:1060px;margin:auto;padding:2rem 1.25rem 4rem}}section{{margin:0 0 2.2rem}}h2{{font-size:1.45rem;line-height:1.3;border-bottom:1px solid var(--line);padding-bottom:.35rem}}
.lead{{font-size:1.17rem;max-width:860px}}.note{{border-left:4px solid var(--blue);background:var(--pale);padding:1rem 1.2rem;margin:1.2rem 0}}.muted{{color:var(--muted)}}
.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;min-width:700px}}th,td{{border-bottom:1px solid var(--line);padding:.6rem .55rem;text-align:left;vertical-align:top}}thead th{{background:var(--pale)}}
code{{overflow-wrap:anywhere}}ul{{padding-left:1.35rem}}li{{margin:.35rem 0}}footer{{border-top:1px solid var(--line);padding:1.5rem 1.25rem;color:var(--muted)}}
@media(max-width:520px){{header{{padding:2rem 1.25rem}}main{{padding-top:1.2rem}}body{{font-size:15px}}}}
@media print{{header{{background:#fff;color:#000;padding:0}}header p{{color:#333}}nav{{display:none}}main{{padding:0}}a{{color:#000;text-decoration:none}}}}
</style></head><body>
<header><div class="muted" style="color:#bcd3ec">AIMeth · M2.12 · v1 · {tag(created)}</div><h1>ARC P2 难度校准与进化对照</h1><p>{tag(status)}</p></header>
<nav aria-label="报告导航"><a href="#outcome">结论</a><a href="#evidence">实际证据</a><a href="#mapping">需求对照</a><a href="#limits">解释边界</a><a href="#next">下一阶段</a></nav>
<main>
<section id="outcome"><h2>结论与范围</h2><p class="lead">本里程碑实现了 ARC 题目加载、受限程序执行、精确评分、双模型单程序校准，以及不含空间与分化机制的进化搜索对照。下表报告的是单模型程序成功率，不能据此推断多 Agent 组织优势。</p>
<div class="note"><strong>P2 pilot：</strong>{pilot_text}</div></section>
<section id="evidence"><h2>实际证据</h2><div class="scroll"><table><thead><tr><th>模型</th><th>结算 / 计划</th><th>HTTP 200</th><th>提取程序</th><th>可执行</th><th>成功样本 / 1600</th><th>pass@4 任务 / 400</th><th>保守估计 ¥</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="muted">估算费用采用官方公开的高峰、未缓存输入和输出单价，以及内部 10 元/美元安全换算。它是上界式预算记录，非提供商已核对账单；各家上限 300 元。</p>
<p>原始请求和完整响应、usage、延迟、失败与未知状态保存在访问受限的本地追加式回执中。公开表仅含汇总、任务 ID 和哈希。</p></section>
<section id="mapping"><h2>用户要求与交付</h2><div class="scroll"><table><thead><tr><th>要求</th><th>实施及证据</th><th>未解决</th></tr></thead><tbody>
<tr><td>两条分支推送与独立开发分支</td><td>源分支分别推送；开发基于 <code>{tag(baseline_commit)}</code>，实现提交 <code>{tag(implementation_commit)}</code></td><td>报告交付提交见相邻版本记录</td></tr>
<tr><td>ARC 评测器</td><td>400 题加载、测试答案隔离、最多两次候选输出的精确评分、2 秒受限执行及单元测试</td><td>沙箱不是敌对代码安全性的形式证明</td></tr>
<tr><td>双模型四次采样</td><td>同一题集、提示与思考配置；每次独立请求均有回执；CSV 含模型内 pass@1 与 pass@4</td><td>模型权重摘要与训练污染未知</td></tr>
<tr><td>40 题 pilot 与其余题保留</td><td>预定 20%–60% 难度区间、输入面积分层、确定性哈希择题</td><td>保留题已参与难度探测，非全程未触碰的测试集</td></tr>
<tr><td>进化搜索对照</td><td>同一 transform 表达、训练对评分、显式 LLM 调用总预算；仅两题冒烟</td><td>尚无正式进化对照或组织效应估计</td></tr>
</tbody></table></div></section>
<section id="limits"><h2>负面结果与科学解释</h2><ul>{negative_html}</ul><p>最初 DeepSeek 8,192-token 配置的一个请求全部用于思考，没有最终程序，独立保留为失败探测。早期评分器对普通局部变量和合法 NumPy 操作过严；初版评分留档，最终全部回执按修正后的同一规则重新评分。模型请求成功、程序可执行和测试通过为三个不同层次。</p></section>
<section id="next"><h2>下一阶段就绪度</h2><p>ARC 工程接口可供后续设计；pilot 清单只有在两家各 1,600 次结算且不少于 40 题满足预定难度时才可用于 P2 组织试验。确认性组织比较仍需独立群体重复、预算匹配和预先冻结的对照。数学或生物学能力的涌现尚未从本次校准得到证明。</p>
<p class="muted">数据包 SHA-256：<code>a87291143a4d5206cb5264eeb280a1b9c367e3523a992f4eff5702265471dbac</code>。源协议：<a href="../docs/p2-arc-calibration-protocol-v1.md">P2 ARC 协议</a>。价格与接口依据：<a href="https://api-docs.deepseek.com/quick_start/pricing/">DeepSeek 官方</a>、<a href="https://docs.z.ai/guides/overview/pricing">Z.AI 官方</a>。</p></section>
</main><footer>版本化研究报告 · 生成时间 {tag(created)} · AIMeth</footer></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html)
    digest = sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(digest + "\n")
    return {"html": str(output), "sha256": digest, "ready": ready}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--baseline-commit", required=True)
    p.add_argument("--implementation-commit", required=True)
    args = p.parse_args()
    print(json.dumps(build(args.summary, args.output, args.baseline_commit, args.implementation_commit)))


if __name__ == "__main__":
    main()
