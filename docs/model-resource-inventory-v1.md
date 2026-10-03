# 大模型测试资源盘点 v1（2026-10-02 用户补充）

**盘点日期：** 2026-10-02  
**范围：** AIMeth 可用于后续数学群体测试的集群节点、院内模型服务和官方公网 API。  
**证据原则：** “历史成功”只表示相应时间、作业和请求曾成功；不代表当前在线、配额可用、可承担群体负载或适合数学评估。下文将 Codex 本地观察与用户报告分开标注；本轮没有进行集群认证。院内网关地址保留在私有项目控制记录 D-011；此公开清单不重复内部地址或任何凭证。

## 资源总览

| 资源 | 已知模型 / 能力 | 证据状态 | 当前可用性 | 主要限制 / 下一步 |
|---|---|---|---|---|
| **GPU08：项目可申请的 H20 节点** | 本地 `DeepSeek-V4-Flash-0731`；历史运行载荷使用 8×H20 | 2026-09-30 作业 `233657` 完成单次 loopback 推理；随后 2026-10-01 记录显示 v8 作业 `235511` 曾运行于 8×H20。用户在 2026-10-02 补充了 GPU08 登录入口；地址保存在私有控制记录 | **未知**；没有本轮 Slurm/checkpoint 刷新。禁止用旧凭据认证 | 历史项目记录把该入口称为 `tln01` 登录/跳转路径；本次未验证它是 GPU08 直连还是登录跳转。v8 后续最终状态未知；需新安全认证方式后核验 |
| **GPU01** | 历史用户信息称院内 GLM / DeepSeek Flash 推理后端可能在此节点 | 节点归属来自用户报告；没有独立核验 GPU01 上的模型进程、模型权重或网关路由 | **未知** | 不作为已确认推理节点；需补充当前调度方式、项目是否可用、模型服务地址与路由证明 |
| **院内模型网关** | 历史目录/调用中见 `glm-5.3-flash`、`deepseek-v4-flash-0731`、`deepseek-v4-flash-vision-exp` | GLM 与 DeepSeek Flash 在院内服务上均有历史调用；vision ID 曾出现在 served-ID 列表但没有测试。路由到 GPU01 的说法未经独立证明，权重内容/版本未认证 | **未知**；本轮没有请求模型目录或调用 | 这是 API 服务，不等于可调度 GPU。网关运行主机 `tln02`、接入节点 `tln01` / `cln02` 是控制/登录路径；不要按 GPU 推理节点计。实际 API 地址和 secret 仅留在私有控制记录/密钥配置中 |
| **tcu165（历史 CPU 执行节点）** | 曾通过院内 GLM 网关发起客户端请求 | 历史作业 `232984`（4 CPU / 16 GB、0 GPU）与 `233163`（0 GPU）均在本地项目记录中标记为已结束；输出失败已留档 | 最新证据未见活动的本项目作业；**当前调度状态未核验** | 不再向 tcu165 提交推理客户端或 GPU任务。这里的“停用”指停止本项目使用该路径，不是关停共享集群节点；没有当前活动 JobID 可取消 |
| **Z.AI / 智谱官方公网 API** | `glm-5.3-flash`；OpenAI 兼容接口 | 2026-09-30 历史批处理与同步调用见上文；Codex 本地新 WP1 配对请求曾在 `api.z.ai` 和 `open.bigmodel.cn` 收到 401（BigModel code 1000）；随后用户报告新测试在两个端点均鉴权成功、模型目录各 11 个。两项证据属于不同来源/尝试，均保留 | **用户报告 API 可用；Codex 环境仍未配置可用安全凭据。额度与限速未知** | 用户报告：`glm-5.3-flash` 在 64-token 上限内只输出思考、无 final content；禁用思考返回 400/1210，称该模型必须启用思考。`glm-4.5-air` 最小 `API_OK` 成功，可暂作普通调用连通性候选；任务质量/成本/吞吐未知。历史批处理限制仍未解决。详见 `runs/public-api-cell-wp1-20261002-v2/user-reported-glm-api-tests-20261002.json` |
| **DeepSeek 官方公网 API** | `deepseek-flash` | 2026-09-30 `/models` 与 4 个关闭 thinking 的角色请求成功；2026-10-02 新 WP1 请求 HTTP 200、served ID `deepseek-flash`、JSON/schema 有效，580 prompt + 2,204 completion tokens | **本次单次调用可用；额度/账单仍未知** | 单次设计征询不能证明模型/架构优劣；未测试 Batch、10K、数学正确性或组织效应。密钥未写入运行记录 |

