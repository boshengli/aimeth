# SLCW 原设计、现有实现与数学适配 · v2

16 项机制已建立来源与代码对照；当前计划以 SLCW 群体计算和治理为主线。单 Agent 运行及成功均非前置条件，小群体数学成功也不是扩规模前置。完整 V1/V2 数学运行器尚未实现。

这是一份源码和计划审计，不是新的模型试验，也没有证明任何架构优于另一架构。来源论文的生物学结论本轮未重新核验；原始 ZIP 未恢复，笔记、重建稿、规范和实现分开标注。

Current plan: [population-plan-v2.md](population-plan-v2.md). Human report: [M2.6 v2](../milestones/m2-6-slcw-realignment-v2.html).

Source IDs resolve to the hashed inventory below. Adaptations and acceptance criteria are proposals, not implemented behavior.

## M01 · 格点、层次与规模分母 (V1 → V2)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| 原始笔记是 10×10 的 100 个分析格点、4 个 Observer、1 个 Chief；重建稿把行解释为组织层、列解释为阶段。V2 将 10×10 降为兼容布局，并不要求固定组织规模。 [S01](#source-s01) [S02](#source-s02) [S04](#source-s04) | GLM 默认 10×10、34 个活跃格点。Codex engine 的 fixed 模式登记 100 个分析记录；另一模式登记 8 个分析 + Patterning/Interface/Vascular 各 1 个记录。登记数量不能代表同时推理数量。 [S09](#source-s09) [S12](#source-s12) [S13](#source-s13) | compile_arm 提供 S/I/L/X 固定群体图；compile_roles 提供 E0/E1/C/S 四角色 H/F 图。均不是完整 SLCW V1/V2。10K 配置可编译不等于 10K 推理已执行。 [A01](#source-a01) [A02](#source-a02) | 将格点映射到证明义务、方法或反例搜索任务，另存 group_id 与 layer_id。“100 组”及“100 组×100 工作者=10K 工作者”属于扩展方案；需另加治理角色数，不能回写成原始设计。 | 导出 roster、组织图和调用账本，分别统计组数、工作者数、治理角色数、活跃客户端、并发数、GPU 数与请求数。 缺口：固定图底座可复用；完整层状 roster 与任务分配待实现 |

## M02 · 局部通信与 30% 参数 (V1 / V2)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| V1 重建稿的 30% 是每格点每轮参与邻接广播的概率。V2 保留局部通信并增加受限长程路径。 [S02](#source-s02) [S03](#source-s03) | GLM VascularRouter 使用 p_comm 概率发送邻接与筛选后的长程消息；Core Step6 则按带宽额度过滤。概率与配额的分母不同，不能称作同一个实验参数。 [S07](#source-s07) [S16](#source-s16) | AIMeth 固定图按轮发送带内容哈希和父事件的消息；H/F 有固定消息数与字符数限制，不是来源中的 30% 抽样规则。 [A01](#source-a01) [A02](#source-a02) [A03](#source-a03) | 冻结通信抽样单位、方向、时序、总字节及 token 预算。记录实际发送/未发送/丢弃原因；不能仅以同一名义概率宣称通信成本匹配。 | 小图 fixture 的接收集合、预算扣减和断点续接一致；实跑保留实现后的通信矩阵与完整内容。 缺口：持久消息已有；SLCW 概率/配额策略待适配 |

## M03 · 区域 Observer (V1)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| 4 个 Observer 监视区域并协调局部身份共识。重建稿是按组织层划域，不能假设必然四等分为每组 25 个格点。 [S01](#source-s01) [S02](#source-s02) | DPV4 consensus 根据区域身份和票数作判定；GLM 主循环确实调用 Observer。该实现服务生物身份分类。 [S06](#source-s06) [S10](#source-s10) [S11](#source-s11) | H/F 的 critic/synthesizer 有同伴消息，但没有 SLCW 区域 Observer 的监视状态与职责。 [A02](#source-a02) | 区域对应某个子定理或方法族；Observer 跟踪证明义务覆盖、相互矛盾的假设、重复依赖和预算，提出协调请求。共识只表示协调状态。 | 一条有效反例在多数错误候选下仍进入未解决清单；区域摘要能追溯到每条候选及证据。 缺口：区域治理待实现 |

