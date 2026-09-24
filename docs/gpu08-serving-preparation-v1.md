# GPU08 independent serving preparation v1

Status: preparation in progress, not a completed serving milestone. No new GPU service or scientific call has started. M2.3's completed report remains `milestones/m2-3-role-contract-v1.html`.

The user authorized all GPU08 resources. Slurm still reports eight GPUs allocated and hides other users' jobs under `PrivateData=jobs,usage`; the previous immediate allocation failed busy. A reservation account does not identify the occupying job. Do not terminate unidentified workloads or bypass scheduling. The pending question concerns the old allocation's JobID/release, not renewed permission.

## Observed assets

CPU-only jobs 220138 and 220153 completed in 38 and 70 seconds. The first hashed three existing SIF images and recorded installed package versions. The second inspected installed Python source symbols and ran CLI help. See `reports/gpu08-preparation-v1/runtime-inventory.json` for full content hashes and observations. `tools/inspect_serving_runtime.py` is the exact symbol-audit script executed inside the containers.

| Image label | Installed runtime | Observed candidate status |
|---|---|---|
| sglang-dsv4-hopper | SGLang 0.5.16 | DeepSeek V4 model class found; CLI help exits 0 |
| sglang-glm53 | SGLang 0.5.18 | Expected GLM5Next model class not found; do not select solely from the filename |
| vllm-openai | vLLM 0.1.dev20051+g487ecf187 | GLM5Next and DeepSeek V4 implementations found; CPU-only help fails to infer device type |

Symbol discovery does not prove successful imports, GPU kernel compatibility, loading or generation. The vLLM failure happened without a visible GPU and is not evidence of GPU incompatibility. Current [SGLang GLM documentation](https://docs.sglang.io/cookbook/autoregressive/GLM/GLM-5.3-Flash) specifies a build including GLM-5.3 support, version 0.5.20 or later. Use the existing vLLM candidate for GPU preflight before deciding whether an isolated newer image is needed; do not overwrite the old images.

Existing model directories contain 48 DeepSeek shards (166,886,535,336 bytes) and 62 GLM shards (328,337,455,672 bytes). Their config-level quantization labels do not establish every tensor's storage precision. CPU-only job 220152 is comparing 133 relevant files, including all 110 weight shards, against official repository identities:

- `deepseek-ai/DeepSeek-V4-Flash-0731` revision `7872f01b1d1fe23eabc4c98b48bffcef5a386062`.
- `zai-org/GLM-5.3-Flash` revision `eb9eb208eb0d988989d07a6a12d0fdeb5f52574a`.

Each file receives a flushed JSONL record; missing, size-mismatched and hash-mismatched files are retained. This snapshot does not claim the full weight check is complete. Raw site paths, build labels and private scheduler records stay in the registered private run directory.

## Next bounded execution

`examples/gpu08-serving-profiles-v1.json` contains proposed TP8 profiles, loopback API binding, 32K context, eight concurrent requests and one model loaded at a time. DeepSeek option names were checked against the installed CLI; GLM arguments still require a GPU-visible check. The profiles are not an executable or frozen scientific experiment, and do not claim measured throughput.

The DeepSeek Hopper starting point uses the existing original checkpoint with the Marlin runner, following the [SGLang Hopper guidance](https://docs.sglang.io/cookbook/autoregressive/DeepSeek/DeepSeek-V4). The GLM starting point uses the installed vLLM candidate with automatic KV dtype; the [official recipe](https://github.com/vllm-project/recipes/blob/main/models/zai-org/GLM-5.3-Flash.yaml) requires BF16 KV on Hopper. H20-specific execution still needs validation. Do not infer support from H100/H200 recipe badges.

Before model loading: finish file identity checks, obtain the scheduler allocation, verify all eight H20 devices/topology and CUDA access, validate actual arguments, and freeze a bounded launch manifest. Keep approved model/image files read-only and use independent job-local caches and logs. Bind the API to loopback, use controlled access, and stop the owned service at the end of the bounded smoke job. Preserve failed loads and outputs without silently changing model, prompt or parser settings.

After loading: separately record small non-mathematical endpoint smoke requests with full responses, usage and latency. Check actual reasoning and structured-output behavior; provider-specific flags are not interchangeable. Only then freeze a new role-contract or population experiment. Model-serving success is not organization efficacy, reliable 10K execution or a mathematical proof.

This preparation does not change old scores or authorize a new population comparison after M2.3's failed 32/32 format gate. A completed serving increment must include its own versioned HTML, executable source/parameter identities, full failure accounting and browser/evidence validation.

## Follow-up finding during weight audit

The ongoing audit found that local GLM `chat_template.jinja` has 10,644 bytes, while the pinned official revision has 10,950. Its local digest matches the earlier inventory; the separately fetched official file matches the repository Git blob identity. See `reports/gpu08-preparation-v1/template-difference.json` for both hashes and the source URL. Differences involve content handling, whitespace and tool-message serialization/control flow; they do not establish the cause of past gateway or mathematical failures. No administrator file was changed. A future independently mounted template must be separately versioned and recorded before generating new scientific data.