## 推荐的当前资源分层

1. **本地模型主候选：GPU08 + 本地 DeepSeek-V4-Flash-0731。** 有一次有效推理和一次后续 v8 启动/运行快照；当前状态及 v8 最终结果均待安全核验。
2. **院内 API 候选：院内网关的 GLM / DeepSeek Flash served IDs。** 需要重新确认在线、路由、响应模式、额度和后端身份；API 调用所在 CPU 主机不代表模型在 CPU 上推理。
3. **公网 API 备用：DeepSeek `deepseek-flash`；智谱 `glm-4.5-air`（普通调用候选）与 `glm-5.3-flash`（长推理候选）。** GLM-4.5-Air 仅有用户报告的短 `API_OK`；GLM-5.3-Flash final 输出受思考预算影响。没有模型完成 WP1 配对答题，也未证明支持本项目 10K 工作负载。

## 尚需补充 / 确认

请补充资源信息即可，**不要在文档、聊天或 Git 中发送 API key / 密码**。Codex 侧先前 GLM key 测试曾返回 401；用户之后报告另行测试已成功鉴权。所有 key 均不得写入文档、聊天或 Git，聊天/图片中曾曝光的 key 应撤销/轮换。DeepSeek 已完成一条新版 WP1 设计征询，但额度、限速与费用仍未知。

- 集群：除 GPU08、GPU01 外可用的 GPU 节点/分区；每节点 GPU 型号和数量；本项目可用队列/账号；是否支持项目自己的作业内 SSH 或服务发现。
- GPU08：v8 当前/最终状态以及是否已完成数据审计；登录入口地址已由用户提供并存于私有控制记录。仍需轮换密码或新的安全认证方式；此处不读取历史凭据、不做认证。
- 院内网关：三个 served ID 是否仍开放；哪个 endpoint/credential profile 应使用；是否可查真实后端节点、权重 revision、限速、并发与上下文/输出上限。
- 公网 API：DeepSeek / 智谱账号是否仍可用、计划预算与速率限制、是否有已授权的 Batch 能力。只需确认凭据是否通过安全配置可用，不提供密钥值。
- 其它模型：可用的官方 API 厂商、准确模型 ID、账户/区域限制，以及是否有院内托管版本。

## 可追溯来源

- 私有控制记录：`PROJECT.yaml`、`STATUS.md`、`DECISIONS.md`（尤其 D-011、D-029 及 2026-10-02 GPU08 快照）。
- 公开运行证据：`milestones/m2-7-gpu08-deepseek-local-v1.html` 与 `.json`；`milestones/m2-7-public-api-test-v1.html` 与 `.json`；`milestones/m2-7-public-api-deepseek-v1.html` 与 `.json`。
- 院内校准边界：`docs/cluster-pilot-v1.md`；该文明确网关路由与权重身份未被独立认证。

## 2026-10-02 · Receipt audit for submission plan M2.11

The active worktree contains `runs/deepseek-api-cell-calibration-v1/receipts.jsonl` (SHA-256 `a65b43ad4795109608745e6ee8d513c584243605e6592ef49936185b86c923b4`). Recomputed results: fast 8/8 with mean elapsed 2.086 s and 680 input / 269 output tokens; deep 4/4 with mean elapsed 10.245 s and 492 input / 6,699 output tokens, including 5,496 reasoning tokens. Total 8,140 tokens. These are per-request averages, not batch wall time. Receipts attest JSON parsing and required-key presence only; full schema/semantic checks and mathematical correctness were not established. Final response bodies were not preserved, limiting replay. The earlier control-directory path pointed to the primary checkout; the evidence used here is in the active worktree. See [submission protocol](public-api-submission-test-plan-v1.md); no new API calls were made for this audit.
