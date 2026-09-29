#!/usr/bin/env python3
"""Render the frozen SLCW source audit without network or browser access."""
import argparse
import hashlib
import html
import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEM = "milestones/m2-6-slcw-realignment-v2"


def read(path):
    return json.loads((ROOT / path).read_text())


def esc(value):
    return html.escape(str(value), quote=True)


def refs(cell):
    return " ".join(f'<a href="#source-{esc(s)}">[{esc(s)}]</a>' for s in cell["sources"])


def paragraph(cell):
    return f'<p>{esc(cell["text"])} {refs(cell)}</p>'


def render(data, sources, evidence, qa):
    md = [f'# {data["title"]} · v2', "", data["outcome"], "", data["claim_boundary"], "",
          "Current plan: [population-plan-v2.md](population-plan-v2.md). "
          "Human report: [M2.6 v2](../milestones/m2-6-slcw-realignment-v2.html).", "",
          "Source IDs resolve to the hashed inventory below. Adaptations and acceptance criteria are proposals, not implemented behavior.", ""]
    cards = []
    for row in data["rows"]:
        md.extend([f'## {row["id"]} · {row["title"]} ({row["version"]})', "",
                   "| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |",
                   "|---|---|---|---|---|"])
        cells = [row[k]["text"] + " " + " ".join(f'[{s}](#source-{s.lower()})' for s in row[k]["sources"])
                 for k in ("original", "workflow", "aimeth")]
        cells += [row["adaptation"], row["acceptance"] + " 缺口：" + row["status"]]
        md.extend(["| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |", ""])
        cards.append(f'''<article id="{esc(row['id'])}" class="mechanism">
<header><span class="eyebrow">{esc(row['id'])} · {esc(row['version'])}</span><h3>{esc(row['title'])}</h3><p class="status">{esc(row['status'])}</p></header>
<div class="mapping"><section><h4>原设计</h4>{paragraph(row['original'])}</section>
<section><h4>现有实现</h4><p class="label">0013-Workflow</p>{paragraph(row['workflow'])}<p class="label">AIMeth</p>{paragraph(row['aimeth'])}</section>
<section><h4>数学任务适配 · 提案</h4><p>{esc(row['adaptation'])}</p><h4>需要留下的验收证据</h4><p>{esc(row['acceptance'])}</p></section></div></article>''')
    source_html = []
    md += ["## 来源与代码身份", "", "Private Workflow files are identified by relative path and SHA-256; they are not redistributed. Hashes attest bytes, not successful execution.", ""]
    for s in sources["sources"]:
        identity = esc(s["identity"])
        link = esc(s["path"])
        if s["scope"] == "aimeth":
            link = f'<a href="https://github.com/boshengli/aimeth/blob/{esc(s["identity"])}/{esc(s["path"])}">{link}</a>'
        source_html.append(f'<li id="source-{esc(s["id"])}"><strong>{esc(s["id"])} · {esc(s["scope"])}</strong><p class="path">{link}</p><p>核对行：{esc(s["inspected_lines"])} · {s["bytes"]} bytes</p><p class="hash">SHA-256 {esc(s["sha256"])}</p><p>{identity}</p></li>')
        md += [f'<a id="source-{s["id"].lower()}"></a>', f'**{s["id"]} · {s["scope"]}** — `{s["path"]}`; lines {s["inspected_lines"]}; {s["bytes"]} bytes; SHA-256 `{s["sha256"]}`; identity `{s["identity"]}`.', ""]
    gates = "".join(f'<li><h3>{esc(g["id"])} · {esc(g["name"])}</h3><p>{esc(g["requirement"])}</p><p class="muted">验收：{esc(g["evidence"])} · 当前：{esc(g["state"])}</p></li>' for g in data["admission"]["gates"])
    needs = "".join(f'<tr><th scope="row">{esc(r["request"])}</th><td>{esc(r["response"])}</td><td>{esc(r["evidence"])}</td><td>{esc(r["gap"])}</td></tr>' for r in data["requirements"])
    links = "".join(f'<a href="#{esc(r["id"])}">{esc(r["id"])} {esc(r["title"])}</a>' for r in data["rows"])
    document = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><title>M2.6 v2 · SLCW 设计对照</title>
