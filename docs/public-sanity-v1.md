# Public API antiderivative diagnostic · v1

2026-09-16. Planned after inspecting institutional calibration job 190045, where all 16 antiderivative cases failed strict acceptance. This is explicitly an exploratory, selected-problem diagnostic and is not pooled with the frozen 48-case experiment.

The user authorized public API tests if needed, prioritizing DeepSeek and GLM. Use at most eight calls: each provider × original/certificate-only prompt × two repetitions. Copy the matching institutional 2048-token case's task, seed and realized message construction; change only the endpoint, public served ID and documented provider-format options. No mathematical answer or evaluator hint is sent.

Providers: DeepSeek `deepseek-flash` at its official HTTPS API, and GLM `glm-5.2` at the documented BigModel standard pay-as-you-go endpoint. DeepSeek documentation states that `deepseek-flash` denotes V4.1-Flash and the legacy V4 Flash aliases now route to it. These are not asserted to be the same weights as the institutional served IDs, especially institutional GLM-5.3-flash. The comparison can establish that the task/format/evaluator can succeed on another service; it cannot isolate a deployment defect from model/version differences.

Provider options: `thinking.type=disabled`, `response_format.type=json_object`, max_tokens=2048, temperature=0.6, top_p=1. The client records a sampling seed but does not assume each provider honors it. No hidden retries or response repair. 8-call / 16384 reserved-output-token ceiling, 10-minute total deadline, 120-second supervised request cutoff, request <=16384 bytes. Use the existing personal API credential files in memory only; no key in code, public traces or project control files. Run the small diagnostic from the local client; the main population and factorial calibration remain institutional jobs.

Every result and unknown usage is retained with a separate journal, endpoint identity, request hash and exact verdict. Official endpoint URLs are public; credential values and uncontrolled error response bodies are never journaled. An authorization/model-not-found failure stops further requests to that provider, leaving the unstarted denominator explicit. No alternate model is silently substituted.

Sources checked before execution:

- [DeepSeek current model identities](https://api-docs.deepseek.com/quick_start/pricing/)
- [DeepSeek thinking toggle](https://api-docs.deepseek.com/guides/thinking_mode/)
- [BigModel standard endpoint and authentication](https://docs.bigmodel.cn/cn/api/introduction)
- [BigModel GLM-5.2 API and output parameters](https://docs.bigmodel.cn/api-reference/模型-api/对话补全)
- [BigModel thinking mode](https://docs.bigmodel.cn/cn/guide/capabilities/thinking-mode)

No price estimate or invoice total is inferred from token counts. Record observed provider token usage and provider-side costs only if actually supplied.
