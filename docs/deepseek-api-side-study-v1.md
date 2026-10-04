# DeepSeek API 支线研究与 AIMeth 调用方案 v1

日期：2026-10-02  
状态：API 设计建议；不是已冻结的群体实验协议

## 结论

对 AIMeth，DeepSeek 最适合采用同一模型的两种固定通道。模型身份、思考模式、预算和路由比例在组织架构比较前冻结；不能在运行后把模式切换造成的差异归因于组织形式。

| 通道 | 模型 | 模式 | AIMeth 用途 | 初始工程预算 |
|---|---|---|---|---|
| 快速细胞通道 | `deepseek-flash` | thinking disabled | 高频局部状态、短消息、表达更新、候选提名、事件 JSON | `max_tokens=512`，同步或短流式 |
| 深度审查通道 | `deepseek-flash` | thinking enabled | 少量 Observer/Chief、证明义务审查、冲突分析、跨结构规划 | `reasoning_effort=high`，`max_tokens=8192`，流式 |
| 工具协调通道 | `deepseek-flash` | 默认非思考；需要推理时单独启用 | 受控状态提交、检查点写入、调度与恢复工具 | 非思考优先；严格工具调用先做小样本校准 |

“细胞通道”与“深度审查通道”是运行工程分层，不是新的科学目标。它们服务于任务条件下的细胞状态更新、分化、增殖和组织形成研究；API 响应速度、JSON 有效率和成本是支撑指标，不是涌现能力本身。

## 资料核对

