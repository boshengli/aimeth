# 背景与交接原型审计

审计日期：2026-09-14。范围：本地交接包、PDF 第 1–2 页视觉核对、全文文本关键词检索、原型源代码和若干一手网页。未逐页验证 166 页证明，未编译公开 Lean 仓库，未运行 H20/Slurm/vLLM。

## 1. 来源与权威边界

当前用户要求是开展研究并完成第一步。附件 `NEXT_AGENT_PROMPT.md`、`SKILL.md` 和对话摘要是历史材料；没有执行其中的 `sbatch`、没有安装附带 skill，也没有把其中参数提升为已验证最优值。

交接清单的 21 个 SHA-256 全部匹配。单独提供的 PDF 与包内副本一致：`0e779481c4da40bd28d1e642e1d8ca57447d129610df28dfa5a11e9af8ae228f`。这证明收到的副本一致，不证明外部来源真实性或数学正确性。工具显示 PDF 共 166 页；3 个 Python 文件通过 AST 语法检查，2 个 shell 文件通过 `bash -n`。结果见 `reports/handoff-audit.json`。

## 2. 已核验的外部背景

| 来源 | 本次可支持的陈述 | 证据边界 |
|---|---|---|
| [OpenAI 公告，2026-09-08](https://openai.com/index/navier-stokes-solution/) | 作者报告约 10K Agent，并描述分组、跨组信息汇总和运行中更新模型 | 作者自述；不是控制实验，不能证明规模/拓扑必要性 |
| [Clay 公告，2026-09-11](https://www.claymath.org/news/navier-stokes-announcement/) | Clay 讨论了问题看来已解决的公告，并说明评估与归属过程将审慎进行 | 不是本项目独立证明验证或奖项已完成裁决 |
| [Fefferman 官方问题陈述](https://www.claymath.org/wp-content/uploads/2022/06/navierstokes.pdf) | A/B 为无外力正则性方向；C/D 允许合条件外力的 breakdown 方向 | 目标与函数空间必须完整保存，不能混称不同变体 |
| [OpenAI 形式化仓库](https://github.com/openai/NavierStokesAndEuler) | 公开了伴随材料与构建说明 | 本次只读 README；没有核查所有公理或成功重建 |
| [Kim et al., arXiv:2512.08296v3](https://arxiv.org/abs/2512.08296v3) | 已有对单 Agent、独立、中心化、去中心化、混合结构的对照研究 | 预印本；本次读摘要和系统/方法相关部分，未复算结果；不能外推为前沿 PDE 的 10K 定律 |
| [vLLM reproducibility 文档](https://docs.vllm.ai/en/latest/usage/reproducibility/) | 默认执行不保证可复现；版本、硬件、批次行为均有关 | 当前网页不等于用户安装版本，部署前需再次绑定版本 |

基于这些来源的本项目推断：更有价值的研究空间是**控制模型与预算、客观验证成果、追踪机制，并系统分析规模边界**。目前没有足够检索证明这是全领域首次，也不声称“首次”。这是一轮定向背景核验，不是系统综述。

## 3. PDF 的实际范围

第 1 页署名 OpenAI，题名 *Finite Time Blowup for Navier–Stokes*。Theorem 1.1 给出任意正黏度下有光滑时空紧支撑外力、零初始速度、能量一致有界而有限时间速度无界的构造，并说明对应 C/D。这里只核对“论文声称了什么”。

文本检索未发现独立单词 agent/agents、10,000、multi-agent。Agent 数量与组织来源是网页而不是数学 PDF。未检出关键词本身并不能证明所有组织信息绝对不存在。

不向生成端提供 PDF 只是污染控制的一部分：现有题面已经来自参考定理，模式列表包含策略提示。若使用这些提示，需登记为允许的先验信息，而非宣称无提示再发现。

## 4. 原型的关键问题

行号对应交接包内 `skill/h20_10k_navier_agent_skill/` 的原始文件；具体行号及 mock 实测保存在审计 JSON。

| ID | 定位 | 发现与影响 | 下一步验收条件 |
|---|---|---|---|
| E01 | `scripts/calibrate_concurrency.sh`，`--limit 128` | 各档仅 128 个任务，C>128 时实际请求并发不可能达到设定值；高档比较失效 | 预热与实测分开；请求数足以持续占满最大并发，记录实际活跃请求 |
| E02 | `scripts/submit_10k.py`，`load_done` | 只按 agent_id 续跑；新模型/题面/参数复用结果文件可跳过旧 ID | run/config/task/model/prompt 指纹一致才可恢复；不一致必须拒绝 |
| E03 | `scripts/submit_10k.py`，`stream: False` | 无流式首 token 时间，不能由最终请求延迟推算 TTFT | 真实流式事件或服务端指标；缺失字段为 unknown |
| E04 | `slurm/navier_10k.sbatch`，提交命令 | 种子写入记录，但没有传 `--send-seed`；种子文本不是采样随机种子 | 记录并检查实际 API 请求种子及环境；仍不能承诺逐字确定性 |
| E05 | `scripts/submit_10k.py`，返回结果 | 丢弃 finish_reason、任意额外组织元数据及尝试历史；mock 中截断/空内容仍为 ok | 分离传输成功、模型完成与证明验证；保留原始响应、每次 attempt 和元数据 |
| E06 | `scripts/submit_10k.py`，`append_jsonl/load_done` | 忽略损坏 JSON 行且无跨进程锁；半行后追加有吞并新行风险 | 可恢复 journal/数据库、进程互斥、损坏显式报告、幂等逻辑结果 |
| E07 | `scripts/generate_population.py`，suffix | 默认每个轨迹禁止协作；提交器每记录仅一次 LLM 请求，没有持久记忆/消息路由 | I 基线可用；多轮 O 策略需独立实现，不能仅加组织标签 |
| E08 | `slurm/navier_10k.sbatch`，ROOT 与日志 | 由 `$0` 推导项目根；Slurm 拷贝脚本场景会有路径风险；日志目录需在 sbatch 前存在 | 使用明确项目根/SLURM_SUBMIT_DIR，实际集群 smoke 验证工作目录与退出清理 |
| E09 | `scripts/submit_10k.py`，main | 失败计数不导致非零退出；调度器可能看到作业“成功”而大量 Agent 失败 | 明确允许失败阈值与退出状态；传输失败不可当科研阴性结果 |

E01–E05、E07、E09 来自可复核源码；E02、E04、E05 有本地 mock 示例。E06–E08 的运行风险未做集群故障注入，不能写成已经发生的线上故障。线程池确实限制同时请求，但一次性创建所有 futures；这不是交接文字所称的完整异步有界生产者队列。

8×H20 96GB、Slurm、vLLM、TP/DP、384 并发均是交接声明/起始建议，未现场核实。不得将 768GB 汇总容量等同于任意模型可用显存，更不能据此承诺吞吐。

## 5. 本次完成与未完成

完成：来源哈希与语法重验、定理范围核对、一手背景核验、关键程序行为 mock、研究和复现规范、可运行的文件完整性检查。

未完成：生产提交器修复、真实基准、数学解答/正确性、组织形式排名、功效分析定稿、GitHub 推送。Science 官方 editorial policies 页面本次读取失败，因此本交付采用项目自定的科学质量规范，不声称逐条核验了最新投稿政策。