## M04 · COLOR、Quarantine 与少数意见 (V1 → V2)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| V1 用 COLOR 表示身份形成，Quarantine 处理冲突/证据不足；V2 要求保留替代解释和少数候选，不以一致性压制异议。 [S01](#source-s01) [S02](#source-s02) [S03](#source-s03) [S04](#source-s04) | GLM 隔离复审是模拟 PI 放行：把 confidence 提高至至少 0.75 并无条件返回 release，没有独立证据复审；Patterning 可能追加候选。Codex CandidateRegistry 提供 preserve_minority 等状态操作，但不能证明完整链路已保护少数意见。 [S06](#source-s06) [S07](#source-s07) [S14](#source-s14) | 运行器保留失败与事件，但缺少候选隔离、异议上诉及复审协议；事件日志不能代替科学治理。 [A03](#source-a03) [A02](#source-a02) | 把 COLOR 定义为组织状态，不赋予数学真值。隔离针对某条主张及其下游依赖；保留原文、异议与申诉路径，不因持不同结论删除 Agent。 | 隔离→复审→恢复/否证事件及预算完整；多数不接受的正确反例仍可抵达独立验证器。 缺口：候选治理待实现；不得用共识过滤最终证据 |

## M05 · Chief、全局收敛与停止 (V1)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| V1 原始笔记含 80% 收敛与 STOP；重建稿还要求无隔离/冲突并设轮次上限。V2 明确停止不等于科学结论成立。 [S01](#source-s01) [S02](#source-s02) [S04](#source-s04) | GLM 主循环 Chief 记录状态并检查停止；这是一致性与过程终止机制。它不检验 Navier–Stokes 定理。 [S06](#source-s06) | H/F select_synthesizer 按预定种子选一个终末 synthesizer，未形成全局 Chief 的候选证明合成；store.status 的 complete 只意味着安排的步骤成功结束。 [A02](#source-a02) [A03](#source-a03) | Chief 交付候选证明、假设清单和未完成义务图。预算耗尽、协调收敛、有效否证与证明核验分别记录；80% 不作为数学成功阈值。 | 全体一致但错误的候选被验证器拒绝；预算停止后仍能交付完整未完成/阴性报告。 缺口：全局合成与科学停止语义待实现 |

## M06 · 探索与验证双通道 (V2)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| V2 将 Explore Lane 与 Validation Lane 分开，探索产生候选，验证设计和执行独立检查。 [S03](#source-s03) [S04](#source-s04) | Core population 登记 Harvester、Validator、Auditor 等角色；内置 runtime CLI 有公式驱动的演示，外层 Core CLI 则真实调用 analysis_agent。角色登记不能自动证明独立验证链已执行。 [S19](#source-s19) [S22](#source-s22) [S23](#source-s23) | 生成与终末 certificate evaluation 已有分离，但公开开发控制题和固定角色不构成完整的双通道数学研究系统。 [A05](#source-a05) [A02](#source-a02) | 内部审查通道只接收冻结的允许工具/反馈；盲测答案及独立终末评估器密钥不进入生成上下文。允许的验证器反馈和人工提示单独留痕。 | 权限与挂载检查通过；正确、错误、缺假设和循环依赖 fixture 被正确分类；开发集与保留集分别登记。 缺口：评估隔离底座可复用；双通道编排待实现 |

## M07 · 增殖、冻结、合并与重新激活 (V2)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| 原规范包含 explore/specialize/proliferate/freeze/merge/reactivate，按任务和信息需求调整组织。 [S03](#source-s03) | Codex engine 以固定 0.03 改变量写自适应标记；Core population 的扩增创建状态记录。它们不能单独证明新 Agent 真正执行了不同推理任务。 [S12](#source-s12) [S19](#source-s19) | AIMeth manifest 与 schedule 是预登记固定 roster/轮次；不能不改协议就在运行中动态增殖。 [A01](#source-a01) [A03](#source-a03) | 通过有版本的组织变更事件创建新任务与 Agent，冻结不删除历史；变更必须携带触发证据、预算来源和对照臂的等预算处理。 | 重启后 roster/预算/后续任务唯一一致；新增身份有实际调用或明确的未执行原因。 缺口：动态调度待实现 |