- DeepSeek 官方 OpenAI 兼容入口是 `https://api.deepseek.com`，模型目录当前列出 `deepseek-flash` 与 `deepseek-v4-pro`；当前价格页将 `deepseek-flash` 标为 DeepSeek-V4.1-Flash，旧的 `deepseek-v4-flash` 与 `deepseek-v4-flash-vision-exp` 仍可能被接受，但已是退役别名，统一由新 Flash 服务。[首次调用与模型名](https://api-docs.deepseek.com/) [模型与价格](https://api-docs.deepseek.com/quick_start/pricing/)
- `deepseek-flash` 支持思考和非思考模式，思考默认开启；`thinking.type` 可设为 `enabled` 或 `disabled`，思考强度可设 `low/high/max`。思考模式不支持 `temperature`、`presence_penalty` 和 `frequency_penalty` 的有效调节；`top_p` 的有效范围是 0.95–1.0。[思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)
- 当前文档给出的 Flash 上限是 1M context、最多 384K 输出；账户级并发上限为 2500，超过会得到 429。2500 是服务上限，不是本项目应直接采用的并发值；工程试验仍应从低并发开始并测量公平的吞吐曲线。[模型与价格](https://api-docs.deepseek.com/quick_start/pricing/) [限速与隔离](https://api-docs.deepseek.com/quick_start/rate_limit/)
- JSON Output 要求 `response_format={"type":"json_object"}`，提示中必须明确要求 JSON；官方同时警告可能出现空内容、`finish_reason=length` 时内容可能被截断。客户端必须再做 JSON Schema 校验。[JSON Output](https://api-docs.deepseek.com/guides/json_mode/) [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)
- Responses API 支持 JSON Schema、工具调用和显式 reasoning item，适合需要多轮状态/工具链的角色；接口是无状态的，客户端必须保存并回传完整上下文。[Responses API](https://api-docs.deepseek.com/api/create-response/)
- Chat Completions 的严格工具调用是 Beta 功能，需要 `https://api.deepseek.com/beta`、每个 function 设置 `strict=true`，并使用受支持的 JSON Schema。思考模式下不支持 `required` 或指定名称的 tool choice；需要这类确定性调度时应使用非思考通道或先做 Responses API 校准。[工具调用](https://api-docs.deepseek.com/guides/tool_calls/)
- DeepSeek-V3 技术报告描述了 MoE、MLA、无辅助损失负载均衡和多 token 预测等训练/推理设计；这是模型研究背景，不是当前 API 延迟、计费或 10K 扩展性的保证。[DeepSeek-V3 技术报告](https://arxiv.org/abs/2412.19437)

## 已有本地证据与边界

项目已有的 DeepSeek 公网小样本记录显示：目录请求 HTTP 200；4 个思考开启请求均在 2,048 completion-token 上限结束且最终内容为空；随后关闭思考的 4 个请求均 HTTP 200、`finish_reason=stop`，得到可解析 JSON。已知合计 11,844 tokens，账单未核验；没有提交 Batch、完整 10K 或数学正确性评估。

这说明接口参数与输出预算是首要工程变量，不能说明非思考模式更聪明，也不能说明 DeepSeek 已具备群体涌现能力。此前记录使用的旧模型别名和 2,048 上限只作为历史诊断，不应直接作为新确认性条件。

## 推荐请求模板

### 快速细胞通道

```json
{
  "model": "deepseek-flash",
  "messages": [
    {"role": "system", "content": "Return exactly one JSON object. Use the stated schema. Do not add Markdown."},
    {"role": "user", "content": "<bounded local state update and explicit schema>"}
  ],
  "max_tokens": 512,
  "response_format": {"type": "json_object"},
  "stream": false,
  "extra_body": {
    "thinking": {"type": "disabled"},
    "user_id": "aimeth-cell-v1"
  }
}
```

客户端必须检查：HTTP 状态、`finish_reason`、`content` 非空、JSON 可解析、字段满足 schema、响应身份与参数指纹。`user_id` 只用于项目内隔离和审计，不放入个人隐私。

### 深度审查通道

```json
{
  "model": "deepseek-flash",
  "messages": [
    {"role": "system", "content": "Review the evidence and list unresolved proof obligations. Return a JSON object."},
    {"role": "user", "content": "<bounded review task and explicit schema>"}
  ],
  "reasoning_effort": "high",
  "max_tokens": 8192,
  "response_format": {"type": "json_object"},
  "stream": true,
  "stream_options": {"include_usage": true},
  "extra_body": {
    "thinking": {"type": "enabled"},
    "user_id": "aimeth-review-v1"
  }
}
```

思考模式下不设置 `temperature`。若请求包含 tools，后续每一轮必须原样回传完整 `reasoning_content`；缺失会导致 400 或破坏工具链。思考内容不作为数学答案，答案仍需独立评估器检查。

## 任务提交与恢复分析

DeepSeek 当前公开文档没有可供本项目直接使用的官方 Batch 提交流程，因此 10K 适配应采用客户端有界并发，而不是把“2500 并发上限”误当成批处理能力。建议执行顺序如下：

1. **端点和模型校准**：固定 `https://api.deepseek.com`、`deepseek-flash`、提示、模式和预算；先做 8–16 个请求，记录认证、首 token、总延迟、429/5xx、空内容和 schema 有效率。
2. **两通道校准**：快速通道与深度通道分开运行；至少各有一个短 JSON、一个 WP1 概念题和一个数学控制题。数学控制题只诊断接口/格式，不宣称解题成功。
3. **有界群体提交**：候选起始并发为 16，稳定后才比较 32/64；每个请求带 `run_id`、`population_id`、`agent_id`、`cell_id`、`channel`、参数指纹和 `user_id`。并发是工程变量，不能在不同组织架构间不对齐。
4. **分阶段检查点**：每完成一小批请求就写 append-only receipt 和 SQLite/JSONL 检查点；保存请求哈希、响应哈希、状态、usage、耗时和 `finish_reason`。恢复时只重放明确未 dispatch 的项。
5. **不确定结果保护**：请求已发出但超时、连接中断或 HTTP 状态未知时，记为 `unknown`，不得自动重发；服务端可能已接收并计费。只有确认未 dispatch 的项才可重试。
6. **停止规则**：连续出现空 final content、`finish_reason=length`、429、5xx 或响应延迟越界时暂停该通道，先保留失败分母和检查点，再由新的工程版本决定是否改变预算或并发。不得把失败修补成成功。

建议的字段状态集合为：`prepared → dispatch_started → response_received → accepted`，旁支为 `schema_invalid`、`model_error`、`rate_limited`、`transport_failed`、`truncated`、`unknown`。`accepted` 只表示协议接纳，不表示数学正确或组织产生能力。

## AIMeth 路由与公平性

- 细胞状态更新、局部信号和高频短消息：固定使用非思考 `deepseek-flash`。
- 预先登记的 Observer/Chief 审查：固定使用思考 `deepseek-flash`；审查比例和最大 token 预算在比较前冻结。
- 需要确定性状态写入或调度的工具：优先非思考 + strict tool schema；若必须思考，使用 Responses API，并把完整 reasoning/tool 链写入事件记录。
- 不把非思考与思考结果合成一个“DeepSeek 能力分数”；模型模式、路由比例、并发、提示、任务、资源和停止规则均需作为运行卡的一部分。
- API 成功率、响应速度、schema 有效率和 token 成本只是支撑指标。细胞分化、增殖、结构形成和任务能力仍需按主计划另行定义观测量、对照、独立 population 重复与隔离评估器。

## 下一次候选提交卡（准备态）

```yaml
run_id: deepseek-api-cell-calibration-v1
status: prepared_not_submitted
base_url: https://api.deepseek.com
model: deepseek-flash
channels:
  fast_cell: {thinking: disabled, max_tokens: 512, concurrency: 16}
  deep_review: {thinking: enabled, reasoning_effort: high, max_tokens: 8192, concurrency: 4}
tasks: [short_json, WP1_concept_control, math_interface_control]
records: [request_hash, response_hash, status, finish_reason, usage, latency, schema_result]
retry: only_confirmed_not_dispatched
stop_on: [empty_final_content_rate_spike, truncation_spike, 429, repeated_5xx]
scientific_claim: none
```

该卡只表示准备完成，不表示已经提交公网请求。真正提交前，API key 必须从安全环境变量注入（例如 `DEEPSEEK_API_KEY`），不能写入 prompt、仓库、receipt、shell history 或报告。用户此前在对话中粘贴过密钥，建议先撤销并重新生成，再进行下一次测试。

## 当前建议

先用 `deepseek-flash` 非思考模式完成 8–16 个请求的协议校准，再独立做 4 个思考模式深度审查请求；确认 `content`、JSON schema、usage 和延迟都能稳定记录后，才考虑把它接入群体客户端。不要把这次支线校准直接升级为 10K 提交，也不要因为 API 有 2500 并发上限就跳过有界并发、检查点和不确定结果保护。