<style>
:root{{color-scheme:light dark;--bg:#f3f5f4;--paper:#fff;--text:#182f36;--muted:#50656b;--line:#cad7d8;--accent:#086d6b;--tint:#e4f2ee;--warn:#fff1d7}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.75 system-ui,-apple-system,"PingFang SC",sans-serif}}main{{max-width:1420px;margin:auto;padding:40px 30px 80px}}a{{color:var(--accent);text-underline-offset:3px}}a:focus-visible{{outline:3px solid var(--accent);outline-offset:3px}}h1{{font-size:clamp(28px,4vw,48px);line-height:1.3;max-width:950px}}h2{{font-size:27px;margin:48px 0 16px}}h3{{margin:6px 0 12px;font-size:21px}}h4{{margin:0 0 8px}}p{{margin:8px 0 16px}}.eyebrow,.label{{font-weight:700;color:var(--accent);font-size:14px}}.hero,.mechanism,.panel{{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:24px;margin:18px 0}}.hero{{border-top:7px solid var(--accent)}}.lead{{font-size:21px;max-width:1050px}}.muted,.status{{color:var(--muted)}}.note{{padding:16px 20px;background:var(--tint);border-radius:8px}}.warning{{background:var(--warn)}}nav,.jump{{display:flex;flex-wrap:wrap;gap:8px 20px;margin:20px 0}}nav a{{font-weight:650}}.jump a{{font-size:14px}}.mapping{{display:grid;grid-template-columns:0.9fr 1.25fr 1.05fr;gap:24px;border-top:1px solid var(--line);padding-top:20px}}.mapping section+section{{border-left:1px solid var(--line);padding-left:24px}}.mapping p{{font-size:15px}}.label{{margin-top:10px;margin-bottom:3px}}.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;min-width:760px;font-size:15px}}th,td{{padding:14px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}thead{{background:var(--tint)}}.gates{{padding-left:24px}}.gates li{{padding:10px 0}}.sources{{padding-left:24px}}.sources li{{margin:24px 0}}.path,.hash,code{{overflow-wrap:anywhere;word-break:break-word}}.hash{{font:12px/1.8 ui-monospace,monospace}}.sources p{{font-size:13px;margin:4px 0}}article,section,li{{scroll-margin-top:20px}}footer{{margin-top:45px;border-top:1px solid var(--line);padding-top:18px}}
@media(prefers-color-scheme:dark){{:root{{--bg:#112026;--paper:#182a31;--text:#e3efef;--muted:#aec3c7;--line:#36515b;--accent:#83d3c2;--tint:#213e3f;--warn:#453824}}}}
@media(max-width:850px){{main{{padding:20px 14px 50px}}.hero,.mechanism,.panel{{padding:18px}}.mapping{{grid-template-columns:1fr;gap:14px}}.mapping section+section{{border-left:0;border-top:1px solid var(--line);padding:16px 0 0}}.lead{{font-size:18px}}h2{{font-size:24px}}}}
@media print{{:root{{--bg:white;--paper:white;--text:black;--muted:#333;--line:#bbb;--accent:#174c50;--tint:#eee;--warn:#eee}}body{{font-size:11pt}}main{{max-width:none;padding:0}}nav,.jump{{display:none}}.mapping{{display:block}}.mapping section+section{{border-left:0;padding-left:0}}.hero,.mechanism,.panel{{border-radius:0;padding:12px}}h2,h3,h4{{break-after:avoid}}p{{orphans:3;widows:3}}table{{min-width:0;font-size:9pt}}a{{text-decoration:none}}}}
</style></head><body><main>
<header class="hero"><p class="eyebrow">AIMeth · M2.6 · v2 · {esc(data['date'])}</p><h1>从原始组织设计<br>到可检验的群体数学系统</h1><p class="lead">{esc(data['outcome'])}</p><p class="muted">{esc(data['question'])}</p><p>{esc(data['claim_boundary'])}</p></header>
<nav aria-label="报告导航"><a href="#decision">当前决定</a><a href="#mapping">16 项机制对照</a><a href="#gates">实验准入</a><a href="#requirements">要求与证据</a><a href="#readiness">下一步</a><a href="#audit">验证边界</a><a href="#sources">来源</a></nav>
<section id="decision"><h2>单 Agent 成功前提已撤掉</h2><div class="panel"><p>单 Agent 运行：<strong>不要求</strong>。单 Agent 解题成功：<strong>不要求</strong>。小群体先取得数学成功再扩规模：<strong>不要求</strong>。单 Agent 可作为预先登记、等预算的可选参照。</p><p>{esc(data['gate_note'])}</p><p><a href="../docs/population-plan-v2.md">当前计划 v2</a> · <a href="../docs/slcw-math-mapping-v2.md">完整 Markdown 对照</a> · <a href="../docs/slcw-math-mapping-v2.json">结构化矩阵与门槛</a> · <a href="../docs/research-plan-status.json">计划替代索引</a></p><p class="muted">旧 M2.5 提案与历史 3/4、32/32 格式门槛保持原文与原分母；当前入口改用 v2。新准入合约尚未接入一个完整的 SLCW 运行器，不能据此声称新运行器已经通过验收。</p></div><p class="note">{esc(data['counting_note'])}</p></section>
<section id="mapping"><h2>逐项对照：已有什么，还要补什么</h2><p>中列区分两个项目及多条来源实现。右列是数学适配提案及验收要求，均不表示已完成。来源编号可直接跳到哈希清单。</p><div class="jump">{links}</div>{''.join(cards)}</section>
<section id="gates"><h2>留下的门槛只服务于实验有效性</h2><p>无需成功解出某道题才允许研究群体。仍需防止一次无法解释、无法恢复或无法评价的运行消耗研究预算。</p><ol class="gates">{gates}</ol></section>
<section id="requirements"><h2>用户要求、交付与缺口</h2><div class="table-wrap"><table><thead><tr><th>要求</th><th>本次交付</th><th>证据</th><th>仍缺</th></tr></thead><tbody>{needs}</tbody></table></div></section>
<section id="readiness"><h2>下一步是实现群体闭环</h2><div class="panel"><p><strong>可以进入：</strong>按当前计划实现 V1 的区域监视、Chief 合成与异议链，再补 V2 的 Patterning、Interface、Vascular、候选收获、三 Chief 和局部重算。先用确定性 fixture 核对执行语义，不要求单 Agent 数学通过。</p><p><strong>尚不能声称：</strong>两版数学组织已经跑通、已完成有效比较、具备 10K 实际推理或已出现高阶能力。完整架构比较与 Patterning×Vascular 消融分开冻结；每次群体独立初始化，成本包含所有治理、工具和重试。</p><p>主要产出由群体合成并独立检查；数学错误、无收益和未完成义务同样进入结果。Navier–Stokes 探索与可判定的数学控制任务分开报告。</p><p>{esc(data['gpu_note'])}</p></div></section>
<section id="audit"><h2>证据与验证边界</h2><p>代码核对基线：<code>{esc(data['baseline_commit'])}</code>。交付提交由 Git 历史记录，不能与核对基线混为一谈。本轮模型调用：{evidence['new_model_calls']}；本轮集群提交：{evidence['new_cluster_jobs']}。</p><p>静态验证检查结构、来源编号、离线资源、锚点、文件链接和可重复生成；根 <a href="../slcw-alignment-v2-manifest.json">manifest</a> 校验新增快照。它们不构成视觉验收或数学证明。</p><p class="note warning">浏览器视觉 QA 尚未完成：{esc(qa['blocker_zh'])} 桌面、窄屏与交互检查均记为 NOT_CHECKED；本报告内容已交付，里程碑的视觉验收仍开放。</p><p><a href="m2-6-slcw-realignment-v2.evidence.json">核对记录</a> · <a href="m2-6-slcw-realignment-v2.browser-qa.json">浏览器 QA 状态</a> · <a href="m2-6-slcw-realignment-v2.sources.json">来源身份清单</a> · <a href="m2-6-slcw-realignment-v1.html">保留的 v1</a></p><p class="muted">0013 私有来源只公布路径、行范围和哈希，不转存内容；外部审阅者复核这些源码需获得授权访问。哈希证明字节身份，不证明代码曾成功运行。生物学论文结论本轮未重新核验。</p></section>
<section id="sources"><h2>来源与代码身份</h2><ol class="sources">{''.join(source_html)}</ol></section>
<footer><p>AIMeth · 本版完整替代当前计划入口，不覆盖历史协议、分数与报告。所有核心内容均可离线阅读，无外部脚本或字体。</p></footer></main></body></html>\n'''
    return "\n".join(md), document


class AuditHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.tags = [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append(tag)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "href" in attrs:
            self.links.append(attrs["href"])
        if "src" in attrs or tag in ("script", "iframe"):
            raise ValueError("The audit report must have no external runtime resources")


def validate(data, sources, document):
    ids = {s["id"] for s in sources["sources"]}
    assert len(ids) == len(sources["sources"])
    assert len({r["id"] for r in data["rows"]}) == 16
    for r in data["rows"]:
        for field in ("original", "workflow", "aimeth"):
            assert r[field]["text"] and r[field]["sources"]
            assert set(r[field]["sources"]) <= ids
        assert r["adaptation"] and r["acceptance"] and r["status"]
    for key in ("single_agent_success_required", "single_agent_run_required", "small_population_math_success_required_for_scaling"):
        assert data["admission"][key] is False
    for s in sources["sources"]:
        if s["scope"] == "aimeth":
            raw = (ROOT / s["path"]).read_bytes()
            assert len(raw) == s["bytes"] and hashlib.sha256(raw).hexdigest() == s["sha256"], s["id"]
    parser = AuditHTML()
    parser.feed(document)
    assert len(parser.ids) == len(set(parser.ids)), "Duplicate HTML ID"
    for link in parser.links:
        if link.startswith("#"):
            assert link[1:] in parser.ids, link
        elif not link.startswith("https://"):
            assert (ROOT / "milestones" / link).is_file(), link


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Check committed output bytes and static contracts")
    args = parser.parse_args()
    data = read("docs/slcw-math-mapping-v2.json")
    sources = read(STEM + ".sources.json")
    evidence = read(STEM + ".evidence.json")
    qa = read(STEM + ".browser-qa.json")
    markdown, document = render(data, sources, evidence, qa)
    products = {"docs/slcw-math-mapping-v2.md": markdown, STEM + ".html": document}
    for path, content in products.items():
        if args.check:
            assert (ROOT / path).read_text() == content, f"Generated artifact differs: {path}"
        else:
            (ROOT / path).write_text(content)
    # The manifest is built after initial rendering, then required by --check.
    if args.check:
        validate(data, sources, document)
    print(json.dumps({"mode": "check" if args.check else "build", "mechanisms": len(data["rows"]), "sources": len(sources["sources"]), "browser_used": False, "result": "PASS"}))


if __name__ == "__main__":
    main()
