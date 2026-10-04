# GLM API 支线研究与 AIMeth 调用方案 v1

日期：2026-10-02  
状态：API 设计建议；不是已冻结的群体实验协议

## 结论

对 AIMeth，最合适的 GLM 用法是两条固定通道，而不是让所有逻辑 Agent 使用同一个模型：

| 通道 | 模型 | 用途 | 建议调用方式 |
|---|---|---|---|
| 快速细胞通道 | `glm-4.5-air` | 高频局部状态更新、短消息、候选提名、格式化事件 | 关闭思考；短 JSON；同步调用优先；先测并发和限速 |
| 深度审查通道 | `glm-5.3-flash` | 少量 Observer/Chief、复杂规划、证明义务审查和冲突裁决 | 强制思考；`reasoning_effort=high` 或 `max`；足够大的输出上限；长任务使用流式 |

这是一种 API 工程分层，不是新的科学目标。若比较组织架构，模型、端点、提示、输出预算和路由比例必须在比较前冻结；不能在观察到结果后把 Air 和 Flash 混用并归因于组织形式。

## 资料核对

- Z.AI 当前 API 总入口是 `https://api.z.ai/api/paas/v4`，使用 HTTP Bearer 认证；Chat Completions 支持同步和流式返回。[官方 API 总览](https://docs.z.ai/api-reference/introduction) [Chat Completion](https://docs.z.ai/api-reference/llm/chat-completion)
- GLM-5.3-Flash 页面明确写明：上下文长度 1M、最大输出 128K，支持流式、函数调用、上下文缓存和 JSON 结构化输出；`thinking.type` 只支持 `enabled`，推荐 `temperature=1`、`top_p=0.95`、`reasoning_effort=max`。[GLM-5.3-Flash 官方说明](https://docs.z.ai/guides/vlm/glm-5.3-flash)
- Chat Completion 参数页明确区分了模型：GLM-5.3/Flash 强制思考，只接受 `reasoning_effort` 的 `low/high/max`；`glm-4.5-air` 在可用模型列表中，`response_format={"type":"json_object"}` 可用于 JSON 输出。[Chat Completion 参数](https://docs.z.ai/api-reference/llm/chat-completion)
- 结构化输出文档建议使用 JSON mode，并在客户端再次执行 JSON Schema 校验；JSON 可解析不等于内容满足科学任务。[Structured Output](https://docs.z.ai/guides/capabilities/struct-output)
- 多轮工具调用若要保留思考连续性，需要原样、按顺序回传历史 `reasoning_content`，并设置 `clear_thinking=false`；不需要连续思考的普通调用保持默认清理更节省上下文。[Thinking Mode](https://docs.z.ai/guides/capabilities/thinking-mode)
- GLM-4.5 技术报告将 GLM-4.5 描述为同时支持 thinking/direct response 的混合推理模型，并发布了较小的 GLM-4.5-Air；这是模型研究结果，不是当前 API 的服务质量保证。[GLM-4.5 技术报告](https://arxiv.org/abs/2508.06471)

用户侧实测还显示：`glm-4.5-air` 返回 `API_OK`；`glm-5.3-flash` 在 64-token 上限下只生成思考并以 `length` 结束，禁用思考返回 400/1210。该实测与官方“Flash 强制思考”的说明一致，但仍只证明接口行为，不证明数学能力或 10K 可扩展性。

## 推荐请求模板

快速细胞通道：

```json
{
  "model": "glm-4.5-air",
  "messages": [
    {"role": "system", "content": "Return exactly one JSON object matching the schema. Do not add Markdown."},
    {"role": "user", "content": "<bounded local task and explicit schema>"}
  ],
  "thinking": {"type": "disabled"},
  "temperature": 0.2,
  "top_p": 0.95,
  "max_tokens": 512,
  "response_format": {"type": "json_object"},
  "stream": false
}
```

深度审查通道：

```json
{
  "model": "glm-5.3-flash",
  "messages": [
    {"role": "system", "content": "Return a JSON object with the stated fields. State unresolved proof obligations explicitly."},
    {"role": "user", "content": "<bounded review task and explicit schema>"}
  ],
  "thinking": {"type": "enabled", "clear_thinking": true},
  "reasoning_effort": "high",
  "temperature": 1.0,
  "top_p": 0.95,
  "max_tokens": 8192,
  "response_format": {"type": "json_object"},
  "stream": true,
  "tool_stream": true
}
```

`8192` 是本项目的起始工程预算，不是官方最低值；应先用固定小样本测量“有 final content 的比例、输出截断率、p50/p95 首 token 延迟、总延迟和 token 成本”，再冻结预算。对 Flash，不能发送 `thinking.type=disabled` 作为降级方案；需要降低成本时，应该降低路由比例或 `reasoning_effort`，而不是改变模型强制约束。

## AIMeth 的最小验证顺序

1. **端点校准**：在 `api.z.ai` 和 `open.bigmodel.cn` 中选定一个端点；用相同模型、提示和预算比较认证成功率、HTTP 延迟、首 token 延迟、p95 总延迟、429/5xx 和费用。一个实验条件内不要混用端点。
2. **模型校准**：分别对 Air 和 Flash 做短 JSON、WP1 设计题和一个数学控制题。控制题只用于接口/格式诊断，不能替代独立数学评估。
3. **群体接入**：若目标是高频局部交互，先用 Air 固定为细胞通道；Flash 只分配给预先登记的审查角色。记录每个请求的 `run_id`、`agent_id`、模型、端点、参数指纹、请求哈希、HTTP 状态、`finish_reason`、usage、耗时、响应哈希和 schema 校验结果。
4. **故障口径**：401/403 是认证或权限失败；400/1210 是参数/模型约束失败；429 是限速；5xx、连接超时和流中断是技术失败；`finish_reason=length` 且没有最终内容是截断失败。它们都进入失败分母，不能修补成成功。
5. **科学边界**：API 可用性、JSON 有效和响应速度只是支撑指标。细胞自组织、分化、增殖、介观结构和功能改善需要另行定义观测量、对照和独立群体重复。

## 当前建议

对于下一次公网 API 工程试验，先冻结 `glm-4.5-air` + JSON mode + 512 输出 token，做小规模并发和事件记录校准；同时单独准备 `glm-5.3-flash` 的 8K 起始预算深度审查臂。不要把两者的结果合并成一个“GLM 能力分数”，也不要把 Air 的快速响应直接解释为更强的群体涌现。

