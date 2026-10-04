#!/usr/bin/env python3
"""Build the versioned submission snapshot; never contacts a model or browser."""
from pathlib import Path
import argparse,html,json
ROOT=Path(__file__).resolve().parents[1]

def render(e):
    esc=html.escape
    rows=''.join('<tr><th>'+esc(k)+'</th><td>'+esc(str(v))+'</td></tr>' for k,v in [
        ('分析 Agent','100 组 × 100 = 10,000'),('治理角色','400 Observer + 100 组 Chief + 1 全局 Chief'),
        ('计划调用','两轮，共 21,002 个调用槽'),('最大并发','16；不等于逻辑 Agent 数'),
        ('模型','DeepSeek-V4-Flash-0731；本节点独立服务'),('资源上限','8 张 H20，作业 8 小时 30 分钟，群体执行至多 8 小时'),
        ('Slurm 作业',e['job_id']),('观察状态',e['job_state']),('模型状态',e['model_status']),
        ('已观察模型响应',e['observed_model_responses']),('SSH',e['ssh_status'])])
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>M2.7 · 直接 10K 首轮</title><style>
+*{{box-sizing:border-box}}body{{margin:0;background:#f2f5f3;color:#183236;font:17px/1.75 system-ui,-apple-system,"PingFang SC",sans-serif}}main{{max-width:1000px;margin:auto;padding:36px 24px 70px}}header,section{{background:white;border:1px solid #cfddda;border-radius:12px;padding:24px;margin:18px 0}}header{{border-top:7px solid #08796c}}h1{{font-size:38px;line-height:1.3}}h2{{font-size:24px}}p{{margin:12px 0}}a{{color:#076d63}}.big{{font-size:22px}}.note{{background:#fff1d7;padding:14px;border-radius:8px}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;vertical-align:top;border-bottom:1px solid #dae5e2;padding:12px}}th{{width:28%}}code{{overflow-wrap:anywhere;font-size:13px}}small{{color:#506766}}@media(max-width:620px){{main{{padding:12px}}header,section{{padding:17px}}h1{{font-size:29px}}th{{width:34%}}body{{font-size:16px}}}}@media print{{body{{background:white;font-size:11pt}}main{{max-width:none;padding:0}}header,section{{border:0;padding:10px 0}}h2{{break-after:avoid}}}}
+</style></head><body><main><header><small>AIMeth · M2.7 · v1 · {esc(e['snapshot_time'])}</small><h1>直接上 10K，首轮已提交</h1><p class="big">GPU08 作业 <strong>{e['job_id']}</strong> 已取得 8 张 H20；先获得本账号作业，再 SSH 的路径已验证。</p><p>{esc(e['outcome'])}</p><p><a href="#run">实际提交</a> · <a href="#mechanism">组织机制</a> · <a href="#evidence">证据与限制</a> · <a href="#next">接下来</a></p></header>
+<section id="run"><h2>这次具体跑什么</h2><table>{rows}</table><p>探索无外力、R³、光滑快速衰减无散初值的 Navier–Stokes 问题。收集精确引理、反证、证明义务及群体候选；数学错误、分歧和未收敛都保留。</p><p>单 Agent 解题成功、N8/N32/N128 阶梯、完整 V2 实现均不再阻挡本轮。此处是一整个群体运行，阶段子run不能作为独立统计重复。</p></section>
+<section id="mechanism"><h2>两轮群体闭环</h2><p>10,000 分析 Agent → 400 区域 Observer → 100 组 Chief → 全局 Chief → 反馈修订 → 第二轮治理。</p><p>固定30%发送者抽样向同组10×10邻居发送候选；下一轮实际接收自身、邻居、区域、组及全局反馈。四个等分区域与跨组Chief是本次数学适配。原有日志底座保持不变，新驱动冻结跨阶段内容与源事件哈希。</p><p>COLOR/QUARANTINE仅为模型协调标注；固定两轮，不实现完整申诉状态机或V2动态治理。完整响应保留，消息按预算截断并标记，异议与未完成义务优先进入消息。</p></section>
+<section id="evidence"><h2>已验证与尚未验证</h2><p>本地完整规模回放完成 <strong>21,002 个模拟调用</strong>、10,000个分析身份、8阶段；不是模型推理。100项仓库测试通过，包括新增预算竞争、恢复不重复派发、来源篡改拒绝和失败输入进入Observer的测试。</p><p>首次模拟回放完成10,000步后因冗余全库检查停下修正，原记录保留。新版逐run检查全部事件链与引用，完整投影检查每阶段抽一个子run；不声称完整投影已逐一检查。</p><p>独立数学验证、组织优势、完整V2与正式统计比较均未完成。{esc(e['limitations'])}</p><p class="note">HTML已做静态结构与可重复生成检查；此前浏览器策略禁止视觉复核，桌面与窄屏视觉验收仍为未完成，本轮未绕过。</p><p>执行源：<code>{esc(e['source_commit'])}</code><br>执行包 SHA-256：<code>{esc(e['bundle_sha256'])}</code><br>报告交付提交由Git记录，与执行源分别保存。</p><p><a href="../docs/direct-10k-v1.md">当前计划</a> · <a href="../examples/slcw-direct-10k-v1.json">冻结配置</a> · <a href="../reports/direct-10k-readiness-v1.json">完整规模工程证据</a> · <a href="../reports/direct-10k-v1/submission.json">提交观察</a> · <a href="../docs/slcw-math-mapping-v2.md">原设计对照</a></p></section>
+<section id="next"><h2>接下来只围绕实际运行推进</h2><p>模型服务就绪后脚本自动启动群体。按实际响应、预算、失败和未启动分母更新下一版结果；当前报告是带时间戳的提交快照，不是实时页面。</p><p>连续5次传输错误、预算或时间上限触发预声明停止。已发生调用不被删除或退款；改代码、模型或配置须另立版本。全部候选仍需独立数学核验。</p></section></main></body></html>\n'''.replace('\n+','\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    evidence=json.loads((ROOT/'reports/direct-10k-v1/submission.json').read_text())
    content=render(evidence);target=ROOT/'milestones/m2-7-direct-10k-v1.html'
    if a.check:
        assert target.read_text()==content
        from html.parser import HTMLParser
        class Check(HTMLParser):
            def __init__(self):super().__init__();self.ids=set();self.links=[]
            def handle_starttag(self,tag,attrs):
                d=dict(attrs)
                if 'id' in d:self.ids.add(d['id'])
                if 'href' in d:self.links.append(d['href'])
                assert tag not in ('script','iframe') and 'src' not in d
        c=Check();c.feed(content)
        for link in c.links:
            assert link[1:] in c.ids if link.startswith('#') else (target.parent/link).exists()
    else:target.write_text(content)
    print('PASS: deterministic offline submission report; browser not used')
if __name__=='__main__':main()