## M08 · Patterning 与层状 TF 式调控 (V2)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| V2 Patterning 负责多样性、替代解释、稳健性和方法调节；原规范不等于已经实现每一层独立 TF 式治理 Agent。 [S03](#source-s03) | GLM 每轮调用一个 PatterningAgent，按自报信息增益选前五个格点，再调用同一 _call_llm 并按 TF 名称合并候选；没有新的层调控提示。Core Step6 有条件任务生成和路由 kimi-k3 的意图，但所检视 benchmark 用 getattr 读取 dict，仍落入默认 analysis_agent/flash，不能声称实际换模型。 [S06](#source-s06) [S07](#source-s07) [S08](#source-s08) [S15](#source-s15) [S27](#source-s27) | S/I/L/X 与 H/F 目前没有对应的 Patterning 策略。固定角色提示不是层间调控。 [A01](#source-a01) [A02](#source-a02) | 将层定义为问题分解、局部推导、跨模块组合等可检验职责，明确调控信号如何改变分工、工具及预算。逐层 TF 式调控是本项目待冻结的适配提案。 | 每次调控有触发证据、动作和后续执行；与等调用次数的同模型重采样比较，避免将额外计算或换模型的收益归因治理。 缺口：部分来源有重复查询；数学层调控待实现 |

## M09 · Interface 与边界兼容 (V2)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| Interface 检查模块边界及兼容性；相邻关系不应直接推断为调控关系。 [S03](#source-s03) | Codex engine 登记 interface_agent，但 worker 实际统一调用 analysis_agent；已检查链不足以证明独立边界审查已接入。 [S12](#source-s12) [S13](#source-s13) | H/F critic 执行通用批评，不具有明确的定理接口或假设类型检查。 [A02](#source-a02) | 在引理组合边界检查函数空间、定义域、边界条件、正则性、量词和常数依赖，生成精确的兼容/不兼容记录。 | 局部推导各自正确但组合假设冲突的 fixture 被阻止；修复后形成新的候选版本且保留旧失败。 缺口：数学接口协议待实现 |

## M10 · Vascular 类型化长程消息 (V2)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| Vascular 允许关键矛盾、新证据、验证请求、复现失败、工具结果及瓶颈等高价值长程消息。用户“微管束”表述与源码 Vascular 的术语对应尚未最终确认。 [S03](#source-s03) | GLM 同层、候选非空且权重为正的身份消息经 aggregate 累积为票，Observer 使用这些票；跨层消息及其他候选内容不在该聚合器中整合。analyzer 的模型上下文只有格点元数据和 data_slice，常规身份已存在还会跳过查询。Core Step6 inbox_digest 仅有类型和发送接收者，省略候选内容。 [S07](#source-s07) [S08](#source-s08) [S10](#source-s10) [S11](#source-s11) [S16](#source-s16) [S26](#source-s26) | AIMeth enqueue_round 将真实 incoming 内容、父事件、源哈希冻结进请求，具备消息→提示记录；尚无 Vascular 类型语义与跨模块路由。消息被接收不证明模型实际理解或使用。 [A03](#source-a03) [A02](#source-a02) | 携带有来源的引理、反例、验证失败及瓶颈；获准消息内容进入后续推理上下文，并保留预算和源候选版本。 | 核对 message→prompt→receipt→candidate 链；替换消息内容的确定性 fixture 能改变预期输入，随后才用消融检验科学贡献。 缺口：内容链底座已实现；Vascular 策略待实现 |

## M11 · 动态 Observer 与真实任务社区 (V2)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| Observer 随实际社区调整，监视多样性、来源独立性、少数意见和信息增益。 [S03](#source-s03) | GLM build_dynamic_observers 根据归一化代谢通路建社区；Core Observer 对调用方给出的五个数值加权。生物社区和自报数值不能直接替代数学证据独立性。 [S07](#source-s07) [S20](#source-s20) | 已有图与事件查询能力，没有动态任务社区或来源独立性计算器。 [A01](#source-a01) [A03](#source-a03) | 按共享证明义务/证据依赖形成社区，检测候选是否只是共同祖先的复制；社区变化也需要版本化。 | 多个转述同一论据的 Agent 不被计为独立支持；重组后消息与候选来源仍可追溯。 缺口：社区与依赖监视待实现 |

## M12 · 候选收获、优先级与少数保留 (V2)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| 候选在 COLOR 或全局 STOP 之前收获；规范定义候选状态并保留少数方向。 [S03](#source-s03) [S04](#source-s04) | Codex CandidateRegistry 有加权评分、精确归一化去重、优先级和少数状态；Core 也登记收获角色。评分或文本去重不是候选之间的逻辑等价证明。 [S14](#source-s14) [S19](#source-s19) | 现有终末选择器取一个预定代表，不是完整候选档案或经过预算核算的群体合成器。 [A02](#source-a02) | 维护候选证明/反例及证明义务 DAG，记录生成、依赖、反驳、修订和验证结果。群体产出规则预先冻结，禁止事后挑选最好结果。 | 每个终末产物可追溯到中间贡献与否证；无成功候选时仍导出完整候选和失败清单。 缺口：候选底座可借鉴；群体合成待实现 |

## M13 · 三 Chief 的制衡 (V2)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| V2 设综合、怀疑与校准三个 Chief，分离综合决策、反对证据及证据等级。 [S03](#source-s03) | Core 控制器确实调用三 Chief；其方法是确定性 Python：排序、missing_context 检查、reproducibility maturity 检查。不能称为三个独立模型已完成数学互审。 [S21](#source-s21) [S28](#source-s28) | E0/E1/C/S 不是这三个 Chief，终末 synthesizer 也没有对应制衡协议。 [A02](#source-a02) | 综合 Chief 组装候选；怀疑 Chief 列出最强反例和遗漏；校准 Chief 标注证据等级与未完成义务。明确哪些规则执行、哪些调用模型，并核算成本。 | 三份署名决策与原始证据齐全，Chief 有分歧仍可停止并报告；数学真值由独立验证器决定。 缺口：规则治理有来源实现；数学三 Chief 待实现 |

## M14 · 反馈、依赖子图与局部重算 (V2)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| V2 区分验证反馈类型，并只重算受影响子图。 [S03](#source-s03) | Core FeedbackIntegrator 区分 NEGATIVE/FAILED_TECHNICAL、更新候选并创建依赖子图请求；RerunManager.execute 只把 Agent 置 ACTIVE、任务置 READY，然后标 COMPLETE，没有执行器调用。反馈 CLI 保存请求，不等于重执行已经完成。 [S17](#source-s17) [S18](#source-s18) [S22](#source-s22) | 已有失败重试、租约恢复和按轮续接；它们处理执行故障，不会自动识别数学依赖及启动局部修订。 [A03](#source-a03) [A04](#source-a04) | 建立定理/引理/证明义务依赖，数学否证与工具失败分别处理。重算必须真的执行并留下新结果，不能把排入队列视为完成。 | 反例只使受影响后代失效；恢复后不重复提交结果；新候选关联原候选和反馈事件。 缺口：请求状态机制可借鉴；闭环任务执行待实现 |

## M15 · 非 LLM 控制器、持久化与恢复 (V2 + 项目工程要求)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| V2 控制器负责状态、预算、缓存、重算、checkpoint 和停止，不代替科学结论。 [S03](#source-s03) | 来源包含控制状态与 checkpoint 逻辑，但本次是静态代码核对，没有据此认定多机故障恢复、全量 10K 或生产服务已经验证。 [S12](#source-s12) [S17](#source-s17) [S18](#source-s18) [S22](#source-s22) | AIMeth 有事务事件、带 fencing 的租约、原子 receipt/checkpoint/message 提交与哈希校验。保证限于单主机本地持久 SQLite；不支持多主机在共享文件系统上写同一个库。调用/输出预留已有，完整输入 token 与 GPU 时归属仍缺。 [A03](#source-a03) [A04](#source-a04) [A07](#source-a07) [A08](#source-a08) [A11](#source-a11) | 将组织策略与调度/验证/报告分离；新增治理事件纳入既有原子日志，动态任务要补明确的恢复和预算语义。 | 杀进程/过期租约/重复回执 fixture 不丢消息、不双计结果；压力测试报告容量与开销，不伪装为组织科学收益。 缺口：生产底座部分完成；动态组织及多机能力未完成 |

## M16 · 数学任务接口与群体评价 (跨版本研究要求)

| 原设计 | 0013 现有实现 | AIMeth 现有实现 | 数学适配提案 | 验收证据 / 缺口 |
|---|---|---|---|---|
| 来源是生物组织启发的研究系统；不能把生物指标、身份共识或候选数直接转换成数学成功率。V2 本身也区分停止与真值。 [S03](#source-s03) [S04](#source-s04) | Core compute 计算表达富集并登记观察性 claim；benchmark 按基因/概念匹配和计算提名计 recall，surfaced 也含确定性计算提名。该 recall 不是群体证明成功率。 [S23](#source-s23) [S24](#source-s24) [S25](#source-s25) | 旧角色准入检查的是格式/传输，数学结果在终末评价；旧计划另加“capable single-Agent”顺序，是当前必须撤销的研究计划门槛。旧结果与冻结门槛保留不改。 [A05](#source-a05) [A06](#source-a06) [A09](#source-a09) [A10](#source-a10) | 用有限且可独立检查的证明义务/反例任务检验机制；Navier–Stokes 保留为探索性任务。单位是独立初始化的群体 run×任务实例，模型、任务与总资源受控。单 Agent 仅可选等预算参照。 | 盲评逐项检查定理、假设、依赖和证明义务；保留数学错误、少数意见、未收敛及零收益，不以它们阻止下一轮组织研究。 缺口：研究准入已纠正；完整数学适配仍待实施 |

## 来源与代码身份

Private Workflow files are identified by relative path and SHA-256; they are not redistributed. Hashes attest bytes, not successful execution.

<a id="source-s01"></a>
**S01 · workflow** — `S0001-Layer/za/01.GTPplant.md`; lines 5–11; 27–36; 1359 bytes; SHA-256 `2ae9010b0527fb694af12d20af0cf7e588502e8e68b3ea4c92ec19499bc0edd4`; identity `local source snapshot; not a live execution`.

<a id="source-s02"></a>
**S02 · workflow** — `S0001-Layer/za/S0001-DPV4/20260810_层状Agent分析架构设计_DPV4.md`; lines 80–138; 202–215; 15073 bytes; SHA-256 `2af280a44a912ce55e305bec56014960a00e627783c50ab2c7eab6275736ab84`; identity `local source snapshot; not a live execution`.

<a id="source-s03"></a>
**S03 · workflow** — `S0001-Layer/SLCW_Runtime_v0.1/spec/SLCW_Final_DiscoveryTissue/ARCHITECTURE.md`; lines 38–171; 3993 bytes; SHA-256 `6dce7f37e5e7486fa5ee144803dc6e03a23713add01e2c22baf3eeabbfe167d9`; identity `local source snapshot; not a live execution`.

<a id="source-s04"></a>
**S04 · workflow** — `S0001-Layer/SLCW_Runtime_v0.1/spec/SLCW_Final_DiscoveryTissue/FINAL_DECISIONS.md`; lines 3–100; 2302 bytes; SHA-256 `53b506b7eb3bbd7b4351f324a8dc74a0f46964cb8679d9d64be926f01a4cecb7`; identity `local source snapshot; not a live execution`.

<a id="source-s05"></a>
**S05 · workflow** — `S0001-Layer/S0001-GLM/slcw_v1_glm/modes.py`; lines 13–21; 95–102; 3895 bytes; SHA-256 `fcbc813ac06e667b010d710689c66488afc9a4f4ea48c553ab085e39af375654`; identity `local source snapshot; not a live execution`.

<a id="source-s06"></a>
**S06 · workflow** — `S0001-Layer/S0001-GLM/slcw_v1_glm/run_v1.py`; lines 146–159; 199–249; 15669 bytes; SHA-256 `b2e91619796f825a2d8ff8182c23afab2db92bbd9a98c35cedc689f91928015f`; identity `local source snapshot; not a live execution`.

<a id="source-s07"></a>
**S07 · workflow** — `S0001-Layer/S0001-GLM/slcw_v1_glm/observers_adaptive.py`; lines 134–245; 287–340; 16417 bytes; SHA-256 `2f47ee4ba046f9901d76ed5cd0541fba08215f67710b2e5bce429d842bfd581e`; identity `local source snapshot; not a live execution`.

<a id="source-s08"></a>
**S08 · workflow** — `S0001-Layer/S0001-GLM/slcw_v1_glm/analyzer.py`; lines 85–110; 183–220; 18914 bytes; SHA-256 `ea764926837b82e2514f664e1a3c7e9092812071afd00d91da8d64da05903d18`; identity `local source snapshot; not a live execution`.

<a id="source-s09"></a>
**S09 · workflow** — `S0001-Layer/S0001-GLM/slcw_v1_glm/config/defaults_v1_glm.yaml`; lines 15–20; 3274 bytes; SHA-256 `0c76e243f4a6ebdabd8a88693e88a51c90dde0cb3684b5c95578d373f0c7ff98`; identity `local source snapshot; not a live execution`.

<a id="source-s10"></a>
**S10 · workflow** — `S0001-Layer/za/S0001-DPV4/orchestrator/router.py`; lines 83–120; 4888 bytes; SHA-256 `3971a1b57dc13c15ad1681edefa129e167b412297bae87ea8a17a8341e5b28cd`; identity `local source snapshot; not a live execution`.

<a id="source-s11"></a>
**S11 · workflow** — `S0001-Layer/za/S0001-DPV4/orchestrator/consensus.py`; lines 1–160; 7210 bytes; SHA-256 `e22ca94f6ce618162254d3482a6e2e3bc9d6c69c2dca19cd85bc6de153d92dca`; identity `local source snapshot; not a live execution`.

<a id="source-s12"></a>
**S12 · workflow** — `S0001-Layer/S0003-Codex/slcw_core/engine.py`; lines 42–122; 8532 bytes; SHA-256 `11e36909c46488fb44fa096449ae89774b3ac2fe72d212c10ff5a0ace07786d4`; identity `local source snapshot; not a live execution`.

<a id="source-s13"></a>
**S13 · workflow** — `S0001-Layer/S0003-Codex/slcw_core/worker.py`; lines 20–58; 3288 bytes; SHA-256 `36564c77d763e01d02dd9095547b15a0179f8162647a61cf7739679a5b9799b0`; identity `local source snapshot; not a live execution`.

<a id="source-s14"></a>
**S14 · workflow** — `S0001-Layer/S0003-Codex/slcw_core/candidates.py`; lines whole module; 3019 bytes; SHA-256 `ca27af0140909db64fc326c1f4580c8dcdbfedcbf26503f22225e17dd3a082d1`; identity `local source snapshot; not a live execution`.

<a id="source-s15"></a>
**S15 · workflow** — `S0001-Layer/SLCW_Core_v1.0/slcw_core/step6overlay/patterning.py`; lines 1–69; 2736 bytes; SHA-256 `1c64e713449c4dc37b4f7b023a9ccdc7cd0bf1d8cc3a1817f0273f9ee4eb423e`; identity `local source snapshot; not a live execution`.

<a id="source-s16"></a>
**S16 · workflow** — `S0001-Layer/SLCW_Core_v1.0/slcw_core/step6overlay/messaging.py`; lines 1–89; 3778 bytes; SHA-256 `094f256416bb1a2204d74079e64b1fa3bdd43ea49f7929a0f8c0d06a696745ed`; identity `local source snapshot; not a live execution`.

<a id="source-s17"></a>
**S17 · workflow** — `S0001-Layer/SLCW_Core_v1.0/slcw_core/runtime_slcw/feedback.py`; lines 17–end; 3110 bytes; SHA-256 `390193743875417ab1e6f0b4f71bf30a8d3a764c6ac64efa476d23ac7c8fb43e`; identity `local source snapshot; not a live execution`.

<a id="source-s18"></a>
**S18 · workflow** — `S0001-Layer/SLCW_Core_v1.0/slcw_core/runtime_slcw/rerun.py`; lines 26–end; 1569 bytes; SHA-256 `37e3651a96fa5506a65950a4bc50c5f04103e3badf1f7fa3bdabe6f32bd400ac`; identity `local source snapshot; not a live execution`.

<a id="source-s19"></a>
**S19 · workflow** — `S0001-Layer/SLCW_Core_v1.0/slcw_core/runtime_slcw/population.py`; lines 21–end; 2564 bytes; SHA-256 `b4e88ba47d3e2cf72ca5ca62712d52d0883c9697b22354ec98fb2aacd95480c2`; identity `local source snapshot; not a live execution`.

<a id="source-s20"></a>
**S20 · workflow** — `S0001-Layer/SLCW_Core_v1.0/slcw_core/runtime_slcw/observer.py`; lines 12–end; 1282 bytes; SHA-256 `18bcd09eeb06fa32295a7ee365d6047fa9b6f136477465315e91bb76239a0025`; identity `local source snapshot; not a live execution`.

<a id="source-s21"></a>
**S21 · workflow** — `S0001-Layer/SLCW_Core_v1.0/slcw_core/runtime_slcw/chiefs.py`; lines 12–end; 2104 bytes; SHA-256 `72079e252a02b56a7c9a7b66d76c7779bb2b21b750a48256a8c98fab1a88cdd9`; identity `local source snapshot; not a live execution`.

<a id="source-s22"></a>
**S22 · workflow** — `S0001-Layer/SLCW_Core_v1.0/slcw_core/runtime_slcw/cli.py`; lines 38–end; 6864 bytes; SHA-256 `1b3530ec9207920e39e3b17c082cd8975d88e93a1c2ce8508e375d3dd06e7e6a`; identity `local source snapshot; not a live execution`.

<a id="source-s23"></a>
**S23 · workflow** — `S0001-Layer/SLCW_Core_v1.0/slcw_core/cli.py`; lines 49–end; 7685 bytes; SHA-256 `c641e0f2912225e5a0e0f8e0a37ad7dd49d26d2e67d41f7017165bca3df466bc`; identity `local source snapshot; not a live execution`.

<a id="source-s24"></a>
**S24 · workflow** — `S0001-Layer/SLCW_Core_v1.0/slcw_core/compute.py`; lines 279–end; 14618 bytes; SHA-256 `cbe4651c37612141e5a62f7891b6e10c815397cf740fcb688bd0dbe5aa216941`; identity `local source snapshot; not a live execution`.

<a id="source-s25"></a>
**S25 · workflow** — `S0001-Layer/SLCW_Core_v1.0/slcw_core/benchmark.py`; lines 211–end; 16148 bytes; SHA-256 `fbc2d867cdb64fa21924e20b6bab663d9da012b21928231bfae1a073ff152fbe`; identity `local source snapshot; not a live execution`.

<a id="source-s26"></a>
**S26 · workflow** — `S0001-Layer/S0001-GLM/slcw_v1_glm/lattice_bridge.py`; lines 24–end; 2445 bytes; SHA-256 `f73e87ec0e2f178e383be5b8b6094506ce3bc6035d8537427d4856e5f1a48bfc`; identity `local source snapshot; not a live execution`.

<a id="source-a01"></a>
**A01 · aimeth** — `aimeth_design/organizations.py`; lines 25–160; 7898 bytes; SHA-256 `af660f08defdbe6b9fdd90da2eb22e338ec0baa7d49ec122a3b90f107cfeee25`; identity `0234fb6f1e3a247cd9c889ec578a5455499e93aa`.

<a id="source-a02"></a>
**A02 · aimeth** — `aimeth_design/role_routing.py`; lines 16–163; 10056 bytes; SHA-256 `28c05fb16d25781bf7b80a77981232b954dbda59d0f84b33cfbed0a96ac17bfd`; identity `0234fb6f1e3a247cd9c889ec578a5455499e93aa`.

<a id="source-a03"></a>
**A03 · aimeth** — `aimeth_runtime/store.py`; lines 47–160; 275–369; 412–510; 619–end; 44638 bytes; SHA-256 `e360f45fe0f692d79b0e74914270a1b4e9a459082aac7a95e172f0fd1bf7d2ef`; identity `0234fb6f1e3a247cd9c889ec578a5455499e93aa`.

<a id="source-a04"></a>
**A04 · aimeth** — `aimeth_runtime/runner.py`; lines 94–end; 7525 bytes; SHA-256 `0efc191dc03ddd35324538de865f8040ed5ca3aece44a772aebef75cb18671bf`; identity `0234fb6f1e3a247cd9c889ec578a5455499e93aa`.

<a id="source-a05"></a>
**A05 · aimeth** — `aimeth_pilot/role_run.py`; lines 136–139; 190–197; 15110 bytes; SHA-256 `96435ab52cf9ae896f907dd43950ee0a297d3ad507dd5da1de5caddf4292d8e0`; identity `0234fb6f1e3a247cd9c889ec578a5455499e93aa`.

<a id="source-a06"></a>
**A06 · aimeth** — `aimeth_pilot/role_contract.py`; lines 225–246; 15557 bytes; SHA-256 `53af9d142435a482c70a08fdabab488063cc7d8afa6f1213d63fc170f10fbed6`; identity `0234fb6f1e3a247cd9c889ec578a5455499e93aa`.

<a id="source-a07"></a>
**A07 · aimeth** — `aimeth_pilot/role_budget.py`; lines whole module; 5516 bytes; SHA-256 `fdb66b13bfac0f664be48e0aae2f2fc53723fe8d3ae9f549968394187ccd53e8`; identity `0234fb6f1e3a247cd9c889ec578a5455499e93aa`.

<a id="source-a08"></a>
**A08 · aimeth** — `aimeth_pilot/quota.py`; lines whole module; 3181 bytes; SHA-256 `ef8f790522a9cdcbdcb93a032ff34a7b2033d5839a6e8a5a3701e6651b224a0a`; identity `0234fb6f1e3a247cd9c889ec578a5455499e93aa`.

<a id="source-a09"></a>
**A09 · aimeth** — `docs/next-population-plan-v1.md`; lines 1–end; 5010 bytes; SHA-256 `590a87d709168934dc7caf836ae65659b20ab16cd8dfb39065327a69f1555203`; identity `0234fb6f1e3a247cd9c889ec578a5455499e93aa`.

<a id="source-a10"></a>
**A10 · aimeth** — `task-continuation-report-manifest.json`; lines 14–16; 4863 bytes; SHA-256 `5db8477b2a74f3331781695f3d7ba5ec3cdab0c52f85214b90dd60e89c582f13`; identity `0234fb6f1e3a247cd9c889ec578a5455499e93aa`.

<a id="source-a11"></a>
**A11 · aimeth** — `docs/runtime-contract-v1.md`; lines whole document; 8060 bytes; SHA-256 `098a10876a4c4ed2eff695dbf633c53abd19ac181a88d0397be599833d4e6aa3`; identity `0234fb6f1e3a247cd9c889ec578a5455499e93aa`.

<a id="source-s27"></a>
**S27 · workflow** — `S0001-Layer/SLCW_Core_v1.0/slcw_core/bench/comparison.py`; lines 98–130; 12067 bytes; SHA-256 `bf1d82a6c265a56bd2b2541e1c7a456ac3def5c5bb3c084a7047ecd3b835ca0f`; identity `local source snapshot; not a live execution`.

<a id="source-s28"></a>
**S28 · workflow** — `S0001-Layer/SLCW_Core_v1.0/slcw_core/runtime_slcw/controller.py`; lines 68–74; 4775 bytes; SHA-256 `c123beac819537a087c8fc36f2afc2a5076744cac299ad61f4d3d0ed51e0d0e1`; identity `local source snapshot; not a live execution`.
